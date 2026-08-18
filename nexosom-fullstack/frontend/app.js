const CONFIG = window.NEXOSOM_CONFIG || {};
const API = (CONFIG.API_URL || "").replace(/\/$/, "");

let me = null;
let activeGenre = "Todos";
let searchTimer;

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];


function escapeHtml(value = "") {
  return String(value).replace(
    /[&<>"']/g,
    s => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    }[s])
  );
}


function apiPath(path = "") {
  if (!path) return "";

  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const origin = API.replace(/\/api$/, "");
  return origin + path;
}


function headers(json = false) {
  const h = {};

  if (json) {
    h["Content-Type"] = "application/json";
  }

  return h;
}


async function request(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    credentials: "include"
  });

  let data = null;

  try {
    data = await res.json();
  } catch {}

  if (!res.ok) {

    if (res.status === 401 && me) {
      me = null;
      renderAuth();
    }

    throw new Error(
      data?.detail ||
      "Não foi possível concluir esta operação."
    );
  }

  return data;
}


function toast(message) {
  const el = $("#toast");

  el.textContent = message;

  el.classList.add("show");

  clearTimeout(window.__toast);

  window.__toast = setTimeout(() => {
    el.classList.remove("show");
  }, 2400);
}


function openModal(id) {
  $$(".modal").forEach(m => {
    m.classList.remove("open");
  });

  const modal = document.getElementById(id);

  if (!modal) return;

  modal.classList.add("open");

  modal.setAttribute(
    "aria-hidden",
    "false"
  );

  document.body.style.overflow = "hidden";
}


function closeModals() {
  $$(".modal").forEach(m => {
    m.classList.remove("open");

    m.setAttribute(
      "aria-hidden",
      "true"
    );
  });

  document.body.style.overflow = "";
}


function requireLogin(after) {
  if (me) {
    return true;
  }

  window.__afterLogin = after || null;

  openModal("loginModal");

  return false;
}


function renderAuth() {
  $("#accountBtn").textContent =
    me
      ? (
          me.name?.split(" ")[0] ||
          "Minha conta"
        )
      : "Entrar";

  $$(".admin-only").forEach(el => {
    el.classList.toggle(
      "hidden",
      me?.role !== "admin"
    );
  });
}


function platformLabel(key) {
  return {
    spotify: "Spotify",
    youtube: "YouTube",
    deezer: "Deezer",
    apple_music: "Apple Music",
    other: "Outra plataforma"
  }[key] || key;
}


function smartUrl(slug) {
  return `${location.origin}/s/${encodeURIComponent(slug)}`;
}


/* =========================================
   CONTA / LOGIN
========================================= */

async function loadMe() {

  try {

    me = await request(
      "/auth/me",
      {
        headers: headers()
      }
    );

    renderAuth();

  } catch {

    me = null;
    renderAuth();
  }
}


function initGoogle() {

  if (
    !CONFIG.GOOGLE_CLIENT_ID ||
    CONFIG.GOOGLE_CLIENT_ID.startsWith("SEU_")
  ) {

    $("#googleConfigWarning")
      .classList
      .remove("hidden");

    return;
  }

  const attempt = () => {

    if (!window.google?.accounts?.id) {
      return setTimeout(
        attempt,
        250
      );
    }

    google.accounts.id.initialize({
      client_id: CONFIG.GOOGLE_CLIENT_ID,
      callback: handleGoogleCredential
    });

    google.accounts.id.renderButton(
      $("#googleButton"),
      {
        theme: "filled_black",
        size: "large",
        shape: "pill",
        width: 280,
        text: "signin_with"
      }
    );
  };

  attempt();
}


async function handleGoogleCredential(response) {

  try {

    const data = await request(
      "/auth/google",
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json"
        },

        body: JSON.stringify({
          credential: response.credential
        })
      }
    );

    me = data.user;

    renderAuth();

    closeModals();

    toast(
      `Bem-vindo, ${me.name || "artista"}!`
    );

    await loadStats();

    if (window.__afterLogin) {

      const action = window.__afterLogin;

      window.__afterLogin = null;

      action();
    }

  } catch (e) {

    toast(e.message);
  }
}


/* =========================================
   LANÇAMENTOS
========================================= */

async function loadReleases() {

  const term =
    $("#musicSearch")
      ?.value
      .trim() || "";

  const params =
    new URLSearchParams();

  if (activeGenre !== "Todos") {
    params.set(
      "genre",
      activeGenre
    );
  }

  if (term) {
    params.set(
      "q",
      term
    );
  }

  try {

    const rows = await request(
      `/releases?${params.toString()}`
    );

    $("#statReleases").textContent =
      rows.length;

    $("#releaseGrid").innerHTML =
      rows.length

        ? rows.map(r => `
          <article class="release-card">

            <div
              class="release-cover image-cover"
              style="background-image:url('${escapeHtml(apiPath(r.cover_url))}')"
            >
              <span class="genre-badge">
                ${escapeHtml(r.genre)}
              </span>
            </div>

            <div class="release-info">

              <div class="release-topline">

                <div>

                  <h3>
                    ${escapeHtml(r.title)}
                  </h3>

                  <p>
                    ${escapeHtml(r.artist)}
                    •
                    ${escapeHtml(r.city || "Brasil")}
                  </p>

                </div>

              </div>

              <p class="release-desc">
                ${escapeHtml(
                  r.description ||
                  "Novo lançamento independente."
                )}
              </p>

              <div class="release-actions">

                <button
                  class="icon-btn like-btn"
                  data-id="${r.id}"
                >
                  ♡ ${r.likes || 0}
                </button>

                <button
                  class="icon-btn smart-btn"
                  data-slug="${escapeHtml(r.slug)}"
                >
                  Smart Link
                </button>

                <button
                  class="icon-btn share-btn"
                  data-slug="${escapeHtml(r.slug)}"
                >
                  Compartilhar
                </button>

              </div>

            </div>

          </article>
        `).join("")

        : `
          <div class="empty-card">
            Nenhum lançamento encontrado.
            Seja o primeiro a publicar.
          </div>
        `;

  } catch (e) {

    $("#releaseGrid").innerHTML = `
      <div class="empty-card">
        Não foi possível carregar os lançamentos.
        Tente novamente mais tarde.
      </div>
    `;
  }
}


/* =========================================
   COLABORAÇÕES
========================================= */

async function loadCollabs() {

  try {

    const rows =
      await request("/collabs");

    $("#collabGrid").innerHTML =
      rows.length

        ? rows.map(c => `
          <article class="collab-card">

            <div class="collab-top">

              <div class="avatar">
                ${escapeHtml(
                  (c.artist || "AR")
                    .slice(0, 2)
                    .toUpperCase()
                )}
              </div>

              <div>

                <h3>
                  ${escapeHtml(c.artist)}
                </h3>

                <p>
                  ${escapeHtml(
                    c.style || "Música"
                  )}
                  •
                  ${escapeHtml(
                    c.location || "Remoto"
                  )}
                </p>

              </div>

            </div>

            <span class="need-badge">
              PROCURA:
              ${escapeHtml(
                c.looking.toUpperCase()
              )}
            </span>

            <p>
              ${escapeHtml(c.description)}
            </p>

            <div class="collab-footer">

              <small>
                ${c.interests} interessados
              </small>

              <button
                class="btn secondary small interest-btn"
                data-id="${c.id}"
              >
                Tenho interesse
              </button>

            </div>

          </article>
        `).join("")

        : `
          <div class="empty-card">
            Nenhuma colaboração publicada ainda.
          </div>
        `;

  } catch {

    $("#collabGrid").innerHTML = `
      <div class="empty-card">
        Não foi possível carregar colaborações.
      </div>
    `;
  }
}


/* =========================================
   ARTISTAS
========================================= */

async function loadArtists() {

  try {

    const rows =
      await request("/artists");

    $("#statArtists").textContent =
      rows.length;

    $("#artistGrid").innerHTML =
      rows.length

        ? rows.map(a => {

          const name = a.name || "Artista";
          const initials = name
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map(part => part[0])
            .join("")
            .toUpperCase() || "AR";

          return `
            <article class="artist-card">

              <div class="artist-avatar-wrap">
                ${
                  a.picture
                    ? `
                      <img
                        class="artist-photo"
                        src="${escapeHtml(a.picture)}"
                        alt="${escapeHtml(name)}"
                        referrerpolicy="no-referrer"
                        onerror="this.style.display='none';this.nextElementSibling.style.display='grid';"
                      >
                      <div class="avatar artist-fallback" style="display:none;">
                        ${escapeHtml(initials)}
                      </div>
                    `
                    : `
                      <div class="avatar artist-fallback">
                        ${escapeHtml(initials)}
                      </div>
                    `
                }
              </div>

              <h3>${escapeHtml(name)}</h3>

              <p>
                ${a.is_team ? "Equipe NexoSom" : "Artista independente"}
              </p>

              <div class="artist-tags">
                <span>Conta verificada</span>
              </div>

            </article>
          `;
        }).join("")

        : `
          <div class="empty-card">
            Os primeiros artistas aparecerão aqui.
          </div>
        `;

  } catch {}
}


/* =========================================
   ESTATÍSTICAS DO USUÁRIO
========================================= */

async function loadStats() {

  if (!me) return;

  try {

    const s =
      await request(
        "/me/stats",
        {
          headers: headers()
        }
      );

    $("#myReleases").textContent =
      s.releases;

    $("#myClicks").textContent =
      s.clicks;

    $("#myCollabs").textContent =
      s.collabs;

  } catch {}
}


async function showAccount() {

  if (!requireLogin(showAccount)) {
    return;
  }

  $("#accountName").textContent =
    me.name || "Minha conta";

  $("#accountEmail").textContent =
    me.email || "";

  $("#accountRole").textContent =
    me.role === "admin"
      ? "ADMINISTRADOR"
      : "ARTISTA";

  $("#accountAvatar").src =
    me.picture || "";

  await loadStats();

  openModal("accountModal");
}


/* =========================================
   PUBLICAR LANÇAMENTO
========================================= */

async function submitRelease(e) {

  e.preventDefault();

  if (
    !requireLogin(
      () => openModal("releaseModal")
    )
  ) {
    return;
  }

  const form =
    e.currentTarget;

  const file =
    form.cover.files[0];

  if (!file) {
    return toast(
      "Selecione a capa."
    );
  }

  if (
    file.size >
    5 * 1024 * 1024
  ) {

    return toast(
      "A capa deve ter no máximo 5 MB."
    );
  }

  const data =
    new FormData(form);

  const schedule =
    data.get("schedule");

  if (schedule) {

    data.set(
      "schedule",
      new Date(schedule).toISOString()
    );
  }

  const btn =
    form.querySelector(
      "button[type=submit]"
    );

  btn.disabled = true;
  btn.textContent = "Publicando...";

  try {

    const r =
      await request(
        "/releases",
        {
          method: "POST",
          headers: headers(),
          body: data
        }
      );

    form.reset();

    closeModals();

    await loadReleases();
    await loadStats();

    if (
      r.schedule_at &&
      new Date(r.schedule_at) >
      new Date()
    ) {

      toast(
        "Divulgação agendada com sucesso."
      );

    } else {

      toast(
        "Lançamento publicado!"
      );
    }

  } catch (err) {

    toast(err.message);

  } finally {

    btn.disabled = false;
    btn.textContent = "Publicar";
  }
}


/* =========================================
   PUBLICAR COLABORAÇÃO
========================================= */

async function submitCollab(e) {

  e.preventDefault();

  if (
    !requireLogin(
      () => openModal("collabModal")
    )
  ) {
    return;
  }

  const data =
    new FormData(e.currentTarget);

  try {

    await request(
      "/collabs",
      {
        method: "POST",
        headers: headers(),
        body: data
      }
    );

    e.currentTarget.reset();

    closeModals();

    await loadCollabs();
    await loadStats();

    toast(
      "Colaboração publicada."
    );

  } catch (err) {

    toast(err.message);
  }
}


/* =========================================
   CURTIR
========================================= */

async function like(id) {

  if (!requireLogin()) {
    return;
  }

  try {

    const d =
      await request(
        `/releases/${id}/like`,
        {
          method: "POST",
          headers: headers()
        }
      );

    toast(
      d.liked
        ? "Curtida registrada."
        : "Você já curtiu."
    );

    await loadReleases();

  } catch (e) {

    toast(e.message);
  }
}


/* =========================================
   INTERESSE EM COLABORAÇÃO
========================================= */

async function interest(id) {

  if (!requireLogin()) {
    return;
  }

  try {

    const d =
      await request(
        `/collabs/${id}/interest`,
        {
          method: "POST",
          headers: headers()
        }
      );

    toast(
      d.registered
        ? "Interesse registrado."
        : "Não foi possível registrar novamente."
    );

    await loadCollabs();

  } catch (e) {

    toast(e.message);
  }
}


/* =========================================
   SMART LINK PÚBLICO
========================================= */

async function renderSmartLink(slug) {

  /* Esconde partes do site normal */
  $("#mainSite")
    .classList
    .add("hidden");

  $("#siteFooter")
    .classList
    .add("hidden");

  /* Esconde o menu somente no Smart Link */
  $(".topbar")
    .classList
    .add("hidden");


  const page =
    $("#smartPublicPage");

  page
    .classList
    .remove("hidden");


  page.innerHTML = `
    <div class="smart-public-card">
      Carregando...
    </div>
  `;


  try {

    const r =
      await request(
        `/s/${encodeURIComponent(slug)}`
      );


    const buttons =
      Object.entries(
        r.platforms || {}
      )
      .map(([key, url]) => `
        <button
          class="stream-btn public-stream"
          data-release="${r.id}"
          data-platform="${key}"
          data-url="${escapeHtml(url)}"
        >
          <b>
            ${escapeHtml(
              platformLabel(key)
            )}
          </b>

          <span>
            Ouvir →
          </span>
        </button>
      `)
      .join("");


    page.innerHTML = `
      <div class="smart-public-card">

        <a
          href="/"
          class="smart-brand brand"
        >

          <span class="brand-mark">
            <span></span>
            <span></span>
            <span></span>
          </span>

          <strong>
            NexoSom
          </strong>

        </a>


        <img
          class="public-cover"
          src="${escapeHtml(
            apiPath(r.cover_url)
          )}"
          alt="Capa de ${escapeHtml(
            r.title
          )}"
        >


        <span class="eyebrow">
          ${escapeHtml(r.genre)}
        </span>


        <h1>
          ${escapeHtml(r.title)}
        </h1>


        <p class="public-artist">
          ${escapeHtml(r.artist)}
        </p>


        <p class="public-desc">
          ${escapeHtml(
            r.description ||
            "Escolha sua plataforma favorita para ouvir."
          )}
        </p>


        <div class="public-platforms">
          ${buttons}
        </div>

      </div>
    `;

  } catch (e) {

    page.innerHTML = `
      <div class="smart-public-card">

        <h1>
          Smart Link não encontrado
        </h1>

        <p>
          ${escapeHtml(e.message)}
        </p>

        <a
          class="btn primary"
          href="/"
        >
          Voltar
        </a>

      </div>
    `;
  }
}


/* =========================================
   ADMIN
========================================= */

async function openAdmin(
  tab = "releases"
) {

  if (
    !me ||
    me.role !== "admin"
  ) {

    return toast(
      "Acesso não autorizado."
    );
  }


  openModal(
    "adminModal"
  );


  try {

    const stats =
      await request(
        "/admin/stats",
        {
          headers: headers()
        }
      );


    $("#adminStats").innerHTML =
      Object.entries(stats)
        .map(([k, v]) => `
          <div>

            <b>
              ${Number(v)
                .toLocaleString(
                  "pt-BR"
                )}
            </b>

            <span>
              ${escapeHtml(
                k.replace(
                  "_",
                  " "
                )
              )}
            </span>

          </div>
        `)
        .join("");


    await loadAdminTab(tab);

  } catch (e) {

    toast(e.message);

    closeModals();
  }
}


async function loadAdminTab(tab) {

  $$(".admin-tabs [data-admin-tab]")
    .forEach(b => {

      b.classList.toggle(
        "active",
        b.dataset.adminTab === tab
      );
    });


  if (tab === "users") {

    const rows =
      await request(
        "/admin/users",
        {
          headers: headers()
        }
      );


    $("#adminContent").innerHTML =
      rows.map(u => `
        <div class="admin-row">

          <div>

            <b>
              ${escapeHtml(
                u.name || "Sem nome"
              )}
            </b>

            <small>
              ${escapeHtml(u.email)}
              •
              ${escapeHtml(u.role)}
            </small>

          </div>


          <button
            class="btn ${
              u.blocked
                ? "primary"
                : "secondary"
            } small admin-block"

            data-id="${u.id}"

            data-block="${!u.blocked}"

            ${
              u.role === "admin"
                ? "disabled"
                : ""
            }
          >
            ${
              u.blocked
                ? "Desbloquear"
                : "Bloquear"
            }
          </button>

        </div>
      `).join("");


  } else {

    const rows =
      await request(
        "/admin/releases",
        {
          headers: headers()
        }
      );


    $("#adminContent").innerHTML =
      rows.map(r => `
        <div class="admin-row">

          <div>

            <b>
              ${escapeHtml(r.title)}
              —
              ${escapeHtml(r.artist)}
            </b>

            <small>
              ${escapeHtml(
                r.owner_email || ""
              )}
              •
              ${escapeHtml(r.status)}
            </small>

          </div>


          <button
            class="btn secondary small admin-status"

            data-id="${r.id}"

            data-status="${
              r.status === "published"
                ? "hidden"
                : "published"
            }"
          >

            ${
              r.status === "published"
                ? "Ocultar"
                : "Publicar"
            }

          </button>

        </div>
      `).join("");
  }
}


/* =========================================
   EVENTOS DE CLIQUE
========================================= */

document.addEventListener(
  "click",
  async e => {


    /* Fechar modal */
    if (
      e.target.closest(
        "[data-close]"
      )
    ) {
      closeModals();
    }


    /* Abrir publicação */
    if (
      e.target.closest(
        "[data-open-release]"
      )
    ) {

      if (
        requireLogin(
          () => openModal(
            "releaseModal"
          )
        )
      ) {

        openModal(
          "releaseModal"
        );
      }
    }


    /* Abrir colaboração */
    if (
      e.target.closest(
        "[data-open-collab]"
      )
    ) {

      if (
        requireLogin(
          () => openModal(
            "collabModal"
          )
        )
      ) {

        openModal(
          "collabModal"
        );
      }
    }


    /* Curtir */
    const likeBtn =
      e.target.closest(
        ".like-btn"
      );

    if (likeBtn) {

      like(
        likeBtn.dataset.id
      );
    }


    /* Interesse */
    const intBtn =
      e.target.closest(
        ".interest-btn"
      );

    if (intBtn) {

      interest(
        intBtn.dataset.id
      );
    }


    /* Smart Link */
    const smartBtn =
      e.target.closest(
        ".smart-btn"
      );

    if (smartBtn) {

      location.href =
        smartUrl(
          smartBtn.dataset.slug
        );
    }


    /* Compartilhar */
    const share =
      e.target.closest(
        ".share-btn"
      );

    if (share) {

      const url =
        smartUrl(
          share.dataset.slug
        );


      if (navigator.share) {

        navigator
          .share({ url })
          .catch(() => {});

      } else {

        navigator
          .clipboard
          ?.writeText(url)
          .then(() => {
            toast(
              "Smart Link copiado."
            );
          });
      }
    }


    /* Clique em plataforma */
    const stream =
      e.target.closest(
        ".public-stream"
      );

    if (stream) {

      try {

        await request(
          `/releases/${stream.dataset.release}/click`,
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify({
              platform:
                stream.dataset.platform
            })
          }
        );

      } catch {}


      window.open(
        stream.dataset.url,
        "_blank",
        "noopener,noreferrer"
      );
    }


    /* Aba do admin */
    const adminTab =
      e.target.closest(
        "[data-admin-tab]"
      );

    if (adminTab) {

      loadAdminTab(
        adminTab.dataset.adminTab
      );
    }


    /* Bloquear usuário */
    const block =
      e.target.closest(
        ".admin-block"
      );

    if (block) {

      await request(
        `/admin/users/${block.dataset.id}/block`,
        {
          method: "PATCH",

          headers:
            headers(true),

          body:
            JSON.stringify({
              blocked:
                block.dataset.block ===
                "true"
            })
        }
      );

      await loadAdminTab(
        "users"
      );
    }


    /* Ocultar/publicar música */
    const status =
      e.target.closest(
        ".admin-status"
      );

    if (status) {

      await request(
        `/admin/releases/${status.dataset.id}/status`,
        {
          method: "PATCH",

          headers:
            headers(true),

          body:
            JSON.stringify({
              status:
                status.dataset.status
            })
        }
      );

      await loadAdminTab(
        "releases"
      );

      await loadReleases();
    }
  }
);


/* =========================================
   BOTÕES
========================================= */

$("#accountBtn")
  .addEventListener(
    "click",
    () => {

      me
        ? showAccount()
        : openModal(
            "loginModal"
          );
    }
  );


$("#adminBtn")
  .addEventListener(
    "click",
    () => openAdmin()
  );


$("#logoutBtn")
  .addEventListener(
    "click",
    async () => {

      try {
        await request(
          "/auth/logout",
          { method: "POST" }
        );
      } catch {}

      me = null;
      renderAuth();
      closeModals();

      toast(
        "Você saiu da conta."
      );
    }
  );


$("#releaseForm")
  .addEventListener(
    "submit",
    submitRelease
  );


$("#collabForm")
  .addEventListener(
    "submit",
    submitCollab
  );


/* =========================================
   FILTROS
========================================= */

$$(".filter[data-genre]")
  .forEach(b => {

    b.addEventListener(
      "click",
      () => {

        $$(".filter[data-genre]")
          .forEach(x => {
            x.classList.remove(
              "active"
            );
          });

        b.classList.add(
          "active"
        );

        activeGenre =
          b.dataset.genre;

        loadReleases();
      }
    );
  });


$("#musicSearch")
  .addEventListener(
    "input",
    () => {

      clearTimeout(
        searchTimer
      );

      searchTimer =
        setTimeout(
          loadReleases,
          300
        );
    }
  );


document.addEventListener(
  "keydown",
  e => {

    if (e.key === "Escape") {
      closeModals();
    }
  }
);


/* =========================================
   INICIAR SITE
========================================= */

(async function boot() {

  if (!API) {

    toast(
      "Serviço temporariamente indisponível."
    );

    return;
  }


  const path =
    location.pathname;


  /* Smart Link público */
  if (
    path.startsWith("/s/")
  ) {

    await renderSmartLink(
      decodeURIComponent(
        path.slice(3)
      )
    );

    return;
  }


  await loadMe();

  initGoogle();


  await Promise.all([
    loadReleases(),
    loadCollabs(),
    loadArtists()
  ]);


  await loadStats();

})();