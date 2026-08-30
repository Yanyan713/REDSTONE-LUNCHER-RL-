"""Installation de Fabric (mod loader) pour une version Minecraft donnée.

Fabric est installé comme une « version custom » : on télécharge le profil
JSON depuis l'API meta.fabricmc.net et on le sauvegarde dans
``data/versions/<fabric_id>.json``. Le profil contient ``inheritsFrom``
(la version Minecraft de base) et les bibliothèques Fabric au format Maven
(gérées par ``versions._maven_to_standard``). Le lanceur fusionne ensuite
la version Fabric avec sa version parent au lancement.
"""
import json
import os

from . import download, paths, versions

FABRIC_META = "https://meta.fabricmc.net/v2"


def list_loaders(mc_version):
    """Liste les versions de Fabric Loader compatibles avec une version Minecraft.

    Retourne une liste de ``{loader_version, stable, intermediary}`` triée
    par date de publication (la plus récente d'abord).
    """
    url = FABRIC_META + "/versions/loader/" + mc_version
    data = download.http_get_json(url)
    out = []
    for item in data:
        loader = item.get("loader", {}) or {}
        inter = item.get("intermediary", {}) or {}
        out.append({
            "loader_version": loader.get("version"),
            "stable": bool(loader.get("stable", False)),
            "intermediary": inter.get("version"),
        })
    return out


def install(mc_version, loader_version=None):
    """Installe Fabric pour une version Minecraft.

    - Si ``loader_version`` est None, prend la dernière version stable.
    - Télécharge le profil JSON Fabric et le sauvegarde comme version custom.
    - Retourne ``{id, loader_version, mc_version, main_class}``.
    """
    if loader_version is None:
        loaders = list_loaders(mc_version)
        if not loaders:
            raise RuntimeError(
                "Aucune version de Fabric compatible avec Minecraft %s. "
                "Vérifie que cette version existe et est supportée par Fabric." % mc_version)
        stable = [l for l in loaders if l.get("stable")]
        chosen = stable[0] if stable else loaders[0]
        loader_version = chosen["loader_version"]

    profile_url = "%s/versions/loader/%s/%s/profile/json" % (
        FABRIC_META, mc_version, loader_version)
    profile = download.http_get_json(profile_url)

    fabric_id = profile.get("id") or ("fabric-loader-%s-%s" % (loader_version, mc_version))
    profile["id"] = fabric_id

    # Sauvegarder le profil comme version custom
    dest = os.path.join(paths.VERSIONS, fabric_id + ".json")
    os.makedirs(paths.VERSIONS, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    # Invalider le cache du manifest pour que la nouvelle version apparaisse
    versions._manifest = None

    return {
        "id": fabric_id,
        "loader_version": loader_version,
        "mc_version": mc_version,
        "main_class": profile.get("mainClass"),
    }


def is_installed(mc_version):
    """Retourne l'ID de la version Fabric installée pour ``mc_version``,
    ou None si aucune n'est installée."""
    try:
        for name in os.listdir(paths.VERSIONS):
            if not name.endswith(".json") or name == "manifest.json":
                continue
            vid = name[:-5]
            # Les profils Fabric ont un ID du type « fabric-loader-<ver>-<mcver> »
            if vid.startswith("fabric-loader-") and vid.endswith("-" + mc_version):
                return vid
    except Exception:
        pass
    return None


def list_installed():
    """Liste toutes les versions Fabric installées (IDs)."""
    out = []
    try:
        for name in sorted(os.listdir(paths.VERSIONS)):
            if not name.endswith(".json") or name == "manifest.json":
                continue
            vid = name[:-5]
            if vid.startswith("fabric-loader-"):
                out.append(vid)
    except Exception:
        pass
    return out
