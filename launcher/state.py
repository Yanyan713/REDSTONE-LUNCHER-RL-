"""État persistant du lanceur (comptes, réglages) dans data/config.json."""
import json
import os
import threading

from . import paths

CONFIG_PATH = os.path.join(paths.DATA, "config.json")
_lock = threading.Lock()

DEFAULTS = {
    "accounts": [],
    "selected_version": None,
    "selected_account": None,
    "settings": {
        "ram_mb": 2048,
        "java_override": "",
        "width": 854,
        "height": 480,
        "auto_install_java": True,
        "fullscreen": False,
        "install_dir": "",
        "proxy": "",
        "dl_mirror": "auto",
        "launch_mode": "vanilla",
    },
}

_state = None


def load():
    global _state
    with _lock:
        if _state is None:
            paths.ensure_dirs()
            loaded = {}
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                except Exception:
                    loaded = {}
            _state = dict(DEFAULTS)
            for k in DEFAULTS:
                if k in loaded and isinstance(loaded[k], type(DEFAULTS[k])):
                    _state[k] = loaded[k]
            if not isinstance(_state.get("accounts"), list):
                _state["accounts"] = []
            _state["settings"] = dict(DEFAULTS["settings"])
            _state["settings"].update(loaded.get("settings", {}) or {})
        return _state


def save():
    with _lock:
        if _state is not None:
            paths.ensure_dirs()
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(_state, f, ensure_ascii=False, indent=2)
