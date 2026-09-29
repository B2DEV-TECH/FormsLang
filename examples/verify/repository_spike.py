"""WP-10 storage spike; deliberately outside the FormsLang product path.

This tests publication ordering and recovery. It is not a migration format or
a replacement for ProjectStore.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path

_SCHEMA = "formslang-spike-checkpoint/1"
_KIND = re.compile(r"[a-z][a-z0-9_-]{0,39}\Z")
_IDENTITY = re.compile(r"sha256:([a-z][a-z0-9_-]{0,39}):([0-9a-f]{64})\Z")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _object_id(kind: str, body: bytes) -> str:
    digest = hashlib.sha256(b"formslang-object/1\0" + kind.encode("ascii") + b"\0" + body).hexdigest()
    return f"sha256:{kind}:{digest}"


class RepositorySpike:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects = self.root / "objects"
        self.objects.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.root / "repository-spike.db", timeout=5)
        self.db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL)")
        self.db.execute("INSERT OR IGNORE INTO state VALUES (1,0)")
        self.db.execute("CREATE TABLE IF NOT EXISTS publication (revision INTEGER PRIMARY KEY, manifest BLOB NOT NULL, state TEXT NOT NULL)")
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def _object_path(self, identity: str) -> Path:
        match = _IDENTITY.fullmatch(identity) if isinstance(identity, str) else None
        if match is None:
            raise ValueError("invalid object identity")
        return self.objects / match[1] / match[2]

    def put_object(self, kind: str, body: bytes) -> str:
        if not isinstance(kind, str) or _KIND.fullmatch(kind) is None or not isinstance(body, bytes):
            raise ValueError("invalid object kind or bytes")
        identity = _object_id(kind, body)
        destination = self._object_path(identity)
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != body:
                raise ValueError("object identity collision")
            return identity
        staged = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".object-", delete=False) as stream:
                staged = Path(stream.name)
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            if destination.exists():
                if destination.read_bytes() != body:
                    raise ValueError("object identity collision")
            else:
                os.replace(staged, destination)
            return identity
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    def read_object(self, identity: str) -> bytes:
        path = self._object_path(identity)
        body = path.read_bytes()
        kind = _IDENTITY.fullmatch(identity)[1]
        if _object_id(kind, body) != identity:
            raise ValueError("object content does not match identity")
        return body

    def status(self) -> dict:
        revision = self.db.execute("SELECT revision FROM state WHERE id=1").fetchone()[0]
        row = self.db.execute("SELECT state FROM publication WHERE revision=?", (revision,)).fetchone()
        return {"revision": revision, "publication": row[0] if row else None}

    def publish(self, expected_revision: int, object_ids: list[str], event: dict, *, fail_at=None) -> dict:
        if type(expected_revision) is not int or expected_revision < 0 or not isinstance(object_ids, list):
            raise ValueError("invalid publication request")
        if not isinstance(event, dict) or not event:
            raise ValueError("event is required")
        for identity in object_ids:
            self.read_object(identity)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            revision = self.db.execute("SELECT revision FROM state WHERE id=1").fetchone()[0]
            if revision != expected_revision:
                raise ValueError("revision changed")
            previous = self.db.execute("SELECT manifest,state FROM publication WHERE revision=?", (revision,)).fetchone()
            if previous is not None and previous[1] != "PUBLISHED":
                raise ValueError("previous publication pending")
            prior = json.loads(previous[0]) if previous else {"objects": [], "events": []}
            manifest = _json_bytes({"schema": _SCHEMA, "revision": revision + 1,
                                    "objects": sorted(set(prior["objects"]) | set(object_ids)),
                                    "events": [*prior["events"], event]})
            self.db.execute("INSERT INTO publication VALUES (?,?,?)", (revision + 1, manifest, "PENDING"))
            self.db.execute("UPDATE state SET revision=? WHERE id=1", (revision + 1,))
            if fail_at == "before_commit":
                raise RuntimeError("injected before commit")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        if fail_at == "after_commit":
            raise RuntimeError("injected after commit")
        self._publish_checkpoint(revision + 1, manifest)
        return {"revision": revision + 1, "checkpoint_sha256": hashlib.sha256(manifest).hexdigest()}

    def _publish_checkpoint(self, revision: int, manifest: bytes) -> None:
        for identity in json.loads(manifest)["objects"]:
            try:
                self.read_object(identity)
            except FileNotFoundError as exc:
                raise ValueError("missing accepted object") from exc
        staged = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix=".checkpoint-", delete=False) as stream:
                staged = Path(stream.name)
                stream.write(manifest)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(staged, self.root / "checkpoint.json")
            self.db.execute("UPDATE publication SET state='PUBLISHED' WHERE revision=? AND state='PENDING'", (revision,))
            self.db.commit()
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    def recover(self) -> int:
        rows = self.db.execute("SELECT revision,manifest FROM publication WHERE state='PENDING' ORDER BY revision").fetchall()
        for revision, manifest in rows:
            self._publish_checkpoint(revision, manifest)
        return len(rows)
