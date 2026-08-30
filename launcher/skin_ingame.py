"""Skin en jeu pour les comptes locaux : installateur Fabric + CustomSkinLoader,
et réponses JsonAPI CustomSkinLoader servies par le lanceur.

Minecraft vanilla ne charge pas de skin pour un compte hors-ligne : le serveur
de session Mojang ne connaît pas ces profils. La solution standard est le mod
CustomSkinLoader (Fabric), qui demande les skins à des serveurs personnalisés —
ici le lanceur lui-même (http://127.0.0.1:8765/api/skins).
"""
import json
import os

from . import auth, fabric, mods, paths

CSL_SLUG = "customskinloader"
SKINS_API_ROOT = "http://127.0.0.1:8765/api/skins"
SELF_ROOT = "http://127.0.0.1:8765"


def account_for_username(username):
    from . import state
    st = state.load()
    want = auth.normalize_username(username)
    for acc in st["accounts"]:
        if auth.normalize_username(acc.get("username", "")) == want:
            return acc
    return None


def csl_profile(username):
    """Réponse JsonAPI CustomSkinLoader pour un pseudo (ou {} si aucun skin)."""
    acc = account_for_username(username)
    if not acc or not auth.has_skin(acc["id"]):
        return {}
    return {
        "player": {
            "name": acc["username"],
            "skins": [{
                "type": "steve",
                "url": "%s/api/accounts/%s/skin.png" % (SELF_ROOT, acc["id"]),
            }],
            "capes": [],
        }
    }


def install_ingame(mcver, account_id):
    """Prépare la version Minecraft pour afficher le skin du compte local :
    installe Fabric si nécessaire, télécharge CustomSkinLoader, écrit sa config
    et sélectionne la version Fabric. Renvoie l'id de la version à lancer."""
    from . import state
    st = state.load()
    acc = next((a for a in st["accounts"] if a["id"] == account_id), None)
    if not acc:
        raise RuntimeError("Compte introuvable.")
    if acc.get("type") == "microsoft":
        raise RuntimeError("Un compte Microsoft affiche déjà son skin officiel en jeu.")

    # 1) Profil Fabric (réutilisé s'il existe déjà pour cette version)
    fabric_version = None
    for name in os.listdir(paths.VERSIONS):
        if not name.endswith(".json") or name == "manifest.json":
            continue
        vid = name[:-5]
        if fabric.is_installed(mcver, vid):
            fabric_version = vid
            break
    if not fabric_version:
        fabric_version = fabric.install(mcver)

    # 2) CustomSkinLoader dans le dossier mods de l'instance Fabric
    mods.install(CSL_SLUG, mcver, "fabric", fabric_version)

    # 3) Config CustomSkinLoader -> serveur local du lanceur
    inst = mods.instance_dir(fabric_version)
    csl_dir = os.path.join(inst, "CustomSkinLoader")
    os.makedirs(csl_dir, exist_ok=True)
    config = {
        "loadlist": [
            {"name": "RedstoneLauncher", "type": "JsonAPI",
             "root": SKINS_API_ROOT, "cache": "default"}
        ]
    }
    with open(os.path.join(csl_dir, "Config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # 4) On sélectionne la version Fabric pour lancer directement avec le skin
    st["selected_version"] = fabric_version
    state.save()
    return fabric_version
