"""Session store for the conversion workbench.

SQLite from the standard library, one file per session. The point is not
persistence for its own sake: a migration review is interrupted constantly,
and a reviewer must be able to close the window, come back tomorrow and find
every decision, every proposal and every version of the code exactly where
they left it.

Every decision is kept, including the ones that were later changed. What was
approved, when, and against which model answer is the audit trail any
review process is entitled to ask for.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .convert import ConversionTask, Proposal

PENDING, APPROVED, REJECTED, NEEDS_WORK = "pending", "approved", "rejected", "needs_work"
STATES = (PENDING, APPROVED, REJECTED, NEEDS_WORK)

SCHEMA = """
CREATE TABLE IF NOT EXISTS session (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    title       TEXT NOT NULL,
    source_path TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task (
    id          TEXT PRIMARY KEY,
    module      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    name        TEXT NOT NULL,
    owner       TEXT NOT NULL DEFAULT '',
    verdict     TEXT NOT NULL DEFAULT '',
    apex_hint   TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL,
    lines       INTEGER NOT NULL DEFAULT 0,
    fingerprint TEXT NOT NULL DEFAULT '',
    meta        TEXT NOT NULL DEFAULT '{}',
    position    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS proposal (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL REFERENCES task(id),
    created_at  TEXT NOT NULL,
    apex_target TEXT NOT NULL DEFAULT '',
    code        TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT '[]',
    questions   TEXT NOT NULL DEFAULT '[]',
    confidence  REAL NOT NULL DEFAULT 0,
    provider    TEXT NOT NULL DEFAULT '',
    model       TEXT NOT NULL DEFAULT '',
    error       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS proposal_task ON proposal(task_id, id);

CREATE TABLE IF NOT EXISTS decision (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL REFERENCES task(id),
    state       TEXT NOT NULL,
    code        TEXT NOT NULL DEFAULT '',
    comment     TEXT NOT NULL DEFAULT '',
    reviewer    TEXT NOT NULL DEFAULT '',
    decided_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS decision_task ON decision(task_id, id);
"""


def _now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


@dataclass
class TaskView:
    """A task with its latest proposal and current decision, for the UI."""

    task: dict
    proposal: dict | None
    state: str
    code: str
    comment: str
    reviewer: str
    decided_at: str

    def to_dict(self) -> dict:
        return {
            **self.task,
            "proposal": self.proposal,
            "state": self.state,
            "final_code": self.code,
            "comment": self.comment,
            "reviewer": self.reviewer,
            "decided_at": self.decided_at,
        }


class Store:
    """One conversion session, backed by a single .db file."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # No WAL: on Windows it keeps file handles alive and makes a session
        # file awkward to move, copy or delete while the tool is running.
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    # -- session ---------------------------------------------------------

    def init_session(self, title: str, source_path: str = "") -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO session (id, title, source_path, created_at) "
            "VALUES (1, ?, ?, ?)",
            (title, source_path, _now()),
        )
        self.db.commit()

    def session(self) -> dict:
        row = self.db.execute("SELECT * FROM session WHERE id = 1").fetchone()
        return dict(row) if row else {}

    # -- tasks -----------------------------------------------------------

    def add_tasks(self, tasks: list[ConversionTask]) -> int:
        """Insert tasks, keeping any that already exist (and their history)."""
        added = 0
        for i, t in enumerate(tasks):
            cur = self.db.execute(
                "INSERT OR IGNORE INTO task (id, module, kind, name, owner, verdict, "
                "apex_hint, source, lines, fingerprint, meta, position) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    t.id, t.module, t.kind, t.name, t.owner, t.verdict, t.apex_hint,
                    t.source, t.lines, t.fingerprint,
                    json.dumps({
                        "builtins": [
                            {"name": n, "verdict": v, "apex": a} for n, v, a in t.builtins
                        ],
                        "item_refs": t.item_refs,
                        "globals": t.globals_used,
                    }),
                    i,
                ),
            )
            added += cur.rowcount
        self.db.commit()
        return added

    def task_ids(self) -> list[str]:
        rows = self.db.execute("SELECT id FROM task ORDER BY position").fetchall()
        return [r["id"] for r in rows]

    def get_task(self, task_id: str) -> ConversionTask | None:
        row = self.db.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        meta = json.loads(row["meta"] or "{}")
        return ConversionTask(
            id=row["id"], module=row["module"], kind=row["kind"], name=row["name"],
            owner=row["owner"], verdict=row["verdict"], apex_hint=row["apex_hint"],
            source=row["source"], lines=row["lines"], fingerprint=row["fingerprint"],
            builtins=[(b["name"], b["verdict"], b["apex"]) for b in meta.get("builtins", [])],
            item_refs=meta.get("item_refs", []),
            globals_used=meta.get("globals", []),
        )

    def pending_tasks(self) -> list[ConversionTask]:
        """Tasks with no proposal yet -- what a 'convert all' run must do."""
        rows = self.db.execute(
            "SELECT t.id FROM task t "
            "WHERE NOT EXISTS (SELECT 1 FROM proposal p WHERE p.task_id = t.id) "
            "ORDER BY t.position"
        ).fetchall()
        return [t for t in (self.get_task(r["id"]) for r in rows) if t is not None]

    # -- proposals -------------------------------------------------------

    def save_proposal(self, task_id: str, p: Proposal) -> int:
        cur = self.db.execute(
            "INSERT INTO proposal (task_id, created_at, apex_target, code, notes, "
            "questions, confidence, provider, model, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id, _now(), p.apex_target, p.code, json.dumps(p.notes),
                json.dumps(p.open_questions), p.confidence, p.provider, p.model, p.error,
            ),
        )
        self.db.commit()
        return int(cur.lastrowid or 0)

    def latest_proposal(self, task_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM proposal WHERE task_id = ? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "apex_target": row["apex_target"],
            "code": row["code"],
            "notes": json.loads(row["notes"] or "[]"),
            "open_questions": json.loads(row["questions"] or "[]"),
            "confidence": row["confidence"],
            "provider": row["provider"],
            "model": row["model"],
            "error": row["error"],
        }

    # -- decisions -------------------------------------------------------

    def set_decision(
        self, task_id: str, state: str, code: str = "", comment: str = "", reviewer: str = ""
    ) -> None:
        if state not in STATES:
            raise ValueError(f"unknown state {state!r}")
        self.db.execute(
            "INSERT INTO decision (task_id, state, code, comment, reviewer, decided_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, state, code, comment, reviewer, _now()),
        )
        self.db.commit()

    def latest_decision(self, task_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM decision WHERE task_id = ? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        return dict(row) if row else None

    def history(self, task_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT state, comment, reviewer, decided_at FROM decision "
            "WHERE task_id = ? ORDER BY id DESC",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- views -----------------------------------------------------------

    def view(self, task_id: str) -> TaskView | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        proposal = self.latest_proposal(task_id)
        decision = self.latest_decision(task_id)
        code = (decision or {}).get("code") or (proposal or {}).get("code", "")
        return TaskView(
            task=task.to_dict(),
            proposal=proposal,
            state=(decision or {}).get("state", PENDING),
            code=code,
            comment=(decision or {}).get("comment", ""),
            reviewer=(decision or {}).get("reviewer", ""),
            decided_at=(decision or {}).get("decided_at", ""),
        )

    def all_views(self) -> list[TaskView]:
        return [v for v in (self.view(i) for i in self.task_ids()) if v is not None]

    def stats(self) -> dict:
        views = self.all_views()
        counts = {s: 0 for s in STATES}
        for v in views:
            counts[v.state] = counts.get(v.state, 0) + 1
        proposed = sum(1 for v in views if v.proposal)
        return {
            "tasks": len(views),
            "proposed": proposed,
            "unproposed": len(views) - proposed,
            **counts,
        }

    # -- export ----------------------------------------------------------

    def export(self, out_dir: Path | str) -> tuple[Path, Path]:
        """Write everything approved, plus the full session record.

        Two files: the PL/SQL a developer can paste into APEX, and the JSON
        that says who approved what, from which model answer.
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        views = self.all_views()
        approved = [v for v in views if v.state == APPROVED]

        sql_path = out / "approved.sql"
        chunks = [
            "-- FormsLang -- approved conversions",
            f"-- session: {self.session().get('title', '')}",
            f"-- exported: {_now()}",
            f"-- units: {len(approved)} approved of {len(views)} reviewed",
            "-- Reviewed by a human, but not executed by FormsLang. Test before use.",
            "",
        ]
        for v in approved:
            t = v.task
            target = (v.proposal or {}).get("apex_target", "")
            chunks.append(f"-- {'=' * 68}")
            chunks.append(f"-- {t['module']} :: {t['kind']} {t['title']}")
            if target:
                chunks.append(f"-- APEX target: {target}")
            if v.reviewer:
                chunks.append(f"-- approved by: {v.reviewer} at {v.decided_at}")
            chunks.append(f"-- {'=' * 68}")
            chunks.append(v.code.rstrip() + "\n")
        sql_path.write_text("\n".join(chunks), encoding="utf-8")

        json_path = out / "session.json"
        json_path.write_text(
            json.dumps(
                {
                    "session": self.session(),
                    "stats": self.stats(),
                    "tasks": [
                        {**v.to_dict(), "history": self.history(v.task["id"])}
                        for v in views
                    ],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return sql_path, json_path
