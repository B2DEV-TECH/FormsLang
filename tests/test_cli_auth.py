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
