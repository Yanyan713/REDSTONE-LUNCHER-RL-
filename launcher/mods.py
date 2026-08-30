"""Gestion des mods : dossier « mods » de l'instance + recherche/installation Modrinth."""
import json
import os
import urllib.parse

from . import download, paths

MODRINTH_API = "https://api.modrinth.com/v2"
MAX_MOD_SIZE = 300 * 1024 * 1024  # 300 Mo, sécurité anti-fichier énorme

LOADERS = ("forge", "fabric", "neoforge", "quilt")


def instance_dir(version_id):
    return os.path.join(paths.instances_root(), version_id)


def mods_dir(version_id):
    return os.path.join(instance_dir(version_id), "mods")


# --------------------------------------------------------------------------
# Fichiers locaux
# --------------------------------------------------------------------------
def list_mods(version_id):
    d = mods_dir(version_id)
    os.makedirs(d, exist_ok=True)
    out = []
    for name in sorted(os.listdir(d)):
        full = os.path.join(d, name)
        if not os.path.isfile(full):
            continue
        enabled = not name.endswith(".disabled")
        base = name[:-9] if name.endswith(".disabled") else name
        out.append({
            "name": name,
            "base": base,
            "enabled": enabled,
            "size": os.path.getsize(full),
        })
    return out


def save_upload(version_id, filename, data):
    filename = os.path.basename((filename or "mod.jar").replace("\\", "/"))
    if not filename:
        filename = "mod.jar"
    if not filename.endswith((".jar", ".zip", ".disabled")):
        filename += ".jar"
    d = mods_dir(version_id)
    os.makedirs(d, exist_ok=True)
    dest = os.path.join(d, filename)
    with open(dest, "wb") as f:
        f.write(data)
    return filename


def toggle(version_id, name, enable):
    d = mods_dir(version_id)
    name = os.path.basename(name)
    full = os.path.join(d, name)
    if not os.path.isfile(full):
        return False
    if enable and name.endswith(".disabled"):
        os.rename(full, full[:-9])
    elif not enable and not name.endswith(".disabled"):
        os.rename(full, full + ".disabled")
    return True


def delete(version_id, name):
    d = mods_dir(version_id)
    base = os.path.basename(name)
    removed = []
    for cand in (base, base + ".disabled"):
        full = os.path.join(d, cand)
        if os.path.isfile(full):
            os.remove(full)
            removed.append(cand)
    return bool(removed)


# --------------------------------------------------------------------------
# Modrinth
# --------------------------------------------------------------------------
def _modrinth_get(path):
    return download.http_get_json(MODRINTH_API + path)


def search(query, mcver=None):
    url = "/search?query=" + urllib.parse.quote(query) + "&limit=20"
    facets = [["project_type:mod"]]
    if mcver:
        facets.append(["versions:" + mcver])
    url += "&facets=" + urllib.parse.quote(json.dumps(facets))
    try:
        d = _modrinth_get(url)
        # Si aucun resultat avec le filtre de version, reessayer sans
        # (version trop recente, snapshot custom, ou ID Fabric au lieu de version vanilla)
        if mcver and not d.get("hits"):
            url2 = "/search?query=" + urllib.parse.quote(query) + "&limit=20&facets=" + \
                urllib.parse.quote(json.dumps([["project_type:mod"]]))
            d = _modrinth_get(url2)
    except Exception:
        # Nouvel essai sans filtre de version (plus permissif)
        url2 = "/search?query=" + urllib.parse.quote(query) + "&limit=20&facets=" + \
            urllib.parse.quote(json.dumps([["project_type:mod"]]))
        d = _modrinth_get(url2)
    hits = []
    for h in d.get("hits", []):
        gv = h.get("versions") or []
        hits.append({
            "title": h.get("title"),
            "slug": h.get("slug"),
            "description": (h.get("description") or "")[:140],
            "downloads": h.get("downloads", 0),
            "author": h.get("author") or "",
            "icon": h.get("icon_url"),
            "loaders": [c for c in h.get("categories", []) if c in LOADERS],
            "game_versions": gv[-6:],
            "nb_versions": len(gv),
        })
    return hits


def install(slug, mcver, loader, version_id):
    """Télécharge le meilleur fichier du mod compatible (version Minecraft + loader)."""
    versions = _modrinth_get("/project/" + slug + "/version")
    cand = [v for v in versions
            if mcver in v.get("game_versions", []) and loader in v.get("loaders", [])]
    if not cand:
        cand = [v for v in versions if loader in v.get("loaders", [])]
    if not cand:
        raise RuntimeError("Aucune version du mod compatible avec « %s »." % loader)
    cand.sort(key=lambda v: v.get("date_published", ""), reverse=True)
    v = cand[0]
    files = v.get("files") or []
    if not files:
        raise RuntimeError("Ce mod n'a pas de fichier à télécharger.")
    f = files[0]
    if f.get("size", 0) > MAX_MOD_SIZE:
        raise RuntimeError("Fichier trop volumineux (%d Mo)." % (f.get("size", 0) // 1048576))

    filename = urllib.parse.unquote(os.path.basename(f["url"].split("?")[0])) or (slug + ".jar")
    d = mods_dir(version_id)
    os.makedirs(d, exist_ok=True)
    dest = os.path.join(d, filename)
    download.download_file(f["url"], dest, size=f.get("size"))
    return {
        "file": filename,
        "mc_version": v.get("game_versions", [])[-1] if v.get("game_versions") else None,
        "loader": loader,
        "mod_version": v.get("version_number"),
    }
