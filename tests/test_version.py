"""The release version is declared in several files; a bump must touch all of them.

``pyproject.toml`` is the source of truth. The others exist because the
packaging tools read them directly: the ``__init__`` fallback for source
checkouts without metadata, ``package.json`` and ``tauri.conf.json`` for
the desktop shell and its installer names, ``Cargo.toml`` for the Rust
crate, and the two lock files that ``npm install`` and ``cargo`` rewrite.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _first(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    assert match, pattern
    return match[1]


def test_every_version_declaration_matches_pyproject():
    expected = _first(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"))
    package_lock = json.loads(_read("desktop/package-lock.json"))
    declared = {
        "formslang/__init__.py": _first(r'^\s*__version__\s*=\s*"([^"]+)"', _read("formslang/__init__.py")),
        "desktop/package.json": json.loads(_read("desktop/package.json"))["version"],
        "desktop/package-lock.json": package_lock["version"],
        "desktop/package-lock.json (root package)": package_lock["packages"][""]["version"],
        "desktop/src-tauri/tauri.conf.json": json.loads(_read("desktop/src-tauri/tauri.conf.json"))["version"],
        "desktop/src-tauri/Cargo.toml": _first(r'^version\s*=\s*"([^"]+)"', _read("desktop/src-tauri/Cargo.toml")),
        "desktop/src-tauri/Cargo.lock": _first(
            r'^name = "formslang-desktop"\nversion = "([^"]+)"', _read("desktop/src-tauri/Cargo.lock"),
        ),
    }
    stale = {path: found for path, found in declared.items() if found != expected}
    assert not stale, f"pyproject.toml says {expected}; out of step: {stale}"
