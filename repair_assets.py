"""Vérifie et répare le cache d'assets de D:\\.minecraft (lanceur officiel).

Utilise l'index de la version donnée pour télécharger les objets manquants
ou corrompus dans D:\\.minecraft\\assets\\objects. N'efface rien.
Téléchargement en parallèle (8 fichiers simultanés) + miroir de secours.
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from launcher.download import download_file  # noqa: E402

MC = r"D:\.minecraft"
ASSETS = os.path.join(MC, "assets")
OBJECTS = os.path.join(ASSETS, "objects")
INDEXES = os.path.join(ASSETS, "indexes")
BASE = "https://resources.download.minecraft.net"


def find_index_for(version_id):
    # l'index d'assets porte l'id de l'index (souvent la version majeure)
    if not os.path.isdir(INDEXES):
        return None
    for name in sorted(os.listdir(INDEXES)):
        if name.endswith(".json"):
            try:
                with open(os.path.join(INDEXES, name), "r", encoding="utf-8") as f:
                    d = json.load(f)
                if d.get("objects"):
                    # on garde le plus récent qui correspond (approx)
                    return os.path.join(INDEXES, name), d
            except Exception:
                continue
    return None


def main():
    idx_path, index = find_index_for("26.2")
    if not idx_path:
        print("Aucun index d'assets trouvé dans", INDEXES)
        return
    print("Index utilisé :", idx_path)
    objects = index.get("objects", {})
    print("Objets dans l'index :", len(objects))

    missing = []
    corrupt = []
    ok = 0
    for key, obj in objects.items():
        h = obj.get("hash")
        if not h:
            continue
        dest = os.path.join(OBJECTS, h[:2], h)
        if not os.path.exists(dest):
            missing.append((key, obj, dest))
        elif os.path.getsize(dest) != obj.get("size", 0):
            corrupt.append((key, obj, dest))
        else:
            ok += 1

    print("Présents et valides :", ok)
    print("Manquants :", len(missing))
    print("Corrompus (mauvaise taille) :", len(corrupt))

    todo = missing + corrupt
    if not todo:
        print("Rien à réparer : le cache d'assets est complet.")
        return

    total = sum(o.get("size", 0) for _, o, _ in todo)
    print("À télécharger : %d fichiers (%.1f Mo)" % (len(todo), total / 1048576))

    done_size = 0
    done_count = 0
    lock = __import__("threading").Lock()
    errors = []

    def work(item):
        nonlocal done_size, done_count
        key, obj, dest = item
        h = obj["hash"]
        url = "%s/%s/%s" % (BASE, h[:2], h)
        try:
            download_file(url, dest, sha1=h, size=obj.get("size"))
            with lock:
                done_size += obj.get("size", 0)
                done_count += 1
                print("  [%d/%d] %s  (%.1f%%)" % (
                    done_count, len(todo), h[:12],
                    done_size / total * 100 if total else 0), flush=True)
        except Exception as e:
            with lock:
                done_count += 1
                errors.append((h[:12], str(e)))

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(work, todo))

    print("Terminé : %d fichiers / %d à faire." % (len(todo) - len(errors), len(todo)))
    if errors:
        print("Échecs (%d) :" % len(errors))
        for h, e in errors[:20]:
            print("  %s : %s" % (h, e))


if __name__ == "__main__":
    main()
