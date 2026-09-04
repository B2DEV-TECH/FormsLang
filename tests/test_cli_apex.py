"""``formslang apex validate|import``: SQLcl from the command line, password off argv."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import types

import pytest

from formslang import apeximport, cli, secrets

COMPILE_ERRORS = (
    "APEXlang Compile Errors:\n"
    "File: pages/p00001-demo.apx\n"
    "Type: PLUGIN_NOT_FOUND\n"
    "Error: Unable to find plugin for pageItem component: textArea\n"
)


@pytest.fixture()
def zip_path(tmp_path):
    path = tmp_path / "demo.apex.zip"
    path.write_bytes(b"PK")
    return path


@pytest.fixture()
def sqlcl(monkeypatch):
    """A stand-in SQLcl: records what it was handed, answers what the test says."""
    calls: list[dict] = []
    reply = {"code": 0, "stdout": "Application imported.\n", "stderr": ""}

    def fake_run(argv, *, input, capture_output, text, timeout, check):
        calls.append({"argv": argv, "input": input, "timeout": timeout})
        return subprocess.CompletedProcess(argv, reply["code"], reply["stdout"], reply["stderr"])

    monkeypatch.setattr(apeximport.subprocess, "run", fake_run)
    return types.SimpleNamespace(calls=calls, reply=reply)


@pytest.fixture()
def ci_env(monkeypatch):
    """The CI route: target and password in the environment, nothing saved."""
    monkeypatch.setenv(apeximport.ENV_APEX_CONNECT, "db.example.com:1521/APEXPDB")
    monkeypatch.setenv(apeximport.ENV_APEX_USER, "FORMSLANG")
    monkeypatch.setenv(apeximport.ENV_APEX_PASSWORD, "s3cr3t!")


def test_validate_runs_sqlcl_with_the_password_on_stdin_only(zip_path, sqlcl, ci_env, capsys):
    exit_code = cli.main(["apex", "validate", str(zip_path), "--sqlcl", "fake-sql"])
    assert exit_code == 0

    (call,) = sqlcl.calls
    assert call["argv"] == ["fake-sql", "-S", "-thin", "/nolog"]
    assert all("s3cr3t!" not in arg for arg in call["argv"])
    assert "connect FORMSLANG/s3cr3t!@db.example.com:1521/APEXPDB" in call["input"]
    assert f"apex validate -input {zip_path}" in call["input"]
    assert call["timeout"] == apeximport.TIMEOUT_SECONDS

    out = capsys.readouterr().out
    assert "Validate : demo.apex.zip" in out
    assert "Target   : FORMSLANG@db.example.com:1521/APEXPDB" in out
    assert "Result   : OK" in out
    assert "s3cr3t!" not in out


def test_import_uses_the_import_verb(zip_path, sqlcl, ci_env):
    assert cli.main(["apex", "import", str(zip_path), "--sqlcl", "fake-sql"]) == 0
    assert f"apex import -input {zip_path}" in sqlcl.calls[0]["input"]
    assert "apex validate" not in sqlcl.calls[0]["input"]


def test_flags_override_the_environment(zip_path, sqlcl, ci_env):
    exit_code = cli.main(
        [
            "apex", "validate", str(zip_path), "--sqlcl", "fake-sql",
            "--connect", "other:1521/PDB", "--user", "OTHER", "--timeout", "7",
        ]
    )
    assert exit_code == 0
    assert "connect OTHER/s3cr3t!@other:1521/PDB" in sqlcl.calls[0]["input"]
    assert sqlcl.calls[0]["timeout"] == 7


def test_compile_errors_fail_the_command_even_when_sqlcl_exits_zero(zip_path, sqlcl, ci_env, capsys):
    sqlcl.reply.update(code=0, stdout=COMPILE_ERRORS)
    exit_code = cli.main(["apex", "import", str(zip_path), "--sqlcl", "fake-sql"])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "PLUGIN_NOT_FOUND" in out
    assert "nothing was imported" in out


def test_a_failing_sqlcl_exit_code_is_reported(zip_path, sqlcl, ci_env, capsys):
    sqlcl.reply.update(code=3, stdout="", stderr="ORA-01017: invalid credential\n")
    assert cli.main(["apex", "validate", str(zip_path), "--sqlcl", "fake-sql"]) == 1
    out = capsys.readouterr().out
    assert "ORA-01017" in out
    assert "FAILED (exit 3)" in out


def test_json_output_carries_the_verdict(zip_path, sqlcl, ci_env, capsys):
    sqlcl.reply.update(code=0, stdout=COMPILE_ERRORS)
    exit_code = cli.main(["apex", "validate", str(zip_path), "--sqlcl", "fake-sql", "--json"])
    assert exit_code == 1
    data = json.loads(capsys.readouterr().out)
    assert data["command"] == "validate"
    assert data["ok"] is False
    assert data["exit_code"] == 0
    assert "PLUGIN_NOT_FOUND" in data["stdout"]
    assert "s3cr3t!" not in json.dumps(data)


def test_the_password_saved_from_the_workbench_is_reused(zip_path, sqlcl, monkeypatch):
    monkeypatch.delenv(apeximport.ENV_APEX_PASSWORD, raising=False)
    monkeypatch.setenv(apeximport.ENV_APEX_CONNECT, "h:1521/S")
    monkeypatch.setenv(apeximport.ENV_APEX_USER, "U")
    secrets.set_secret(apeximport.SERVICE, apeximport.account_key("U", "h:1521/S"), "saved-pw")

    assert cli.main(["apex", "validate", str(zip_path), "--sqlcl", "fake-sql"]) == 0
    assert "connect U/saved-pw@h:1521/S" in sqlcl.calls[0]["input"]


def test_a_person_at_a_terminal_is_prompted(zip_path, sqlcl, monkeypatch):
    monkeypatch.delenv(apeximport.ENV_APEX_PASSWORD, raising=False)
    monkeypatch.setenv(apeximport.ENV_APEX_CONNECT, "h:1521/S")
    monkeypatch.setenv(apeximport.ENV_APEX_USER, "U")
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "typed-pw")

    assert cli.main(["apex", "validate", str(zip_path), "--sqlcl", "fake-sql"]) == 0
    assert "connect U/typed-pw@h:1521/S" in sqlcl.calls[0]["input"]


def test_no_password_and_no_terminal_is_refused_before_sqlcl_runs(zip_path, sqlcl, monkeypatch, capsys):
    """A CI job with the secret missing must fail loudly, not hang on a
    prompt nobody will answer."""
    monkeypatch.delenv(apeximport.ENV_APEX_PASSWORD, raising=False)
    monkeypatch.setenv(apeximport.ENV_APEX_CONNECT, "h:1521/S")
    monkeypatch.setenv(apeximport.ENV_APEX_USER, "U")
    monkeypatch.setattr(sys, "stdin", io.StringIO())

    assert cli.main(["apex", "validate", str(zip_path), "--sqlcl", "fake-sql"]) == 2
    assert sqlcl.calls == []
    err = capsys.readouterr().err
    assert apeximport.ENV_APEX_PASSWORD in err


def test_a_missing_target_is_refused_with_every_way_to_set_it(zip_path, sqlcl, monkeypatch, capsys):
    for name in (apeximport.ENV_APEX_CONNECT, apeximport.ENV_APEX_USER, apeximport.ENV_APEX_PASSWORD):
        monkeypatch.delenv(name, raising=False)

    assert cli.main(["apex", "validate", str(zip_path), "--sqlcl", "fake-sql"]) == 2
    assert sqlcl.calls == []
    err = capsys.readouterr().err
    assert "--connect" in err
    assert apeximport.ENV_APEX_CONNECT in err
    assert "Settings" in err


def test_a_missing_zip_is_refused(tmp_path, sqlcl, ci_env, capsys):
    exit_code = cli.main(["apex", "validate", str(tmp_path / "nope.apex.zip"), "--sqlcl", "fake-sql"])
    assert exit_code == 2
    assert "no such export" in capsys.readouterr().err
    assert sqlcl.calls == []
