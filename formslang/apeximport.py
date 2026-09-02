"""Direct APEX import/validate via SQLcl -- credentials never touch disk or argv.

FormsLang's export always produces a self-contained ``<alias>.apex.zip`` that
the user can hand to SQLcl themselves (``apex import -input``, see the
manifest ``apexlang.py`` already writes). This module is the opt-in shortcut
that drives SQLcl for the user, but it draws the same trust boundary
:mod:`formslang.secrets` already draws for the AI provider key: a password is
either typed fresh for this one run, or handed to the OS credential store; it
is never written into ``config.json``, a temp file, or a subprocess argument
list. It travels to SQLcl the same way ``secrets.py`` documents for its own
backends -- over stdin, in a ``connect`` command, never as an argument a
process listing could show.

Each saved connection lives under ``(service=SERVICE, account=<username +
connect string>)`` in whatever OS credential store :mod:`formslang.secrets`
already uses -- which is inherently per FormsLang user, since that store is
scoped to the OS account running the app.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import load_config

SERVICE = "FormsLang:apex-import"
ENV_SQLCL_PATH = "FORMSLANG_SQLCL_PATH"

#: SQLcl hangs waiting for a password it will never get if the connect string
#: is wrong; this is the ceiling on how long a broken target blocks the one
#: workbench request thread handling it.
_TIMEOUT_SECONDS = 120

_UNSAFE_ACCOUNT_CHARS = re.compile(r"[^A-Za-z0-9_.:-]")


@dataclass(frozen=True)
class ImportResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str


def sqlcl_binary() -> str:
    """The SQLcl executable to run: env override, then Settings, then PATH."""
    import os
    import shutil

    override = os.environ.get(ENV_SQLCL_PATH, "").strip()
    if override:
        return override
    configured = str(load_config().get("sqlcl_path") or "").strip()
    if configured:
        return configured
    return shutil.which("sql") or shutil.which("sql.exe") or ""


def account_key(username: str, connect_string: str) -> str:
    """A credential-store account name safe under ``secrets._clean_identifier``.

    ``connect_string`` routinely contains ``/`` and ``:`` (``host:port/service``),
    neither of which that validator allows, so unsafe characters are folded to
    ``_`` -- this only has to be stable and collision-free enough to find the
    same saved password again next time, not human-typeable.
    """
    return _UNSAFE_ACCOUNT_CHARS.sub("_", f"{username}@{connect_string}")


def _token(name: str, value: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    if any(ch.isspace() or ord(ch) < 32 for ch in value):
        raise ValueError(f"{name} cannot contain whitespace or control characters")
    return value


def run_import(
    zip_path: Path,
    *,
    connect_string: str,
    username: str,
    password: str,
    validate_only: bool = False,
) -> ImportResult:
    """Drive SQLcl non-interactively against one exported ZIP.

    Runs ``apex validate -input`` when ``validate_only`` (Level 5: checks the
    package against the target workspace, changes nothing) or
    ``apex import -input`` (Level 6: the real import) -- the exact commands
    already documented in the export manifest, never a new command invented
    here. The password rides SQLcl's own ``connect user/password@target``
    line over stdin, the same place :mod:`formslang.secrets` puts a secret
    for ``secret-tool``/``security`` -- not a subprocess argument, not a file.
    """
    binary = sqlcl_binary()
    if not binary:
        raise ValueError(
            "SQLcl was not found. Install it, or set its path in Settings "
            f"(or the {ENV_SQLCL_PATH} environment variable)."
        )
    connect_string = _token("connection string", connect_string)
    username = _token("username", username)
    password = str(password or "")
    if not password:
        raise ValueError("a password is required")
    if not zip_path.is_file():
        raise ValueError(f"no such export: {zip_path.name}")

    verb = "validate" if validate_only else "import"
    script = (
        "whenever sqlerror exit failure\n"
        "whenever oserror exit failure\n"
        f"connect {username}/{password}@{connect_string}\n"
        f"apex {verb} -input {zip_path}\n"
        "exit success\n"
    )
    try:
        proc = subprocess.run(
            [binary, "-S", "/nolog"],
            input=script,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise ValueError(f"could not run SQLcl ({binary}): {e}") from None

    # Defense in depth: the password should never be echoed back by a
    # `connect` command, but nothing that came out of this process is kept
    # or shown to the caller with the secret still in it.
    def scrub(text: str) -> str:
        return text.replace(password, "***") if password else text

    return ImportResult(
        ok=proc.returncode == 0,
        exit_code=proc.returncode,
        stdout=scrub(proc.stdout),
        stderr=scrub(proc.stderr),
    )
