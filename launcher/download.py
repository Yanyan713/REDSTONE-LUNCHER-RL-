"""Téléchargements : proxy local, miroirs multiples, progression fiable jusqu'à 100 %.

Corrections apportées :
- La boucle de lecture s'arrête dès que la taille annoncée (Content-Length) est atteinte,
  et la progression est forcée à 100 % en fin de fichier -> plus de blocage à 99,9 %.
- Miroirs de secours (BMCLAPI) si la source officielle Mojang est lente/injoignable.
- Proxy local configurable (réglage « proxy ») appliqué à tous les téléchargements.
"""
import glob
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request

USER_AGENT = "RedstoneLauncher/1.0"

# Miroirs officiels communautaires (BMCLAPI, très utilisé en Chine / asie)
MIRROR_MAP = [
    ("https://libraries.minecraft.net/", "https://bmclapi2.bangbang93.com/libraries/"),
    ("https://resources.download.minecraft.net/", "https://bmclapi2.bangbang93.com/assets/"),
    ("https://piston-data.mojang.com/", "https://bmclapi2.bangbang93.com/"),
    ("https://piston-meta.mojang.com/", "https://bmclapi2.bangbang93.com/"),
    ("https://launchermeta.mojang.com/", "https://bmclapi2.bangbang93.com/"),
    ("https://launcher.mojang.com/", "https://bmclapi2.bangbang93.com/"),
]

# Si aucun octet n'est reçu pendant cette durée, on considère la source bloquée
# et on bascule sur le miroir (évite les téléchargements figés à l'infini).
STALL_TIMEOUT = 12  # secondes


class Job:
    """État global d'un lancement : progression partagée avec l'interface web."""

    def __init__(self):
        self._lock = threading.Lock()
        self._d = {
            "active": False,
            "status": "idle",      # idle | working | running | done | error
            "stage": "",
            "message": "",
            "current": 0,
            "total": 0,
            "percent": 0.0,
            "pid": None,
            "error": None,
            "log_file": None,
        }

    def set(self, **kw):
        with self._lock:
            self._d.update(kw)
            if "current" in kw or "total" in kw:
                total = self._d.get("total") or 0
                cur = self._d.get("current") or 0
                if cur >= total and total:
                    self._d["percent"] = 100.0
                else:
                    self._d["percent"] = round(cur / total * 100, 1) if total else 0.0

    def snapshot(self):
        with self._lock:
            return dict(self._d)

    def begin(self, stage, message=""):
        self.set(active=True, status="working", stage=stage, message=message,
                 current=0, total=0, percent=0.0, pid=None, error=None)

    def stage(self, stage, message=""):
        self.set(stage=stage, message=message, current=0, total=0, percent=0.0)

    def running(self, pid, message):
        self.set(active=True, status="running", pid=pid, message=message)

    def done(self, message):
        self.set(active=False, status="done", message=message, pid=None)

    def fail(self, msg):
        self.set(active=False, status="error", error=msg, message=msg, pid=None)


JOB = Job()


def _settings():
    from . import state  # import tardif (évite la dépendance circulaire)
    return state.load()["settings"]


def proxy_setting():
    p = (_settings().get("proxy") or "").strip()
    return p or None


def mirror_mode():
    return _settings().get("dl_mirror", "auto")  # "off" | "auto" | "bmclapi"


def _build_opener():
    p = proxy_setting()
    if p:
        return urllib.request.build_opener(urllib.request.ProxyHandler({"http": p, "https": p}))
    # par défaut : proxy système (variables d'environnement / registre Windows)
    return urllib.request.build_opener()


_opener_cache = {}


def opener():
    key = proxy_setting() or "system"
    if key not in _opener_cache:
        _opener_cache[key] = _build_opener()
    return _opener_cache[key]


def urlopen(url, data=None, headers=None, timeout=45):
    """Requête HTTP/HTTPS à travers le proxy configuré (ou système)."""
    req = urllib.request.Request(url, data=data,
                                 headers={"User-Agent": USER_AGENT, **(headers or {})})
    return opener().open(req, timeout=timeout)


def http_get_json(url, headers=None):
    """GET JSON avec repli sur les miroirs si la source officielle échoue."""
    last = None
    for cand in _url_candidates(url):
        try:
            with urlopen(cand, headers=headers) as r:
                return json.load(r)
        except Exception as e:
            last = e
    raise last


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _url_candidates(url):
    """[source officielle] + [miroir(s)] selon le réglage dl_mirror."""
    mode = mirror_mode()
    if mode == "off":
        return [url]
    mirror = None
    for orig, m in MIRROR_MAP:
        if url.startswith(orig):
            mirror = m + url[len(orig):]
            break
    if mirror is None:
        return [url]
    if mode == "bmclapi":
        return [mirror, url]   # miroir en premier
    return [url, mirror]       # auto : officiel puis miroir


def _download_to(url, dest, size, progress, headers):
    """Télécharge `url` vers `dest` en s'arrêtant pile à la taille annoncée.

    Le timeout de lecture (STALL_TIMEOUT) coupe une source qui n'envoie plus
    d'octets : download_file bascule alors sur le miroir.
    """
    with urlopen(url, headers=headers, timeout=STALL_TIMEOUT) as r:
        total = int(r.headers.get("Content-Length") or 0)
        if size and not total:
            total = size
        done = 0
        with open(dest, "wb") as f:
            while True:
                if total and done >= total:
                    break
                want = (1 << 16) if not total else min(1 << 16, total - done)
                chunk = r.read(want)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
            # dernière mise à jour : on force 100 %
            if progress and total:
                progress(total, total)


def download_file(url, dest, sha1=None, sha256=None, size=None, progress=None, headers=None):
    """Télécharge `url` vers `dest` (vérification sha1/sha256/taille, miroirs, reprise).

    Retourne False si le fichier existait déjà et est valide, True sinon.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        ok_size = size is None or os.path.getsize(dest) == size
        ok_sha1 = sha1 is None or sha1_file(dest) == sha1
        ok_sha256 = sha256 is None or sha256_file(dest) == sha256
        if ok_size and ok_sha1 and ok_sha256:
            return False

    # nettoyage des .tmp orphelins d'une session précédente
    base = os.path.basename(dest)
    try:
        for stale in glob.glob(os.path.join(os.path.dirname(dest), base + ".tmp*")):
            try:
                os.remove(stale)
            except OSError:
                pass
    except Exception:
        pass

    tmp = dest + ".tmp%d.%d" % (os.getpid(), threading.get_ident())
    candidates = _url_candidates(url)
    errors = []
    success = False
    for cand in candidates:
        try:
            _download_to(cand, tmp, size, progress, headers)
            if sha1 and sha1_file(tmp) != sha1:
                raise RuntimeError("Empreinte SHA1 invalide pour " + cand)
            if sha256 and sha256_file(tmp) != sha256:
                raise RuntimeError("Empreinte SHA256 invalide pour " + cand)
            if size is not None and os.path.getsize(tmp) != size:
                raise RuntimeError("Taille inattendue pour " + cand)
            success = True
            break
        except Exception as e:
            errors.append("%s (%s)" % (cand, e))
            try:
                os.remove(tmp)
            except OSError:
                pass
            time.sleep(1.0)

    if not success:
        raise RuntimeError("Échec du téléchargement (%d source(s) essayée(s)) : %s"
                           % (len(candidates), errors[-1] if errors else "inconnu"))
    os.replace(tmp, dest)
    return True


def download_any(urls, dest, sha1=None, sha256=None, size=None, progress=None, headers=None):
    """Tente plusieurs URLs (miroirs) : la première qui réussit gagne.

    Utile quand les sources n'ont pas un schéma d'URL déductible (ex : Java).
    """
    last = None
    for i, url in enumerate(urls):
        try:
            download_file(url, dest, sha1=sha1, sha256=sha256, size=size,
                          progress=progress, headers=headers)
            return True
        except Exception as e:
            last = e
    raise RuntimeError("Échec (%d source(s)) : %s" % (len(urls), last))
