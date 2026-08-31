"""``formslang auth bootstrap-owner`` (design §7.1) -- host CLI only, never HTTP."""

from __future__ import annotations

import pytest

from formslang import authstore, cli

EMAIL = "owner@example.com"
PASSWORD = "correct horse battery staple"


def _run(monkeypatch, argv, passwords=(PASSWORD, PASSWORD)):
    answers = iter(passwords)
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": next(answers))
    return cli.main(argv)


def test_bootstrap_owner_creates_the_first_owner(monkeypatch, capsys):
    exit_code = _run(monkeypatch, ["auth", "bootstrap-owner", EMAIL])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert EMAIL in out

    store = authstore.AuthStore(authstore.default_db_path())
    try:
        user = store.get_user_by_email(EMAIL)
        assert user is not None
        org = store.get_organization_by_slug("local")
        membership = store.get_membership(org["id"], user["id"])
        assert membership["role"] == authstore.OWNER
    finally:
        store.close()


def test_bootstrap_owner_accepts_a_custom_org(monkeypatch):
    exit_code = _run(
        monkeypatch,
        ["auth", "bootstrap-owner", EMAIL, "--org-slug", "acme", "--org-name", "Acme Corp"],
    )
    assert exit_code == 0

    store = authstore.AuthStore(authstore.default_db_path())
    try:
        org = store.get_organization_by_slug("acme")
        assert org is not None
        assert org["name"] == "Acme Corp"
    finally:
        store.close()


def test_bootstrap_owner_refuses_to_run_twice(monkeypatch, capsys):
    first = _run(monkeypatch, ["auth", "bootstrap-owner", EMAIL])
    assert first == 0

    second = _run(monkeypatch, ["auth", "bootstrap-owner", "second@example.com"])
    assert second == 2
    assert "ERROR" in capsys.readouterr().err


def test_bootstrap_owner_rejects_mismatched_passwords(monkeypatch, capsys):
    exit_code = _run(monkeypatch, ["auth", "bootstrap-owner", EMAIL], passwords=("one", "two"))
    assert exit_code == 2
    assert "do not match" in capsys.readouterr().err

    store = authstore.AuthStore(authstore.default_db_path())
    try:
        assert store.get_user_by_email(EMAIL) is None
    finally:
        store.close()


def test_bootstrap_owner_rejects_an_empty_email(monkeypatch, capsys):
    exit_code = cli.main(["auth", "bootstrap-owner", "  "])
    assert exit_code == 2
    assert "email must not be empty" in capsys.readouterr().err


def test_the_auth_subcommand_requires_a_sub_action():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["auth"])


# -- formslang auth reset-owner (design SS7.5) -------------------------------


def _bootstrap(monkeypatch):
    assert _run(monkeypatch, ["auth", "bootstrap-owner", EMAIL]) == 0


def test_reset_owner_sets_a_new_password_that_actually_works(monkeypatch, capsys):
    _bootstrap(monkeypatch)

    exit_code = _run(
        monkeypatch, ["auth", "reset-owner", EMAIL],
        passwords=("a brand new passphrase", "a brand new passphrase"),
    )
    assert exit_code == 0
    assert EMAIL in capsys.readouterr().out

    store = authstore.AuthStore(authstore.default_db_path())
    try:
        result = store.login(EMAIL, "a brand new passphrase")
        assert result.ok
        assert not store.login(EMAIL, PASSWORD).ok
    finally:
        store.close()


def test_reset_owner_revokes_every_existing_session(monkeypatch):
    _bootstrap(monkeypatch)
    store = authstore.AuthStore(authstore.default_db_path())
    try:
        login = store.login(EMAIL, PASSWORD)
        assert store.get_session(login.session_token) is not None
    finally:
        store.close()

    _run(
        monkeypatch, ["auth", "reset-owner", EMAIL],
        passwords=("a brand new passphrase", "a brand new passphrase"),
    )

    store = authstore.AuthStore(authstore.default_db_path())
    try:
        assert store.get_session(login.session_token) is None
    finally:
        store.close()


def test_reset_owner_preserves_mfa_by_default(monkeypatch):
    _bootstrap(monkeypatch)
    store = authstore.AuthStore(authstore.default_db_path())
    try:
        from conftest import setup_confirmed_mfa

        user = store.get_user_by_email(EMAIL)
        setup_confirmed_mfa(store, user["id"])
    finally:
        store.close()

    _run(
        monkeypatch, ["auth", "reset-owner", EMAIL],
        passwords=("a brand new passphrase", "a brand new passphrase"),
    )

    store = authstore.AuthStore(authstore.default_db_path())
    try:
        result = store.login(EMAIL, "a brand new passphrase")
        assert result.scope == authstore.MFA_PENDING
    finally:
        store.close()


def test_reset_owner_with_clear_mfa_removes_the_enrollment(monkeypatch, capsys):
    _bootstrap(monkeypatch)
    store = authstore.AuthStore(authstore.default_db_path())
    try:
        from conftest import setup_confirmed_mfa

        user = store.get_user_by_email(EMAIL)
        setup_confirmed_mfa(store, user["id"])
        assert store.has_confirmed_mfa(user["id"])
    finally:
        store.close()

    exit_code = _run(
        monkeypatch, ["auth", "reset-owner", EMAIL, "--clear-mfa"],
        passwords=("a brand new passphrase", "a brand new passphrase"),
    )
    assert exit_code == 0
    assert "MFA cleared" in capsys.readouterr().out

    store = authstore.AuthStore(authstore.default_db_path())
    try:
        result = store.login(EMAIL, "a brand new passphrase")
        assert result.scope == authstore.BOOTSTRAP_MFA  # Owner: mandatory re-enrollment
    finally:
        store.close()


def test_reset_owner_refuses_a_non_owner_account(monkeypatch, capsys):
    _bootstrap(monkeypatch)
    store = authstore.AuthStore(authstore.default_db_path())
    try:
        owner = store.get_user_by_email(EMAIL)
        org = store.get_organization_by_slug("local")
        store.create_user("dev@example.com", PASSWORD)
        dev = store.get_user_by_email("dev@example.com")
        store.create_membership(org["id"], dev["id"], authstore.DEVELOPER)
    finally:
        store.close()

    exit_code = _run(
        monkeypatch, ["auth", "reset-owner", "dev@example.com"],
        passwords=("whatever passphrase", "whatever passphrase"),
    )
    assert exit_code == 2
    assert "ERROR" in capsys.readouterr().err


def test_reset_owner_refuses_an_unknown_email(monkeypatch, capsys):
    _bootstrap(monkeypatch)
    exit_code = _run(
        monkeypatch, ["auth", "reset-owner", "nobody@example.com"],
        passwords=("whatever passphrase", "whatever passphrase"),
    )
    assert exit_code == 2
    assert "ERROR" in capsys.readouterr().err


def test_reset_owner_rejects_mismatched_passwords(monkeypatch, capsys):
    _bootstrap(monkeypatch)
    exit_code = _run(monkeypatch, ["auth", "reset-owner", EMAIL], passwords=("one", "two"))
    assert exit_code == 2
    assert "do not match" in capsys.readouterr().err


def test_reset_owner_rejects_an_empty_email(monkeypatch, capsys):
    exit_code = cli.main(["auth", "reset-owner", "  "])
    assert exit_code == 2
    assert "email must not be empty" in capsys.readouterr().err
