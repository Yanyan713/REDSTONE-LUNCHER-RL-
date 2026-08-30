"use strict";

// ---------------- utilitaires ----------------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const api = {
  async get(path) {
    const r = await fetch(path);
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Erreur");
    return j;
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Erreur");
    return j;
  },
  async del(path) {
    const r = await fetch(path, { method: "DELETE" });
    return r.json();
  },
  async upload(path, formData) {
    const r = await fetch(path, { method: "POST", body: formData });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Erreur");
    return j;
  },
};

const fmtSize = (b) => {
  if (!b) return "—";
  if (b > 1 << 30) return (b / (1 << 30)).toFixed(1) + " Go";
  if (b > 1 << 20) return (b / (1 << 20)).toFixed(0) + " Mo";
  return Math.max(1, (b / (1 << 10)).toFixed(0)) + " Ko";
};

const TYPE_LABEL = {
  release: "Release", snapshot: "Snapshot", old_beta: "Bêta", old_alpha: "Alpha",
};

let toastTimer = null;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 4200);
}

// ---------------- état ----------------
let VERSIONS = [];
let CURRENT_VERSION = null;
let ACCOUNTS = [];
let SETTINGS = {};
let CURRENT_MODE = "vanilla";
let MODS_VIEW_VERSION = null;
let filter = "all";
let query = "";
let pollTimer = null;
let logTimer = null;

// ---------------- versions ----------------
async function loadVersions(force) {
  const data = await api.get("/api/versions" + (force ? "?force=1" : ""));
  VERSIONS = data.versions;
  const selected = CURRENT_VERSION || null;
  renderList();
  if (selected) selectVersion(selected, false);
  return data;
}

function filteredVersions() {
  const q = query.trim().toLowerCase();
  return VERSIONS.filter((v) => {
    if (filter !== "all" && v.type !== filter) return false;
    if (q && !v.id.toLowerCase().includes(q)) return false;
    return true;
  });
}

function renderList() {
  const list = $("#versionList");
  list.innerHTML = "";
  const items = filteredVersions();
  if (!items.length) {
    list.innerHTML = '<div class="muted" style="padding:16px;text-align:center">Aucune version.</div>';
    return;
  }
  for (const v of items) {
    const li = document.createElement("li");
    li.className = "version-item" + (CURRENT_VERSION === v.id ? " selected" : "");
    li.innerHTML =
      `<span class="vname">${escapeHtml(v.id)}</span>` +
      `<span class="vtype ${v.type}">${TYPE_LABEL[v.type] || v.type}</span>`;
    li.onclick = () => selectVersion(v.id);
    list.appendChild(li);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function selectVersion(id, persist = true) {
  CURRENT_VERSION = id;
  renderList();
  if (persist) api.post("/api/select", { version: id }).catch(() => {});
  $("#emptyState").classList.add("hidden");
  $("#detailPane").classList.remove("hidden");
  try {
    const d = await api.get("/api/version/" + encodeURIComponent(id));
    $("#dVersion").textContent = d.id;
    $("#dType").textContent = TYPE_LABEL[d.type] || d.type;
    $("#dType").className = "badge " + d.type;
    $("#dDate").textContent = d.release_time ? new Date(d.release_time).toLocaleDateString("fr-FR") : "";
    $("#dJava").textContent = d.java ? "Java " + d.java : "Java 8";
    $("#dSizeClient").textContent = fmtSize(d.size_client);
    $("#dSizeAssets").textContent = fmtSize(d.size_assets);
    refreshJavaHint(d.java);
  } catch (e) {
    toast("Erreur version : " + e.message);
  }
}

// ---------------- comptes ----------------
async function loadAccounts() {
  const d = await api.get("/api/accounts");
  ACCOUNTS = d.accounts;
  renderAccountSelect();
  renderAccountList();
}

function renderAccountSelect() {
  const sel = $("#accountSelect");
  sel.innerHTML = "";
  if (!ACCOUNTS.length) {
    sel.innerHTML = '<option value="">Aucun compte — ajoute-en un</option>';
  } else {
    for (const a of ACCOUNTS) {
      const opt = document.createElement("option");
      opt.value = a.id;
      opt.textContent = a.label || a.username;
      sel.appendChild(opt);
    }
  }
}

function renderAccountList() {
  const box = $("#accountList");
  box.innerHTML = "";
  if (!ACCOUNTS.length) {
    box.innerHTML = '<div class="muted">Aucun compte pour l\'instant.</div>';
    return;
  }
  for (const a of ACCOUNTS) {
    const div = document.createElement("div");
    div.className = "account-item";
    const idEnc = encodeURIComponent(a.id);
    const skinSrc = a.has_skin ? `/api/accounts/${idEnc}/skin.png?t=${Date.now()}` : "";
    div.innerHTML =
      `<div class="acc-main">` +
        (skinSrc
          ? `<img class="acc-skin" src="${skinSrc}" alt="skin">`
          : `<div class="acc-skin placeholder">?</div>`) +
        `<div class="acc-id"><div class="acc-name">${escapeHtml(a.username)}</div>` +
        `<div class="acc-type">${a.type === "microsoft" ? "Microsoft" : "Local (hors-ligne)"}</div></div>` +
      `</div>` +
      `<div class="acc-actions">` +
        `<label class="btn small" title="Ajouter / remplacer le skin (PNG 64x64 ou 128x128)">Skin` +
          `<input type="file" accept="image/png" class="hidden" data-skin="${idEnc}"></label>` +
        (a.has_skin
          ? `<button class="btn small ghost" data-skindel="${idEnc}" title="Retirer le skin">✕ Skin</button>` : "") +
        `<button class="acc-del" title="Supprimer le compte" data-del="${idEnc}">✕</button>` +
      `</div>`;
    div.querySelector("[data-del]").onclick = async () => {
      await api.del("/api/accounts/" + idEnc);
      await loadAccounts();
    };
    const fileInput = div.querySelector("[data-skin]");
    fileInput.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("file", file);
      try {
        await api.upload("/api/accounts/" + idEnc + "/skin", fd);
        toast("Skin ajouté à « " + a.username + " ».");
        await loadAccounts();
      } catch (err) { toast("Erreur skin : " + err.message); }
      fileInput.value = "";
    };
    const delSkin = div.querySelector("[data-skindel]");
    if (delSkin) delSkin.onclick = async () => {
      await api.del("/api/accounts/" + idEnc + "/skin");
      toast("Skin retiré.");
      await loadAccounts();
    };
    box.appendChild(div);
  }
}

// ---------------- réglages ----------------
async function loadSettings() {
  const d = await api.get("/api/settings");
  SETTINGS = d.settings;
  $("#ramSlider").value = SETTINGS.ram_mb || 2048;
  $("#ramLabel").textContent = (SETTINGS.ram_mb || 2048) + " Mo";
  $("#setJava").value = SETTINGS.java_override || "";
  $("#setAutoJava").checked = SETTINGS.auto_install_java !== false;
  $("#setFullscreen").checked = SETTINGS.fullscreen === true;
  $("#setWidth").value = SETTINGS.width || 854;
  $("#setHeight").value = SETTINGS.height || 480;
  $("#setInstallDir").value = SETTINGS.install_dir || "";
  $("#setProxy").value = SETTINGS.proxy || "";
  $("#setMirror").value = SETTINGS.dl_mirror || "auto";
  CURRENT_MODE = SETTINGS.launch_mode || "vanilla";
  updateModeUI();
}

// ---------------- mode Vanilla / Shaders ----------------
function updateModeUI() {
  const btnV = $("#modeVanilla");
  const btnS = $("#modeShaders");
  const hint = $("#modeHint");
  if (btnV) btnV.classList.toggle("active", CURRENT_MODE === "vanilla");
  if (btnS) btnS.classList.toggle("active", CURRENT_MODE === "shaders");
  if (hint) {
    if (CURRENT_MODE === "shaders") {
      hint.textContent = "Fabric + Sodium + Iris + shaders (installé automatiquement)";
    } else {
      hint.textContent = "Minecraft vanilla, sans mods ni shaders";
    }
  }
}

function setMode(mode) {
  CURRENT_MODE = mode;
  updateModeUI();
  api.post("/api/settings", { launch_mode: mode }).catch(() => {});
}

async function refreshJavaHint(required) {
  try {
    const d = await api.get("/api/java");
    const avail = [];
    if (d.system_major) avail.push("système (Java " + d.system_major + ")");
    for (const b of d.bundled) avail.push("Java " + b.major + " (embarquée)");
    $("#javaStatus").innerHTML = avail.length
      ? "Java disponible : " + avail.join(", ") + "."
      : "Aucun Java détecté.";
    if (required) {
      const ok = (d.system_major && d.system_major >= required) ||
                 d.bundled.some((b) => b.major >= required);
      $("#javaRow").innerHTML = ok
        ? `<span class="muted">Java ${required} détecté — prêt.</span>`
        : (SETTINGS.auto_install_java !== false
            ? `<span><b>Java ${required} sera téléchargé automatiquement</b> au premier lancement.</span>`
            : `<span><b>Java ${required} manquant</b> — installe-le ou active le téléchargement auto.</span>`);
    }
  } catch (e) { /* silencieux */ }
}

// ---------------- lancement / progression ----------------
async function play() {
  const version = CURRENT_VERSION;
  const account = $("#accountSelect").value;
  if (!version) return toast("Sélectionne une version.");
  if (!account) return toast("Ajoute d'abord un compte (ex : un compte local).");

  let launchVersion = version;

  // Mode Shaders : installer le pack complet (Fabric + mods + shaders) si nécessaire,
  // puis lancer la version Fabric. L'installateur est idempotent (ne retélécharge pas
  // ce qui est déjà présent).
  if (CURRENT_MODE === "shaders") {
    const mcVersion = version.startsWith("fabric-loader-")
      ? version.rsplit("-", 1)[1]
      : version;
    try {
      $("#btnPlay").disabled = true;
      $("#btnPlay").textContent = "Vérification du pack Shaders…";
      await api.post("/api/shaders/install", { version: mcVersion });
      await waitForJobDone();
      // Récupérer l'ID de la version Fabric installée
      const inst = await api.get("/api/fabric/installed?mc=" + encodeURIComponent(mcVersion));
      if (inst.installed) {
        launchVersion = inst.installed;
        await loadVersions(true);
      } else {
        throw new Error("Fabric n'a pas pu être installé.");
      }
    } catch (e) {
      toast("Erreur mode Shaders : " + e.message);
      $("#btnPlay").disabled = false;
      $("#btnPlay").innerHTML = "▶&nbsp; JOUER";
      return;
    }
  }

  $("#btnPlay").disabled = true;
  try {
    await api.post("/api/launch", {
      version: launchVersion, account,
      ram_mb: +$("#ramSlider").value,
      width: +$("#setWidth").value,
      height: +$("#setHeight").value,
    });
    $("#progressArea").classList.remove("hidden");
    startPolling();
  } catch (e) {
    toast("Échec du lancement : " + e.message);
    $("#btnPlay").disabled = false;
  }
}

async function waitForJobDone() {
  return new Promise((resolve) => {
    const check = setInterval(async () => {
      try {
        const p = await api.get("/api/progress");
        if (p.status === "done" || p.status === "error") {
          clearInterval(check);
          resolve(p);
        }
      } catch (e) { /* ignore */ }
    }, 1000);
  });
}

function startPolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const p = await api.get("/api/progress");
      renderProgress(p);
    } catch (e) { /* serveur indisponible */ }
  }, 500);
}

function renderProgress(p) {
  $("#pStage").textContent = p.stage || p.status || "";
  $("#pPercent").textContent = p.total ? p.percent + "%" : "";
  $("#pBar").style.width = (p.percent || 0) + "%";
  $("#pMessage").textContent = p.message || "";
  if (p.status === "running") {
    $("#btnPlay").disabled = true;
    $("#btnPlay").textContent = "● " + (p.message || "En jeu…");
  } else if (p.status === "done") {
    $("#btnPlay").disabled = false;
    $("#btnPlay").textContent = "▶ JOUER";
    clearInterval(pollTimer);
    if (p.message) toast(p.message);
  } else if (p.status === "error") {
    $("#btnPlay").disabled = false;
    $("#btnPlay").textContent = "▶ JOUER";
    clearInterval(pollTimer);
    toast("Erreur : " + (p.error || p.message));
    $("#pStage").textContent = "Erreur";
    $("#pBar").style.width = "100%";
    $("#pBar").style.background = "linear-gradient(90deg,#b62324,#f85149)";
  }
  // journal
  if (p.status === "running" || p.status === "done" || p.status === "error") {
    if (!logTimer) {
      logTimer = setInterval(async () => {
        try {
          const d = await api.get("/api/logs");
          $("#logText").textContent = d.logs || "";
        } catch (e) {}
      }, 1200);
    }
  } else {
    clearInterval(logTimer); logTimer = null;
  }
}

// ---------------- modals ----------------
function openModal(id) {
  $("#" + id).classList.remove("hidden");
}
function closeModals() {
  $$(".modal").forEach((m) => m.classList.add("hidden"));
  $("#msArea").classList.add("hidden");
  $("#msMessage").textContent = "";
}

// ---------------- Microsoft ----------------
async function msLogin() {
  const btn = $("#btnMSLogin");
  btn.disabled = true;
  $("#msMessage").textContent = "Demande du code à Microsoft…";
  try {
    const d = await api.post("/api/auth/microsoft/start", {});
    $("#msArea").classList.remove("hidden");
    $("#msUri").textContent = d.verification_uri;
    $("#msCode").textContent = d.user_code;
    $("#msMessage").textContent = "En attente de validation… (ne ferme pas cette fenêtre)";
    window.open(d.verification_uri + "?otc=" + d.user_code, "_blank");
    const iv = setInterval(async () => {
      try {
        const r = await api.get("/api/auth/microsoft/status");
        if (r.status === "ok") {
          clearInterval(iv);
          $("#msArea").classList.add("hidden");
          $("#msMessage").textContent = "Connecté : " + r.account.username;
          await loadAccounts();
          toast("Compte Microsoft ajouté : " + r.account.username);
          btn.disabled = false;
        } else if (r.status === "error" || r.status === "expired") {
          clearInterval(iv);
          $("#msMessage").textContent = r.message || "Connexion annulée.";
          btn.disabled = false;
        }
      } catch (e) {
        clearInterval(iv); btn.disabled = false;
      }
    }, 1500);
  } catch (e) {
    $("#msMessage").textContent = "Erreur : " + e.message;
    btn.disabled = false;
  }
}

// ---------------- init ----------------
async function init() {
  try {
    // Chargement rapide depuis le cache, puis actualisation silencieuse
    // depuis les serveurs Mojang (les nouvelles versions apparaissent automatiquement).
    await Promise.all([loadVersions(false), loadAccounts(), loadSettings()]);
    const sel = CURRENT_VERSION;
    if (sel) selectVersion(sel, false);
    // Actualisation en arrière-plan : ne bloque pas l'interface
    loadVersions(true).catch(() => {});
  } catch (e) {
    toast("Impossible de joindre le lanceur : " + e.message);
  }

  $("#search").addEventListener("input", (e) => { query = e.target.value; renderList(); });
  $$(".filter-tabs button").forEach((b) => {
    b.onclick = () => {
      $$(".filter-tabs button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      filter = b.dataset.filter;
      renderList();
    };
  });
  $("#btnRefresh").onclick = async () => {
    $("#btnRefresh").disabled = true;
    try { await loadVersions(true); toast("Liste des versions actualisée."); }
    catch (e) { toast("Échec de l'actualisation : " + e.message); }
    $("#btnRefresh").disabled = false;
  };
  $("#ramSlider").addEventListener("input", () => {
    $("#ramLabel").textContent = $("#ramSlider").value + " Mo";
  });

  $("#modeVanilla").onclick = () => setMode("vanilla");
  $("#modeShaders").onclick = () => setMode("shaders");

  $("#btnPlay").onclick = play;
  $("#btnBedrock").onclick = openBedrock;
  $("#btnAccounts").onclick = () => openModal("modalAccounts");
  $("#btnSettings").onclick = () => { loadSettings(); refreshJavaHint(); openModal("modalSettings"); };
  $$(".modal [data-close]").forEach((b) => (b.onclick = closeModals));
  $$(".modal").forEach((m) => m.addEventListener("click", (e) => {
    if (e.target === m) closeModals();
  }));

  $("#btnNewAccount").onclick = () => openModal("modalAccounts");
  $("#btnAddOffline").onclick = async () => {
    const name = $("#offlineName").value.trim();
    if (!name) return toast("Entre un nom de compte local.");
    try {
      await api.post("/api/accounts/offline", { username: name });
      $("#offlineName").value = "";
      await loadAccounts();
      toast("Compte local « " + name + " » créé.");
    } catch (e) { toast("Erreur : " + e.message); }
  };
  $("#btnMSLogin").onclick = msLogin;

  $("#btnSaveSettings").onclick = async () => {
    try {
      await api.post("/api/settings", {
        java_override: $("#setJava").value.trim(),
        auto_install_java: $("#setAutoJava").checked,
        fullscreen: $("#setFullscreen").checked,
        width: +$("#setWidth").value || 854,
        height: +$("#setHeight").value || 480,
        ram_mb: +$("#ramSlider").value,
        install_dir: $("#setInstallDir").value.trim(),
        proxy: $("#setProxy").value.trim(),
        dl_mirror: $("#setMirror").value,
      });
      SETTINGS = (await api.get("/api/settings")).settings;
      closeModals();
      toast("Réglages enregistrés. Les nouvelles parties seront installées dans ce dossier.");
    } catch (e) { toast("Erreur : " + e.message); }
  };

  // ---------------- mods ----------------
  $("#btnMods").onclick = () => {
    if (!CURRENT_VERSION) return toast("Sélectionne d'abord une version.");
    openMods();
  };
  $("#modFileInput").addEventListener("change", (e) => {
    uploadModFiles(e.target.files);
    e.target.value = "";
  });
  const dz = $("#dropZone");
  dz.addEventListener("click", () => $("#modFileInput").click());
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("drag");
    uploadModFiles(e.dataTransfer.files);
  });
  $("#btnInstallShaders").onclick = installShadersPack;
  $("#btnFabricInstall").onclick = installFabric;

  // ---------------- Bedrock ----------------
  $("#btnBedrockPlay").onclick = async () => {
    try {
      await api.post("/api/bedrock/launch");
      toast("Minecraft Bedrock lance.");
    } catch (e) { toast("Erreur : " + e.message); }
  };
  $("#btnBedrockStore").onclick = () => api.post("/api/bedrock/open-store").catch(() => {});
  $("#btnBedrockOpenFolder").onclick = () => api.post("/api/bedrock/open-folder").catch(() => {});
  const dzB = $("#dropZoneBedrock");
  dzB.addEventListener("click", () => $("#bedrockPackInput").click());
  dzB.addEventListener("dragover", (e) => { e.preventDefault(); dzB.classList.add("drag"); });
  dzB.addEventListener("dragleave", () => dzB.classList.remove("drag"));
  dzB.addEventListener("drop", (e) => {
    e.preventDefault();
    dzB.classList.remove("drag");
    uploadBedrockPack(e.dataTransfer.files);
  });
  $("#bedrockPackInput").addEventListener("change", (e) => {
    uploadBedrockPack(e.target.files);
    e.target.value = "";
  });

  // ---------------- explorateur de dossiers ----------------
  $("#btnBrowse").onclick = openFolderBrowser;
  $("#btnFolderUp").onclick = () => {
    folderState.path = folderState.parent || "";
    renderFolder();
  };
  $("#btnFolderChoose").onclick = () => {
    if (!folderState.path) return toast("Choisis un dossier.");
    $("#setInstallDir").value = folderState.path;
    closeModals();
    toast("Dossier choisi : " + folderState.path);
  };
};

// ---------------- mods ----------------
async function openMods() {
  // En mode Shaders, afficher les mods de l'instance Fabric (si installée)
  let displayVersion = CURRENT_VERSION;
  if (CURRENT_MODE === "shaders" && !CURRENT_VERSION.startsWith("fabric-loader-")) {
    const mcVersion = CURRENT_VERSION;
    try {
      const inst = await api.get("/api/fabric/installed?mc=" + encodeURIComponent(mcVersion));
      if (inst.installed) displayVersion = inst.installed;
    } catch (e) { /* rester sur la version vanilla */ }
  }
  MODS_VIEW_VERSION = displayVersion;
  $("#modsVersion").textContent = displayVersion;
  renderShadersList();
  openModal("modalMods");
  await loadMods();
  await loadFabricStatus();
}

// ---------------- Fabric ----------------
async function loadFabricStatus() {
  const statusEl = $("#fabricStatus");
  const actionsEl = $("#fabricActions");
  const selectEl = $("#fabricLoaderSelect");
  const btnEl = $("#btnFabricInstall");

  try {
    // Verifier si Fabric est deja installe pour cette version
    const inst = await api.get("/api/fabric/installed?mc=" + encodeURIComponent(CURRENT_VERSION));
    if (inst.installed) {
      statusEl.innerHTML = '✅ Installé : <b>' + escapeHtml(inst.installed) + '</b><br>' +
        '<span class="muted">Sélectionne cette version dans la liste pour jouer avec des mods.</span>';
      actionsEl.style.display = "none";
      return;
    }

    // Charger la liste des loaders Fabric compatibles
    statusEl.textContent = "Chargement des versions Fabric…";
    const data = await api.get("/api/fabric/loaders?mc=" + encodeURIComponent(CURRENT_VERSION));
    const loaders = data.loaders || [];
    if (!loaders.length) {
      statusEl.textContent = "Aucune version de Fabric compatible avec " + CURRENT_VERSION + ".";
      actionsEl.style.display = "none";
      return;
    }

    // Remplir le select (versions stables d'abord, puis les autres)
    selectEl.innerHTML = "";
    const stable = loaders.filter((l) => l.stable);
    const others = loaders.filter((l) => !l.stable);
    for (const l of stable) {
      const opt = document.createElement("option");
      opt.value = l.loader_version;
      opt.textContent = l.loader_version + " (stable)";
      selectEl.appendChild(opt);
    }
    for (const l of others.slice(0, 10)) {
      const opt = document.createElement("option");
      opt.value = l.loader_version;
      opt.textContent = l.loader_version;
      selectEl.appendChild(opt);
    }

    statusEl.innerHTML = 'Fabric non installé pour <b>' + escapeHtml(CURRENT_VERSION) + '</b>.<br>' +
      '<span class="muted">Installe Fabric pour pouvoir utiliser des mods.</span>';
    actionsEl.style.display = "flex";
  } catch (e) {
    statusEl.textContent = "Erreur Fabric : " + e.message;
    actionsEl.style.display = "none";
  }
}

async function installFabric() {
  const loaderVersion = $("#fabricLoaderSelect").value;
  const btn = $("#btnFabricInstall");
  btn.disabled = true;
  btn.textContent = "Installation…";
  try {
    await api.post("/api/fabric/install", { mc: CURRENT_VERSION, loader_version: loaderVersion });
    toast("Installation de Fabric lancée…");
    // Attendre un peu puis rafraichir le statut et la liste des versions
    setTimeout(async () => {
      await loadFabricStatus();
      await loadVersions(true);
      toast("Fabric installé ! La version est disponible dans la liste.");
    }, 2000);
  } catch (e) {
    toast("Erreur installation Fabric : " + e.message);
  }
  btn.disabled = false;
  btn.textContent = "Installer Fabric";
}

async function loadMods() {
  try {
    const d = await api.get("/api/mods?version=" + encodeURIComponent(MODS_VIEW_VERSION));
    renderMods(d.mods);
  } catch (e) { toast("Erreur mods : " + e.message); }
}

function renderMods(mods) {
  const box = $("#modList");
  box.innerHTML = "";
  if (!mods.length) {
    box.innerHTML = '<li class="muted" style="padding:8px">Aucun mod pour cette version.</li>';
    return;
  }
  for (const m of mods) {
    const li = document.createElement("li");
    li.className = "mod-item" + (m.enabled ? "" : " disabled");
    li.innerHTML =
      `<span class="mname">${escapeHtml(m.name)}</span>` +
      `<span class="msize">${fmtSize(m.size)}</span>` +
      `<button class="mtoggle ${m.enabled ? "on" : ""}">${m.enabled ? "Activé" : "Désactivé"}</button>` +
      `<button class="mdel" title="Supprimer">✕</button>`;
    li.querySelector(".mtoggle").onclick = async () => {
      await api.post("/api/mods/toggle", { version: MODS_VIEW_VERSION, name: m.name, enable: !m.enabled });
      await loadMods();
    };
    li.querySelector(".mdel").onclick = async () => {
      if (!confirm("Supprimer le mod « " + m.name + " » ?")) return;
      await api.post("/api/mods/delete", { version: MODS_VIEW_VERSION, name: m.name });
      await loadMods();
    };
    box.appendChild(li);
  }
}

async function uploadModFiles(fileList) {
  if (!MODS_VIEW_VERSION) return;
  const files = [...fileList].filter((f) => f.name.endsWith(".jar") || f.name.endsWith(".zip"));
  if (!files.length) return toast("Seuls les fichiers .jar / .zip sont acceptés.");
  const fd = new FormData();
  fd.append("version", MODS_VIEW_VERSION);
  for (const f of files) fd.append("files", f, f.name);
  try {
    const r = await api.upload("/api/mods", fd);
    toast(r.saved.length + " mod(s) ajouté(s).");
    await loadMods();
  } catch (e) { toast("Erreur upload : " + e.message); }
}

// ---------------- Pack Shaders ----------------
const SHADERS_PACK = [
  { name: "Sodium", desc: "Optimisation des performances" },
  { name: "Sodium Extra", desc: "Options supplémentaires pour Sodium" },
  { name: "Entity Culling", desc: "Ne rend pas les entités cachées" },
  { name: "Iris", desc: "Chargement de shaders" },
  { name: "Complementary Shaders", desc: "Shaders équilibrés" },
  { name: "BSL Shaders", desc: "Shaders réalistes" },
  { name: "Vanilla Plus", desc: "Shaders légers style vanilla" },
];

function renderShadersList() {
  const box = $("#shadersList");
  if (!box) return;
  box.innerHTML = "";
  for (const s of SHADERS_PACK) {
    const div = document.createElement("div");
    div.className = "shader-item";
    div.innerHTML = `<span class="shader-name">${escapeHtml(s.name)}</span>` +
      `<span class="muted">${escapeHtml(s.desc)}</span>`;
    box.appendChild(div);
  }
}

async function installShadersPack() {
  const btn = $("#btnInstallShaders");
  btn.disabled = true;
  btn.textContent = "Installation…";
  try {
    await api.post("/api/shaders/install", { version: CURRENT_VERSION });
    toast("Pack Shaders en cours d'installation…");
    // Poll progress
    const check = setInterval(async () => {
      try {
        const p = await api.get("/api/progress");
        if (p.status === "done") {
          clearInterval(check);
          btn.disabled = false;
          btn.textContent = "⚡ Installer le pack Shaders";
          toast("Pack Shaders installé ! Sélectionne la version Fabric pour jouer.");
          await loadVersions(true);
          await loadMods();
        } else if (p.status === "error") {
          clearInterval(check);
          btn.disabled = false;
          btn.textContent = "⚡ Installer le pack Shaders";
          toast("Erreur : " + (p.error || "inconnue"));
        }
      } catch (e) { /* ignore */ }
    }, 1500);
  } catch (e) {
    toast("Erreur : " + e.message);
    btn.disabled = false;
    btn.textContent = "⚡ Installer le pack Shaders";
  }
}

// ---------------- Minecraft Bedrock ----------------
async function loadBedrockStatus() {
  try {
    const d = await api.get("/api/bedrock/status");
    const notInstalled = document.querySelector(".bedrock-not-installed");
    const installed = document.querySelector(".bedrock-installed");
    if (d.installed) {
      notInstalled.classList.add("hidden");
      installed.classList.remove("hidden");
      $("#bedrockVersion").textContent = "Version " + (d.version || "inconnue");
      renderBedrockPacks(d.resource_packs || []);
    } else {
      notInstalled.classList.remove("hidden");
      installed.classList.add("hidden");
    }
  } catch (e) {
    toast("Erreur Bedrock : " + e.message);
  }
}

function renderBedrockPacks(packs) {
  const box = $("#bedrockPackList");
  box.innerHTML = "";
  if (!packs.length) {
    box.innerHTML = '<li class="muted" style="padding:8px">Aucun resource pack installé.</li>';
    return;
  }
  for (const p of packs) {
    const li = document.createElement("li");
    li.className = "mod-item";
    li.innerHTML =
      `<span class="mname">${escapeHtml(p.name)}</span>` +
      `<span class="msize">${escapeHtml(p.version || "")}</span>` +
      `<button class="mdel" title="Supprimer">✕</button>`;
    li.querySelector(".mdel").onclick = async () => {
      if (!confirm("Supprimer le pack « " + p.name + " » ?")) return;
      await api.del("/api/bedrock/packs/" + encodeURIComponent(p.folder));
      await loadBedrockStatus();
    };
    box.appendChild(li);
  }
}

async function openBedrock() {
  openModal("modalBedrock");
  await loadBedrockStatus();
}

async function uploadBedrockPack(fileList) {
  const files = [...fileList].filter((f) => f.name.endsWith(".mcpack") || f.name.endsWith(".zip"));
  if (!files.length) return toast("Seuls les fichiers .mcpack / .zip sont acceptes.");
  const fd = new FormData();
  fd.append("file", files[0], files[0].name);
  try {
    const r = await api.upload("/api/bedrock/packs", fd);
    toast("Resource pack installe : " + (r.pack?.folder || files[0].name));
    await loadBedrockStatus();
  } catch (e) { toast("Erreur : " + e.message); }
}

// ---------------- explorateur de dossiers ----------------
const folderState = { path: "", parent: null };

async function openFolderBrowser() {
  folderState.path = "";
  openModal("modalFolder");
  await renderFolder();
}

async function renderFolder() {
  try {
    const d = await api.get("/api/fs/list?path=" + encodeURIComponent(folderState.path));
    folderState.path = d.path;
    folderState.parent = d.parent;
    $("#folderPath").textContent = d.path || "Choisir un lecteur";
    $("#btnFolderUp").disabled = !d.parent;
    const box = $("#folderList");
    box.innerHTML = "";
    if (!d.dirs.length) {
      box.innerHTML = '<li class="muted" style="padding:8px">(dossier vide)</li>';
    }
    for (const name of d.dirs) {
      const li = document.createElement("li");
      li.className = "folder-item";
      li.innerHTML = `<span class="fico">📁</span>${escapeHtml(name)}`;
      li.onclick = async () => {
        folderState.path = d.path ? d.path + (d.path.endsWith("\\") ? "" : "\\") + name : name;
        await renderFolder();
      };
      box.appendChild(li);
    }
  } catch (e) {
    toast("Impossible de lire le dossier : " + e.message);
  }
}

init();
