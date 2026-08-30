"""Serveur HTTP local : sert l'interface web et expose l'API du lanceur."""
import json
import mimetypes
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import auth, bedrock, fabric, java as java_mod, launch, mods, paths, shaders_pack, state, versions
from .download import JOB


def _send_json(handler, code, obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def _read_body(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    if not length:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _read_raw(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    return handler.rfile.read(length) if length else b""


def parse_multipart(content_type, body):
    """Parse minimaliste d'un corps multipart/form-data."""
    m = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', content_type or "")
    if not m:
        return []
    boundary = (m.group(1) or m.group(2)).strip().encode()
    parts = []
    for chunk in body.split(b"--" + boundary):
        chunk = chunk.lstrip(b"\r\n")
        if chunk in (b"--", b"--\r\n", b""):
            continue
        header_blob, sep, content = chunk.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = {}
        for line in header_blob.split(b"\r\n"):
            if b":" in line:
                k, v = line.split(b":", 1)
                headers[k.strip().lower().decode("utf-8", "replace")] = v.strip().decode("utf-8", "replace")
        if content.endswith(b"\r\n"):
            content = content[:-2]
        cd = headers.get("content-disposition", "")
        name, filename = None, None
        for piece in cd.split(";"):
            piece = piece.strip()
            if piece.startswith("name="):
                name = piece[5:].strip('"')
            elif piece.startswith("filename="):
                filename = piece[9:].strip('"')
        parts.append({
            "name": name,
            "filename": filename,
            "content_type": headers.get("content-type"),
            "data": content,
        })
    return parts


def list_directory(path):
    """Liste les lecteurs (si path vide) ou les sous-dossiers d'un chemin."""
    if not path:
        import string
        drives = []
        for letter in string.ascii_uppercase:
            if os.path.exists(letter + ":\\"):
                drives.append(letter + ":\\")
        return {"path": "", "parent": None, "dirs": drives}
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    if parent == path:
        parent = None
    entries = sorted(os.listdir(path))
    dirs = [e for e in entries if os.path.isdir(os.path.join(path, e))]
    return {"path": path, "parent": parent, "dirs": dirs}


class Handler(BaseHTTPRequestHandler):
    server_version = "RedstoneLauncher/1.0"

    def log_message(self, *args):
        pass

    def _handle(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path.startswith("/api/"):
                self._api(method, path[len("/api/"):], parse_qs(parsed.query))
            else:
                self._static(path)
        except Exception as e:
            try:
                _send_json(self, 500, {"error": str(e)})
            except Exception:
                pass

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_DELETE(self):
        self._handle("DELETE")

    # ------------------------------------------------------------------ API
    def _api(self, method, route, query):
        st = state.load()

        if route == "versions":
            if query.get("force", ["0"])[0] == "1":
                versions.refresh()
            return _send_json(self, 200, {
                "versions": versions.list_versions(),
                "latest": versions.latest(),
            })

        if route.startswith("version/"):
            vid = route[len("version/"):]
            meta = versions.get_version_meta(vid)
            client = meta.get("downloads", {}).get("client", {})
            return _send_json(self, 200, {
                "id": vid,
                "type": meta.get("type"),
                "release_time": meta.get("releaseTime"),
                "java": (meta.get("javaVersion") or {}).get("majorVersion"),
                "size_client": client.get("size", 0),
                "size_assets": (meta.get("assetIndex") or {}).get("totalSize", 0),
            })

        if route == "accounts":
            accounts = []
            for a in st["accounts"]:
                acc = dict(a)
                acc["has_skin"] = auth.has_skin(a["id"])
                accounts.append(acc)
            return _send_json(self, 200, {
                "accounts": accounts,
                "selected": st["selected_account"],
            })

        # ---- skins de comptes (avant la suppression générique) ----
        if route.startswith("accounts/") and route.endswith("/skin"):
            aid = route[len("accounts/"):-len("/skin")]
            png = auth.skin_path(aid)
            if method == "POST":
                parts = parse_multipart(self.headers.get("Content-Type", ""), _read_raw(self))
                data = b""
                for part in parts:
                    if part["name"] == "file" and part.get("data"):
                        data = part["data"]
                        break
                if not data:
                    raise ValueError("Fichier skin manquant.")
                auth.save_skin(aid, data)
                return _send_json(self, 200, {"ok": True})
            if method == "DELETE":
                return _send_json(self, 200, {"ok": auth.remove_skin(aid)})
            return _send_json(self, 200, {"has_skin": os.path.isfile(png)})

        if route.startswith("accounts/") and route.endswith("/skin.png"):
            aid = route[len("accounts/"):-len("/skin.png")]
            png = auth.skin_path(aid)
            if not os.path.isfile(png):
                return self.send_error(404)
            with open(png, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if route == "accounts/offline" and method == "POST":
            body = _read_body(self)
            acc = auth.create_offline(body.get("username", ""))
            st["accounts"].append(acc)
            st["selected_account"] = acc["id"]
            state.save()
            return _send_json(self, 200, {"account": acc})

        if route.startswith("accounts/") and method == "DELETE":
            aid = route[len("accounts/"):]
            st["accounts"] = [a for a in st["accounts"] if a["id"] != aid]
            if st["selected_account"] == aid:
                st["selected_account"] = None
            state.save()
            return _send_json(self, 200, {"ok": True})

        if route == "auth/microsoft/start" and method == "POST":
            info = auth.start_microsoft()
            return _send_json(self, 200, {
                "user_code": info["user_code"],
                "verification_uri": info["verification_uri"],
                "expires_in": info["expires_in"],
                "interval": info["interval"],
            })

        if route == "auth/microsoft/status":
            res = auth.microsoft_status()
            if res.get("status") == "ok":
                acc = res["account"]
                st["accounts"].append(acc)
                st["selected_account"] = acc["id"]
                state.save()
                return _send_json(self, 200, {"status": "ok", "account": acc})
            return _send_json(self, 200, res)

        if route == "settings":
            if method == "POST":
                body = _read_body(self)
                st["settings"].update({k: v for k, v in body.items() if k in st["settings"]})
                state.save()
            return _send_json(self, 200, {"settings": st["settings"]})

        if route == "select" and method == "POST":
            body = _read_body(self)
            if body.get("version"):
                st["selected_version"] = body["version"]
            if body.get("account"):
                st["selected_account"] = body["account"]
            state.save()
            return _send_json(self, 200, {"ok": True})

        if route == "java":
            return _send_json(self, 200, java_mod.status())

        if route == "java/install" and method == "POST":
            body = _read_body(self)
            major = int(body.get("major", 8))

            def worker():
                try:
                    java_mod.install_java(major, progress=_java_progress)
                    JOB.done("Java %d installé avec succès." % major)
                except Exception as e:
                    JOB.fail("Installation de Java %d : %s" % (major, e))

            JOB.begin("Installation de Java", "Installation de Java %d…" % major)
            threading.Thread(target=worker, daemon=True).start()
            return _send_json(self, 200, {"ok": True})

        if route == "launch" and method == "POST":
            body = _read_body(self)
            for k in ("ram_mb", "width", "height"):
                if k in body:
                    st["settings"][k] = int(body[k])
            if body.get("version"):
                st["selected_version"] = body["version"]
            if body.get("account"):
                st["selected_account"] = body["account"]
            state.save()
            version = body.get("version") or st["selected_version"]
            account = body.get("account") or st["selected_account"]
            if not version:
                raise ValueError("Sélectionne une version dans la liste.")
            if not account:
                raise ValueError("Sélectionne un compte, ou crée un compte local.")
            launch.launch(version, account)
            return _send_json(self, 200, {"ok": True})

        if route == "progress":
            return _send_json(self, 200, JOB.snapshot())

        if route == "logs":
            return _send_json(self, 200, {"logs": launch.current_log_tail()})

        # ---- explorateur de dossiers (choix du dossier d'installation) ----
        if route == "fs/list":
            p = (query.get("path", [""])[0])
            return _send_json(self, 200, list_directory(p))

        # ---- gestion des mods ----
        if route == "mods":
            version = query.get("version", [""])[0]
            if method == "POST":
                parts = parse_multipart(self.headers.get("Content-Type", ""),
                                        _read_raw(self))
                version = ""
                files = []
                for part in parts:
                    if part["name"] == "version":
                        version = part["data"].decode("utf-8", "replace").strip()
                    elif part["name"] == "files" and part.get("data"):
                        files.append((part["filename"], part["data"]))
                if not version:
                    raise ValueError("Version manquante.")
                saved = [mods.save_upload(version, fn, data) for fn, data in files]
                return _send_json(self, 200, {"ok": True, "saved": saved})
            return _send_json(self, 200, {"mods": mods.list_mods(version)})

        if route == "mods/toggle" and method == "POST":
            body = _read_body(self)
            ok = mods.toggle(body.get("version", ""), body.get("name", ""), bool(body.get("enable")))
            return _send_json(self, 200, {"ok": ok})

        if route == "mods/delete" and method == "POST":
            body = _read_body(self)
            ok = mods.delete(body.get("version", ""), body.get("name", ""))
            return _send_json(self, 200, {"ok": ok})

        if route == "modrinth/search":
            q = query.get("q", [""])[0]
            mcver = query.get("version", [""])[0] or None
            return _send_json(self, 200, {"results": mods.search(q, mcver)})

        if route == "modrinth/install" and method == "POST":
            body = _read_body(self)
            res = mods.install(body.get("slug", ""), body.get("mcver", ""),
                               body.get("loader", "fabric"), body.get("version", ""))
            return _send_json(self, 200, {"ok": True, "installed": res})

        # ---- Fabric (mod loader) ----
        if route == "fabric/loaders":
            mc = query.get("mc", [""])[0]
            if not mc:
                raise ValueError("Version Minecraft manquante.")
            return _send_json(self, 200, {"loaders": fabric.list_loaders(mc)})

        if route == "fabric/installed":
            mc = query.get("mc", [""])[0]
            if mc:
                return _send_json(self, 200, {"installed": fabric.is_installed(mc)})
            return _send_json(self, 200, {"installed_all": fabric.list_installed()})

        if route == "fabric/install" and method == "POST":
            body = _read_body(self)
            mc = body.get("mc", "")
            if not mc:
                raise ValueError("Version Minecraft manquante.")
            loader_ver = body.get("loader_version") or None

            def worker():
                try:
                    res = fabric.install(mc, loader_ver)
                    JOB.done("Fabric %s installé pour Minecraft %s (version « %s »)." % (
                        res["loader_version"], mc, res["id"]))
                except Exception as e:
                    JOB.fail("Installation de Fabric : %s" % e)

            JOB.begin("Installation de Fabric",
                      "Téléchargement du profil Fabric pour Minecraft %s…" % mc)
            threading.Thread(target=worker, daemon=True).start()
            return _send_json(self, 200, {"ok": True})

        # ---- Pack Shaders ----
        if route == "shaders/install" and method == "POST":
            body = _read_body(self)
            version = body.get("version", "")
            if not version:
                raise ValueError("Version manquante.")

            def worker():
                try:
                    res = shaders_pack.install_shaders_pack(version)
                    JOB.done("Pack Shaders installé : %d mod(s) et %d shader(s) (version « %s »)." % (
                        len(res["mods"]), len(res["shaders"]), res["fabric_id"]))
                except Exception as e:
                    JOB.fail("Installation du pack Shaders : %s" % e)

            JOB.begin("Pack Shaders", "Installation du pack Shaders…")
            threading.Thread(target=worker, daemon=True).start()
            return _send_json(self, 200, {"ok": True})

        # ---- Minecraft Bedrock ----
        if route == "bedrock/status":
            return _send_json(self, 200, bedrock.status())

        if route == "bedrock/launch" and method == "POST":
            try:
                bedrock.launch()
                return _send_json(self, 200, {"ok": True})
            except Exception as e:
                return _send_json(self, 400, {"error": str(e)})

        if route == "bedrock/open-store" and method == "POST":
            bedrock.open_store_page()
            return _send_json(self, 200, {"ok": True})

        if route == "bedrock/open-folder" and method == "POST":
            bedrock.open_resource_packs_folder()
            return _send_json(self, 200, {"ok": True})

        if route == "bedrock/packs":
            if method == "POST":
                # Upload d'un resource pack .mcpack
                parts = parse_multipart(self.headers.get("Content-Type", ""),
                                        _read_raw(self))
                for part in parts:
                    if part["name"] == "file" and part.get("data"):
                        import tempfile
                        tmp = tempfile.NamedTemporaryFile(
                            suffix=os.path.splitext(part.get("filename", "pack.mcpack"))[1],
                            delete=False)
                        tmp.write(part["data"])
                        tmp.close()
                        try:
                            res = bedrock.install_resource_pack(tmp.name, part.get("filename"))
                            return _send_json(self, 200, {"ok": True, "pack": res})
                        finally:
                            os.unlink(tmp.name)
                raise ValueError("Fichier manquant.")
            return _send_json(self, 200, {"packs": bedrock.list_resource_packs()})

        if route.startswith("bedrock/packs/") and method == "DELETE":
            folder = route[len("bedrock/packs/"):]
            ok = bedrock.delete_resource_pack(folder)
            return _send_json(self, 200, {"ok": ok})

        return _send_json(self, 404, {"error": "not found"})

    # ------------------------------------------------------------- statique
    def _static(self, path):
        if path in ("/", "/index.html"):
            rel = "index.html"
        else:
            rel = path.lstrip("/")
        full = os.path.normpath(os.path.join(paths.WEB, rel))
        if not full.startswith(os.path.normpath(paths.WEB)):
            return self.send_error(403)
        if not os.path.isfile(full):
            return self.send_error(404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _java_progress(message, done, total):
    JOB.set(stage="Installation de Java", message=message, current=done, total=total)


def start_server(port=8765):
    # Corrige au démarrage les pseudos locaux invalides (ex : « joueur 1 » -> « joueur_1 »)
    # pour éviter « Invalid characters in username » dans le jeu.
    st = state.load()
    if auth.sanitize_stored_accounts(st["accounts"]):
        state.save()

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("Redstone Launcher prêt sur http://127.0.0.1:%d  (Ctrl+C pour arrêter)" % port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du lanceur.")
