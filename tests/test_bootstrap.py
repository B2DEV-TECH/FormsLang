"""bootstrap_owner: the very first Owner, and the live-query guard against re-running it."""

from __future__ import annotations

import pytest

from formslang import authstore

PASSWORD = "correct horse battery staple"


def test_bootstrap_owner_creates_organization_user_and_membership(auth_store):
    result = auth_store.bootstrap_owner("owner@example.com", PASSWORD)
    org = auth_store.get_organization(result["organization_id"])
    user = auth_store.get_user(result["user_id"])
    membership = auth_store.get_membership(result["organization_id"], result["user_id"])
    assert org["slug"] == "local"
    assert user["email"] == "owner@example.com"
    assert membership["role"] == authstore.OWNER


def test_bootstrap_owner_refuses_to_run_twice(auth_store):
    auth_store.bootstrap_owner("owner@example.com", PASSWORD)
    with pytest.raises(authstore.BootstrapAlreadyDone):
        auth_store.bootstrap_owner("second@example.com", PASSWORD)
    assert auth_store.get_user_by_email("second@example.com") is None


def test_bootstrap_owner_is_a_live_query_not_a_flag(auth_store):
    result = auth_store.bootstrap_owner("owner@example.com", PASSWORD)
    # There is no supported way to leave an organization Owner-less through
    # the public API (remove_membership refuses it) -- simulate the row
    # disappearing some other way, to prove bootstrap re-derives its guard
    # from a live COUNT(*) rather than consulting a separate "already ran"
    # flag anywhere.
    auth_store.db.execute(
        "DELETE FROM membership WHERE org_id = ? AND user_id = ?",
        (result["organization_id"], result["user_id"]),
    )
    second = auth_store.bootstrap_owner("second-owner@example.com", "another password 2")
    assert second["organization_id"] == result["organization_id"]
    assert auth_store.count_owners(result["organization_id"]) == 1


def test_bootstrap_owner_with_a_custom_organization(auth_store):
    result = auth_store.bootstrap_owner(
        "owner@example.com", PASSWORD, org_slug="acme", org_name="Acme Corp"
    )
    org = auth_store.get_organization(result["organization_id"])
    assert org["slug"] == "acme"
    assert org["name"] == "Acme Corp"


def test_bootstrap_owner_with_a_duplicate_email_does_not_leave_a_dangling_organization(auth_store):
    auth_store.create_user("owner@example.com", PASSWORD)
    with pytest.raises(authstore.DuplicateEmail):
        auth_store.bootstrap_owner("owner@example.com", "a different password")
    org = auth_store.get_organization_by_slug("local")
    assert org is not None
    assert auth_store.count_owners(org["id"]) == 0
