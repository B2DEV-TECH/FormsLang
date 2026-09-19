"""Project transactions over the existing session Store; SQLite owns state."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import time
from contextlib import closing, contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from .project_manifest import relative_source_path
from .project_model import (
    ProjectBusy,
    ProjectDescriptor,
    ProjectError,
    RevisionConflict,
    canonical_json,
    descriptor_from_dict,
    descriptor_to_dict,
    validate_descriptor,
)
from .store import Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS modernization_project (
 id INTEGER PRIMARY KEY CHECK(id=1), schema_version TEXT NOT NULL,
 descriptor_json TEXT NOT NULL, analysis_revision TEXT,
 review_revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS project_assessment (
 revision TEXT PRIMARY KEY, source_revision TEXT NOT NULL,
 analyzed_at TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_module_session (
 source_id TEXT NOT NULL, revision TEXT NOT NULL, relative_store TEXT NOT NULL UNIQUE,
 provenance_json TEXT NOT NULL, PRIMARY KEY(source_id,revision)
);
CREATE TRIGGER IF NOT EXISTS project_blueprint_review_revision AFTER INSERT ON blueprint_review
BEGIN
 UPDATE modernization_project SET review_revision=review_revision+1 WHERE id=1;
END;
"""

RUN_SCHEMA = """
CREATE TABLE IF NOT EXISTS project_configuration (
 id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO project_configuration VALUES (1,0);
CREATE TABLE IF NOT EXISTS project_discovery_run (
 run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, inventory_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_discovery_entry (
 run_id TEXT NOT NULL, source_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
 payload_json TEXT NOT NULL, PRIMARY KEY(run_id,source_id), UNIQUE(run_id,ordinal)
);
CREATE TABLE IF NOT EXISTS project_discovery_diagnostic (
 run_id TEXT NOT NULL, ordinal INTEGER NOT NULL, payload_json TEXT NOT NULL,
 PRIMARY KEY(run_id,ordinal)
);
CREATE TABLE IF NOT EXISTS project_job (
 job_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, operation TEXT NOT NULL,
 requested_revision TEXT, requested_configuration INTEGER NOT NULL,
 status TEXT NOT NULL, phase TEXT NOT NULL, processed INTEGER NOT NULL DEFAULT 0,
 total INTEGER, warnings_count INTEGER NOT NULL DEFAULT 0, errors_count INTEGER NOT NULL DEFAULT 0,
 started_at TEXT NOT NULL, finished_at TEXT, cancellation_requested INTEGER NOT NULL DEFAULT 0,
 owner_token TEXT NOT NULL, owner_pid INTEGER NOT NULL, heartbeat TEXT NOT NULL,
 safe_failure_json TEXT, outcome_json TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS project_job_active ON project_job(project_id)
 WHERE status IN ('QUEUED','RUNNING');
CREATE TABLE IF NOT EXISTS project_analysis_run (
 job_id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_derived_source (
 source_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, xml_sha256 TEXT NOT NULL,
 relative_path TEXT NOT NULL, tool_identity_json TEXT NOT NULL
);
"""


def contained_path(directory: Path, relative: str) -> Path:
    base = directory.resolve()
    candidate = base / relative_source_path(relative)
    if not candidate.resolve().is_relative_to(base):
        raise ProjectError("Project path escapes its storage directory")
    return candidate


def replace_mirror(source: Path, destination: Path) -> None:
    """Atomic replace with a bounded Windows reader-sharing retry, never fallback writes."""
    for attempt in range(10):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            if os.name != 'nt' or getattr(exc, 'winerror', None) not in {5, 32, 33} or attempt == 9:
                raise
            time.sleep(.025)


class ProjectStore:
    """One connection owned by one service/worker, never a global shared session."""

    def __init__(self, root: Path, session: Store):
        self.root = root.resolve()
        self.directory = self.root / ".formslang"
        self.session = session
        self.session.db.execute("PRAGMA busy_timeout=1000")

    @classmethod
    def create(cls, root: Path, descriptor: ProjectDescriptor) -> ProjectStore:
        payload = descriptor_to_dict(descriptor)
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        final = root / ".formslang"
        if final.exists() or final.is_symlink():
            raise ProjectError("Project already exists; open it instead")
        with tempfile.TemporaryDirectory(prefix=".project-create-", dir=root) as staging:
            staged_db = Path(staging) / "project.session.db"
            session = Store(staged_db, reconcile_jobs=False)
            try:
                session.db.executescript(SCHEMA + RUN_SCHEMA)
                session.init_session(descriptor.name)
                session.db.execute("INSERT INTO modernization_project VALUES (1,?,?,NULL,0)",
                                   ("formslang-project/1", canonical_json(payload)))
                session.db.commit()
            finally:
                session.close()
            # Reserve the directory exclusively, then atomically link a complete DB.
            # rename() may overwrite an empty destination directory on POSIX.
            try:
                final.mkdir()
                os.link(staged_db, final / "project.session.db")
            except OSError as exc:
                raise ProjectError("Project creation could not publish; inspect destination") from exc
        return cls.open(root)

    @classmethod
    def open(cls, root: Path) -> ProjectStore:
        root = Path(root).resolve()
        directory = root / ".formslang"
        if directory.resolve() != directory:
            raise ProjectError("Project storage directory is redirected")
        path = contained_path(directory, "project.session.db")
        if not path.is_file():
            raise ProjectError("Project database is missing; select an existing project")
        try:
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as check:
                if check.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ProjectError("Project database integrity check failed")
                row = check.execute("SELECT schema_version,descriptor_json FROM modernization_project WHERE id=1").fetchone()
                if not row or row[0] != "formslang-project/1":
                    raise ProjectError("Unsupported project database schema")
                authoritative = descriptor_from_dict(json.loads(row[1]))
        except (sqlite3.Error, json.JSONDecodeError) as exc:
            raise ProjectError("Not a valid FormsLang project database") from exc
        mirror = contained_path(directory, "project.json")
        if mirror.exists():
            try:
                if mirror.stat().st_size > 1024 * 1024:
                    raise ProjectError("Project descriptor exceeds size limit")
                raw = json.loads(mirror.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeError):
                raw = None
            except OSError as exc:
                raise ProjectError("Project descriptor cannot be read") from exc
            if raw is not None and descriptor_from_dict(raw).id != authoritative.id:
                raise ProjectError("Project descriptor identity does not match database")
        result = cls(root, Store(path, reconcile_jobs=False))
        try:
            result._migrate_runs()
            result.sync_descriptor()
        except Exception:
            result.close()
            raise
        return result

    def _migrate_runs(self) -> None:
        db = self.session.db
        required = {'project_configuration', 'project_discovery_run',
                    'project_discovery_entry', 'project_discovery_diagnostic',
                    'project_job', 'project_analysis_run', 'project_derived_source'}
        present = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if required <= present:
            return
        try:
            db.executescript('BEGIN IMMEDIATE;\n' + RUN_SCHEMA + '\nCOMMIT;')
        except sqlite3.Error as exc:
            db.rollback()
            raise ProjectError('Project run schema could not be migrated; existing state is preserved') from exc

    @contextmanager
    def _write(self):
        db = self.session.db
        if db.in_transaction:
            raise ProjectError('Project write requires its own transaction')
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except sqlite3.Error as exc:
            db.rollback()
            if 'locked' in str(exc).lower() or 'busy' in str(exc).lower():
                raise ProjectBusy('Project is busy; retry after the current operation') from exc
            raise ProjectError('Project update failed; previous state is preserved') from exc
        except Exception:
            db.rollback()
            raise

    def configuration_revision(self) -> int:
        return self.session.db.execute('SELECT revision FROM project_configuration WHERE id=1').fetchone()[0]

    def replace_roots(self, roots, *, expected_configuration: int) -> ProjectDescriptor:
        if type(expected_configuration) is not int or expected_configuration < 0:
            raise ProjectError('Invalid configuration precondition')
        with self._write() as db:
            if db.execute("SELECT 1 FROM project_job WHERE status IN ('QUEUED','RUNNING')").fetchone():
                raise ProjectBusy('Analysis is active; retry relink after it finishes')
            if self.configuration_revision() != expected_configuration:
                raise RevisionConflict('Project configuration changed; reload before relinking')
            updated = replace(self.descriptor(), source_roots=roots)
            validate_descriptor(updated)
            db.execute('UPDATE modernization_project SET descriptor_json=? WHERE id=1',
                       (canonical_json(descriptor_to_dict(updated)),))
            db.execute('UPDATE project_configuration SET revision=revision+1 WHERE id=1')
        self.sync_descriptor()
        return updated

    def record_discovery(self, result, *, run_id: str) -> None:
        from .project_discovery import DiscoveryResult
        from .project_manifest import source_id

        if not isinstance(result, DiscoveryResult) or not isinstance(run_id, str) or not re.fullmatch('[a-f0-9]{32}', run_id):
            raise ProjectError('Invalid discovery run')
        with self._write() as db:
            if db.execute('SELECT 1 FROM project_discovery_run WHERE run_id=?', (run_id,)).fetchone():
                raise RevisionConflict('Discovery run is immutable; create a new run')
            db.execute('INSERT INTO project_discovery_run VALUES (?,?,?)',
                       (run_id, datetime.now(timezone.utc).isoformat(), canonical_json(result.inventory)))
            for ordinal, entry in enumerate(result.entries):
                identity = source_id(entry.candidate.root_id, entry.candidate.relative_path)
                db.execute('INSERT INTO project_discovery_entry VALUES (?,?,?,?)',
                           (run_id, identity, ordinal, canonical_json(asdict(entry))))
            for ordinal, item in enumerate(result.diagnostics):
                db.execute('INSERT INTO project_discovery_diagnostic VALUES (?,?,?)',
                           (run_id, ordinal, canonical_json(asdict(item))))

    def discovery(self, run_id: str | None, *, offset=0, limit=50) -> dict:
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise ProjectError('Use a nonnegative offset and limit between 1 and 200')
        db = self.session.db
        row = (db.execute('SELECT * FROM project_discovery_run ORDER BY rowid DESC LIMIT 1').fetchone()
               if run_id is None else db.execute('SELECT * FROM project_discovery_run WHERE run_id=?', (run_id,)).fetchone())
        if row is None:
            return {'available': False, 'entries': [], 'diagnostics': [], 'total': 0, 'diagnostics_total': 0}
        identity = row['run_id']
        entries = db.execute('SELECT payload_json FROM project_discovery_entry WHERE run_id=? ORDER BY ordinal LIMIT ? OFFSET ?',
                             (identity, limit, offset)).fetchall()
        diagnostics = db.execute('SELECT payload_json FROM project_discovery_diagnostic WHERE run_id=? ORDER BY ordinal LIMIT ? OFFSET ?',
                                 (identity, limit, offset)).fetchall()
        return {'available': True, 'run_id': identity, 'created_at': row['created_at'],
                'inventory': json.loads(row['inventory_json']),
                'entries': [json.loads(r[0]) for r in entries],
                'diagnostics': [json.loads(r[0]) for r in diagnostics],
                'total': db.execute('SELECT count(*) FROM project_discovery_entry WHERE run_id=?', (identity,)).fetchone()[0],
                'diagnostics_total': db.execute('SELECT count(*) FROM project_discovery_diagnostic WHERE run_id=?', (identity,)).fetchone()[0],
                'offset': offset, 'limit': limit}

    def descriptor(self) -> ProjectDescriptor:
        row = self.session.db.execute("SELECT descriptor_json FROM modernization_project WHERE id=1").fetchone()
        if not row:
            raise ProjectError("Project metadata is missing")
        return descriptor_from_dict(json.loads(row[0]))

    def sync_descriptor(self) -> None:
        destination = contained_path(self.directory, "project.json")
        payload = canonical_json(descriptor_to_dict(self.descriptor())) + "\n"
        try:
            if destination.is_file() and destination.read_text(encoding="utf-8", errors="replace") == payload:
                return
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                    dir=self.directory, prefix=".descriptor-", delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                except Exception:
                    stream.close()
                    temporary.unlink(missing_ok=True)
                    raise
            try:
                replace_mirror(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError as exc:
            raise ProjectError("Project descriptor could not be saved; SQLite state is preserved") from exc

    def load_assessment(self) -> dict | None:
        row = self.session.db.execute("SELECT a.payload_json FROM project_assessment a JOIN modernization_project p ON p.analysis_revision=a.revision WHERE p.id=1").fetchone()
        return json.loads(row[0]) if row else None

    def save_assessment(self, assessment: dict, *, expected_revision: str | None,
                        job_id: str | None = None, owner_token: str | None = None,
                        expected_configuration: int | None = None) -> None:
        from .project_assessment import validate_assessment

        fenced = any(v is not None for v in (job_id, owner_token, expected_configuration))
        if fenced and (not job_id or not owner_token or type(expected_configuration) is not int):
            raise ProjectError('Publication requires complete job ownership preconditions')
        descriptor = self.descriptor()
        validate_assessment(descriptor, assessment)
        revision = assessment["analysis_revision"]
        db = self.session.db
        try:
            db.execute("BEGIN IMMEDIATE")
            descriptor = self.descriptor()
            validate_assessment(descriptor, assessment)
            if fenced:
                job = db.execute('SELECT * FROM project_job WHERE job_id=? AND project_id=?',
                                 (job_id, descriptor.id)).fetchone()
                if (job is None or job['owner_token'] != owner_token or job['status'] != 'RUNNING'
                        or job['operation'] != 'ANALYZE' or self.configuration_revision() != expected_configuration
                        or job['requested_configuration'] != expected_configuration
                        or job['requested_revision'] != expected_revision):
                    raise RevisionConflict('Project job ownership or configuration changed')
                if job['cancellation_requested']:
                    from .project_jobs import AnalysisCancelled
                    raise AnalysisCancelled('Analysis cancelled before publication')
            elif db.execute("SELECT 1 FROM project_job WHERE status IN ('QUEUED','RUNNING')").fetchone():
                raise ProjectBusy('A project job owns publication; wait for it to finish')
            current = db.execute("SELECT analysis_revision FROM modernization_project WHERE id=1").fetchone()[0]
            if current != expected_revision:
                raise RevisionConflict("Assessment changed; reload before publishing")
            existing = db.execute("SELECT payload_json FROM project_assessment WHERE revision=?", (revision,)).fetchone()
            if existing:
                previous = json.loads(existing[0])
                # Keep the original analysis clock for repeated exports of a revision.
                if canonical_json({k: v for k, v in previous.items() if k != "analyzed_at"}) != canonical_json({k: v for k, v in assessment.items() if k != "analyzed_at"}):
                    raise RevisionConflict("Assessment content differs for the same revision")
                assessment = previous
            else:
                db.execute("INSERT INTO project_assessment VALUES (?,?,?,?)",
                    (revision, assessment["source_revision"], assessment["analyzed_at"], canonical_json(assessment)))
            updated = replace(descriptor, analysis_revision=revision,
                              engine_version=assessment["blueprint"]["engine_version"])
            db.execute("UPDATE modernization_project SET analysis_revision=?,descriptor_json=? WHERE id=1",
                       (revision, canonical_json(descriptor_to_dict(updated))))
            db.execute("INSERT OR REPLACE INTO blueprint_snapshot VALUES (1,?)",
                       (canonical_json(assessment["blueprint"]),))
            if fenced:
                completed = ('COMPLETED_WITH_WARNINGS' if assessment.get('completion_state') in
                             {'INCOMPLETE', 'COMPLETE_WITH_WARNINGS'} or assessment['status'] == 'Incomplete'
                             else 'COMPLETED')
                outcome = {'analysis_revision': revision,
                           'completion_state': assessment.get('completion_state', 'COMPLETE')}
                db.execute('UPDATE project_job SET status=?,finished_at=?,outcome_json=? WHERE job_id=?',
                           (completed, datetime.now(timezone.utc).isoformat(), canonical_json(outcome), job_id))
            db.commit()
        except sqlite3.OperationalError as exc:
            db.rollback()
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                raise ProjectBusy("Project is busy; retry after the current operation") from exc
            raise ProjectError("Assessment could not be published") from exc
        except sqlite3.Error as exc:
            db.rollback()
            raise ProjectError("Assessment could not be published") from exc
        except Exception:
            db.rollback()
            raise
        self.sync_descriptor()

    def add_module_session(self, source_id: str, revision: str, relative_store: str,
                           provenance: dict) -> None:
        if any(not re.fullmatch(r"[a-f0-9]{64}", value) for value in (source_id, revision)):
            raise ProjectError("Invalid module session identity")
        expected = f"modules/{source_id}/{revision}.session.db"
        if relative_store != expected or not contained_path(self.directory, relative_store).is_file():
            raise ProjectError("Invalid module session location")
        with self.session.db:
            self.session.db.execute("INSERT INTO project_module_session VALUES (?,?,?,?)",
                (source_id, revision, relative_store, canonical_json(provenance)))

    def module_sessions(self) -> list[dict]:
        return [{**dict(row), "provenance": json.loads(row["provenance_json"])}
                for row in self.session.db.execute("SELECT * FROM project_module_session ORDER BY source_id,revision")]

    def close(self) -> None:
        self.session.close()
