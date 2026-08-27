"""User settings on disk.

FormsLang has always been configured through environment variables, and it
still is -- the environment wins, always. What this module adds is the file
the in-app Settings screen writes, so a choice made in the UI survives a
restart: ``%APPDATA%\\FormsLang\\config.json`` on Windows,
``$XDG_CONFIG_HOME/formslang/config.json`` elsewhere.

The API key is the delicate entry. Keeping it here is a deliberate,
documented trade -- the alternative (environment-only) is what made the
product hard to use. The rules that make it acceptable: the file is written
atomically with owner-only permissions where the OS supports them, the key
is never logged, and it never travels to the browser (``/api/settings``
reports only that a key exists). ``FORMSLANG_CONFIG_DIR`` overrides the
directory, which is also how the tests keep their hands off a real config.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# The whole vocabulary of the settings file. Anything else is dropped on
# load and on save, so a hand-edited file cannot smuggle surprises in.
SETTING_KEYS = ("provider", "model", "api_key", "base_url", "deployment", "api_version")


def config_dir() -> Path:
    override = os.environ.get("FORMSLANG_CONFIG_DIR", "").strip()
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("APPDATA", "").strip()
        return (Path(base) if base else Path.home() / "AppData" / "Roaming") / "FormsLang"
    base = os.environ.get("XDG_CONFIG_HOME", "").strip()
    return (Path(base) if base else Path.home() / ".config") / "formslang"


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict:
    """The saved settings, or ``{}`` -- a missing or broken file is not an error."""
    try:
        raw = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        k: str(v).strip()
        for k, v in raw.items()
        if k in SETTING_KEYS and isinstance(v, (str, int, float)) and str(v).strip()
    }


def save_config(settings: dict) -> Path:
    """Write the settings atomically, keeping only the known keys."""
    clean = {
        k: str(settings[k]).strip()
        for k in SETTING_KEYS
        if str(settings.get(k) or "").strip()
    }
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)  # best effort; a no-op on Windows ACLs
    except OSError:
        pass
    os.replace(tmp, path)
    return path
