"""Bridge to the Oracle Forms toolchain (frmf2xml / Forms2XML).

This is the only FormsLang module that depends on Oracle binaries being
installed on the machine. Nothing is redistributed: we locate an ORACLE_HOME
that the user installed themselves and invoke their own tools.

Golden rule: conversion NEVER writes into the source directory. Forms2XML
emits the XML next to the .fmb, so to keep the source tree untouched we
copy the module into a temporary directory, convert it there, and move the
result into the output directory.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Suffix Forms2XML applies per module type.
_XML_SUFFIX = {".fmb": "_fmb.xml", ".mmb": "_mmb.xml", ".olb": "_olb.xml"}

_CANDIDATE_HOMES = (
    r"C:\Oracle\Middleware\Oracle_Home",
    r"C:\oracle\Middleware\Oracle_Home",
    r"C:\Oracle\Middleware\Oracle_Home1",
    r"C:\DevSuiteHome_1",
)

_JARS = (
    r"jlib\frmxmltools.jar",
    r"jlib\frmjdapi.jar",
    r"oracle_common\modules\oracle.xdk\xmlparserv2.jar",
)


class OracleToolchainError(RuntimeError):
    """ORACLE_HOME missing or incomplete for Forms module conversion."""


@dataclass(frozen=True)
class Toolchain:
    """Resolved Oracle Forms paths on this machine."""

    oracle_home: Path
    java_exe: Path
    classpath: str

    @property
    def bin_dir(self) -> Path:
        return self.oracle_home / "bin"


def detect_toolchain(oracle_home: str | os.PathLike[str] | None = None) -> Toolchain:
    """Resolve the toolchain, validating that every piece actually exists.

    Order: explicit argument > ORACLE_HOME environment variable > known
    install paths. Failing here is a fact about the environment, not a bug --
    the message names exactly which file was missing.
    """
    candidates: list[Path] = []
    if oracle_home:
        candidates.append(Path(oracle_home))
    from_env = os.environ.get("ORACLE_HOME", "").strip()
    if from_env:
        candidates.append(Path(from_env))
    candidates.extend(Path(c) for c in _CANDIDATE_HOMES)

    tried: list[str] = []
    for home in candidates:
        java = home / "oracle_common" / "jdk" / "bin" / "java.exe"
        if os.name != "nt":
            java = home / "oracle_common" / "jdk" / "bin" / "java"
        jars = [home / j.replace("\\", os.sep) for j in _JARS]
        missing = [p for p in [java, *jars] if not p.exists()]
        if not missing:
            return Toolchain(
                oracle_home=home,
                java_exe=java,
                classpath=os.pathsep.join(str(j) for j in jars),
            )
        if home.exists():
            tried.append(f"{home} (missing: {missing[0].name})")

    detail = "; ".join(tried) if tried else "no ORACLE_HOME found"
    raise OracleToolchainError(
        "Oracle Forms was not found on this machine. Set ORACLE_HOME or pass "
        f"--oracle-home. Tried: {detail}"
    )


def expected_xml_name(module: Path) -> str:
    """Name of the XML file Forms2XML will produce for this module."""
    return module.stem + _XML_SUFFIX.get(module.suffix.lower(), "_fmb.xml")


def convert_module(
    module: Path,
    out_dir: Path,
    toolchain: Toolchain,
    *,
    timeout: int = 180,
    overwrite: bool = False,
) -> tuple[Path, str]:
    """Convert one .fmb/.mmb to XML and return (xml_path, conversion_log).

    The Forms2XML log is returned in full: it carries the dangling-reference
    warnings (e.g. "Object group child X has no real object") that are a
    signal of technical debt in the module and feed into the assessment.
    """
    module = Path(module)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / expected_xml_name(module)

    if target.exists() and not overwrite:
        return target, ""

    # Sandbox: work on an isolated copy so the XML is never born in the
    # source tree.
    with tempfile.TemporaryDirectory(prefix="formslang_") as tmp:
        work = Path(tmp)
        local = work / module.name
        shutil.copy2(module, local)
        log_path = work / "convert.log"
        bat_path = work / "_convert.bat"

        java_cmd = (
            f'"{toolchain.java_exe}" '
            f'-Djava.library.path="%ORACLE_HOME%\\bin" '
            f'-classpath "{toolchain.classpath}" '
            f"oracle.forms.util.xmltools.Forms2XML "
            f'"{local}"'
        )
        bat_path.write_text(
            "@echo off\r\n"
            f"set ORACLE_HOME={toolchain.oracle_home}\r\n"
            "set PATH=%ORACLE_HOME%\\bin;%PATH%\r\n"
            f'{java_cmd} > "{log_path}" 2>&1\r\n',
            encoding="ascii",
            errors="replace",
        )

        kwargs: dict = {}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(
                ["cmd.exe", "/c", str(bat_path)],
                capture_output=True,
                text=True,
                cwd=str(work),
                timeout=timeout,
                check=False,
                **kwargs,
            )
        except subprocess.TimeoutExpired:
            raise OracleToolchainError(
                f"Forms2XML exceeded {timeout}s converting {module.name}"
            ) from None

        log = ""
        if log_path.exists():
            log = log_path.read_text(encoding="utf-8", errors="replace")

        produced = work / expected_xml_name(module)
        if not produced.exists():
            alt = work / (module.stem + ".xml")
            produced = alt if alt.exists() else produced
        if not produced.exists():
            err = (log or proc.stderr or proc.stdout or "no XML produced").strip()
            raise OracleToolchainError(f"{module.name}: {err[:400]}")

        shutil.move(str(produced), str(target))

    return target, log
