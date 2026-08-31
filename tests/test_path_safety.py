"""``resolve_project_path`` and ``adopt_project`` (design §8): containment,
symlink safety, and non-destructive rollback on a bad copy."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from formslang import authstore, projects
from formslang.store import Store

PASSWORD = "correct horse battery staple"


def _owner(auth_store) -> dict:
    return auth_store.bootstrap_owner("owner@example.com", PASSWORD)


def _legacy_project(auth_store, owner, tmp_path, name="legacy.session.db") -> dict:
    source = tmp_path / name
    store = Store(source)
    store.init_session("DEMO_ORDER")
    store.close()
    return auth_store.register_external_project(
        owner["organization_id"], "Demo Order", source, created_by=owner["user_id"],
    )


def test_resolve_project_path_returns_the_original_file_for_external_legacy(
    auth_store, tmp_path,
):
    owner = _owner(auth_store)
    project = _legacy_project(auth_store, owner, tmp_path)

    resolved = projects.resolve_project_path(project, data_dir=tmp_path / "data")

    assert resolved == Path(project["external_path"])


def test_adopting_a_project_copies_the_file_and_leaves_the_original_untouched(
    auth_store, tmp_path,
):
    owner = _owner(auth_store)
    project = _legacy_project(auth_store, owner, tmp_path)
    original_bytes = Path(project["external_path"]).read_bytes()
    data_dir = tmp_path / "data"

    adopted = projects.adopt_project(
        auth_store, project["id"], data_dir=data_dir, actor_user_id=owner["user_id"],
    )

    assert adopted["storage_mode"] == authstore.ADOPTED
    assert adopted["external_path"] is None
    assert adopted["adopted_at"] is not None

    resolved = projects.resolve_project_path(adopted, data_dir=data_dir)
    assert resolved.is_file()
    assert resolved.read_bytes()[:16] == original_bytes[:16]
    assert Path(project["external_path"]).read_bytes() == original_bytes  # untouched


def test_adopted_project_path_is_contained_under_data_dir(auth_store, tmp_path):
    owner = _owner(auth_store)
    project = _legacy_project(auth_store, owner, tmp_path)
    data_dir = tmp_path / "data"

    adopted = projects.adopt_project(
        auth_store, project["id"], data_dir=data_dir, actor_user_id=owner["user_id"],
    )
    resolved = projects.resolve_project_path(adopted, data_dir=data_dir)

    assert data_dir.resolve() in resolved.parents


def test_a_symlink_inside_the_data_dir_cannot_point_outside_it(auth_store, tmp_path):
    owner = _owner(auth_store)
    project = _legacy_project(auth_store, owner, tmp_path)
    data_dir = tmp_path / "data"
    outside_secret = tmp_path / "outside.session.db"
    outside_secret.write_bytes(b"not yours")

    adopted = projects.adopt_project(
        auth_store, project["id"], data_dir=data_dir, actor_user_id=owner["user_id"],
    )
    real_path = Path(adopted["session_db_path"])
    try:
        real_path.unlink()
        real_path.symlink_to(outside_secret)
    except OSError:
        pytest.skip("symlinks require elevated privileges on this platform")

    with pytest.raises(projects.ProjectPathEscape):
        projects.resolve_project_path(adopted, data_dir=data_dir)


def test_adoption_of_a_missing_original_file_is_refused(auth_store, tmp_path):
    owner = _owner(auth_store)
    project = _legacy_project(auth_store, owner, tmp_path)
    Path(project["external_path"]).unlink()

    with pytest.raises(projects.AdoptionError):
        projects.adopt_project(
            auth_store, project["id"], data_dir=tmp_path / "data", actor_user_id=owner["user_id"],
        )

    assert auth_store.get_project(project["id"])["storage_mode"] == authstore.EXTERNAL_LEGACY


def test_adoption_of_a_non_formslang_sqlite_file_is_refused_and_leaves_no_partial_state(
    auth_store, tmp_path,
):
    owner = _owner(auth_store)
    foreign = tmp_path / "foreign.db"
    conn = sqlite3.connect(foreign)
    conn.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    project = auth_store.register_external_project(
        owner["organization_id"], "Foreign", foreign, created_by=owner["user_id"],
    )
    data_dir = tmp_path / "data"

    with pytest.raises(projects.AdoptionError):
        projects.adopt_project(
            auth_store, project["id"], data_dir=data_dir, actor_user_id=owner["user_id"],
        )

    assert auth_store.get_project(project["id"])["storage_mode"] == authstore.EXTERNAL_LEGACY
    leftover_dirs = list((data_dir / "orgs").rglob("*.tmp")) if (data_dir / "orgs").exists() else []
    assert leftover_dirs == []


def test_adopting_a_project_twice_is_refused(auth_store, tmp_path):
    owner = _owner(auth_store)
    project = _legacy_project(auth_store, owner, tmp_path)
    data_dir = tmp_path / "data"

    projects.adopt_project(
        auth_store, project["id"], data_dir=data_dir, actor_user_id=owner["user_id"],
    )
    with pytest.raises(projects.AdoptionError):
        projects.adopt_project(
            auth_store, project["id"], data_dir=data_dir, actor_user_id=owner["user_id"],
        )


def test_adopting_a_project_writes_one_audit_row(auth_store, tmp_path):
    owner = _owner(auth_store)
    project = _legacy_project(auth_store, owner, tmp_path)
    data_dir = tmp_path / "data"

    projects.adopt_project(
        auth_store, project["id"], data_dir=data_dir, actor_user_id=owner["user_id"],
    )

    rows = auth_store.db.execute(
        "SELECT * FROM audit_log WHERE event_type = 'PROJECT_ADOPTED'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["target_id"] == project["id"]
    assert rows[0]["org_id"] == owner["organization_id"]
