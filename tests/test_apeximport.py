"""apeximport: SQLcl-driven validate/import, with the password kept off argv."""

from __future__ import annotations

import subprocess

import pytest

from formslang import apeximport


def test_account_key_folds_the_unsafe_characters_a_connect_string_carries():
    key = apeximport.account_key("FORMSLANG", "localhost:1521/FREEPDB1")
    assert key == "FORMSLANG_localhost:1521_FREEPDB1"


def test_sqlcl_binary_prefers_the_environment_override(monkeypatch):
    monkeypatch.setenv(apeximport.ENV_SQLCL_PATH, "C:/tools/sql.exe")
    assert apeximport.sqlcl_binary() == "C:/tools/sql.exe"


def test_run_import_refuses_when_sqlcl_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(apeximport, "sqlcl_binary", lambda: "")
    zip_path = tmp_path / "demo.apex.zip"
    zip_path.write_bytes(b"x")
    with pytest.raises(ValueError, match="SQLcl was not found"):
        apeximport.run_import(zip_path, connect_string="h:1521/S", username="U", password="p")


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        ("connection string", {"connect_string": "", "username": "U", "password": "p"}),
        ("username", {"connect_string": "h:1521/S", "username": "", "password": "p"}),
    ],
)
def test_run_import_requires_connect_string_and_username(monkeypatch, tmp_path, field, kwargs):
    monkeypatch.setattr(apeximport, "sqlcl_binary", lambda: "sql")
    zip_path = tmp_path / "demo.apex.zip"
    zip_path.write_bytes(b"x")
    with pytest.raises(ValueError, match=field):
        apeximport.run_import(zip_path, **kwargs)


def test_run_import_requires_a_password(monkeypatch, tmp_path):
    monkeypatch.setattr(apeximport, "sqlcl_binary", lambda: "sql")
    zip_path = tmp_path / "demo.apex.zip"
    zip_path.write_bytes(b"x")
    with pytest.raises(ValueError, match="password is required"):
        apeximport.run_import(zip_path, connect_string="h:1521/S", username="U", password="")


def test_run_import_refuses_a_missing_zip(monkeypatch, tmp_path):
    monkeypatch.setattr(apeximport, "sqlcl_binary", lambda: "sql")
    with pytest.raises(ValueError, match="no such export"):
        apeximport.run_import(
            tmp_path / "missing.apex.zip", connect_string="h:1521/S", username="U", password="p",
        )


def test_run_import_never_puts_the_password_on_the_command_line(monkeypatch, tmp_path):
    """The one property that matters most: no argv token holds the secret."""
    zip_path = tmp_path / "demo.apex.zip"
    zip_path.write_bytes(b"x")
    monkeypatch.setattr(apeximport, "sqlcl_binary", lambda: "sql")

    captured = {}

    def fake_run(argv, *, input, capture_output, text, timeout, check):
        captured["argv"] = argv
        captured["input"] = input
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    monkeypatch.setattr(apeximport.subprocess, "run", fake_run)

    result = apeximport.run_import(
        zip_path, connect_string="host:1521/FREEPDB1", username="FORMSLANG", password="s3cr3t!",
    )

    assert result.ok is True
    assert "s3cr3t!" not in captured["argv"]
    assert all("s3cr3t!" not in arg for arg in captured["argv"])
    assert "s3cr3t!" in captured["input"]  # the only place it may travel: SQLcl's own stdin
    assert "connect FORMSLANG/s3cr3t!@host:1521/FREEPDB1" in captured["input"]
    assert f"apex import -input {zip_path}" in captured["input"]


def test_run_import_uses_validate_when_asked(monkeypatch, tmp_path):
    zip_path = tmp_path / "demo.apex.zip"
    zip_path.write_bytes(b"x")
    monkeypatch.setattr(apeximport, "sqlcl_binary", lambda: "sql")

    captured = {}

    def fake_run(argv, *, input, capture_output, text, timeout, check):
        captured["input"] = input
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(apeximport.subprocess, "run", fake_run)

    apeximport.run_import(
        zip_path, connect_string="h:1521/S", username="U", password="p", validate_only=True,
    )
    assert f"apex validate -input {zip_path}" in captured["input"]
    assert "apex import" not in captured["input"]


def test_run_import_scrubs_the_password_out_of_captured_output(monkeypatch, tmp_path):
    zip_path = tmp_path / "demo.apex.zip"
    zip_path.write_bytes(b"x")
    monkeypatch.setattr(apeximport, "sqlcl_binary", lambda: "sql")

    def fake_run(argv, *, input, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(
            argv, 1, stdout="connecting as s3cr3t!\n", stderr="denied: s3cr3t!",
        )

    monkeypatch.setattr(apeximport.subprocess, "run", fake_run)

    result = apeximport.run_import(
        zip_path, connect_string="h:1521/S", username="U", password="s3cr3t!",
    )
    assert result.ok is False
    assert result.exit_code == 1
    assert "s3cr3t!" not in result.stdout
    assert "s3cr3t!" not in result.stderr
    assert "***" in result.stdout
