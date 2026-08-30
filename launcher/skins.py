"""Skins personnalisés pour comptes locaux (hors-ligne).

Minecraft vanilla n'affiche pas de skin custom pour un compte hors-ligne :
le joueur utilise alors la texture Steve/Alex par défaut. L'astuce, SANS
mod et SANS Fabric, est de fournir un resource pack qui remplace
``assets/minecraft/textures/entity/player/steve.png`` (et ``alex.png``)
par le skin de l'utilisateur. En solo, le joueur local utilise bien cette
texture de secours -> le skin apparaît en jeu.

Limites :
- Ne fonctionne que pour les comptes locaux (un compte Microsoft utilise
  son skin officiel, indépendant de ce resource pack).
- Dans un monde multijoueur, tous les joueurs qui tombent sur le skin
  par défaut (mode hors-ligne) verraient aussi ce skin — mais en solo
  seul le joueur local est concerné.
- Pour les versions très anciennes (pré-1.6, avant les resource packs),
  cette méthode ne s'applique pas.
"""
import json
import os
import re
import zipfile

from . import auth, paths

PACK_NAME = "RL_CustomSkin.zip"
PACK_FOLDER = "RL_CustomSkin"  # nom d'affichage interne


# ---------------------------------------------------------------------------
# pack_format selon la version Minecraft
# ---------------------------------------------------------------------------
# Un pack_format trop élevé pour une ancienne version = refus. Trop bas
# pour une version récente = simple avertissement, le pack marche quand
# même. On couvre les versions courantes ; défaut = 6 (compatible large).
_PACK_FORMAT_TABLE = [
    ("1.21.5", 55), ("1.21.4", 46), ("1.21.3", 42), ("1.21.2", 42),
    ("1.21.1", 34), ("1.21", 34),
    ("1.20.6", 32), ("1.20.5", 32), ("1.20.4", 22), ("1.20.3", 22),
    ("1.20.2", 18), ("1.20.1", 15), ("1.20", 15),
    ("1.19.4", 13), ("1.19.3", 12), ("1.19.2", 9), ("1.19.1", 9),
    ("1.19", 9),
    ("1.18.2", 8), ("1.18.1", 8), ("1.18", 8),
    ("1.17.1", 7), ("1.17", 7),
    ("1.16.5", 6), ("1.16.4", 6), ("1.16.3", 6), ("1.16.2", 6),
    ("1.16.1", 5), ("1.16", 5),
    ("1.15.2", 5), ("1.15.1", 5), ("1.15", 5),
    ("1.14.4", 4), ("1.14.3", 4), ("1.14.2", 4), ("1.14.1", 4),
    ("1.14", 4),
    ("1.13.2", 4), ("1.13.1", 4), ("1.13", 4),
    ("1.12.2", 3), ("1.12.1", 3), ("1.12", 3),
    ("1.11.2", 3), ("1.11.1", 3), ("1.11", 3),
    ("1.10.2", 2), ("1.10.1", 2), ("1.10", 2),
    ("1.9.4", 2), ("1.9.3", 2), ("1.9.2", 2), ("1.9.1", 2), ("1.9", 2),
    ("1.8.9", 1), ("1.8.8", 1), ("1.8", 1),
    ("1.7.10", 1), ("1.7", 1),
    ("1.6.4", 1), ("1.6", 1),
]


def _version_tuple(v):
    """Extrait un tuple (major, minor, patch) depuis une chaîne de version
    release (ex: '1.20.4' -> (1,20,4)). Pour les snapshots / anciens
    formats, retourne None."""
    m = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?$", v.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def pack_format_for(version_id):
    """Détermine le pack_format adapté à la version. Pour les snapshots ou
    versions inconnues, on renvoie 6 (compatible large, simple avertissement
    sur les versions récentes)."""
    vt = _version_tuple(version_id)
    if vt is None:
        return 6
    # Recherche la version la plus proche <= dans la table
    best = 6
    for prefix, fmt in _PACK_FORMAT_TABLE:
        pt = _version_tuple(prefix)
        if pt and vt >= pt:
            best = fmt
            break
    return best


# ---------------------------------------------------------------------------
# Découverte des skins par défaut depuis le client.jar
# ---------------------------------------------------------------------------
# Minecraft 1.19.3+ propose 9 skins par défaut (Steve, Alex, Ari, Efe,
# Kai, Makena, Noor, Sunny, Zuri) — et Mojang en ajoute régulièrement.
# Plutôt que de maintenir une liste figée, on découvre dynamiquement tous
# les PNG de joueur dans le client.jar de la version, et on les remplace
# tous par le skin de l'utilisateur.
_PLAYER_SKIN_RE = re.compile(r"^assets/minecraft/textures/entity/player/(?:slim/|wide/)?([a-z0-9_]+)\.png$")
# Anciennes versions (1.8-1.13) : les skins sont directement dans entity/
_LEGACY_SKIN_RE = re.compile(r"^assets/minecraft/textures/entity/(steve|alex)\.png$")


def _discover_default_skins(version_id):
    """Retourne la liste des chemins de textures de skins par défaut
    présents dans le client.jar de la version. Inclut aussi les chemins
    legacy (entity/steve.png, entity/alex.png) pour les anciennes versions.
    """
    paths_found = set()
    client_jar = os.path.join(paths.VERSIONS, version_id, "client.jar")
    if os.path.exists(client_jar):
        try:
            with zipfile.ZipFile(client_jar, "r") as z:
                for name in z.namelist():
                    if _PLAYER_SKIN_RE.match(name) or _LEGACY_SKIN_RE.match(name):
                        paths_found.add(name)
        except Exception:
            pass
    # Toujours inclure les chemins connus en fallback (même si le jar
    # n'est pas encore téléchargé ou a une structure inattendue).
    # Inclut a la fois l'ancien format (player/steve.png) et le nouveau
    # (player/slim/steve.png, player/wide/steve.png) pour Minecraft 26.x+.
    skin_names = ["steve", "alex", "ari", "efe", "kai", "makena", "noor", "sunny", "zuri"]
    fallback = set()
    for name in skin_names:
        fallback.add("assets/minecraft/textures/entity/player/%s.png" % name)
        fallback.add("assets/minecraft/textures/entity/player/slim/%s.png" % name)
        fallback.add("assets/minecraft/textures/entity/player/wide/%s.png" % name)
    fallback.add("assets/minecraft/textures/entity/steve.png")
    fallback.add("assets/minecraft/textures/entity/alex.png")
    return sorted(paths_found | fallback)


# ---------------------------------------------------------------------------
# Création du resource pack
# ---------------------------------------------------------------------------
def _write_pack_zip(zip_path, skin_bytes, version_id, skin_paths):
    """Crée le zip du resource pack. Remplace TOUS les skins par défaut
    (découverts depuis le client.jar + fallback) par le skin de l'utilisateur.
    Utilise `supported_formats` avec une large plage pour éviter que
    Minecraft ne supprime le pack car « incompatible » (pack_format trop
    ancien pour les versions récentes comme 26.x)."""
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    pack_meta = {
        "pack": {
            "pack_format": pack_format_for(version_id),
            # Large plage de formats supportés : accepte toutes les versions
            # de 1.6 (format 1) jusqu'à un futur lointain (format 9999).
            # Ce champ est ignoré par les versions < 1.20.5 qui ne le
            # connaissent pas, et il évite la suppression automatique du
            # pack par les versions récentes.
            "supported_formats": {"min_inclusive": 1, "max_inclusive": 9999},
            "description": "Redstone Launcher — skin personnalise (local)",
        }
    }
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pack.mcmeta", json.dumps(pack_meta, indent=2))
        for skin_path in skin_paths:
            z.writestr(skin_path, skin_bytes)


# ---------------------------------------------------------------------------
# options.txt : activer / désactiver le pack
# ---------------------------------------------------------------------------
def _read_options(game_dir):
    """Lit options.txt -> dict clé -> valeur brute (chaîne)."""
    path = os.path.join(game_dir, "options.txt")
    data = {}
    if not os.path.exists(path):
        return data, path
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if ":" in line:
                k, v = line.split(":", 1)
                data[k] = v
    return data, path


def _write_options(game_dir, data):
    """Écrit options.txt depuis un dict (ordre préservé pour les clés
    existantes, nouvelles clés ajoutées à la fin)."""
    path = os.path.join(game_dir, "options.txt")
    # On préserve l'ordre du fichier original si possible
    existing_order = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n").rstrip("\r")
                if ":" in line:
                    k = line.split(":", 1)[0]
                    if k not in existing_order:
                        existing_order.append(k)
    for k in data:
        if k not in existing_order:
            existing_order.append(k)
    with open(path, "w", encoding="utf-8", errors="replace") as f:
        for k in existing_order:
            if k in data:
                f.write("%s:%s\n" % (k, data[k]))


def _parse_pack_list(raw):
    """Parse la valeur brute de resourcePacks (JSON array) -> liste de
    noms. Tolérant : si ce n'est pas du JSON valide, retourne []."""
    if not raw:
        return []
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            return [str(x) for x in val]
    except Exception:
        pass
    return []


def _pack_in_list(pack_name, lst):
    """Vérifie si un pack est présent dans une liste, en gérant le préfixe
    'file/' que Minecraft ajoute aux packs basés sur des fichiers."""
    return pack_name in lst or ("file/" + pack_name) in lst


def _remove_pack_from_list(pack_name, lst):
    """Retire toutes les occurrences d'un pack d'une liste (avec et sans
    le préfixe 'file/'). Retourne une nouvelle liste."""
    return [x for x in lst if x != pack_name and x != "file/" + pack_name]


def enable_pack(game_dir):
    """Ajoute RL_CustomSkin.zip en tête de la liste resourcePacks de
    options.txt (priorité maximale : il écrase les autres packs qui
    toucheraient aussi steve.png). Nettoie aussi l'entrée
    incompatibleResourcePacks si elle contient encore notre pack (sinon
    Minecraft garde une trace de l'ancienne incompatibilité). Gère le
    préfixe 'file/' que Minecraft ajoute aux noms de packs, et élimine
    les doublons."""
    data, _ = _read_options(game_dir)
    packs = _parse_pack_list(data.get("resourcePacks", ""))
    # Retirer toutes les occurrences de notre pack (avec et sans 'file/'),
    # puis en remettre une seule en tête (évite les doublons).
    packs = _remove_pack_from_list(PACK_NAME, packs)
    packs.insert(0, PACK_NAME)
    data["resourcePacks"] = json.dumps(packs)
    # Retirer notre pack de la liste des incompatibles (si present)
    inc = _parse_pack_list(data.get("incompatibleResourcePacks", ""))
    if _pack_in_list(PACK_NAME, inc):
        inc = _remove_pack_from_list(PACK_NAME, inc)
        if inc:
            data["incompatibleResourcePacks"] = json.dumps(inc)
        else:
            data.pop("incompatibleResourcePacks", None)
    _write_options(game_dir, data)


def disable_pack(game_dir):
    """Retire RL_CustomSkin.zip de la liste resourcePacks ET de
    incompatibleResourcePacks (sans toucher aux autres packs de
    l'utilisateur). Gère le préfixe 'file/'."""
    data, path = _read_options(game_dir)
    changed = False

    # Retirer de resourcePacks
    packs = _parse_pack_list(data.get("resourcePacks", ""))
    if _pack_in_list(PACK_NAME, packs):
        packs = _remove_pack_from_list(PACK_NAME, packs)
        data["resourcePacks"] = json.dumps(packs)
        changed = True

    # Retirer aussi de incompatibleResourcePacks (si present)
    inc = _parse_pack_list(data.get("incompatibleResourcePacks", ""))
    if _pack_in_list(PACK_NAME, inc):
        inc = _remove_pack_from_list(PACK_NAME, inc)
        if inc:
            data["incompatibleResourcePacks"] = json.dumps(inc)
        else:
            data.pop("incompatibleResourcePacks", None)
        changed = True

    if changed:
        _write_options(game_dir, data)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------
def _pack_is_valid(zip_path):
    """Vérifie qu'un pack existe, est un zip valide, contient un
    pack.mcmeta avec supported_formats, et au moins un skin PNG."""
    if not os.path.exists(zip_path):
        return False
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            if "pack.mcmeta" not in names:
                return False
            mcmeta = json.loads(z.read("pack.mcmeta"))
            if "supported_formats" not in mcmeta.get("pack", {}):
                return False
            has_skin = any(n.endswith(".png") and "player" in n for n in names)
            if not has_skin:
                return False
        return True
    except Exception:
        return False


def _pack_marked_incompatible(game_dir):
    """Retourne True si notre pack est present dans incompatibleResourcePacks
    de options.txt (ce qui signifie que Minecraft l'a juge incompatible)."""
    data, _ = _read_options(game_dir)
    inc = _parse_pack_list(data.get("incompatibleResourcePacks", ""))
    return _pack_in_list(PACK_NAME, inc)


def apply_skin_for_launch(game_dir, account, version_id):
    """Applique le skin personnalise pour ce lancement.

    Comportement :
    - Compte Microsoft ou compte local sans skin -> desactive le pack.
    - Compte local avec skin -> SUPPRIME l'ancien pack (s'il existe), en
      cree un nouveau de zero, verifie qu'il est valide, et l'active dans
      options.txt. Si le pack etait marque incompatible par Minecraft, il
      est forcement recree. Une retentative est effectuee si le premier
      pack est invalide.

    Retourne True si un skin a ete applique, False sinon.
    """
    if not account or account.get("type") != "offline":
        disable_pack(game_dir)
        return False

    account_id = account.get("id")
    if not account_id or not auth.has_skin(account_id):
        disable_pack(game_dir)
        return False

    # Lire le skin
    try:
        skin_path = auth.skin_path(account_id)
        with open(skin_path, "rb") as f:
            skin_bytes = f.read()
        if len(skin_bytes) < 100:
            disable_pack(game_dir)
            return False
    except Exception:
        disable_pack(game_dir)
        return False

    zip_path = os.path.join(game_dir, "resourcepacks", PACK_NAME)
    skin_paths = _discover_default_skins(version_id)

    # Force la recreation : supprimer l'ancien pack (surtout s'il etait
    # marque incompatible ou corrompu), puis en creer un nouveau.
    need_recreate = True
    if _pack_is_valid(zip_path) and not _pack_marked_incompatible(game_dir):
        # Pack valide et non marque incompatible : on pourrait sauter la
        # recreation, mais par securite on force quand meme (le skin a
        # peut-etre change). On garde donc need_recreate = True.
        pass

    for attempt in range(2):  # 1 essai + 1 retentative
        try:
            # Supprimer l'ancien pack pour partir de zero
            if os.path.exists(zip_path):
                os.remove(zip_path)
            _write_pack_zip(zip_path, skin_bytes, version_id, skin_paths)
            if _pack_is_valid(zip_path):
                enable_pack(game_dir)
                return True
            # Pack invalide : on reessaie une fois
        except Exception:
            # Erreur a la creation : on reessaie une fois
            pass

    # Les deux essais ont echoue : desactiver le pack pour ne pas bloquer
    # le lancement avec un fichier corrompu.
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    except Exception:
        pass
    disable_pack(game_dir)
    return False


def skin_pack_path(game_dir):
    """Retourne le chemin du zip du resource pack de skin (pour info)."""
    return os.path.join(game_dir, "resourcepacks", PACK_NAME)


# ---------------------------------------------------------------------------
# Methode principale : patcher directement le client.jar
# ---------------------------------------------------------------------------
# Le resource pack est systematiquement rejete par les versions recentes
# de Minecraft (26.x) pour "incompatibilite", meme avec supported_formats.
# On patch donc directement le client.jar : on remplace les PNG de skins
# par defaut DANS le jar, ce qui ne depend pas du tout du systeme de
# resource packs. Le jeu charge alors directement les textures modifiees.
PATCHED_JAR_NAME = "client_skinned.jar"


def get_patched_client_jar(version_id, account):
    """Retourne le chemin vers un client.jar patché avec le skin du compte.

    - Si le compte n'est pas local ou n'a pas de skin -> retourne None.
    - Si le client.jar original n'existe pas -> retourne None.
    - Si un jar patché existe deja et est a jour (plus recent que le jar
      original et le fichier de skin) -> le réutilise.
    - Sinon, crée un nouveau jar patché en copiant le jar original et en
      remplaçant tous les PNG de skins par defaut par le skin de l'utilisateur.

    Le jar patché est utilisé dans le classpath a la place du client.jar
    original. Le jeu charge alors directement les textures modifiées, sans
    passer par le systeme de resource packs (qui rejette le pack sur les
    versions recentes).
    """
    if not account or account.get("type") != "offline":
        return None

    account_id = account.get("id")
    if not account_id or not auth.has_skin(account_id):
        return None

    original_jar = os.path.join(paths.VERSIONS, version_id, "client.jar")
    patched_jar = os.path.join(paths.VERSIONS, version_id, PATCHED_JAR_NAME)

    if not os.path.exists(original_jar):
        return None

    # Lire le skin
    try:
        skin_file = auth.skin_path(account_id)
        with open(skin_file, "rb") as f:
            skin_bytes = f.read()
        if len(skin_bytes) < 100:
            return None
    except Exception:
        return None

    # Decouvrir tous les chemins de skins par defaut depuis le jar original
    skin_paths = _discover_default_skins(version_id)

    # Verifier si le jar patché est deja a jour
    if os.path.exists(patched_jar):
        try:
            orig_mtime = os.path.getmtime(original_jar)
            skin_mtime = os.path.getmtime(skin_file)
            patched_mtime = os.path.getmtime(patched_jar)
            if patched_mtime > orig_mtime and patched_mtime > skin_mtime:
                # Verifier rapidement que le jar patché contient bien le skin
                # sur au moins un des chemins decouverts.
                with zipfile.ZipFile(patched_jar, "r") as z:
                    names = set(z.namelist())
                    for test_path in skin_paths:
                        if test_path in names:
                            if z.read(test_path) == skin_bytes:
                                return patched_jar
                            break  # Le premier chemin trouve ne match pas -> recreer
        except Exception:
            pass  # En cas d'erreur, on recrée le jar

    # Creer le jar patché : copier toutes les entrées du jar original,
    # mais remplacer les PNG de skins par le skin de l'utilisateur.
    try:
        with zipfile.ZipFile(original_jar, "r") as zin:
            with zipfile.ZipFile(patched_jar, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename in skin_paths:
                        zout.writestr(item, skin_bytes)
                    else:
                        zout.writestr(item, zin.read(item.filename))
        return patched_jar
    except Exception:
        # En cas d'erreur, supprimer le jar patché partiel et retourner None
        try:
            if os.path.exists(patched_jar):
                os.remove(patched_jar)
        except Exception:
            pass
        return None
