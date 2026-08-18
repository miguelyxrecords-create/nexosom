import io
import os
import re
import time
import uuid
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from typing import Optional

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jose import JWTError, jwt
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from pymongo import MongoClient, ASCENDING, DESCENDING
import gridfs

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "nexosom")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
CORS_ORIGINS = [x.strip().rstrip("/") for x in os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",") if x.strip()]
JWT_HOURS = int(os.getenv("JWT_HOURS", "12"))
MAX_COVER_MB = int(os.getenv("MAX_COVER_MB", "5"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes", "on"}
COOKIE_NAME = "nexosom_session"

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI não configurado.")
if not GOOGLE_CLIENT_ID:
    raise RuntimeError("GOOGLE_CLIENT_ID não configurado.")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET deve existir e ter pelo menos 32 caracteres.")
if not ADMIN_EMAIL:
    raise RuntimeError("ADMIN_EMAIL não configurado.")

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000, tz_aware=True)
db = client[MONGODB_DB]
covers = gridfs.GridFSBucket(db, bucket_name="covers")

app = FastAPI(title="NexoSom API", version="1.0.0", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/auth") else response.headers.get("Cache-Control", "no-cache")
    return response

@app.on_event("startup")
def startup():
    client.admin.command("ping")
    db.users.create_index([("google_sub", ASCENDING)], unique=True)
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.releases.create_index([("slug", ASCENDING)], unique=True)
    db.releases.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    db.releases.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
    db.collabs.create_index([("created_at", DESCENDING)])

class GoogleLogin(BaseModel):
    credential: str = Field(min_length=50)

class ClickPayload(BaseModel):
    platform: str

class BlockPayload(BaseModel):
    blocked: bool

class StatusPayload(BaseModel):
    status: str

_auth_hits = {}

def rate_limit_auth(request: Request):
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "unknown")
    now = time.time()
    hits = [t for t in _auth_hits.get(ip, []) if now - t < 60]
    if len(hits) >= 12:
        raise HTTPException(429, "Muitas tentativas. Aguarde um minuto.")
    hits.append(now)
    _auth_hits[ip] = hits

def utcnow():
    return datetime.now(timezone.utc)

def oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(404, "Registro não encontrado.")

def clean_text(value: Optional[str], max_len=500):
    value = (value or "").strip()
    return value[:max_len]

def slugify(value: str):
    norm = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()
    return norm[:60] or "musica"

def make_slug(title: str, artist: str):
    return f"{slugify(title)}-{slugify(artist)}-{uuid.uuid4().hex[:6]}"

def create_token(user):
    exp = utcnow() + timedelta(hours=JWT_HOURS)
    payload = {
        "sub": str(user["_id"]),
        "email": user["email"],
        "role": user.get("role", "artist"),
        "exp": exp,
        "iat": utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def session_token(request: Request):
    cookie_token = request.cookies.get(COOKIE_NAME, "").strip()
    if cookie_token:
        return cookie_token

    # Compatibilidade temporária com clientes antigos que ainda enviem Bearer token.
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()

    raise HTTPException(401, "Faça login para continuar.")

def current_user(request: Request):
    token = session_token(request)
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Sessão inválida ou expirada.")
    user = db.users.find_one({"_id": oid(user_id)})
    if not user:
        raise HTTPException(401, "Usuário não encontrado.")
    if user.get("blocked") and user.get("email", "").lower() != ADMIN_EMAIL:
        raise HTTPException(403, "Conta bloqueada pelo administrador.")
    return user

def admin_user(user=Depends(current_user)):
    if user.get("email", "").lower() != ADMIN_EMAIL or user.get("role") != "admin":
        raise HTTPException(403, "Acesso exclusivo do administrador.")
    return user

def user_public(user):
    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "picture": user.get("picture", ""),
        "role": user.get("role", "artist"),
        "blocked": bool(user.get("blocked")),
        "created_at": user.get("created_at"),
    }

def release_public(doc, include_private=False):
    out = {
        "id": str(doc["_id"]),
        "slug": doc["slug"],
        "title": doc["title"],
        "artist": doc["artist"],
        "genre": doc["genre"],
        "city": doc.get("city", ""),
        "description": doc.get("description", ""),
        "platforms": doc.get("platforms", {}),
        "cover_url": f"/api/covers/{doc['cover_id']}" if doc.get("cover_id") else "",
        "likes": doc.get("likes_count", 0),
        "schedule_at": doc.get("schedule_at"),
        "created_at": doc.get("created_at"),
        "owner_name": doc.get("owner_name", ""),
        "status": doc.get("status", "published"),
    }
    if include_private:
        out["owner_id"] = doc.get("owner_id")
        out["owner_email"] = doc.get("owner_email")
        out["clicks_total"] = doc.get("clicks_total", 0)
        out["clicks"] = doc.get("clicks", {})
    return out

def collab_public(doc):
    return {
        "id": str(doc["_id"]),
        "artist": doc["artist"],
        "looking": doc["looking"],
        "style": doc.get("style", ""),
        "location": doc.get("location", ""),
        "description": doc["description"],
        "interests": doc.get("interests_count", 0),
        "created_at": doc.get("created_at"),
    }

PLATFORM_HOSTS = {
    "spotify": ("spotify.com", "spotify.link"),
    "youtube": ("youtube.com", "youtu.be"),
    "deezer": ("deezer.com", "deezer.page.link"),
    "apple_music": ("music.apple.com",),
}

def validate_platform_url(platform: str, value: str):
    try:
        parsed = urlparse(value)
    except Exception:
        raise HTTPException(400, "Link de plataforma inválido.")

    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise HTTPException(400, f"O link de {platform} deve usar https://")

    allowed = PLATFORM_HOSTS.get(platform)
    if allowed:
        host = parsed.hostname.lower().rstrip(".")
        if not any(host == domain or host.endswith("." + domain) for domain in allowed):
            raise HTTPException(400, f"O link informado não pertence à plataforma {platform}.")


def sanitize_cover(data: bytes):
    if len(data) > MAX_COVER_MB * 1024 * 1024:
        raise HTTPException(413, f"A capa deve ter no máximo {MAX_COVER_MB} MB.")
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > 25_000_000:
            raise HTTPException(400, "A imagem é grande demais. Use uma capa de até 25 megapixels.")
        image.verify()
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image)
        if image.width < 300 or image.height < 300:
            raise HTTPException(400, "A capa deve ter pelo menos 300x300 pixels.")
        image.thumbnail((2000, 2000))
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=88, method=6)
        return output.getvalue()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Arquivo de capa inválido.")

@app.get("/api/health")
def health():
    return {"ok": True}

@app.post("/api/auth/google")
def google_login(body: GoogleLogin, request: Request, response: Response):
    rate_limit_auth(request)
    try:
        info = id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except Exception:
        raise HTTPException(401, "Login Google inválido.")

    email = (info.get("email") or "").strip().lower()
    if not email or not info.get("email_verified"):
        raise HTTPException(401, "O Google não confirmou este e-mail.")

    google_sub = info.get("sub")
    if not google_sub:
        raise HTTPException(401, "Conta Google inválida.")

    existing = db.users.find_one({"google_sub": google_sub})
    if existing and existing.get("blocked") and email != ADMIN_EMAIL:
        raise HTTPException(403, "Conta bloqueada pelo administrador.")

    role = "admin" if email == ADMIN_EMAIL else "artist"
    now = utcnow()
    db.users.update_one(
        {"google_sub": google_sub},
        {
            "$set": {
                "email": email,
                "name": clean_text(info.get("name"), 100),
                "picture": clean_text(info.get("picture"), 500),
                "role": role,
                "last_login": now,
            },
            "$setOnInsert": {
                "created_at": now,
                "blocked": False,
            },
        },
        upsert=True,
    )
    user = db.users.find_one({"google_sub": google_sub})
    token = create_token(user)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=JWT_HOURS * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/api",
    )
    return {"user": user_public(user)}

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/api")
    return {"ok": True}

@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user_public(user)

@app.get("/api/releases")
def list_releases(genre: str = "", q: str = "", limit: int = 30):
    limit = min(max(limit, 1), 60)
    now = utcnow()
    query = {
        "status": "published",
        "$or": [
            {"schedule_at": None},
            {"schedule_at": {"$lte": now}},
            {"schedule_at": {"$exists": False}},
        ],
    }
    if genre and genre.lower() != "todos":
        query["genre"] = clean_text(genre, 40)
    if q:
        safe = re.escape(clean_text(q, 80))
        query["$and"] = [{"$or": [{"title": {"$regex": safe, "$options": "i"}}, {"artist": {"$regex": safe, "$options": "i"}}]}]
    docs = db.releases.find(query).sort("created_at", DESCENDING).limit(limit)
    return [release_public(x) for x in docs]

@app.get("/api/releases/{release_id}")
def get_release(release_id: str):
    doc = db.releases.find_one({"_id": oid(release_id), "status": "published"})
    if not doc:
        raise HTTPException(404, "Lançamento não encontrado.")
    if doc.get("schedule_at") and doc["schedule_at"] > utcnow():
        raise HTTPException(404, "Lançamento não encontrado.")
    return release_public(doc)

@app.get("/api/s/{slug}")
def smart_link(slug: str):
    doc = db.releases.find_one({"slug": slug, "status": "published"})
    if not doc or (doc.get("schedule_at") and doc["schedule_at"] > utcnow()):
        raise HTTPException(404, "Smart Link não encontrado.")
    return release_public(doc)

@app.post("/api/releases")
async def create_release(
    title: str = Form(...),
    artist: str = Form(...),
    genre: str = Form(...),
    city: str = Form(""),
    description: str = Form(""),
    spotify: str = Form(""),
    youtube: str = Form(""),
    deezer: str = Form(""),
    apple_music: str = Form(""),
    other: str = Form(""),
    schedule: str = Form(""),
    cover: UploadFile = File(...),
    user=Depends(current_user),
):
    if cover.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(400, "Use JPG, PNG ou WEBP para a capa.")
    raw = await cover.read(MAX_COVER_MB * 1024 * 1024 + 1)
    safe_cover = sanitize_cover(raw)
    cover_id = covers.upload_from_stream(
        f"{uuid.uuid4().hex}.webp",
        io.BytesIO(safe_cover),
        metadata={"owner_id": str(user["_id"]), "content_type": "image/webp"},
    )

    schedule_at = None
    if schedule:
        try:
            parsed = datetime.fromisoformat(schedule.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            schedule_at = parsed.astimezone(timezone.utc)
        except ValueError:
            covers.delete(cover_id)
            raise HTTPException(400, "Data de agendamento inválida.")

    platforms = {}
    for key, value in {
        "spotify": spotify, "youtube": youtube, "deezer": deezer,
        "apple_music": apple_music, "other": other
    }.items():
        value = clean_text(value, 700)
        if value:
            try:
                validate_platform_url(key, value)
            except HTTPException:
                covers.delete(cover_id)
                raise
            platforms[key] = value
    if not platforms:
        covers.delete(cover_id)
        raise HTTPException(400, "Adicione pelo menos um link de plataforma.")

    doc = {
        "slug": make_slug(title, artist),
        "title": clean_text(title, 120),
        "artist": clean_text(artist, 100),
        "genre": clean_text(genre, 40),
        "city": clean_text(city, 80),
        "description": clean_text(description, 1200),
        "platforms": platforms,
        "cover_id": cover_id,
        "owner_id": str(user["_id"]),
        "owner_email": user["email"],
        "owner_name": user.get("name", ""),
        "status": "published",
        "schedule_at": schedule_at,
        "likes_count": 0,
        "liked_by": [],
        "clicks_total": 0,
        "clicks": {},
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    result = db.releases.insert_one(doc)
    doc["_id"] = result.inserted_id
    return release_public(doc, include_private=True)

@app.get("/api/covers/{cover_id}")
def get_cover(cover_id: str):
    try:
        grid_out = covers.open_download_stream(ObjectId(cover_id))
    except Exception:
        raise HTTPException(404, "Capa não encontrada.")
    return StreamingResponse(
        grid_out,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=86400"},
    )

@app.post("/api/releases/{release_id}/like")
def like_release(release_id: str, user=Depends(current_user)):
    rid = oid(release_id)
    uid = str(user["_id"])
    result = db.releases.update_one(
        {"_id": rid, "status": "published", "liked_by": {"$ne": uid}},
        {"$addToSet": {"liked_by": uid}, "$inc": {"likes_count": 1}},
    )
    doc = db.releases.find_one({"_id": rid})
    if not doc:
        raise HTTPException(404, "Lançamento não encontrado.")
    return {"liked": bool(result.modified_count), "likes": doc.get("likes_count", 0)}

@app.post("/api/releases/{release_id}/click")
def click_release(release_id: str, body: ClickPayload):
    platform = body.platform.strip().lower()
    if platform not in {"spotify", "youtube", "deezer", "apple_music", "other"}:
        raise HTTPException(400, "Plataforma inválida.")
    rid = oid(release_id)
    doc = db.releases.find_one({"_id": rid, "status": "published"})
    if not doc or platform not in doc.get("platforms", {}):
        raise HTTPException(404, "Link não encontrado.")
    db.releases.update_one(
        {"_id": rid},
        {"$inc": {f"clicks.{platform}": 1, "clicks_total": 1}},
    )
    return {"ok": True}

@app.delete("/api/releases/{release_id}")
def delete_own_release(release_id: str, user=Depends(current_user)):
    doc = db.releases.find_one({"_id": oid(release_id)})
    if not doc:
        raise HTTPException(404, "Lançamento não encontrado.")
    is_admin = user.get("email", "").lower() == ADMIN_EMAIL and user.get("role") == "admin"
    if doc.get("owner_id") != str(user["_id"]) and not is_admin:
        raise HTTPException(403, "Você não pode excluir este lançamento.")
    if doc.get("cover_id"):
        try:
            covers.delete(doc["cover_id"])
        except Exception:
            pass
    db.releases.delete_one({"_id": doc["_id"]})
    return {"ok": True}

@app.get("/api/me/releases")
def my_releases(user=Depends(current_user)):
    docs = db.releases.find({"owner_id": str(user["_id"])}).sort("created_at", DESCENDING)
    return [release_public(x, include_private=True) for x in docs]

@app.get("/api/me/stats")
def my_stats(user=Depends(current_user)):
    docs = list(db.releases.find({"owner_id": str(user["_id"])}, {"clicks_total": 1}))
    collabs_count = db.collabs.count_documents({"owner_id": str(user["_id"])})
    return {
        "releases": len(docs),
        "clicks": sum(x.get("clicks_total", 0) for x in docs),
        "collabs": collabs_count,
    }

@app.get("/api/collabs")
def list_collabs(limit: int = 30):
    docs = db.collabs.find({"status": "published"}).sort("created_at", DESCENDING).limit(min(max(limit,1),60))
    return [collab_public(x) for x in docs]

@app.post("/api/collabs")
def create_collab(
    artist: str = Form(...),
    looking: str = Form(...),
    style: str = Form(""),
    location: str = Form(""),
    description: str = Form(...),
    user=Depends(current_user),
):
    doc = {
        "artist": clean_text(artist, 100),
        "looking": clean_text(looking, 60),
        "style": clean_text(style, 80),
        "location": clean_text(location, 100),
        "description": clean_text(description, 1000),
        "owner_id": str(user["_id"]),
        "owner_email": user["email"],
        "interested_by": [],
        "interests_count": 0,
        "status": "published",
        "created_at": utcnow(),
    }
    result = db.collabs.insert_one(doc)
    doc["_id"] = result.inserted_id
    return collab_public(doc)

@app.post("/api/collabs/{collab_id}/interest")
def interest_collab(collab_id: str, user=Depends(current_user)):
    cid = oid(collab_id)
    uid = str(user["_id"])
    result = db.collabs.update_one(
        {"_id": cid, "status": "published", "owner_id": {"$ne": uid}, "interested_by": {"$ne": uid}},
        {"$addToSet": {"interested_by": uid}, "$inc": {"interests_count": 1}},
    )
    doc = db.collabs.find_one({"_id": cid})
    if not doc:
        raise HTTPException(404, "Colaboração não encontrada.")
    return {"registered": bool(result.modified_count), "interests": doc.get("interests_count", 0)}

@app.get("/api/artists")
def artists(limit: int = 12):
    pipeline = [
        {"$match": {"blocked": False}},
        {"$sort": {"created_at": -1}},
        {"$limit": min(max(limit,1),30)},
        {"$project": {"name": 1, "picture": 1, "role": 1}},
    ]
    result = []
    for u in db.users.aggregate(pipeline):
        result.append({
            "id": str(u["_id"]),
            "name": u.get("name", "Artista"),
            "picture": u.get("picture", ""),
            "is_team": u.get("role") == "admin",
        })
    return result

@app.get("/api/admin/stats")
def admin_stats(admin=Depends(admin_user)):
    now = utcnow()
    return {
        "users": db.users.count_documents({}),
        "releases": db.releases.count_documents({}),
        "published": db.releases.count_documents({"status": "published"}),
        "scheduled": db.releases.count_documents({"schedule_at": {"$gt": now}}),
        "blocked_users": db.users.count_documents({"blocked": True}),
        "clicks": sum(x.get("clicks_total", 0) for x in db.releases.find({}, {"clicks_total": 1})),
    }

@app.get("/api/admin/users")
def admin_users(admin=Depends(admin_user)):
    return [user_public(x) for x in db.users.find({}).sort("created_at", DESCENDING).limit(200)]

@app.patch("/api/admin/users/{user_id}/block")
def admin_block_user(user_id: str, body: BlockPayload, admin=Depends(admin_user)):
    target = db.users.find_one({"_id": oid(user_id)})
    if not target:
        raise HTTPException(404, "Usuário não encontrado.")
    if target.get("email", "").lower() == ADMIN_EMAIL:
        raise HTTPException(400, "A conta do dono não pode ser bloqueada.")
    db.users.update_one({"_id": target["_id"]}, {"$set": {"blocked": body.blocked}})
    return {"ok": True}

@app.get("/api/admin/releases")
def admin_releases(admin=Depends(admin_user)):
    docs = db.releases.find({}).sort("created_at", DESCENDING).limit(200)
    return [release_public(x, include_private=True) for x in docs]

@app.patch("/api/admin/releases/{release_id}/status")
def admin_release_status(release_id: str, body: StatusPayload, admin=Depends(admin_user)):
    if body.status not in {"published", "hidden"}:
        raise HTTPException(400, "Status inválido.")
    result = db.releases.update_one({"_id": oid(release_id)}, {"$set": {"status": body.status, "updated_at": utcnow()}})
    if not result.matched_count:
        raise HTTPException(404, "Lançamento não encontrado.")
    return {"ok": True}
