"""Import consistent legacy snapshots without opening or migrating originals as Store."""

from __future__ import annotations

import base64
import hashlib
import os
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path

from .project_manifest import source_id
from .project_model import ProjectBusy, ProjectError, canonical_json
from .project_store import ProjectStore, contained_path
from .store import SCHEMA, Store

BACKUP_TIMEOUT_SECONDS = 10


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _schema(db):
    return db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()


def _validate(db) -> None:
    db.execute("PRAGMA trusted_schema=OFF")
    if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise ProjectError("Legacy database integrity check failed")
    with closing(sqlite3.connect(":memory:")) as reference:
        reference.executescript(SCHEMA)
        allowed = {(r[0], r[1]) for r in _schema(reference)}
    schema = _schema(db)
    for kind, name, _table, sql in schema:
        if (kind, name) not in allowed or kind in {"trigger", "view"}:
            raise ProjectError("Unrecognized legacy database schema")
        if kind == "table" and sql and not sql.upper().startswith("CREATE TABLE"):
            raise ProjectError("Unsupported legacy table definition")
    columns = {r[1] for r in db.execute("PRAGMA table_info(session)")}
    if not {"id", "title", "source_path", "created_at"} <= columns:
        raise ProjectError("Not a FormsLang session")
    sessions = db.execute("SELECT id,title FROM session").fetchall()
    if len(sessions) != 1 or sessions[0][0] != 1 or not str(sessions[0][1] or "").strip():
        raise ProjectError("Legacy session identity is missing")
    tables = {r[1] for r in schema if r[0] == "table"}
    if not tables.intersection({"task", "blueprint_snapshot"}):
        raise ProjectError("Legacy session has no recognized content structure")


def _scalar(value):
    if isinstance(value, bytes):
        return {"sqlite_blob": base64.b64encode(value).decode("ascii")}
    return value


def _rows(db, columns_by_table=None):
    result = {}
    tables = columns_by_table or {
        row[1]: [r[1] for r in db.execute("PRAGMA table_info(" + _quote(row[1]) + ")")]
        for row in _schema(db) if row[0] == "table"
    }
    for table, columns in sorted(tables.items()):
        rows = db.execute("SELECT " + ",".join(map(_quote, columns)) + " FROM " + _quote(table)).fetchall()
        encoded = [[_scalar(value) for value in row] for row in rows]
        result[table] = {"columns": columns, "rows": sorted(encoded, key=canonical_json)}
    return result


def _backup(source: Path, destination: Path) -> None:
    deadline = time.monotonic() + BACKUP_TIMEOUT_SECONDS

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise ProjectBusy("Legacy session is busy; retry after its current operation")

    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)) as original:
        _validate(original)
        with closing(sqlite3.connect(destination)) as copied:
            original.backup(copied, pages=256, progress=progress, sleep=0.05)
            _validate(copied)


def _publish_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except FileExistsError:
        # Retry after a crash may find the previously published, unlinked copy.
        if destination.read_bytes() != source.read_bytes():
            raise ProjectError("Existing migration artifact differs; preserved without overwrite") from None


def import_legacy_session(project: ProjectStore, source: Path, *, source_key: str) -> dict:
    identity = source_id("legacy", source_key)
    source = Path(source).resolve()
    if not source.is_file():
        raise ProjectError("Legacy session is missing; select an existing session")
    if source == project.session.path.resolve():
        raise ProjectError("A project cannot import its own project database")
    directory = project.directory
    try:
        with tempfile.TemporaryDirectory(prefix=".legacy-import-", dir=directory) as staging:
            snapshot = Path(staging) / "snapshot.session.db"
            _backup(source, snapshot)
            snapshot_sha = hashlib.sha256(snapshot.read_bytes()).hexdigest()
            with closing(sqlite3.connect(snapshot)) as db:
                before = _rows(db)
                logical = {"schema": _schema(db), "tables": before}
                revision = hashlib.sha256(canonical_json(logical).encode("utf-8")).hexdigest()
            relative = f"modules/{identity}/{revision}.session.db"
            result = {"source_id": identity, "revision": revision, "relative_store": relative,
                      "snapshot_sha256": snapshot_sha, "already_imported": False}
            existing = next((x for x in project.module_sessions()
                             if x["source_id"] == identity and x["revision"] == revision), None)
            if existing:
                if not contained_path(directory, existing["relative_store"]).is_file():
                    raise ProjectError("Imported session is missing; restore its backup")
                return {**result, "snapshot_sha256": existing["provenance"]["snapshot_sha256"],
                        "already_imported": True}
            backup = contained_path(directory, f"backups/{snapshot_sha}.session.db")
            _publish_file(snapshot, backup)
            migrated_path = Path(staging) / "migrated.session.db"
            # A second SQLite snapshot, not a mutable hardlink to the backup.
            _backup(snapshot, migrated_path)
            migrated = Store(migrated_path, reconcile_jobs=False)
            try:
                after = _rows(migrated.db, {name: facts["columns"] for name, facts in before.items()})
                if after != before:
                    raise ProjectError("Legacy migration changed existing rows; original preserved")
            finally:
                migrated.close()
            target = contained_path(directory, relative)
            _publish_file(migrated_path, target)
            project.add_module_session(identity, revision, relative, {
                "migration_version": "legacy-import/1", "original_path": str(source),
                "snapshot_sha256": snapshot_sha,
            })
            return result
    except ProjectError:
        raise
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        raise ProjectError("Legacy session could not be imported; original preserved") from exc
