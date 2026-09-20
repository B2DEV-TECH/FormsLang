"""Project state survives interrupted mirrors and rejects foreign/corrupt inputs."""

import json
import os
import sqlite3
import threading

import pytest

from formslang.project_model import ProjectDescriptor, ProjectError, SourceRoot
from formslang.project_store import ProjectStore
from formslang.store import Store


def create(tmp_path):
    return ProjectStore.create(tmp_path, ProjectDescriptor(id="b" * 32, name="Orders"))


@pytest.mark.skipif(os.name != 'nt', reason='Windows sharing violation regression')
def test_descriptor_publication_tolerates_short_lived_windows_reader(tmp_path):
    store = create(tmp_path)
    mirror = tmp_path / '.formslang/project.json'
    reader = mirror.open('rb')
    release = threading.Timer(.08, reader.close)
    release.start()
    try:
        store.replace_roots((SourceRoot('f', 'forms', 'sources'),), expected_configuration=0)
        assert json.loads(mirror.read_text())['source_roots'][0]['id'] == 'f'
    finally:
        release.join(timeout=2)
        reader.close()
        store.close()


@pytest.mark.parametrize("corruption", ["stale", "broken", "missing"])
def test_open_repairs_descriptor_from_sqlite(tmp_path, corruption):
    store = create(tmp_path)
    expected = store.descriptor()
    store.close()
    path = tmp_path / ".formslang/project.json"
    if corruption == "missing":
        path.unlink()
    elif corruption == "broken":
        path.write_text("{", encoding="utf-8")
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["name"] = "uncommitted edit"
        path.write_text(json.dumps(payload), encoding="utf-8")
    reopened = ProjectStore.open(tmp_path)
    try:
        assert reopened.descriptor() == expected
        assert json.loads(path.read_text(encoding="utf-8"))["name"] == "Orders"
    finally:
        reopened.close()


@pytest.mark.parametrize("change", [{"id": "c" * 32}, {"store": "../outside.db"},
                                   {"project_version": "future/99"}])
def test_foreign_or_unsafe_mirror_fails_closed(tmp_path, change):
    create(tmp_path).close()
    path = tmp_path / ".formslang/project.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**payload, **change}), encoding="utf-8")
    with pytest.raises(ProjectError):
        ProjectStore.open(tmp_path)


def test_duplicate_create_never_overwrites(tmp_path):
    create(tmp_path).close()
    before = (tmp_path / ".formslang/project.session.db").read_bytes()
    with pytest.raises(ProjectError):
        create(tmp_path)
    assert (tmp_path / ".formslang/project.session.db").read_bytes() == before


def test_mirror_write_failure_keeps_authority_reopenable(tmp_path, monkeypatch):
    import formslang.project_store as persistence

    create(tmp_path).close()
    mirror = tmp_path / ".formslang/project.json"
    mirror.unlink()
    real_replace = persistence.os.replace

    def fail_replace(source, destination):
        if str(destination).endswith("project.json"):
            raise PermissionError("private-host-location")
        return real_replace(source, destination)

    monkeypatch.setattr(persistence.os, "replace", fail_replace)
    with pytest.raises(ProjectError) as error:
        ProjectStore.open(tmp_path)
    assert "private-host-location" not in str(error.value)
    monkeypatch.setattr(persistence.os, "replace", real_replace)
    store = ProjectStore.open(tmp_path)
    assert store.descriptor().name == "Orders"
    store.close()


def test_unrelated_and_corrupt_databases_not_initialized(tmp_path):
    directory = tmp_path / ".formslang"
    directory.mkdir()
    path = directory / "project.session.db"
    for content in (b"not sqlite", b""):
        path.write_bytes(content)
        with pytest.raises(ProjectError):
            ProjectStore.open(tmp_path)
        assert path.read_bytes() == content


def test_opt_out_preserves_running_legacy_job(tmp_path):
    path = tmp_path / "legacy.session.db"
    original = Store(path)
    original.db.execute("INSERT INTO job_run(started_at,status) VALUES ('now','running')")
    original.db.commit()
    another = Store(path, reconcile_jobs=False)
    assert another.db.execute("SELECT status FROM job_run").fetchone()[0] == "running"
    another.close()
    original.close()


def test_review_sequence_transactional_and_external_commit_visible(tmp_path):
    first = create(tmp_path)
    second = ProjectStore.open(tmp_path)
    insert = "INSERT INTO blueprint_review(entity,revision,action,comment,reviewer,decided_at) VALUES ('e','r','DEFER','why','who','now')"
    try:
        for _ in range(2):
            first.session.db.execute(insert)
            first.session.db.commit()
        first.session.db.execute(insert)
        first.session.db.rollback()
        assert second.session.db.execute("SELECT review_revision FROM modernization_project").fetchone()[0] == 2
    finally:
        first.close()
        second.close()


def test_module_links_cannot_escape_and_are_durable(tmp_path):
    store = create(tmp_path)
    try:
        with pytest.raises(ProjectError):
            store.add_module_session("a" * 64, "b" * 64, "../outside.db", {})
        relative = "modules/" + "a" * 64 + "/" + "b" * 64 + ".session.db"
        path = tmp_path / ".formslang" / relative
        path.parent.mkdir(parents=True)
        with sqlite3.connect(path):
            pass
        store.add_module_session("a" * 64, "b" * 64, relative, {"version": "legacy-import/1"})
        assert store.module_sessions()[0]["relative_store"] == relative
    finally:
        store.close()
