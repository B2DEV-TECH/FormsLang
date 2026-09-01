"""``register_external_project`` (design §9) -- idempotent, concurrency-safe registration."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from formslang import authstore
from formslang.store import Store

PASSWORD = "correct horse battery staple"


def _owner(auth_store) -> dict:
    return auth_store.bootstrap_owner("owner@example.com", PASSWORD)


def _session_file(tmp_path: Path, name: str = "legacy.session.db") -> Path:
    path = tmp_path / name
    store = Store(path)
    store.init_session("DEMO_ORDER")
    store.close()
    return path


def test_registering_a_new_file_creates_one_external_legacy_project(auth_store, tmp_path):
    owner = _owner(auth_store)
    source = _session_file(tmp_path)

    project = auth_store.register_external_project(
        owner["organization_id"], "Demo Order", source, created_by=owner["user_id"],
    )

    assert project["storage_mode"] == authstore.EXTERNAL_LEGACY
    assert project["session_db_path"] is None
    assert Path(project["external_path"]).name.lower() == "legacy.session.db"


def test_registering_the_same_path_twice_returns_the_same_project(auth_store, tmp_path):
    owner = _owner(auth_store)
    source = _session_file(tmp_path)

    first = auth_store.register_external_project(
        owner["organization_id"], "Demo Order", source, created_by=owner["user_id"],
    )
    second = auth_store.register_external_project(
        owner["organization_id"], "Demo Order (again)", source, created_by=owner["user_id"],
    )

    assert first["id"] == second["id"]
    assert len(auth_store.list_projects_for_org(owner["organization_id"])) == 1


def test_registering_a_relative_and_an_absolute_path_to_the_same_file_is_one_project(
    auth_store, tmp_path, monkeypatch,
):
    owner = _owner(auth_store)
    source = _session_file(tmp_path)
    monkeypatch.chdir(tmp_path)

    absolute = auth_store.register_external_project(
        owner["organization_id"], "Demo Order", source, created_by=owner["user_id"],
    )
    relative = auth_store.register_external_project(
        owner["organization_id"], "Demo Order", Path(source.name), created_by=owner["user_id"],
    )

    assert absolute["id"] == relative["id"]


def test_registering_a_path_that_does_not_exist_is_refused(auth_store, tmp_path):
    owner = _owner(auth_store)

    with pytest.raises(ValueError):
        auth_store.register_external_project(
            owner["organization_id"], "Ghost", tmp_path / "nope.session.db",
            created_by=owner["user_id"],
        )
    assert auth_store.list_projects_for_org(owner["organization_id"]) == []


def test_two_concurrent_registration_runs_do_not_duplicate_a_project(tmp_path):
    """§9's concurrency requirement: BEGIN IMMEDIATE serializes the two runs."""
    store = authstore.AuthStore(tmp_path / "auth.db")
    try:
        owner = _owner(store)
        source = _session_file(tmp_path)
        errors = []
        results = []

        def register():
            try:
                results.append(
                    store.register_external_project(
                        owner["organization_id"], "Demo Order", source,
                        created_by=owner["user_id"],
                    )
                )
            except Exception as e:  # pragma: no cover -- surfaced via `errors` # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=register) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len({p["id"] for p in results}) == 1
        assert len(store.list_projects_for_org(owner["organization_id"])) == 1
    finally:
        store.close()


def test_a_project_from_another_organization_is_invisible_to_list(auth_store, tmp_path):
    owner = _owner(auth_store)
    other_org = auth_store.create_organization("other", "Other Org")
    source = _session_file(tmp_path)

    auth_store.register_external_project(
        other_org, "Not Yours", source, created_by=owner["user_id"],
    )

    assert auth_store.list_projects_for_org(owner["organization_id"]) == []
