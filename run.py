"""Point d'entrée : démarre le serveur local et ouvre l'interface web."""
import os
import sys
import threading
import traceback
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from launcher import paths, state          # noqa: E402
from launcher.server import start_server    # noqa: E402

BANNER = r"""
    ____       _                 _                 
   |  _ \ ___ | | ___  __ _  ___| |_ ___  _ __ ___ 
   | |_) / _ \| |/ _ \/ _` |/ __| __/ _ \| '__/ _ \
   |  _ < (_) | |  __/ (_| | (__| || (_) | | |  __/
   |_| \_\___/|_|\___|\__,_|\___|\__\___/|_|  \___|
             __  _       __          __
            / / | |     / /   ____ _/ /_
           / /  | | /| / /   / __ `/ __/
          / /___| |/ |/ /   / /_/ / /_  
         /_____/|__/|__/    \__,_/\__/  

   Redstone Launcher (RL) - toutes les versions Minecraft
"""


def main():
    paths.ensure_dirs()
    state.load()
    port = int(os.environ.get("RL_PORT", "8765"))
    url = "http://127.0.0.1:%d" % port
    print(BANNER)
    print("Lanceur démarré : " + url)
    print("Garde cette fenêtre ouverte pendant que tu joues.")
    try:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
        start_server(port)
    except Exception:
        # Tout crash non géré est journalisé dans data/logs/crash.log
        try:
            crash = os.path.join(paths.LOGS, "crash.log")
            with open(crash, "a", encoding="utf-8") as f:
                f.write("=" * 40 + "\n" + traceback.format_exc() + "\n")
            print("Erreur inattendue, détail dans : " + crash)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    main()
