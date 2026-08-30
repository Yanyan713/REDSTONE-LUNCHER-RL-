"""Détection et installation de Java (via Adoptium/Eclipse Temurin)."""
import os
import re
import shutil
import subprocess
import zipfile

from . import paths, state
from .download import download_any, http_get_json

_jvm_arch = None

# Miroirs pour télécharger Temurin (GitHub est souvent lent/instable hors proxy).
# %d = version majeure, %s = nom du fichier (ex: OpenJDK8U-jdk_x64_windows_hotspot_8u504b01.zip)
JAVA_MIRRORS = [
    "https://mirror.sjtu.edu.cn/github-release/adoptium/temurin%d-binaries/LatestRelease/%s",
    "https://mirrors.tuna.tsinghua.edu.cn/Adoptium/%d/jdk/x64/windows/%s",
    "https://mirrors.ustc.edu.cn/adoptium/releases/%d/jdk/x64/windows/normal/eclipse/%s",
]


def _parse_java_version(text):
    m = re.search(r'version "([^"]+)"', text or "")
    if not m:
        return None
    v = m.group(1)
    if v.startswith("1."):  # ex: 1.8.0_404
        try:
            return int(v.split(".")[1])
        except Exception:
            return None
    try:
        return int(v.split(".")[0])
    except Exception:
        return None


def _java_major(java_exe):
    try:
        out = subprocess.run([java_exe, "-version"], capture_output=True, text=True, timeout=20)
        return _parse_java_version(out.stdout + out.stderr)
    except Exception:
        return None


def system_java_major():
    return _java_major("java")


def _find_in(dirpath, min_major):
    """Cherche un java.exe >= min_major sous dirpath (2 niveaux max)."""
    if not os.path.isdir(dirpath):
        return None
    for root, dirs, files in os.walk(dirpath):
        depth = root[len(dirpath):].count(os.sep)
        if depth > 2:
            dirs[:] = []
            continue
        if "java.exe" in files and os.path.basename(root) == "bin":
            java = os.path.join(root, "java.exe")
            maj = _java_major(java)
            if maj is not None and maj >= min_major:
                return {"path": java, "major": maj}
    return None


_STANDARD_ROOTS = [
    r"C:\Program Files\Java",
    r"C:\Program Files\Eclipse Adoptium",
    r"C:\Program Files\Microsoft",
    r"C:\Program Files\Zulu",
    r"C:\Program Files (x86)\Java",
    r"C:\Program Files\Temurin",
]


def _collect_candidates():
    """Liste (major, chemin) de tous les Java détectés (embarqués, système, dossiers classiques)."""
    cands = []

    st = state.load()
    override = (st["settings"].get("java_override") or "").strip()
    if override:
        if override.lower().endswith(".exe") and os.path.isfile(override):
            maj = _java_major(override)
            if maj is not None:
                cands.append((maj, override))
        else:
            p = _find_in(override, 1)
            if p:
                cands.append((p["major"], p["path"]))

    # JRE embarquées (data/java)
    if os.path.isdir(paths.JAVA):
        for name in sorted(os.listdir(paths.JAVA)):
            full = os.path.join(paths.JAVA, name)
            if os.path.isdir(full):
                p = _find_in(full, 1)
                if p:
                    cands.append((p["major"], p["path"]))

    # Java système (sur le PATH)
    sm = system_java_major()
    if sm is not None:
        cands.append((sm, "java"))

    # Dossiers d'installation classiques
    for root in _STANDARD_ROOTS:
        if not os.path.isdir(root):
            continue
        try:
            names = os.listdir(root)
        except Exception:
            continue
        for name in names:
            full = os.path.join(root, name)
            if os.path.isdir(full):
                p = _find_in(full, 1)
                if p:
                    cands.append((p["major"], p["path"]))

    # dédoublonnage (même chemin)
    seen, out = set(), []
    for maj, path in cands:
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((maj, path))
    return out


def find_java(min_major):
    """Retourne le java.exe adapté à la version requise.

    Règle : les versions <= 1.12 (Java 8) plantent sur Java 9+ -> on n'accepte
    QUE Java 8 pour elles (sinon le lanceur télécharge Java 8 automatiquement).
    Pour les versions modernes (16+), on prend la version la plus proche >= requise.
    """
    best = None  # (major, path)
    for maj, path in _collect_candidates():
        if min_major <= 8:
            ok = (maj == 8)  # anciennes versions : uniquement Java 8
        else:
            ok = maj >= min_major
        if not ok:
            continue
        if best is None or abs(maj - min_major) < abs(best[0] - min_major):
            best = (maj, path)
    return best[1] if best else None


def bundled_javas():
    """Liste des JRE téléchargées par le lanceur."""
    out = []
    if os.path.isdir(paths.JAVA):
        for name in sorted(os.listdir(paths.JAVA)):
            full = os.path.join(paths.JAVA, name)
            if os.path.isdir(full):
                p = _find_in(full, 8)
                if p:
                    out.append({"name": name, "major": p["major"], "path": p["path"]})
    return out


def install_java(major, progress=None):
    """Télécharge et installe une JDK Temurin de la version majeure donnée."""
    target = os.path.join(paths.JAVA, "jdk-%d" % major)
    p = _find_in(target, major)
    if p:
        return p["path"]

    url = ("https://api.adoptium.net/v3/assets/latest/%d/hotspot"
           "?os=windows&architecture=x64&image_type=jdk" % major)
    assets = http_get_json(url)
    if not assets:
        raise RuntimeError("Aucune version Java %d disponible chez Adoptium." % major)
    pkg = assets[0]["binary"]["package"]
    dl = pkg["link"]
    name = pkg["name"]
    checksum = pkg.get("checksum")  # SHA256
    pkg_size = pkg.get("size")

    def cb(done, total):
        if progress:
            progress("Téléchargement de Java %d…" % major, done, total)

    # URLs candidates : GitHub officiel + miroirs chinois
    urls = [dl] + [t % (major, name) for t in JAVA_MIRRORS]
    tmp_zip = os.path.join(paths.JAVA, name)
    download_any(urls, tmp_zip, sha256=checksum, size=pkg_size, progress=cb)

    extract_to = os.path.join(paths.JAVA, ".extract")
    if os.path.exists(extract_to):
        shutil.rmtree(extract_to, ignore_errors=True)
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(tmp_zip) as z:
        z.extractall(extract_to)
    os.remove(tmp_zip)

    inner = None
    for entry in os.listdir(extract_to):
        full = os.path.join(extract_to, entry)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "bin", "java.exe")):
            inner = full
            break
    if inner is None:
        shutil.rmtree(extract_to, ignore_errors=True)
        raise RuntimeError("Extraction de Java échouée.")

    if os.path.exists(target):
        shutil.rmtree(target, ignore_errors=True)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(inner, target)
    shutil.rmtree(extract_to, ignore_errors=True)

    final = _find_in(target, major)
    return final["path"] if final else os.path.join(target, "bin", "java.exe")


def status():
    return {
        "system_major": system_java_major(),
        "bundled": bundled_javas(),
        "auto_install": state.load()["settings"].get("auto_install_java", True),
    }
