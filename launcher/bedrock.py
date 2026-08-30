"""Gestion de Minecraft Bedrock Edition (Windows 10/11 via Microsoft Store).

Contrairement a Java, Mojang ne propose pas de telechargement officiel des
anciennes versions Bedrock. Le jeu est distribue via le Microsoft Store et
se met a jour automatiquement. Ce module permet de :
- Detecter si Minecraft Bedrock est installe.
- Connaitre la version installee.
- Lancer le jeu.
- Gerer les resource packs (.mcpack).
"""
import os
import shutil
import subprocess

# Identifiant du package Minecraft Bedrock sur le Microsoft Store
BEDROCK_PACKAGE_NAME = "Microsoft.MinecraftUWP"
BEDROCK_PACKAGE_FAMILY = "Microsoft.MinecraftUWP_8wekyb3d8bbwe"
# L'ID d'application de Minecraft Bedrock est "Game" (pas "App" comme la plupart des UWP).
# L'executable est GameLaunchHelper.exe en mode "full trust".
BEDROCK_APP_ID = "Game"

# Dossier des resource packs Bedrock
def bedrock_data_dir():
    """Dossier de donnees de Minecraft Bedrock."""
    local = os.environ.get("LOCALAPPDATA", "")
    return os.path.join(local, "Packages", BEDROCK_PACKAGE_FAMILY,
                         "LocalState", "games", "com.mojang")


def resource_packs_dir():
    """Dossier des resource packs Bedrock."""
    return os.path.join(bedrock_data_dir(), "resource_packs")


def behavior_packs_dir():
    """Dossier des behavior packs Bedrock."""
    return os.path.join(bedrock_data_dir(), "behavior_packs")


def is_installed():
    """Verifie si Minecraft Bedrock est installe via le Microsoft Store."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-AppxPackage -Name %s | Select-Object -First 1 | "
             "ForEach-Object { $_.Version }" % BEDROCK_PACKAGE_NAME],
            capture_output=True, text=True, timeout=15
        )
        version = result.stdout.strip()
        return bool(version)
    except Exception:
        return False


def get_version():
    """Retourne la version installee de Minecraft Bedrock, ou None."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-AppxPackage -Name %s | Select-Object -First 1 | "
             "ForEach-Object { $_.Version }" % BEDROCK_PACKAGE_NAME],
            capture_output=True, text=True, timeout=15
        )
        version = result.stdout.strip()
        return version if version else None
    except Exception:
        return None


def get_install_location():
    """Retourne le chemin d'installation de Minecraft Bedrock, ou None."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-AppxPackage -Name %s | Select-Object -First 1 | "
             "ForEach-Object { $_.InstallLocation }" % BEDROCK_PACKAGE_NAME],
            capture_output=True, text=True, timeout=15
        )
        loc = result.stdout.strip()
        return loc if loc else None
    except Exception:
        return None


def launch():
    """Lance Minecraft Bedrock. Retourne True si le lancement a ete initie."""
    if not is_installed():
        raise RuntimeError(
            "Minecraft Bedrock n'est pas installe. Installe-le depuis le Microsoft Store : "
            "https://www.microsoft.com/store/productId/9NBLGGH2JHXJ")
    try:
        # Utiliser cmd /c start avec shell:appsFolder est la methode la plus fiable
        # pour lancer une application UWP "full trust" depuis Python.
        # L'ID d'application est "Game" (pas "App").
        shell_path = "shell:appsFolder\\%s!%s" % (BEDROCK_PACKAGE_FAMILY, BEDROCK_APP_ID)
        subprocess.Popen(
            ["cmd", "/c", "start", "", shell_path],
            shell=True
        )
        return True
    except Exception as e:
        raise RuntimeError("Impossible de lancer Minecraft Bedrock : %s" % e)


def open_store_page():
    """Ouvre la page Microsoft Store de Minecraft Bedrock."""
    try:
        subprocess.Popen(
            ["explorer.exe", "ms-windows-store://pdp/?ProductId=9NBLGGH2JHXJ"],
            shell=False
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Resource packs
# ---------------------------------------------------------------------------
def list_resource_packs():
    """Liste les resource packs installes dans le dossier Bedrock."""
    d = resource_packs_dir()
    out = []
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        full = os.path.join(d, name)
        if os.path.isdir(full):
            # Lire le manifest.json pour avoir le nom et la version
            manifest = os.path.join(full, "manifest.json")
            pack_name = name
            pack_version = ""
            pack_desc = ""
            if os.path.isfile(manifest):
                try:
                    import json
                    with open(manifest, "r", encoding="utf-8") as f:
                        m = json.load(f)
                    header = m.get("header", {})
                    pack_name = header.get("name", name)
                    ver = header.get("version", [])
                    pack_version = ".".join(str(v) for v in ver) if isinstance(ver, list) else str(ver)
                    pack_desc = header.get("description", "")
                except Exception:
                    pass
            out.append({
                "folder": name,
                "name": pack_name,
                "version": pack_version,
                "description": pack_desc,
                "path": full,
            })
    return out


def install_resource_pack(filepath, filename=None):
    """Installe un resource pack Bedrock (.mcpack ou .zip).

    Un .mcpack est simplement un zip contenant un manifest.json a la racine
    (ou dans un sous-dossier). On l'extrait dans le dossier resource_packs.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError("Fichier introuvable : %s" % filepath)

    d = resource_packs_dir()
    os.makedirs(d, exist_ok=True)

    base = filename or os.path.basename(filepath)
    # Enlever l'extension
    pack_name = base
    for ext in (".mcpack", ".zip"):
        if pack_name.lower().endswith(ext):
            pack_name = pack_name[:-len(ext)]
            break

    dest = os.path.join(d, pack_name)

    # Si le dossier existe deja, le supprimer d'abord
    if os.path.exists(dest):
        shutil.rmtree(dest, ignore_errors=True)

    import zipfile
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            # Verifier si le manifest est a la racine ou dans un sous-dossier
            names = z.namelist()
            has_root_manifest = any(n == "manifest.json" or n.endswith("/manifest.json")
                                    for n in names)

            if has_root_manifest and not any(n == "manifest.json" for n in names):
                # Le manifest est dans un sous-dossier -> extraire dans un dossier
                # Trouver le dossier racine
                root_dirs = set(n.split("/")[0] for n in names if "/" in n)
                if len(root_dirs) == 1:
                    # Extraire tout, puis renommer le sous-dossier
                    temp_dest = dest + "_temp"
                    if os.path.exists(temp_dest):
                        shutil.rmtree(temp_dest, ignore_errors=True)
                    z.extractall(temp_dest)
                    sub = os.path.join(temp_dest, list(root_dirs)[0])
                    if os.path.isdir(sub):
                        shutil.move(sub, dest)
                    shutil.rmtree(temp_dest, ignore_errors=True)
                else:
                    z.extractall(dest)
            else:
                # Manifest a la racine -> extraire directement
                z.extractall(dest)
    except zipfile.BadZipFile:
        raise RuntimeError("Le fichier n'est pas un .mcpack/.zip valide.")

    return {"folder": pack_name, "path": dest}


def delete_resource_pack(folder_name):
    """Supprime un resource pack par son nom de dossier."""
    d = resource_packs_dir()
    target = os.path.join(d, os.path.basename(folder_name))
    if os.path.isdir(target):
        shutil.rmtree(target, ignore_errors=True)
        return True
    return False


def open_resource_packs_folder():
    """Ouvre le dossier des resource packs dans l'explorateur."""
    d = resource_packs_dir()
    os.makedirs(d, exist_ok=True)
    try:
        subprocess.Popen(["explorer.exe", d])
        return True
    except Exception:
        return False


def status():
    """Retourne l'etat complet de Minecraft Bedrock."""
    installed = is_installed()
    return {
        "installed": installed,
        "version": get_version() if installed else None,
        "install_location": get_install_location() if installed else None,
        "resource_packs": list_resource_packs() if installed else [],
        "resource_packs_dir": resource_packs_dir(),
        "store_url": "https://www.microsoft.com/store/productId/9NBLGGH2JHXJ",
    }
