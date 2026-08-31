"""Schema, migrations, organizations, users and membership (§4 of the design doc)."""

from __future__ import annotations

import sqlite3

import pytest

from formslang import authstore

PASSWORD = "correct horse battery staple"


def test_opening_the_store_twice_on_the_same_file_does_not_fail(tmp_path):
    path = tmp_path / "auth.db"
    first = authstore.AuthStore(path)
    first.close()
    second = authstore.AuthStore(path)
    second.close()


def test_the_schema_version_is_recorded_exactly_once(tmp_path):
    path = tmp_path / "auth.db"
    authstore.AuthStore(path).close()
    authstore.AuthStore(path).close()
    db = sqlite3.connect(path)
    rows = db.execute("SELECT version FROM schema_migration").fetchall()
    db.close()
    assert rows == [(authstore._SCHEMA_VERSION,)]


def test_foreign_keys_are_enforced(auth_store):
    with pytest.raises(sqlite3.IntegrityError):
        auth_store.db.execute(
            "INSERT INTO membership (id, org_id, user_id, role, created_at) "
            "VALUES ('m1', 'missing-org', 'missing-user', 'OWNER', '2026-01-01 00:00:00')"
        )


def test_a_membership_referencing_a_missing_organization_is_rejected(auth_store):
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    with pytest.raises(sqlite3.IntegrityError):
        auth_store.create_membership("no-such-org", user_id, authstore.DEVELOPER)


def test_creating_an_organization_returns_a_usable_id(auth_store):
    org_id = auth_store.create_organization("acme", "Acme Corp")
    org = auth_store.get_organization(org_id)
    assert org["slug"] == "acme"
    assert org["name"] == "Acme Corp"


def test_a_duplicate_organization_slug_is_rejected(auth_store):
    auth_store.create_organization("acme", "Acme Corp")
    with pytest.raises(authstore.DuplicateSlug):
        auth_store.create_organization("acme", "Acme Corp Again")


def test_get_or_create_organization_is_idempotent(auth_store):
    first = auth_store.get_or_create_organization("acme", "Acme Corp")
    second = auth_store.get_or_create_organization("acme", "Different Name")
    assert first["id"] == second["id"]
    assert second["name"] == "Acme Corp"


def test_a_missing_organization_returns_none_not_an_exception(auth_store):
    assert auth_store.get_organization("does-not-exist") is None
    assert auth_store.get_organization_by_slug("does-not-exist") is None


def test_creating_a_user_hashes_the_password_not_stores_it(auth_store):
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    user = auth_store.get_user(user_id)
    assert user["password_hash"] != PASSWORD
    assert user["password_algo"] == "scrypt"


def test_a_duplicate_email_is_rejected(auth_store):
    auth_store.create_user("dev@example.com", PASSWORD)
    with pytest.raises(authstore.DuplicateEmail):
        auth_store.create_user("dev@example.com", "a different password")


def test_email_lookup_is_case_insensitive(auth_store):
    user_id = auth_store.create_user("Dev@Example.com", PASSWORD)
    found = auth_store.get_user_by_email("dev@example.com")
    assert found["id"] == user_id


def test_a_missing_user_returns_none_not_an_exception(auth_store):
    assert auth_store.get_user("does-not-exist") is None
    assert auth_store.get_user_by_email("nobody@example.com") is None


def test_creating_a_membership_with_an_unknown_role_is_rejected(auth_store):
    org_id = auth_store.create_organization("acme", "Acme Corp")
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    with pytest.raises(ValueError):
        auth_store.create_membership(org_id, user_id, "SUPERUSER")


def test_a_user_cannot_be_a_member_of_the_same_organization_twice(auth_store):
    org_id = auth_store.create_organization("acme", "Acme Corp")
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    auth_store.create_membership(org_id, user_id, authstore.DEVELOPER)
    with pytest.raises(ValueError):
        auth_store.create_membership(org_id, user_id, authstore.ADMIN)


def test_demoting_the_last_owner_is_refused(auth_store):
    org_id = auth_store.create_organization("acme", "Acme Corp")
    user_id = auth_store.create_user("owner@example.com", PASSWORD)
    auth_store.create_membership(org_id, user_id, authstore.OWNER)
    with pytest.raises(authstore.LastOwnerError):
        auth_store.update_membership_role(org_id, user_id, authstore.ADMIN)
    assert auth_store.get_membership(org_id, user_id)["role"] == authstore.OWNER


def test_demoting_one_of_two_owners_is_allowed(auth_store):
    org_id = auth_store.create_organization("acme", "Acme Corp")
    owner1 = auth_store.create_user("owner1@example.com", PASSWORD)
    owner2 = auth_store.create_user("owner2@example.com", PASSWORD)
    auth_store.create_membership(org_id, owner1, authstore.OWNER)
    auth_store.create_membership(org_id, owner2, authstore.OWNER)
    auth_store.update_membership_role(org_id, owner1, authstore.ADMIN)
    assert auth_store.get_membership(org_id, owner1)["role"] == authstore.ADMIN


def test_removing_the_last_owner_is_refused(auth_store):
    org_id = auth_store.create_organization("acme", "Acme Corp")
    user_id = auth_store.create_user("owner@example.com", PASSWORD)
    auth_store.create_membership(org_id, user_id, authstore.OWNER)
    with pytest.raises(authstore.LastOwnerError):
        auth_store.remove_membership(org_id, user_id)


def test_removing_a_non_member_is_refused(auth_store):
    org_id = auth_store.create_organization("acme", "Acme Corp")
    with pytest.raises(authstore.NotAMember):
        auth_store.remove_membership(org_id, "no-such-user")


def test_changing_a_developer_role_revokes_their_sessions(auth_store):
    org_id = auth_store.create_organization("acme", "Acme Corp")
    user_id = auth_store.create_user("dev@example.com", PASSWORD)
    auth_store.create_membership(org_id, user_id, authstore.DEVELOPER)
    raw_token, _session = auth_store.create_session(user_id, org_id)
    auth_store.update_membership_role(org_id, user_id, authstore.VIEWER)
    assert auth_store.get_session(raw_token) is None


def test_auth_enabled_defaults_to_off(monkeypatch):
    monkeypatch.delenv(authstore.AUTH_ENV, raising=False)
    assert authstore.auth_enabled() is False


def test_auth_enabled_reads_the_env_flag(monkeypatch):
    monkeypatch.setenv(authstore.AUTH_ENV, "1")
    assert authstore.auth_enabled() is True
    monkeypatch.setenv(authstore.AUTH_ENV, "0")
    assert authstore.auth_enabled() is False


def test_default_db_path_follows_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("FORMSLANG_DATA_DIR", str(tmp_path / "data"))
    assert authstore.default_db_path() == tmp_path / "data" / "auth.db"
