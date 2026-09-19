"""Project-wide revisions conservatively invalidate approval, never its history."""

import copy
import sqlite3

import pytest

from formslang import blueprint
from formslang.model import FormModule, Trigger
from formslang.project_assessment import bind_assessment, current_assessment
from formslang.project_manifest import ManifestEntry, source_id
from formslang.project_model import ProjectDescriptor, ProjectError, RevisionConflict
from formslang.project_store import ProjectStore


def assessment(descriptor, digest="1", engine="v1"):
    payload = blueprint.build([FormModule(name="Demo", triggers=[
        Trigger("WHEN-BUTTON-PRESSED", "AUDIT_API.save;", "form", ""),
    ])])
    entry = ManifestEntry(source_id("db", "api.pkb"), "db", "api.pkb", "database",
                          True, "available", 18, digest * 64)
    original = copy.deepcopy(payload)
    result = bind_assessment(descriptor, (entry,), payload, engines={"rules": engine},
                            options={}, analyzed_at="2026-09-19T12:00:00Z", status="Current")
    assert payload == original
    return result


@pytest.mark.parametrize("change", [{"digest": "2"}, {"engine": "v2"}])
def test_changed_source_or_engine_preserves_but_stales_review(tmp_path, change):
    descriptor = ProjectDescriptor(id="c" * 32, name="Demo")
    store = ProjectStore.create(tmp_path, descriptor)
    try:
        first = assessment(descriptor)
        second = assessment(descriptor, **change)
        assert first["analysis_revision"] != second["analysis_revision"]
        if "engine" in change:
            assert first["source_revision"] == second["source_revision"]
        store.save_assessment(first, expected_revision=None)
        finding = first["blueprint"]["findings"][0]
        store.session.review_blueprint(entity=finding["entity"], revision=finding["revision"],
            action="APPROVE", reviewer="Analyst", comment="Accepted architecture")
        assert store.session.blueprint()["findings"][0]["review_state"] == "APPROVE"
        assert store.session.task_ids() == []
        store.save_assessment(second, expected_revision=first["analysis_revision"])
        reviewed = store.session.blueprint()["findings"][0]
        assert reviewed["review_state"] == "STALE"
        assert len(reviewed["review_history"]) == 1
        assert reviewed["review_history"][0]["reviewer"] == "Analyst"
        assert "human_decision" not in reviewed
    finally:
        store.close()


def test_reopen_no_analysis_and_outer_engine_stales(tmp_path, monkeypatch):
    descriptor = ProjectDescriptor(id="c" * 32, name="Demo")
    store = ProjectStore.create(tmp_path, descriptor)
    saved = assessment(descriptor)
    store.save_assessment(saved, expected_revision=None)
    finding = saved["blueprint"]["findings"][0]
    store.session.review_blueprint(entity=finding["entity"], revision=finding["revision"],
        action="APPROVE", reviewer="Analyst", comment="Accepted architecture")
    store.close()

    def forbidden(*args, **kwargs):
        raise AssertionError("reopening must not analyze")

    monkeypatch.setattr(blueprint, "build", forbidden)
    store = ProjectStore.open(tmp_path)
    try:
        current = current_assessment(store, expected_engines={"rules": "v1"})
        assert current["status"] == "Current" and current["review_revision"] == 1
        stale = current_assessment(store, expected_engines={"rules": "v2"})
        assert stale["status"] == "Stale"
        finding = stale["blueprint"]["findings"][0]
        assert finding["review_state"] == "STALE" and "human_decision" not in finding
        assert store.load_assessment() == saved
    finally:
        store.close()


def test_stale_publication_and_failed_transaction_leave_previous_result(tmp_path):
    descriptor = ProjectDescriptor(id="c" * 32, name="Demo")
    store = ProjectStore.create(tmp_path, descriptor)
    other = ProjectStore.open(tmp_path)
    first = assessment(descriptor)
    second = assessment(descriptor, digest="2")
    try:
        store.save_assessment(first, expected_revision=None)
        with pytest.raises(RevisionConflict):
            other.save_assessment(second, expected_revision=None)
        assert other.load_assessment() == first
        store.session.db.execute("CREATE TEMP TRIGGER fail_snapshot BEFORE INSERT ON blueprint_snapshot BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with pytest.raises(ProjectError):
            store.save_assessment(second, expected_revision=first["analysis_revision"])
        assert store.load_assessment() == first
        assert store.descriptor().analysis_revision == first["analysis_revision"]
        assert store.session.db.execute("SELECT count(*) FROM project_assessment").fetchone()[0] == 1
    finally:
        other.close()
        store.close()


@pytest.mark.parametrize("field,value", [("project_id", "d" * 32), ("source_revision", "0" * 64),
    ("analysis_revision", "0" * 64), ("schema_version", "future/99"), ("status", "Complete")])
def test_malformed_assessment_not_published(tmp_path, field, value):
    descriptor = ProjectDescriptor(id="c" * 32, name="Demo")
    store = ProjectStore.create(tmp_path, descriptor)
    try:
        saved = assessment(descriptor)
        saved[field] = value
        with pytest.raises(ProjectError):
            store.save_assessment(saved, expected_revision=None)
        assert store.load_assessment() is None
    finally:
        store.close()


def test_locked_publication_returns_busy(tmp_path):
    from formslang.project_model import ProjectBusy

    descriptor = ProjectDescriptor(id="c" * 32, name="Demo")
    store = ProjectStore.create(tmp_path, descriptor)
    with sqlite3.connect(store.session.path) as locked:
        locked.execute("BEGIN IMMEDIATE")
        try:
            with pytest.raises(ProjectBusy):
                store.save_assessment(assessment(descriptor), expected_revision=None)
        finally:
            locked.rollback()
            store.close()
