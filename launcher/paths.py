"""Chemins du lanceur : tout est stocké localement dans ./data (portable).

Supporte aussi l'environnement PyInstaller (frozen) :
- Les assets web (web/) sont bundles dans l'exe et extraits dans sys._MEIPASS.
- Les donnees utilisateur (versions, instances, logs...) sont stockees a cote de l'exe.
"""
import os
import sys

# Detection de l'environnement PyInstaller
_FROZEN = getattr(sys, "frozen", False)
_BUNDLE_DIR = getattr(sys, "_MEIPASS", None)  # dossier d'extraction (one-file) ou bundle (one-dir)

if _FROZEN and _BUNDLE_DIR:
    # Environnement compile :
    # - ROOT = dossier contenant l'exe (pour les donnees utilisateur, portable)
    # - WEB = dossier web bundle dans _MEIPASS (lecture seule)
    ROOT = os.path.dirname(os.path.abspath(sys.executable))
    WEB = os.path.join(_BUNDLE_DIR, "web")
else:
    # Environnement de developpement :
    # Racine du projet = parent du dossier "launcher"
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    WEB = os.path.join(ROOT, "web")

DATA = os.path.join(ROOT, "data")

VERSIONS = os.path.join(DATA, "versions")       # manifest + jsons de version + client.jar
LIBRARIES = os.path.join(DATA, "libraries")     # bibliothèques téléchargées
ASSETS = os.path.join(DATA, "assets")           # racine des assets
INDEXES = os.path.join(ASSETS, "indexes")       # index d'assets
OBJECTS = os.path.join(ASSETS, "objects")       # fichiers d'assets (hash/2/hash)
JAVA = os.path.join(DATA, "java")               # JRE téléchargées
INSTANCES = os.path.join(DATA, "instances")     # dossiers de jeu par version
LOGS = os.path.join(DATA, "logs")               # logs de lancement
NATIVES = os.path.join(DATA, "natives")         # natives extraites par version
SKINS = os.path.join(DATA, "skins")             # skins uploadés par compte


def ensure_dirs():
    for d in (VERSIONS, LIBRARIES, INDEXES, OBJECTS, JAVA, INSTANCES, LOGS, NATIVES, SKINS):
        os.makedirs(d, exist_ok=True)


def instances_root():
    """Dossier d'installation des parties (instances), configurable par l'utilisateur."""
    from . import state  # import tardif pour éviter une dépendance circulaire
    s = (state.load()["settings"].get("install_dir") or "").strip()
    if s and os.path.isabs(s):
        return s
    return INSTANCES

