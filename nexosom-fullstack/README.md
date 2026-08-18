# NexoSom — versão pronta para deploy

Projeto full-stack para comunidade de artistas independentes.

## Estrutura

- `frontend/` — HTML, CSS e JavaScript
- `backend/` — FastAPI + MongoDB Atlas + GridFS
- `render.yaml` — configuração do backend no Render
- `netlify.toml` — configuração do frontend no Netlify
- `scripts/build-netlify.mjs` — prepara automaticamente a conexão frontend → backend
- `backend/.env.example` — modelo de variáveis locais, sem segredos reais

## Segurança aplicada

- O arquivo real `backend/.env` não faz parte deste pacote e está bloqueado no `.gitignore`.
- Login Google é validado no servidor com a biblioteca oficial do Google.
- Sessão em cookie `HttpOnly`; o JavaScript não recebe mais o JWT.
- Cookie de produção usa `Secure`.
- Admin é validado no backend em todas as rotas administrativas.
- Capa é validada, reprocessada e salva em WEBP no GridFS.
- Limite de tamanho e de megapixels para imagem.
- Links de Spotify, YouTube, Deezer e Apple Music são validados por domínio.
- Analytics detalhado não é devolvido nas rotas públicas.
- Cabeçalhos básicos de segurança no backend e no Netlify.
- Fallback de avatar quando a foto externa do Google falhar.

## Desenvolvimento local

Crie `backend/.env` a partir de `backend/.env.example` e coloque seus valores reais.

Backend:

```powershell
cd backend
py -m uvicorn main:app --reload
```

Frontend:

```powershell
cd frontend
py server.py
```

Abra `http://localhost:5500`.

O servidor local está configurado para não manter cache durante o desenvolvimento.

## Deploy

Leia `DEPLOY.md` e siga na ordem:

1. GitHub privado
2. Render
3. Netlify
4. Google Cloud OAuth
5. testes finais
