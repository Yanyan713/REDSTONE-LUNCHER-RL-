"""Cœur du lanceur : prépare une version (client, libs, natives, assets, Java)
puis construit et démarre le processus Minecraft."""
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import threading
import time
import traceback
import zipfile
from concurrent.futures import ThreadPoolExecutor

from . import auth, java as java_mod, paths, skins, state, versions
from .download import JOB, download_file

ASSETS_BASE = "https://resources.download.minecraft.net"


def current_os():
    p = sys.platform
    if p.startswith("win"):
        return "windows"
    if p == "darwin":
        return "osx"
    return "linux"


def current_arch():
    m = platform.machine().lower()
    if m in ("amd64", "x86_64"):
        return "x86_64"
    if m in ("aarch64", "arm64"):
        return "arm64"
    return "x86"


def _rules_allow(rules, osname, osarch, features=None):
    if not rules:
        return True
    features = features or {}
    allowed = False
    for rule in rules:
        os_rule = rule.get("os") or {}
        ok = True
        if "name" in os_rule and os_rule["name"] != osname:
            ok = False
        if ok and "arch" in os_rule and os_rule["arch"] != osarch:
            ok = False
        if ok:
            # Conditions sur les "features" (ex : is_demo_user, has_quick_plays_support…).
            # Si une feature ne correspond pas à notre configuration, la règle ne s'applique pas.
            feat = rule.get("features") or {}
            for k, v in feat.items():
                if features.get(k) != v:
                    ok = False
                    break
        if ok:
            allowed = (rule.get("action", "allow") == "allow")
    return allowed


def resolve_libraries(meta, osname, osarch):
    """Sépare les bibliothèques (classpath) et les natives pour l'OS courant."""
    jars, natives = [], []
    for lib in meta.get("libraries", []):
        if not _rules_allow(lib.get("rules"), osname, osarch):
            continue
        dl = lib.get("downloads") or {}
        artifact = dl.get("artifact")
        if artifact and artifact.get("url"):
            jars.append(artifact)
        classifiers = dl.get("classifiers") or {}
        natives_map = lib.get("natives") or {}
        classifier = natives_map.get(osname)
        if classifier and classifier in classifiers:
            natives.append(classifiers[classifier])
        else:
            for cname, cval in classifiers.items():
                if cname == "natives-" + osname:
                    natives.append(cval)
                    break
    return jars, natives


# ---------------------------------------------------------------------------
# Préparation
# ---------------------------------------------------------------------------
def _download_many(items, stage, workers=6):
    """Télécharge plusieurs fichiers en parallèle (assets / bibliothèques).

    items = [(url, dest, sha1, size), ...]. La progression globale (barre 0-100 %)
    est mise à jour sous verrou, même en parallèle.
    """
    total = sum((sz or 0) for _, _, _, sz in items)
    if not items:
        JOB.set(stage=stage, current=0, total=0)
        return
    shared = {"done": 0, "lock": threading.Lock()}
    JOB.stage(stage, "Téléchargement (%d fichiers, %.1f Mo)…" % (len(items), total / 1048576))

    def work(item):
        url, dest, sha1, size = item
        prev = [0]

        def cb(d, t):
            with shared["lock"]:
                if d < prev[0]:
                    # nouvelle tentative (compteur remis à zéro) : on retire l'ancien
                    shared["done"] -= prev[0]
                    prev[0] = 0
                shared["done"] += d - prev[0]
                prev[0] = d
                JOB.set(stage=stage, current=shared["done"], total=total)

        download_file(url, dest, sha1=sha1, size=size, progress=cb)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(work, it) for it in items]
        for f in futures:
            f.result()  # relève la première erreur -> échec propre du lancement
    JOB.set(stage=stage, current=total, total=total)  # force 100 %


def _download_with_job(url, dest, sha1, size, stage, base_done, total):
    def cb(done, total_chunk):
        JOB.set(stage=stage, current=base_done + done, total=total)
    return download_file(url, dest, sha1=sha1, size=size, progress=cb)


def _prepare_client(meta, version_id):
    client = meta["downloads"]["client"]
    dest = os.path.join(paths.VERSIONS, version_id, "client.jar")
    total = client.get("size", 0)
    JOB.stage("Téléchargement du jeu", version_id)

    def cb(d, t):
        JOB.set(stage="Téléchargement du jeu", message=version_id,
                current=d, total=total)

    download_file(client["url"], dest, sha1=client.get("sha1"),
                  size=client.get("size"), progress=cb)
    JOB.set(stage="Téléchargement du jeu", current=total, total=total)
    return dest


def _prepare_libraries(meta, osname, osarch):
    jars, natives = resolve_libraries(meta, osname, osarch)
    classpath = [os.path.join(paths.LIBRARIES, a["path"]) for a in jars]
    items = [(a["url"], os.path.join(paths.LIBRARIES, a["path"]),
              a.get("sha1"), a.get("size")) for a in jars]
    _download_many(items, "Bibliothèques")
    return classpath, natives


def _prepare_natives(meta_version_id, natives):
    if not natives:
        return os.path.join(paths.NATIVES, meta_version_id)
    natives_dir = os.path.join(paths.NATIVES, meta_version_id)
    os.makedirs(natives_dir, exist_ok=True)
    JOB.stage("Bibliothèques natives", "Téléchargement et extraction des natives…")
    for i, art in enumerate(natives):
        dest = os.path.join(paths.LIBRARIES, art["path"])
        download_file(art["url"], dest, sha1=art.get("sha1"), size=art.get("size"))
        with zipfile.ZipFile(dest) as z:
            z.extractall(natives_dir)
    return natives_dir


def _prepare_assets(meta):
    ai = meta.get("assetIndex") or {}
    index_id = ai.get("id") or meta.get("assets") or "legacy"
    index_path = os.path.join(paths.INDEXES, index_id + ".json")
    JOB.stage("Assets", "Index des assets (" + index_id + ")…")
    download_file(ai["url"], index_path, sha1=ai.get("sha1"), size=ai.get("size"))
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    objects = index.get("objects", {})
    items = []
    for key, obj in objects.items():
        h = obj.get("hash")
        if not h:
            continue
        dest = os.path.join(paths.OBJECTS, h[:2], h)
        if not os.path.exists(dest) or os.path.getsize(dest) != obj.get("size", 0):
            url = "%s/%s/%s" % (ASSETS_BASE, h[:2], h)
            items.append((url, dest, h, obj.get("size")))

    _download_many(items, "Assets")
    return index_id


def _prepare_logging(meta, version_id):
    lg = (meta.get("logging") or {}).get("client")
    if not lg:
        return None
    dest = os.path.join(paths.LOGS, version_id + "-log4j2.xml")
    f = lg.get("file") or {}
    download_file(f["url"], dest, sha1=f.get("sha1"))
    return dest


def _find_account(account_id):
    st = state.load()
    for acc in st["accounts"]:
        if acc["id"] == account_id:
            return acc
    return None


# ---------------------------------------------------------------------------
# Construction de la commande
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"\$\{([^}]+)\}")


def _sub(text, values):
    def repl(m):
        return values.get(m.group(1), m.group(0))
    return _TOKEN_RE.sub(repl, text)


def _resolve_args(args, values, osname, osarch, features=None):
    out = []
    for a in args or []:
        if isinstance(a, str):
            out.append(_sub(a, values))
        elif isinstance(a, dict):
            if not _rules_allow(a.get("rules"), osname, osarch, features):
                continue
            val = a.get("value", [])
            if isinstance(val, str):
                val = [val]
            for v in val:
                out.append(_sub(v, values))
    return out


_QUICKPLAY_FLAGS = ("--quickPlayPath", "--quickPlaySingleplayer",
                    "--quickPlayMultiplayer", "--quickPlayRealms")


def _strip_bad_args(mc_args):
    """Retire les arguments quick play (et leur valeur) ainsi que tout jeton
    non résolu (${...}) : un quick play inattendu ferait planter Minecraft
    (« Only one quick play option can be specified »)."""
    out = []
    skip_next = False
    for a in mc_args:
        if skip_next:
            skip_next = False
            continue
        if a in _QUICKPLAY_FLAGS:
            skip_next = True
            continue
        if "${" in a:
            continue
        out.append(a)
    return out


def build_launch_command(meta, version_id, account, ram_mb, java_exe, game_dir,
                         natives_dir, assets_root, index_id, width, height,
                         classpath, logging_file, fullscreen=False):
    osname, osarch = current_os(), current_arch()
    values = {
        "auth_player_name": auth.normalize_username(account.get("username", "Player")),
        "auth_session": account.get("access_token", "0"),
        "auth_access_token": account.get("access_token", "0"),
        "auth_uuid": account.get("uuid", "00000000-0000-0000-0000-000000000000"),
        "user_type": "msa" if account.get("type") == "microsoft" else "legacy",
        "user_properties": "{}",
        "clientid": "",
        "auth_xuid": "",
        "version_name": version_id,
        "version_type": meta.get("type", "release"),
        "game_directory": game_dir,
        "game_assets": assets_root,
        "assets_root": assets_root,
        "assets_index_name": index_id,
        "resolution_width": str(width),
        "resolution_height": str(height),
        "natives_directory": natives_dir,
        "classpath": classpath,
        "library_directory": paths.LIBRARIES,
        "launcher_name": "RedstoneLauncher",
        "launcher_version": "1.0",
        # Arguments "quick play" : non utilisés par défaut -> vides (jamais transmis)
        "quickPlayPath": "",
        "quickPlaySingleplayer": "",
        "quickPlayMultiplayer": "",
        "quickPlayRealms": "",
    }

    # Features de lancement : on passe toujours une résolution personnalisée,
    # jamais le mode démo ni le "quick play" (sinon Minecraft plante : « Only one
    # quick play option can be specified »).
    features = {"has_custom_resolution": True}

    jvm = ["-Xmx%dM" % ram_mb, "-Xms%dM" % ram_mb]
    mc_args = []

    if meta.get("arguments"):
        jvm += _resolve_args(meta["arguments"].get("jvm", []), values, osname, osarch, features)
        mc_args = _resolve_args(meta["arguments"].get("game", []), values, osname, osarch, features)
        mc_args = _strip_bad_args(mc_args)
    else:
        # Versions <= 1.12 : arguments de jeu en une seule chaîne
        template = (meta.get("minecraftArguments") or "").strip()
        mc_args = [_sub(tok, values) for tok in template.split()]
        jvm += ["-Djava.library.path=" + natives_dir, "-cp", classpath]

    if logging_file:
        jvm.append("-Dlog4j.configurationFile=" + logging_file)
    jvm += ["-Dminecraft.launcher.brand=RedstoneLauncher",
            "-Dminecraft.launcher.version=1.0"]

    # Pour les très anciennes versions (alpha/bêta), la fenêtre doit être dans
    # le thread AWT ; on l'autorise explicitement.
    if meta.get("arguments") is None:
        jvm.append("-Djava.awt.headless=false")

    if fullscreen:
        mc_args.append("--fullscreen")

    return [java_exe] + jvm + [meta.get("mainClass", "net.minecraft.client.main.Main")] + mc_args


# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------
def launch(version_id, account_id, ram_mb=2048, width=854, height=480, java_override=None):
    if JOB.snapshot()["active"]:
        raise RuntimeError("Un lancement est déjà en cours (jeu en exécution ou préparation).")
    st = state.load()
    ram = int(ram_mb or st["settings"].get("ram_mb", 2048))
    w = int(width or st["settings"].get("width", 854))
    h = int(height or st["settings"].get("height", 480))
    jo = java_override or st["settings"].get("java_override")
    thread = threading.Thread(target=_launch_worker,
                              args=(version_id, account_id, ram, w, h, jo),
                              daemon=True)
    thread.start()
    return True


def _launch_worker(version_id, account_id, ram_mb, width, height, java_override):
    osname, osarch = current_os(), current_arch()
    try:
        JOB.begin("Préparation", "Récupération des informations de version…")
        meta = versions.get_version_meta(version_id)

        account = _find_account(account_id)
        if not account:
            raise RuntimeError("Compte introuvable.")
        account = auth.ensure_valid(account)

        client_path = _prepare_client(meta, version_id)

        # Skin personnalise (compte local uniquement) : on patcher
        # directement le client.jar pour remplacer les skins par defaut.
        # Cette methode ne depend pas du systeme de resource packs (qui
        # rejette le pack sur les versions recentes comme 26.x).
        patched_client = skins.get_patched_client_jar(version_id, account)
        if patched_client:
            client_path = patched_client
            JOB.stage("Skin", "Skin personnalise injecte dans le client.jar.")

        classpath_entries, natives = _prepare_libraries(meta, osname, osarch)
        classpath = os.pathsep.join(classpath_entries + [client_path])
        natives_dir = _prepare_natives(version_id, natives)
        index_id = _prepare_assets(meta)
        logging_file = _prepare_logging(meta, version_id)

        required = (meta.get("javaVersion") or {}).get("majorVersion", 8)
        java_exe = java_override or java_mod.find_java(required)
        if not java_exe:
            if state.load()["settings"].get("auto_install_java", True):
                JOB.stage("Installation de Java", "Java %d requis — téléchargement automatique…" % required)
                java_exe = java_mod.install_java(required, progress=_java_progress)
            else:
                raise RuntimeError("Java %d introuvable. Active le téléchargement automatique de Java "
                                   "dans les réglages, ou installe Java %d." % (required, required))

        game_dir = os.path.join(paths.instances_root(), version_id)
        os.makedirs(game_dir, exist_ok=True)
        os.makedirs(os.path.join(game_dir, "mods"), exist_ok=True)

        # Desactiver l'ancien resource pack de skin (s'il existe) pour
        # eviter le message "incompatible" sur les versions recentes.
        # Le skin est desormais injecte directement dans le client.jar.
        skins.disable_pack(game_dir)

        fullscreen = bool(state.load()["settings"].get("fullscreen", False))
        cmd = build_launch_command(meta, version_id, account, ram_mb, java_exe,
                                   game_dir, natives_dir, paths.ASSETS, index_id,
                                   width, height, classpath, logging_file, fullscreen)

        JOB.stage("Lancement", "Démarrage de Minecraft…")
        log_path = os.path.join(paths.LOGS, "%s-%d.log" % (version_id, int(time.time())))
        logf = open(log_path, "w", encoding="utf-8", errors="replace")
        logf.write("$ " + " ".join(shlex.quote(x) for x in cmd) + "\n\n")
        logf.flush()

        flags = 0
        if osname == "windows":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        proc = subprocess.Popen(cmd, cwd=game_dir, stdout=logf, stderr=logf,
                                creationflags=flags)
        JOB.set(log_file=log_path)
        JOB.running(proc.pid, "Minecraft lancé (PID %d). Ferme la fenêtre du jeu pour terminer." % proc.pid)

        threading.Thread(target=_wait_process, args=(proc, logf, version_id), daemon=True).start()
    except Exception as e:
        JOB.fail(str(e))
        traceback.print_exc()


def _java_progress(message, done, total):
    JOB.set(stage="Installation de Java", message=message, current=done, total=total)


def _wait_process(proc, logf, version_id):
    code = proc.wait()
    try:
        logf.close()
    except Exception:
        pass
    if JOB.snapshot().get("pid") == proc.pid:
        if code == 0:
            JOB.done("Minecraft s'est fermé normalement (code 0).")
        else:
            JOB.done("Minecraft s'est fermé (code %d). Vérifie les logs si besoin." % code)


def current_log_tail(lines=120):
    snap = JOB.snapshot()
    path = snap.get("log_file")
    if not path or not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = f.readlines()
    return "".join(data[-lines:])
