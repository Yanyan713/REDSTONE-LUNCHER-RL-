"""Comptes : compte local (hors-ligne, usage éducatif) et compte Microsoft (device code)."""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import uuid

from . import download, paths

# L'ancien ID « 00000000402b5328 » (forme v1 compressée) a été révoqué par
# Microsoft : les endpoints /consumers/oauth2/v2.0/* le rejettent avec
# « unauthorized_client / AADSTS700016 ». On utilise désormais un ID client
# v2 (forme UUID) encore actif sur le tenant « consumers » — celui de
# Prism Launcher, qui passe le device code flow (vérifié 2026-08).
CLIENT_ID = "c36a9fb6-4f2a-41ff-90bd-ae7cc92031eb"
TENANT = "consumers"

DEVICE_CODE_URL = "https://login.microsoftonline.com/%s/oauth2/v2.0/devicecode" % TENANT
TOKEN_URL = "https://login.microsoftonline.com/%s/oauth2/v2.0/token" % TENANT
XBL_URL = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
MC_LOGIN_URL = "https://api.minecraftservices.com/authentication/login_with_xbox"
MC_PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"

_pending = {}
_pending_lock = threading.Lock()


def _post_form(url, data):
    body = urllib.parse.urlencode(data).encode()
    try:
        with download.urlopen(url, data=body,
                              headers={"Content-Type": "application/x-www-form-urlencoded"}) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except Exception:
            raise RuntimeError("Erreur HTTP %d auprès de Microsoft" % e.code)


def _post_json(url, payload):
    body = json.dumps(payload).encode()
    try:
        with download.urlopen(url, data=body,
                              headers={"Content-Type": "application/json",
                                       "Accept": "application/json"}) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except Exception:
            raise RuntimeError("Erreur HTTP %d auprès de l'API" % e.code)


def _get_json(url, headers=None):
    with download.urlopen(url, headers=headers) as r:
        return json.load(r)


# --------------------------------------------------------------------------
# Compte local (hors-ligne) - pour une utilisation éducative / sans connexion
# --------------------------------------------------------------------------
# Minecraft n'accepte que lettres, chiffres et « _ » dans un pseudo (pas d'espace).
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")


def normalize_username(username):
    """Nettoie un pseudo : lettres/chiffres/« _ » uniquement, sans espace, max 16. """
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", (username or "").strip())
    return cleaned[:16]


def create_offline(username):
    name = (username or "").strip()
    if not name:
        raise ValueError("Le nom d'utilisateur est vide.")
    if not _USERNAME_RE.match(name):
        raise ValueError("Pseudo invalide : uniquement des lettres, des chiffres et "
                         "« _ » (pas d'espace, 1 à 16 caractères). Exemple : joueur_1")
    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, "offline:" + name))
    return {
        "id": "offline-" + uid[:8],
        "type": "offline",
        "username": name,
        "uuid": uid,
        "access_token": "0" * 32,
        "label": name + " (local)",
    }


def sanitize_stored_accounts(accounts):
    """Corrige les pseudos existants invalides (ex : espaces) pour éviter
    « Invalid characters in username » dans le jeu."""
    changed = False
    for acc in accounts:
        if acc.get("type") == "offline":
            n = normalize_username(acc.get("username", ""))
            if n and n != acc.get("username"):
                acc["username"] = n
                acc["label"] = n + " (local)"
                changed = True
    return changed


# --------------------------------------------------------------------------
# Skins (image locale attachée à un compte)
# --------------------------------------------------------------------------
def skin_path(account_id):
    return os.path.join(paths.SKINS, account_id + ".png")


def has_skin(account_id):
    return os.path.isfile(skin_path(account_id))


def save_skin(account_id, data):
    """Enregistre le skin PNG d'un compte (64x64 ou 128x128, format Minecraft)."""
    if not data[:8] == b"\x89PNG\r\n\x1a\n":
        raise ValueError("Le fichier doit être une image PNG (skin Minecraft).")
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Image trop lourde (max 10 Mo).")
    os.makedirs(paths.SKINS, exist_ok=True)
    with open(skin_path(account_id), "wb") as f:
        f.write(data)
    return True


def remove_skin(account_id):
    p = skin_path(account_id)
    if os.path.exists(p):
        try:
            os.remove(p)
            return True
        except OSError:
            return False
    return False


# --------------------------------------------------------------------------
# Compte Microsoft (device code flow)
# --------------------------------------------------------------------------
def start_microsoft():
    """Demande un device code à Microsoft (le user doit le saisir sur le site)."""
    resp = _post_form(DEVICE_CODE_URL, {
        "client_id": CLIENT_ID,
        "scope": "XboxLive.signin offline_access",
    })
    if "error" in resp:
        raise RuntimeError(resp.get("error_description") or resp.get("error"))
    info = {
        "device_code": resp["device_code"],
        "user_code": resp["user_code"],
        "verification_uri": resp.get("verification_uri", "https://microsoft.com/link"),
        "expires_in": int(resp.get("expires_in", 900)),
        "interval": int(resp.get("interval", 5)),
        "created": time.time(),
    }
    with _pending_lock:
        _pending["device_code"] = info
    return info


def microsoft_status():
    """Interroge Microsoft tant que l'utilisateur n'a pas validé le code."""
    with _pending_lock:
        info = _pending.get("device_code")
    if not info:
        return {"status": "idle"}
    if time.time() - info["created"] > info["expires_in"]:
        with _pending_lock:
            _pending.pop("device_code", None)
        return {"status": "expired"}

    resp = _post_form(TOKEN_URL, {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": CLIENT_ID,
        "device_code": info["device_code"],
    })
    err = resp.get("error")
    if err == "authorization_pending":
        return {"status": "pending",
                "user_code": info["user_code"],
                "verification_uri": info["verification_uri"]}
    if err:
        with _pending_lock:
            _pending.pop("device_code", None)
        return {"status": "error", "message": resp.get("error_description") or err}
    with _pending_lock:
        _pending.pop("device_code", None)
    account = _exchange_tokens(resp)
    return {"status": "ok", "account": account}


def _exchange_tokens(ms):
    """Token Microsoft -> XBL -> XSTS -> token Minecraft -> profil."""
    access_token = ms["access_token"]
    refresh_token = ms.get("refresh_token")

    # 1) Xbox Live
    xbl = _post_json(XBL_URL, {
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": "d=" + access_token,
        },
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT",
    })
    xbl_token = xbl["Token"]
    uhs = xbl["DisplayClaims"]["xui"][0]["uhs"]

    # 2) XSTS
    xsts = _post_json(XSTS_URL, {
        "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
        "RelyingParty": "rp://api.minecraftservices.com/",
        "TokenType": "JWT",
    })
    if "XErr" in xsts:
        raise RuntimeError("Compte Xbox non valide (XErr=%s). Vérifie que le compte "
                           "Microsoft possède un profil Xbox." % xsts["XErr"])
    xsts_token = xsts["Token"]

    # 3) Connexion Minecraft
    mc = _post_json(MC_LOGIN_URL, {
        "identityToken": "XBL3.0 x=%s;%s" % (uhs, xsts_token),
    })
    if "access_token" not in mc:
        raise RuntimeError("Le compte Microsoft n'a pas accès à Minecraft "
                           "(jeu non acheté sur ce compte ?).")
    mc_token = mc["access_token"]

    # 4) Profil Minecraft
    try:
        profile = _get_json(MC_PROFILE_URL, {"Authorization": "Bearer " + mc_token})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError("Ce compte n'a pas de profil Minecraft.")
        raise

    return {
        "id": "ms-" + profile["id"][:8],
        "type": "microsoft",
        "username": profile["name"],
        "uuid": profile["id"],
        "access_token": mc_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + int(mc.get("expires_in", 86400)),
        "label": profile["name"] + " (Microsoft)",
    }


def refresh_microsoft(account):
    """Rafraîchit le token d'un compte Microsoft (reconnexion automatique)."""
    if account.get("type") != "microsoft" or not account.get("refresh_token"):
        return account
    resp = _post_form(TOKEN_URL, {
        "client_id": CLIENT_ID,
        "scope": "XboxLive.signin offline_access",
        "refresh_token": account["refresh_token"],
        "grant_type": "refresh_token",
    })
    if "error" in resp:
        raise RuntimeError("Connexion Microsoft expirée, reconnecte le compte.")
    new_ms = {
        "access_token": resp["access_token"],
        "refresh_token": resp.get("refresh_token", account["refresh_token"]),
    }
    refreshed = _exchange_tokens(new_ms)
    return refreshed


def ensure_valid(account):
    """Retourne un compte utilisable (Microsoft rafraîchi si nécessaire)."""
    if account.get("type") == "microsoft":
        if account.get("expires_at", 0) - time.time() < 120:
            return refresh_microsoft(account)
    return account
