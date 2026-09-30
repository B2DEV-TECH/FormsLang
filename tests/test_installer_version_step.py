"""Exercise the Windows installer workflow's version step itself."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/build-installers.yml"


def _version_step_script() -> str:
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index("      - name: Read the version the installers will carry")
    run = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "run: |")
    end = next(i for i in range(run + 1, len(lines)) if lines[i].startswith("      - "))
    return textwrap.dedent("\n".join(lines[run + 1 : end]))


@pytest.mark.parametrize(
    ("version", "msi_version"),
    [("2.2.0", ""), ("3.0.0-beta.1", "2.99.1")],
)
def test_installer_version_step_accepts_stable_and_beta(
    tmp_path: Path, version: str, msi_version: str
) -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        pytest.skip("PowerShell is required to run the Windows installer step")

    config = tmp_path / "desktop/src-tauri/tauri.conf.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"version": version}), encoding="utf-8")
    output = tmp_path / "github-output.txt"
    completed = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", _version_step_script()],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_OUTPUT": str(output)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    raw_output = output.read_bytes()
    output_text = raw_output.decode("utf-16" if raw_output.startswith(b"\xff\xfe") else "utf-8")
    assert output_text.splitlines() == [
        f"version={version}",
        f"artifact=installers-{version}",
        f"msi_version={msi_version}",
    ]


@pytest.mark.parametrize("version", ["3.0.0-beta.0", "3.0.0-beta.65536", "3.0.0-rc.1"])
def test_installer_version_step_rejects_unmapped_prereleases(
    tmp_path: Path, version: str
) -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        pytest.skip("PowerShell is required to run the Windows installer step")

    config = tmp_path / "desktop/src-tauri/tauri.conf.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"version": version}), encoding="utf-8")
    output = tmp_path / "github-output.txt"
    completed = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", _version_step_script()],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_OUTPUT": str(output)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode != 0
    assert not output.exists()
