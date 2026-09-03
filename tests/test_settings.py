"""Settings: the file on disk, the precedence rules, and the key that never
comes back.

Every promise in docs/SPEC.md §5-§6 about configuration is pinned here. The
suite runs against an isolated ``FORMSLANG_CONFIG_DIR`` (see conftest), so
nothing on the developer's machine leaks in and nothing leaks out.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from formslang.ai import EchoProvider, provider_from_env
from formslang.config import config_path, key_location, load_config, save_config
from formslang.convert import build_tasks
from formslang.parser import parse_xml
from formslang.store import Store
from formslang.workbench import Handler, Workbench


@pytest.fixture()
def server(tmp_path, sample_xml):
    store = Store(tmp_path / "s.db")
    store.init_session("DEMO_ORDER", str(sample_xml))
    store.add_tasks(build_tasks(parse_xml(sample_xml)))
    wb = Workbench(store, EchoProvider(), tmp_path / "export")

    handler = type("BoundHandler", (Handler,), {"workbench": wb})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        yield base, wb
    finally:
        httpd.shutdown()
        httpd.server_close()
        store.close()


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# -- the file on disk ------------------------------------------------------


def test_settings_round_trip_survives_a_restart():
    save_config({"provider": "ollama", "model": "llama3.3", "api_key": "k"})
    assert load_config() == {"provider": "ollama", "model": "llama3.3", "api_key": "k"}


def test_the_api_key_never_reaches_the_settings_file():
    """The whole point of the credential store: config.json holds no secret."""
    save_config({"provider": "anthropic", "model": "claude-x", "api_key": "SECRET-KEY-123"})
    raw = config_path().read_text(encoding="utf-8")
    assert "SECRET-KEY-123" not in raw
    assert "api_key" not in json.loads(raw)
    # ...and it is still the key everything else reads.
    assert load_config()["api_key"] == "SECRET-KEY-123"
    assert key_location() == "keychain"


def test_a_legacy_plaintext_key_is_moved_out_of_the_file():
    """An upgrade must not leave a key sitting in plaintext."""
    from formslang.config import migrate_plaintext_key

    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"provider": "anthropic", "api_key": "OLD-PLAINTEXT-KEY"}),
        encoding="utf-8",
    )
    # It is honoured before the migration, so nobody is locked out...
    assert load_config()["api_key"] == "OLD-PLAINTEXT-KEY"
    assert key_location() == "file"
    assert migrate_plaintext_key() == "moved"
    # ...and gone from disk after it.
    raw = path.read_text(encoding="utf-8")
    assert "OLD-PLAINTEXT-KEY" not in raw
    assert json.loads(raw) == {"provider": "anthropic"}
    assert load_config()["api_key"] == "OLD-PLAINTEXT-KEY"
    assert key_location() == "keychain"


def test_without_a_credential_store_a_key_is_refused_not_downgraded(monkeypatch, server):
    """No silent fallback to plaintext: the save fails and says what to do."""
    base, _wb = server
    monkeypatch.setenv("FORMSLANG_SECRET_BACKEND", "none")
    status, data = _post(base, "/api/settings", {"provider": "anthropic", "api_key": "SECRET-KEY-123"})
    assert status == 400
    assert "environment variable" in data["error"]
    # Nothing was written at all -- not the key, and not the provider that came
    # with it, so a refused save never leaves a half-applied settings file.
    assert not config_path().exists()
    # And the UI is told, so it can say so before the user types anything.
    status, state = _get(base, "/api/settings")
    assert status == 200
    assert json.loads(state)["secure_storage"]["available"] is False


def test_unknown_keys_are_dropped_on_load_and_on_save():
    save_config({"provider": "ollama", "evil": "payload", "shell": "rm -rf"})
    path = config_path()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw == {"provider": "ollama"}
    # A hand-edited file cannot smuggle keys in either.
    path.write_text(json.dumps({"provider": "echo", "surprise": "x"}), encoding="utf-8")
    assert load_config() == {"provider": "echo"}


def test_a_corrupt_config_file_is_not_an_error():
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not json", encoding="utf-8")
    assert load_config() == {}
    path.write_text('["a list, not a dict"]', encoding="utf-8")
    assert load_config() == {}


def test_the_environment_wins_over_the_config_file(monkeypatch):
    save_config({"provider": "ollama", "model": "llama3.3"})
    monkeypatch.setenv("FORMSLANG_AI_PROVIDER", "echo")
    provider = provider_from_env()
    assert provider.type_id == "echo"
    monkeypatch.delenv("FORMSLANG_AI_PROVIDER")
    assert provider_from_env().type_id == "ollama"


# -- the HTTP surface ------------------------------------------------------


def test_get_settings_never_leaks_the_key(server):
    base, _wb = server
    status, saved = _post(base, "/api/settings", {"provider": "anthropic", "api_key": "SECRET-KEY-123"})
    assert status == 200
    assert saved["has_key"] is True
    assert saved["key_source"] == "keychain"
    # The key is in the credential store...
    assert load_config()["api_key"] == "SECRET-KEY-123"
    # ...and in no answer the browser can ask for.
    for path in ("/api/settings", "/api/state", "/api/providers"):
        status, body = _get(base, path)
        assert status == 200
        assert b"SECRET" not in body, path


def test_saving_settings_swaps_the_live_provider(server):
    base, wb = server
    status, data = _post(base, "/api/settings", {"provider": "ollama", "model": "llama3.3"})
    assert status == 200
    assert data["provider"] == "ollama"
    assert data["model"] == "llama3.3"
    assert wb.provider.type_id == "ollama"
    # The choice is on disk, so a restart comes back to the same provider.
    assert load_config() == {"provider": "ollama", "model": "llama3.3"}


def test_an_unknown_provider_is_refused_and_nothing_is_saved(server):
    base, wb = server
    status, data = _post(base, "/api/settings", {"provider": "skynet"})
    assert status == 400
    assert "unknown AI provider" in data["error"]
    assert wb.provider.type_id == "echo"
    assert load_config() == {}


def test_an_empty_key_forgets_the_stored_one(server):
    base, _wb = server
    _post(base, "/api/settings", {"provider": "anthropic", "api_key": "SECRET-KEY-123"})
    status, data = _post(base, "/api/settings", {"api_key": ""})
    assert status == 200
    assert data["has_key"] is False
    assert data["key_source"] == ""
    assert "api_key" not in load_config()


def test_an_absent_key_field_keeps_the_stored_one(server):
    base, _wb = server
    _post(base, "/api/settings", {"provider": "anthropic", "api_key": "SECRET-KEY-123"})
    # Saving the model again, key field untouched: the key must survive.
    status, data = _post(base, "/api/settings", {"provider": "anthropic", "model": "claude-x"})
    assert status == 200
    assert data["has_key"] is True
    assert load_config()["api_key"] == "SECRET-KEY-123"


def test_no_settings_change_while_a_conversion_is_running(server):
    base, wb = server
    wb.job = {"running": True, "done": 0, "total": 3, "error": ""}
    status, data = _post(base, "/api/settings", {"provider": "ollama"})
    assert status == 400
    assert "wait for it to finish" in data["error"]


def test_settings_test_round_trips_the_offline_provider(server):
    base, _wb = server
    status, data = _post(base, "/api/settings/test", {"provider": "echo"})
    assert status == 200
    assert data["ok"] is True


def test_sqlcl_path_is_saved_and_reported_found(server, monkeypatch, tmp_path):
    """The Settings sheet's own promise: a path typed here is what apeximport uses."""
    monkeypatch.delenv("FORMSLANG_SQLCL_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    base, _wb = server

    status, body = _get(base, "/api/settings")
    assert status == 200
    state = json.loads(body)
    assert state["sqlcl_path"] == ""
    assert state["sqlcl_found"] is False
    assert state["sqlcl_env_override"] is False

    fake_sql = tmp_path / "sql.exe"
    fake_sql.write_text("", encoding="utf-8")
    status, data = _post(base, "/api/settings", {"sqlcl_path": str(fake_sql)})
    assert status == 200
    assert data["sqlcl_path"] == str(fake_sql)
    assert data["sqlcl_found"] is True
    assert load_config()["sqlcl_path"] == str(fake_sql)


def test_the_sqlcl_env_var_wins_over_the_saved_path(server, monkeypatch):
    base, _wb = server
    _post(base, "/api/settings", {"sqlcl_path": r"C:\saved\sql.exe"})
    monkeypatch.setenv("FORMSLANG_SQLCL_PATH", r"C:\env\sql.exe")

    status, body = _get(base, "/api/settings")
    assert status == 200
    state = json.loads(body)
    assert state["sqlcl_env_override"] is True
    assert state["sqlcl_found"] is True
    # The saved value is still there on disk -- only the effective binary
    # (env, in apeximport.sqlcl_binary) is overridden, not the setting itself.
    assert state["sqlcl_path"] == r"C:\saved\sql.exe"


def test_terminal_refuses_anything_not_whitelisted(server):
    base, _wb = server
    # An API provider has no terminal; neither does an arbitrary command.
    for attempt in ("anthropic", "cmd.exe", "powershell", "", "claude; rm -rf /"):
        status, data = _post(base, "/api/terminal", {"provider": attempt})
        assert status == 400, attempt
        assert "no terminal setup" in data["error"], attempt
