"""Legacy imports preserve complete SQLite state, including live WAL commits."""

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from formslang import blueprint
from formslang.apexlang import export_apexlang
from formslang.convert import Proposal, build_tasks
from formslang.parser import parse_xml
from formslang.project_migration import import_legacy_session
from formslang.project_model import ProjectDescriptor, ProjectError
from formslang.project_store import ProjectStore
from formslang.store import APPROVED, REJECTED, Store


def seed(path, xml):
    module = parse_xml(xml)
    legacy = Store(path)
    legacy.init_session(module.name, str(xml))
    legacy.add_tasks(build_tasks(module))
    task_id = legacy.task_ids()[0]
    legacy.save_proposal(task_id, Proposal(code="NULL;", apex_target="Page process"))
    legacy.set_decision(task_id, REJECTED, reviewer="Earlier reviewer")
    legacy.set_decision(task_id, APPROVED, code="NULL;", reviewer="Analyst")
    legacy.set_setting("apex_checksum_salt", "A" * 64)
    legacy.save_module_meta(module.name, {"synthetic": True})
    legacy.confirm_block_key("SYNTH", "SYNTHETIC", "ID", by="Analyst")
    legacy.db.execute("INSERT INTO test_case(id,task_id,run_state,run_by) VALUES ('case',?,'passed','Analyst')", (task_id,))
    legacy.db.commit()
    bp = blueprint.build([module])
    legacy.save_blueprint(bp)
    finding = bp["findings"][0]
    legacy.review_blueprint(entity=finding["entity"], revision=finding["revision"],
                            action="DEFER", reviewer="Architect", comment="Needs owner")
    return legacy, module


def table_rows(path):
    with closing(sqlite3.connect(path)) as db:
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {name: db.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall() for name in names}


def test_full_import_keeps_history_and_export_bytes(tmp_path, sample_xml):
    path = tmp_path / "legacy.session.db"
    legacy, module = seed(path, sample_xml)
    config = {"app_id": 321, "name": "Synthetic", "alias": "SYNTHETIC"}
    exported = export_apexlang(legacy, module, tmp_path / "before", config)
    legacy.close()
    before_bytes = path.read_bytes()
    before_rows = table_rows(path)
    project = ProjectStore.create(tmp_path / "project", ProjectDescriptor(id="a" * 32, name="Orders"))
    try:
        result = import_legacy_session(project, path, source_key="legacy/orders")
        copied_path = project.directory / result["relative_store"]
        assert table_rows(copied_path) == before_rows
        copied = Store(copied_path, reconcile_jobs=False)
        try:
            after = export_apexlang(copied, module, tmp_path / "after", config)
            assert Path(after.zip_path).read_bytes() == Path(exported.zip_path).read_bytes()
        finally:
            copied.close()
        assert path.read_bytes() == before_bytes
        assert not result["already_imported"]
        again = import_legacy_session(project, path, source_key="legacy/orders")
        assert again["already_imported"] and again["revision"] == result["revision"]
        assert len(project.module_sessions()) == 1
        assert project.load_assessment() is None
    finally:
        project.close()


def test_live_wal_and_duplicate_names_keep_distinct_identity(tmp_path, sample_xml):
    legacy, _ = seed(tmp_path / "same.session.db", sample_xml)
    legacy.db.execute("PRAGMA journal_mode=WAL")
    legacy.db.execute("PRAGMA wal_autocheckpoint=0")
    legacy.set_setting("committed_in_wal", "keep-me")
    project = ProjectStore.create(tmp_path / "project", ProjectDescriptor(id="b" * 32, name="Orders"))
    try:
        first = import_legacy_session(project, legacy.path, source_key="first/same")
        second = import_legacy_session(project, legacy.path, source_key="second/same")
        assert first["source_id"] != second["source_id"]
        copied = Store(project.directory / first["relative_store"], reconcile_jobs=False)
        assert copied.setting("committed_in_wal") == "keep-me"
        copied.close()
        legacy.set_setting("committed_in_wal", "new-value")
        changed = import_legacy_session(project, legacy.path, source_key="first/same")
        assert changed["revision"] != first["revision"]
    finally:
        project.close()
        legacy.close()


@pytest.mark.parametrize("kind", ["missing", "corrupt", "unrelated", "trigger", "view"])
def test_invalid_database_is_never_adopted(tmp_path, kind, sample_xml):
    source = tmp_path / "source.session.db"
    if kind == "corrupt":
        source.write_bytes(b"corrupt")
    elif kind == "unrelated":
        with closing(sqlite3.connect(source)) as db:
            db.execute("CREATE TABLE secret(data TEXT)")
    elif kind in {"trigger", "view"}:
        legacy, _ = seed(source, sample_xml)
        sql = ("CREATE TRIGGER unknown_trigger AFTER INSERT ON decision BEGIN DELETE FROM proposal; END"
               if kind == "trigger" else "CREATE VIEW unknown_view AS SELECT * FROM proposal")
        legacy.db.execute(sql)
        legacy.db.commit()
        legacy.close()
    before = source.read_bytes() if source.exists() else None
    project = ProjectStore.create(tmp_path / "project", ProjectDescriptor(id="c" * 32, name="Orders"))
    try:
        with pytest.raises(ProjectError):
            import_legacy_session(project, source, source_key="legacy/source")
        assert project.module_sessions() == []
        assert (source.read_bytes() if source.exists() else None) == before
    finally:
        project.close()


def test_failed_link_commit_can_retry_without_overwriting(tmp_path, sample_xml, monkeypatch):
    legacy, _ = seed(tmp_path / "legacy.session.db", sample_xml)
    legacy.close()
    before = hashlib.sha256(legacy.path.read_bytes()).hexdigest()
    project = ProjectStore.create(tmp_path / "project", ProjectDescriptor(id="d" * 32, name="Orders"))
    real_link = project.add_module_session

    def fail_link(*args, **kwargs):
        raise ProjectError("synthetic failure")

    try:
        monkeypatch.setattr(project, "add_module_session", fail_link)
        with pytest.raises(ProjectError):
            import_legacy_session(project, legacy.path, source_key="legacy/source")
        assert project.module_sessions() == []
        monkeypatch.setattr(project, "add_module_session", real_link)
        assert not import_legacy_session(project, legacy.path, source_key="legacy/source")["already_imported"]
        assert hashlib.sha256(legacy.path.read_bytes()).hexdigest() == before
    finally:
        project.close()


def test_old_minimal_and_blueprint_only_sessions(tmp_path):
    project = ProjectStore.create(tmp_path / "project", ProjectDescriptor(id="e" * 32, name="Orders"))
    try:
        for name in ("old", "blueprint"):
            path = tmp_path / (name + ".session.db")
            with closing(sqlite3.connect(path)) as db:
                db.execute("CREATE TABLE session(id INTEGER PRIMARY KEY,title TEXT NOT NULL,source_path TEXT,created_at TEXT)")
                db.execute("INSERT INTO session VALUES (1,'Synthetic','','now')")
                if name == "old":
                    db.execute("CREATE TABLE task(id TEXT PRIMARY KEY,module TEXT,kind TEXT,name TEXT,owner TEXT,verdict TEXT,apex_hint TEXT,source TEXT,lines INTEGER,fingerprint TEXT,meta TEXT,position INTEGER)")
                else:
                    db.execute("CREATE TABLE blueprint_snapshot(id INTEGER PRIMARY KEY,payload TEXT NOT NULL)")
                db.commit()
            result = import_legacy_session(project, path, source_key=name)
            assert (project.directory / result["relative_store"]).is_file()
    finally:
        project.close()


def test_failing_schema_migration_preserves_source_and_project(tmp_path, sample_xml, monkeypatch):
    legacy, _ = seed(tmp_path / "legacy.session.db", sample_xml)
    legacy.close()
    before = legacy.path.read_bytes()
    project = ProjectStore.create(tmp_path / "project", ProjectDescriptor(id="f" * 32, name="Orders"))

    def broken_migration(self):
        raise RuntimeError("private-migration-detail")

    monkeypatch.setattr(Store, "_migrate", broken_migration)
    try:
        with pytest.raises(ProjectError) as error:
            import_legacy_session(project, legacy.path, source_key="legacy/source")
        assert "private-migration-detail" not in str(error.value)
        assert legacy.path.read_bytes() == before
        assert project.module_sessions() == []
        assert not list(project.directory.glob(".legacy-import-*"))
    finally:
        project.close()


def test_backup_deadline_returns_busy(tmp_path, sample_xml, monkeypatch):
    from formslang import project_migration
    from formslang.project_model import ProjectBusy

    legacy, _ = seed(tmp_path / "legacy.session.db", sample_xml)
    legacy.close()
    project = ProjectStore.create(tmp_path / "project", ProjectDescriptor(id="f" * 32, name="Orders"))
    clock = iter((0, 100, 100, 100))
    monkeypatch.setattr(project_migration.time, "monotonic", lambda: next(clock))
    try:
        with pytest.raises(ProjectBusy):
            import_legacy_session(project, legacy.path, source_key="legacy/source")
        assert project.module_sessions() == []
    finally:
        project.close()
