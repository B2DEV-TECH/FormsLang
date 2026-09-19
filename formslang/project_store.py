"""Project transactions over the existing session Store; SQLite owns state."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import replace
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


def contained_path(directory: Path, relative: str) -> Path:
    base = directory.resolve()
    candidate = base / relative_source_path(relative)
    if not candidate.resolve().is_relative_to(base):
        raise ProjectError("Project path escapes its storage directory")
    return candidate


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
                session.db.executescript(SCHEMA)
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
            result.sync_descriptor()
        except Exception:
            result.close()
            raise
        return result

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
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError as exc:
            raise ProjectError("Project descriptor could not be saved; SQLite state is preserved") from exc

    def load_assessment(self) -> dict | None:
        row = self.session.db.execute("SELECT a.payload_json FROM project_assessment a JOIN modernization_project p ON p.analysis_revision=a.revision WHERE p.id=1").fetchone()
        return json.loads(row[0]) if row else None

    def save_assessment(self, assessment: dict, *, expected_revision: str | None) -> None:
        from .project_assessment import validate_assessment

        descriptor = self.descriptor()
        validate_assessment(descriptor, assessment)
        revision = assessment["analysis_revision"]
        db = self.session.db
        try:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT analysis_revision FROM modernization_project WHERE id=1").fetchone()[0]
            if current != expected_revision:
                raise RevisionConflict("Assessment changed; reload before publishing")
            existing = db.execute("SELECT payload_json FROM project_assessment WHERE revision=?", (revision,)).fetchone()
            if existing:
                previous = json.loads(existing[0])
                # Keep the original analysis clock for repeated exports of a revision.
                if {k: v for k, v in previous.items() if k != "analyzed_at"} != {k: v for k, v in assessment.items() if k != "analyzed_at"}:
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
