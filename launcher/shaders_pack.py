"""Pack Shaders préconfiguré : Sodium + Sodium Extra + Entity Culling + Iris + shaders.

Installe en un clic :
- Fabric (si absent)
- Mods : Sodium, Sodium Extra, Entity Culling, Iris
- Shader packs : Complementary Reimagined, BSL Shaders, Vanilla Plus
"""
import os
import urllib.parse

from . import download, fabric, mods, paths
from .download import JOB

MODRINTH_API = "https://api.modrinth.com/v2"

# Mods à installer (slugs Modrinth)
SHADER_MODS = [
    {"slug": "sodium", "name": "Sodium"},
    {"slug": "sodium-extra", "name": "Sodium Extra"},
    {"slug": "entityculling", "name": "Entity Culling"},
    {"slug": "iris", "name": "Iris"},
]

# Shader packs à installer (slugs Modrinth, type resourcepack, loader iris)
SHADER_PACKS = [
    {"slug": "complementary-reimagined", "name": "Complementary Reimagined"},
    {"slug": "bsl-shaders", "name": "BSL Shaders"},
    {"slug": "vanilla-plus", "name": "Vanilla Plus"},
]


def shaderpacks_dir(version_id):
    return os.path.join(paths.instances_root(), version_id, "shaderpacks")


def _modrinth_get(path):
    return download.http_get_json(MODRINTH_API + path)


def _get_latest_file(slug, mcver, loader="fabric"):
    """Trouve le dernier fichier compatible pour un projet Modrinth."""
    versions = _modrinth_get("/project/" + slug + "/version")
    cand = [v for v in versions
            if mcver in v.get("game_versions", []) and loader in v.get("loaders", [])]
    if not cand:
        cand = [v for v in versions if loader in v.get("loaders", [])]
    if not cand:
        # Dernier recours : n'importe quelle version
        cand = list(versions)
    if not cand:
        raise RuntimeError("Aucune version disponible pour %s." % slug)
    cand.sort(key=lambda v: v.get("date_published", ""), reverse=True)
    v = cand[0]
    files = v.get("files") or []
    if not files:
        raise RuntimeError("Pas de fichier pour %s." % slug)
    # Préférer le fichier principal
    primary = [f for f in files if f.get("primary")]
    return (primary[0] if primary else files[0])


def extract_mc_version(version_id):
    """Extrait la version Minecraft vanilla d'un ID de version (Fabric ou vanilla)."""
    if version_id.startswith("fabric-loader-"):
        # format: fabric-loader-<ver>-<mcver>
        return version_id.rsplit("-", 1)[-1]
    return version_id


def install_shaders_pack(version_id):
    """Installe le pack Shaders complet pour une version.

    - Détecte la version Minecraft vanilla (depuis un ID Fabric ou vanilla).
    - Installe Fabric si nécessaire.
    - Télécharge les mods vers le dossier mods/ de l'instance Fabric.
    - Télécharge les shader packs vers le dossier shaderpacks/.
    Retourne {fabric_id, mods, shaders}.
    """
    mc_version = extract_mc_version(version_id)

    total_steps = len(SHADER_MODS) + len(SHADER_PACKS) + 1  # +1 pour Fabric
    current = 0

    # --- Étape 1 : Installer Fabric ---
    JOB.stage("Fabric", "Vérification de Fabric…")
    fabric_id = fabric.is_installed(mc_version)
    if not fabric_id:
        JOB.stage("Fabric", "Installation de Fabric pour Minecraft %s…" % mc_version)
        res = fabric.install(mc_version)
        fabric_id = res["id"]
    current += 1
    JOB.set(current=current, total=total_steps,
            percent=(current / total_steps) * 100)

    instance_id = fabric_id

    # Créer les dossiers
    os.makedirs(mods.mods_dir(instance_id), exist_ok=True)
    os.makedirs(shaderpacks_dir(instance_id), exist_ok=True)

    # --- Étape 2 : Installer les mods ---
    installed_mods = []
    for mod in SHADER_MODS:
        current += 1
        JOB.stage("Mods", "Installation de %s…" % mod["name"])
        JOB.set(current=current, total=total_steps,
                percent=(current / total_steps) * 100)
        try:
            res = mods.install(mod["slug"], mc_version, "fabric", instance_id)
            installed_mods.append(res["file"])
        except Exception:
            # Continuer avec les autres mods si un échoue
            pass

    # --- Étape 3 : Installer les shader packs ---
    installed_shaders = []
    for sp in SHADER_PACKS:
        current += 1
        JOB.stage("Shaders", "Téléchargement de %s…" % sp["name"])
        JOB.set(current=current, total=total_steps,
                percent=(current / total_steps) * 100)
        try:
            f = _get_latest_file(sp["slug"], mc_version, "iris")
            filename = urllib.parse.unquote(
                os.path.basename(f["url"].split("?")[0])) or (sp["slug"] + ".zip")
            dest = os.path.join(shaderpacks_dir(instance_id), filename)
            download.download_file(f["url"], dest, size=f.get("size"))
            installed_shaders.append(filename)
        except Exception:
            pass

    JOB.set(current=total_steps, total=total_steps, percent=100.0)

    return {
        "fabric_id": fabric_id,
        "mc_version": mc_version,
        "mods": installed_mods,
        "shaders": installed_shaders,
    }
