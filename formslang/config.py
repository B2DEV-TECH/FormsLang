"""User settings on disk.

FormsLang has always been configured through environment variables, and it
still is -- the environment wins, always. What this module adds is the file
the in-app Settings screen writes, so a choice made in the UI survives a
restart: ``%APPDATA%\\FormsLang\\config.json`` on Windows,
``$XDG_CONFIG_HOME/formslang/config.json`` elsewhere.

The API key is the one setting that never lands in that file. It goes to the
operating system's credential store instead -- Windows Credential Manager,
the macOS Keychain, the Secret Service on Linux -- through
:mod:`formslang.secrets`. When the platform offers no such store, saving a
key fails and the user is told to use ``FORMSLANG_AI_KEY``; there is no quiet
fallback to plaintext. Everything else about the key is unchanged: it is
never logged, and it never travels to the browser (``/api/settings`` reports
only that a key exists, and where it lives).

Versions before this one did write the key into ``config.json``. Such a file
is still read, so nobody is locked out by an upgrade, and
:func:`migrate_plaintext_key` moves the value into the credential store and
strips it from disk.

``FORMSLANG_CONFIG_DIR`` overrides the directory, which is also how the tests
keep their hands off a real config.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import secrets
from .secrets import SecureStorageUnavailable  # re-exported for callers

# The whole vocabulary of the settings file. Anything else is dropped on
# load and on save, so a hand-edited file cannot smuggle surprises in.
# ``auth_enabled`` is a string, not a JSON boolean, on purpose: "1"/"true"/
# "on"/"yes" mirror the truthy vocabulary FORMSLANG_AUTH already uses (see
# authstore.auth_enabled), so the same value reads the same way whether it
# came from the environment or from this file. Absent means off, same as
# every other setting here.
SETTING_KEYS = (
    "provider", "model", "api_key", "base_url", "deployment", "api_version", "auth_enabled",
    "sqlcl_path", "apex_connect_string", "apex_username",
)

# What may actually be written to disk. The key is deliberately absent.
FILE_KEYS = tuple(k for k in SETTING_KEYS if k != "api_key")

__all__ = [
    "FILE_KEYS",
    "SETTING_KEYS",
    "SecureStorageUnavailable",
    "config_dir",
    "config_path",
    "data_dir",
    "key_location",
    "load_config",
    "migrate_plaintext_key",
    "save_config",
]


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


def data_dir() -> Path:
    """Where the control-plane database (``auth.db``) and adopted projects live.

    Independent of ``config_dir()`` so a team/server deployment can point
    the two at different volumes -- settings are per-machine, but
    ``auth.db`` and adopted project files are the one thing a server
    deployment needs on durable, backed-up storage. Defaults to the same
    directory as the settings file, since a local desktop install has no
    reason to split them.
    """
    override = os.environ.get("FORMSLANG_DATA_DIR", "").strip()
    return Path(override) if override else config_dir()


def _read_file() -> dict:
    """The raw settings file, filtered to the known keys. ``{}`` if unusable."""
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


def _legacy_key(stored: dict | None = None) -> str:
    """A plaintext key left in ``config.json`` by a version before this one."""
    cfg = _read_file() if stored is None else stored
    return str(cfg.get("api_key") or "").strip()


def load_config() -> dict:
    """The saved settings, or ``{}`` -- a missing or broken file is not an error.

    The API key is filled in from the credential store, so every caller keeps
    reading it the way it always has. A legacy plaintext key is still honoured
    until :func:`migrate_plaintext_key` has moved it.
    """
    cfg = _read_file()
    key = secrets.get_key() or cfg.get("api_key", "")
    cfg.pop("api_key", None)
    if key:
        cfg["api_key"] = key
    return cfg


def key_location() -> str:
    """Where the saved key lives: ``keychain``, ``file`` (legacy), or ``""``."""
    if secrets.get_key():
        return "keychain"
    return "file" if _legacy_key() else ""


def _write_file(clean: dict) -> Path:
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


def save_config(settings: dict) -> Path:
    """Write the settings atomically, keeping only the known keys.

    ``settings`` is the complete desired state: a key in it is stored, a key
    absent from it is forgotten. The value goes to the credential store, never
    to the file, and a failure there raises
    :class:`~formslang.secrets.SecureStorageUnavailable` before anything is
    written -- a saved provider must never imply a saved key.
    """
    key = str(settings.get("api_key") or "").strip()
    if key != secrets.get_key():
        if key:
            secrets.set_key(key)  # raises when there is nowhere safe to put it
        else:
            secrets.delete_key()

    clean = {
        k: str(settings[k]).strip()
        for k in FILE_KEYS
        if str(settings.get(k) or "").strip()
    }
    return _write_file(clean)


def migrate_plaintext_key() -> str:
    """Move a legacy plaintext key out of ``config.json`` into the OS store.

    Returns what happened: ``""`` when there was nothing to move, ``moved``
    when the key is now in the store and gone from disk, or ``blocked`` when
    the platform has no store -- in which case the file is left exactly as it
    was, because losing the user's key is worse than leaving it where it is.
    """
    stored = _read_file()
    legacy = _legacy_key(stored)
    if not legacy:
        return ""
    try:
        secrets.set_key(legacy)
    except (SecureStorageUnavailable, ValueError):
        return "blocked"
    _write_file({k: v for k, v in stored.items() if k in FILE_KEYS})
    return "moved"
