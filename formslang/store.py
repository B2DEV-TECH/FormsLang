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

from . import policy, rules, sensitive, testspec
from .ai import setting as ai_setting
from .analysis import ENGINE_VERSION, UnitAnalysis
from .convert import ConversionTask, Proposal
from .depgraph import DepGraph
from .testspec import TestCase

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
    behavior    TEXT NOT NULL DEFAULT '',
    behavior_reason TEXT NOT NULL DEFAULT '',
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

-- One row per task: what the deterministic engine concluded about it.
-- Cached rather than recomputed on every request, but never trusted blindly:
-- engine_version says which rules produced it, and a mismatch means stale.
CREATE TABLE IF NOT EXISTS unit_analysis (
    task_id        TEXT PRIMARY KEY REFERENCES task(id),
    engine_version TEXT NOT NULL DEFAULT '',
    risk_level     TEXT NOT NULL DEFAULT '',
    risk_score     REAL NOT NULL DEFAULT 0,
    behavior       TEXT NOT NULL DEFAULT '',
    payload        TEXT NOT NULL DEFAULT '{}',
    computed_at    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS analysis_risk ON unit_analysis(risk_level);

-- Test specifications, written from the original Forms behaviour. The
-- generated text and the reviewer's answer to it live in the same row: a
-- case is only worth anything once a person has accepted or rejected it.
CREATE TABLE IF NOT EXISTS test_case (
    id             TEXT PRIMARY KEY,
    task_id        TEXT NOT NULL REFERENCES task(id),
    kind           TEXT NOT NULL DEFAULT '',
    origin         TEXT NOT NULL DEFAULT '',
    title          TEXT NOT NULL DEFAULT '',
    payload        TEXT NOT NULL DEFAULT '{}',
    state          TEXT NOT NULL DEFAULT 'pending',
    reviewer       TEXT NOT NULL DEFAULT '',
    comment        TEXT NOT NULL DEFAULT '',
    position       INTEGER NOT NULL DEFAULT 0,
    spec_version   TEXT NOT NULL DEFAULT '',
    engine_version TEXT NOT NULL DEFAULT '',
    generated_at   TEXT NOT NULL DEFAULT '',
    decided_at     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS test_case_task ON test_case(task_id, position);

-- Module-level facts that are not derivable from the task list alone:
-- object counts, dependency edges, whatever a later phase measures once
-- per loaded module.
CREATE TABLE IF NOT EXISTS module_meta (
    module      TEXT PRIMARY KEY,
    payload     TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL DEFAULT ''
);

-- One row per pipeline stage timing. Wall-clock only -- see telemetry.py
-- for why CPU/memory are not sampled. error_kind is the exception's class
-- name, never str(exception): a stage can fail while holding source text
-- or a model answer, and neither may ever land in this table.
CREATE TABLE IF NOT EXISTS stage_timing (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    stage        TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    duration_ms  REAL NOT NULL DEFAULT 0,
    item_count   INTEGER NOT NULL DEFAULT 0,
    ok           INTEGER NOT NULL DEFAULT 1,
    error_kind   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS stage_timing_stage ON stage_timing(stage, id);

-- One row per "convert" run. This is the durable half of Workbench.job --
-- that dict lives in memory and is gone the moment the process restarts;
-- this row is what lets the UI say "that run was interrupted, N units
-- never got a proposal" instead of silently forgetting it happened.
-- A row left at status='running' after a restart is not a queryable
-- steady state -- see Store.reconcile_job_runs, called once at open().
CREATE TABLE IF NOT EXISTS job_run (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at        TEXT NOT NULL,
    ended_at          TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'running',
    total             INTEGER NOT NULL DEFAULT 0,
    done              INTEGER NOT NULL DEFAULT 0,
    failed            INTEGER NOT NULL DEFAULT 0,
    cancel_requested  INTEGER NOT NULL DEFAULT 0
);
"""

JOB_RUNNING, JOB_COMPLETED, JOB_CANCELLED, JOB_CRASHED = (
    "running", "completed", "cancelled", "crashed",
)

# Columns added after the first release. New tables come free from
# CREATE TABLE IF NOT EXISTS above; new columns do not, so they are applied
# here against whatever the file already has.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    # Snapshot of what the reviewer was looking at when they decided. Kept on
    # the decision row on purpose: if the rules change next month, the record
    # still says what the risk read at the moment of approval.
    ("decision", "risk_level", "TEXT NOT NULL DEFAULT ''"),
    ("decision", "behavior", "TEXT NOT NULL DEFAULT ''"),
    ("decision", "engine_version", "TEXT NOT NULL DEFAULT ''"),
    # The model's own reading of the behaviour, kept apart from the
    # rule engine's so the two can be compared instead of blended.
    ("proposal", "behavior", "TEXT NOT NULL DEFAULT ''"),
    ("proposal", "behavior_reason", "TEXT NOT NULL DEFAULT ''"),
    # Whether someone actually ran this case against the migrated unit, and
    # what happened -- distinct from the reviewer's accept/reject above, and
    # never touched by save_test_cases: a regeneration must not erase a run.
    ("test_case", "run_state", "TEXT NOT NULL DEFAULT 'not_run'"),
    ("test_case", "run_by", "TEXT NOT NULL DEFAULT ''"),
    ("test_case", "run_notes", "TEXT NOT NULL DEFAULT ''"),
    ("test_case", "run_at", "TEXT NOT NULL DEFAULT ''"),
)


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
    analysis: dict | None = None

    def to_dict(self) -> dict:
        return {
            **self.task,
            "proposal": self.proposal,
            "state": self.state,
            "final_code": self.code,
            "comment": self.comment,
            "reviewer": self.reviewer,
            "decided_at": self.decided_at,
            "analysis": self.analysis,
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
        self._migrate()
        self.db.commit()
        self.reconcile_job_runs()

    def _migrate(self) -> None:
        """Add columns that older session files do not have yet.

        A session file written by an earlier build must keep opening. Tables
        are handled by CREATE TABLE IF NOT EXISTS; columns need this.
        """
        for table, column, decl in _ADDED_COLUMNS:
            rows = self.db.execute(f"PRAGMA table_info({table})").fetchall()
            if not rows:
                continue
            if column in {r["name"] for r in rows}:
                continue
            self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

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
            owner=row["owner"], verdict=row["verdict"] or rules.UNKNOWN,
            apex_hint=row["apex_hint"],
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
            "questions, confidence, provider, model, behavior, behavior_reason, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id, _now(), p.apex_target, p.code, json.dumps(p.notes),
                json.dumps(p.open_questions), p.confidence, p.provider, p.model,
                p.behavior, p.behavior_reason, p.error,
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
            "behavior": row["behavior"],
            "behavior_reason": row["behavior_reason"],
            "error": row["error"],
        }

    # -- decisions -------------------------------------------------------

    def set_decision(
        self, task_id: str, state: str, code: str = "", comment: str = "", reviewer: str = ""
    ) -> None:
        if state not in STATES:
            raise ValueError(f"unknown state {state!r}")
        # Freeze what the engine was saying at the moment of the decision. The
        # rules will keep improving; the record of what the reviewer approved
        # against must not move with them.
        row = self.db.execute(
            "SELECT risk_level, behavior, engine_version FROM unit_analysis WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        snapshot = dict(row) if row else {}
        self.db.execute(
            "INSERT INTO decision (task_id, state, code, comment, reviewer, decided_at, "
            "risk_level, behavior, engine_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id, state, code, comment, reviewer, _now(),
                snapshot.get("risk_level", ""),
                snapshot.get("behavior", ""),
                snapshot.get("engine_version", ""),
            ),
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
            "SELECT state, comment, reviewer, decided_at, risk_level, behavior, "
            "engine_version FROM decision WHERE task_id = ? ORDER BY id DESC",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- analysis --------------------------------------------------------

    def save_analysis(self, item: UnitAnalysis) -> None:
        """Store (or replace) the deterministic analysis of one task."""
        self.db.execute(
            "INSERT INTO unit_analysis (task_id, engine_version, risk_level, risk_score, "
            "behavior, payload, computed_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET engine_version = excluded.engine_version, "
            "risk_level = excluded.risk_level, risk_score = excluded.risk_score, "
            "behavior = excluded.behavior, payload = excluded.payload, "
            "computed_at = excluded.computed_at",
            (
                item.task_id, item.engine_version, item.risk.level, item.risk.score,
                item.behavior.value,
                json.dumps(item.to_dict(), ensure_ascii=False),
                _now(),
            ),
        )
        self.db.commit()

    def save_analyses(self, items: list[UnitAnalysis]) -> int:
        for item in items:
            self.save_analysis(item)
        return len(items)

    def analysis_payload(self, task_id: str) -> dict | None:
        """The stored analysis as the UI consumes it, or None if never run."""
        row = self.db.execute(
            "SELECT payload, computed_at, engine_version FROM unit_analysis WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["payload"] or "{}")
        except json.JSONDecodeError:
            # A corrupt row is a missing row: better no analysis than a wrong one.
            return None
        payload["computed_at"] = row["computed_at"]
        payload["stale"] = row["engine_version"] != ENGINE_VERSION
        return payload

    def get_analysis(self, task_id: str) -> UnitAnalysis | None:
        payload = self.analysis_payload(task_id)
        return UnitAnalysis.from_dict(payload) if payload else None

    def all_analyses(self) -> list[UnitAnalysis]:
        """Every stored analysis, in task order. Missing ones are simply absent."""
        out: list[UnitAnalysis] = []
        for task_id in self.task_ids():
            item = self.get_analysis(task_id)
            if item is not None:
                out.append(item)
        return out

    def analysis_coverage(self) -> dict:
        """How much of the session has an analysis, and how much of it is stale.

        The dashboard needs this to avoid quoting a distribution as if it
        covered everything when a third of the units were never measured.
        """
        total = len(self.task_ids())
        rows = self.db.execute(
            "SELECT engine_version FROM unit_analysis"
        ).fetchall()
        analysed = len(rows)
        stale = sum(1 for r in rows if r["engine_version"] != ENGINE_VERSION)
        return {
            "tasks": total,
            "analysed": analysed,
            "missing": max(total - analysed, 0),
            "stale": stale,
            "engine_version": ENGINE_VERSION,
        }

    def stale_task_ids(self) -> list[str]:
        """Tasks with no analysis, or one computed under different rules."""
        rows = self.db.execute(
            "SELECT t.id FROM task t "
            "LEFT JOIN unit_analysis a ON a.task_id = t.id "
            "WHERE a.task_id IS NULL OR a.engine_version <> ? "
            "ORDER BY t.position",
            (ENGINE_VERSION,),
        ).fetchall()
        return [r["id"] for r in rows]

    # -- module metadata -------------------------------------------------

    def save_module_meta(self, module: str, payload: dict) -> None:
        self.db.execute(
            "INSERT INTO module_meta (module, payload, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(module) DO UPDATE SET payload = excluded.payload, "
            "updated_at = excluded.updated_at",
            (module, json.dumps(payload, ensure_ascii=False), _now()),
        )
        self.db.commit()

    def module_meta(self, module: str) -> dict | None:
        row = self.db.execute(
            "SELECT payload, updated_at FROM module_meta WHERE module = ?", (module,)
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["payload"] or "{}")
        except json.JSONDecodeError:
            return None
        payload["module"] = module
        payload["updated_at"] = row["updated_at"]
        return payload

    def save_graph(self, module: str, graph: DepGraph) -> None:
        """Persist the dependency graph beside the module it describes.

        It lives in ``module_meta`` as one JSON document rather than in
        tables of its own: a graph is only ever read whole, for one module
        at a time, and this way a session file stays legible to anyone with
        sqlite3 and no knowledge of this schema.
        """
        meta = self.module_meta(module) or {}
        meta.pop("updated_at", None)
        meta["graph"] = graph.to_dict()
        meta["graph_summary"] = graph.summary()
        self.save_module_meta(module, meta)

    def graph(self, module: str) -> DepGraph | None:
        raw = (self.module_meta(module) or {}).get("graph")
        return DepGraph.from_dict(raw) if raw else None

    def all_module_meta(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT module FROM module_meta ORDER BY module"
        ).fetchall()
        return [m for m in (self.module_meta(r["module"]) for r in rows) if m is not None]

    # -- test specifications ---------------------------------------------

    def save_test_cases(self, task_id: str, cases: list[TestCase]) -> dict:
        """Store a freshly generated specification without losing the review.

        A case keeps its id as long as its text does not change, so a
        regeneration under new rules re-writes the wording and leaves every
        accept and reject exactly where the reviewer put it. Cases that
        vanish are removed only while still pending: a case someone answered
        is evidence, and deleting evidence because the rules moved is
        precisely the silent drift this store exists to prevent.
        """
        now = _now()
        existing = {
            r["id"]: r for r in self.db.execute(
                "SELECT * FROM test_case WHERE task_id = ?", (task_id,)
            ).fetchall()
        }
        fresh_ids = set()
        for position, case in enumerate(cases):
            fresh_ids.add(case.id)
            payload = json.dumps(case.to_dict(), ensure_ascii=False)
            if case.id in existing:
                self.db.execute(
                    "UPDATE test_case SET kind = ?, origin = ?, title = ?, payload = ?, "
                    "position = ?, spec_version = ?, engine_version = ?, generated_at = ? "
                    "WHERE id = ?",
                    (case.kind, case.origin, case.title, payload, position,
                     case.version, ENGINE_VERSION, now, case.id),
                )
                continue
            self.db.execute(
                "INSERT INTO test_case (id, task_id, kind, origin, title, payload, state, "
                "position, spec_version, engine_version, generated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (case.id, task_id, case.kind, case.origin, case.title, payload,
                 testspec.PENDING, position, case.version, ENGINE_VERSION, now),
            )
        gone = [
            r["id"] for r in existing.values()
            if r["id"] not in fresh_ids and r["state"] == testspec.PENDING
        ]
        for case_id in gone:
            self.db.execute("DELETE FROM test_case WHERE id = ?", (case_id,))
        self.db.commit()
        return {
            "written": len(cases),
            "kept": len(fresh_ids & set(existing)),
            "dropped": len(gone),
            "orphaned": len(set(existing) - fresh_ids - set(gone)),
        }

    def _case_row(self, row: sqlite3.Row) -> dict:
        try:
            payload = json.loads(row["payload"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        return {
            **payload,
            "id": row["id"],
            "task_id": row["task_id"],
            "kind": row["kind"],
            "origin": row["origin"],
            "title": row["title"],
            "state": row["state"],
            "reviewer": row["reviewer"],
            "comment": row["comment"],
            "generated_at": row["generated_at"],
            "decided_at": row["decided_at"],
            "run_state": row["run_state"],
            "run_by": row["run_by"],
            "run_notes": row["run_notes"],
            "run_at": row["run_at"],
            # Written under rules that have since moved. Shown, never hidden:
            # a reviewer is entitled to know the case is older than the engine.
            "stale": row["engine_version"] != ENGINE_VERSION
            or row["spec_version"] != testspec.VERSION,
        }

    def test_cases(self, task_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM test_case WHERE task_id = ? ORDER BY position, id", (task_id,)
        ).fetchall()
        return [self._case_row(r) for r in rows]

    def all_test_cases(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT c.* FROM test_case c JOIN task t ON t.id = c.task_id "
            "ORDER BY t.position, c.position, c.id"
        ).fetchall()
        return [self._case_row(r) for r in rows]

    def decide_test_case(self, case_id: str, state: str, reviewer: str = "",
                         comment: str = "") -> bool:
        """Record a reviewer's answer to one case. Unknown states are refused."""
        if state not in testspec.CASE_STATES:
            return False
        cur = self.db.execute(
            "UPDATE test_case SET state = ?, reviewer = ?, comment = ?, decided_at = ? "
            "WHERE id = ?",
            (state, reviewer, comment, _now(), case_id),
        )
        self.db.commit()
        return cur.rowcount > 0

    def record_test_run(self, case_id: str, run_state: str, run_by: str = "",
                        run_notes: str = "") -> bool:
        """Record what happened when someone actually ran this case.

        Kept apart from :meth:`decide_test_case` on purpose: accepting a
        case is a judgement about its wording, running it is a fact about
        the migrated unit, and a case can be re-run any number of times
        without ever being re-reviewed.
        """
        if run_state not in testspec.RUN_STATES:
            return False
        cur = self.db.execute(
            "UPDATE test_case SET run_state = ?, run_by = ?, run_notes = ?, run_at = ? "
            "WHERE id = ?",
            (run_state, run_by, run_notes, _now(), case_id),
        )
        self.db.commit()
        return cur.rowcount > 0

    def stale_test_task_ids(self) -> list[str]:
        """Tasks with no specification, or one written under older rules."""
        rows = self.db.execute(
            "SELECT t.id, "
            "SUM(CASE WHEN c.id IS NULL THEN 1 ELSE 0 END) AS missing, "
            "SUM(CASE WHEN c.engine_version <> ? OR c.spec_version <> ? THEN 1 ELSE 0 END) "
            "AS stale FROM task t LEFT JOIN test_case c ON c.task_id = t.id "
            "GROUP BY t.id, t.position ORDER BY t.position",
            (ENGINE_VERSION, testspec.VERSION),
        ).fetchall()
        return [r["id"] for r in rows if r["missing"] or r["stale"]]

    def test_coverage(self) -> dict:
        """How much of the session has a specification, and how reviewed it is."""
        total = len(self.task_ids())
        rows = self.db.execute(
            "SELECT DISTINCT task_id FROM test_case"
        ).fetchall()
        cases = self.all_test_cases()
        out = testspec.summarize(cases)
        out.update({
            "tasks": total,
            "specified": len(rows),
            "missing": max(total - len(rows), 0),
        })
        return out

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
            analysis=self.analysis_payload(task_id),
        )

    def all_views(self) -> list[TaskView]:
        return [v for v in (self.view(i) for i in self.task_ids()) if v is not None]

    # -- telemetry ---------------------------------------------------------

    def record_stage(
        self, name: str, duration_ms: float, item_count: int = 0,
        ok: bool = True, error_kind: str = "",
    ) -> None:
        """Persist one stage timing. See telemetry.stage() -- the recorder
        this method is built to be passed as."""
        self.db.execute(
            "INSERT INTO stage_timing (stage, started_at, duration_ms, item_count, "
            "ok, error_kind) VALUES (?, ?, ?, ?, ?, ?)",
            (name, _now(), duration_ms, item_count, 1 if ok else 0, error_kind),
        )
        self.db.commit()

    def stage_summary(self) -> dict:
        """count/min/p50/p95/max/total per stage, for the performance baseline.

        Deliberately not a report of what the numbers *should* be -- this is
        only ever what was actually measured on this machine, this session.
        """
        from . import telemetry

        rows = self.db.execute(
            "SELECT stage, duration_ms, ok FROM stage_timing ORDER BY stage, id"
        ).fetchall()
        by_stage: dict[str, list[float]] = {}
        failures: dict[str, int] = {}
        for r in rows:
            by_stage.setdefault(r["stage"], []).append(r["duration_ms"])
            if not r["ok"]:
                failures[r["stage"]] = failures.get(r["stage"], 0) + 1
        return {
            stage: {**telemetry.summarize(durations), "failed": failures.get(stage, 0)}
            for stage, durations in by_stage.items()
        }

    # -- job runs ------------------------------------------------------

    def reconcile_job_runs(self) -> int:
        """Flip any run left at 'running' to 'crashed'.

        Called once when a session file is opened. A row can only be stuck
        at 'running' if the process that owned it never reached start_job's
        finally block -- a crash, a killed process, a forced shutdown. Runs
        this method itself starts and finishes cannot trigger it; it only
        ever sees what an *earlier* process left behind.
        """
        cur = self.db.execute(
            "UPDATE job_run SET status = ?, ended_at = ? "
            "WHERE status = ?",
            (JOB_CRASHED, _now(), JOB_RUNNING),
        )
        self.db.commit()
        return cur.rowcount

    def start_job_run(self, total: int) -> int:
        cur = self.db.execute(
            "INSERT INTO job_run (started_at, status, total) VALUES (?, ?, ?)",
            (_now(), JOB_RUNNING, total),
        )
        self.db.commit()
        return int(cur.lastrowid or 0)

    def update_job_run(self, run_id: int, done: int, failed: int) -> None:
        self.db.execute(
            "UPDATE job_run SET done = ?, failed = ? WHERE id = ?",
            (done, failed, run_id),
        )
        self.db.commit()

    def finish_job_run(self, run_id: int, status: str) -> None:
        if status not in (JOB_COMPLETED, JOB_CANCELLED, JOB_CRASHED):
            raise ValueError(f"unknown job_run status {status!r}")
        self.db.execute(
            "UPDATE job_run SET status = ?, ended_at = ? WHERE id = ?",
            (status, _now(), run_id),
        )
        self.db.commit()

    def request_job_cancel(self, run_id: int) -> bool:
        """Set the flag _run_job polls between tasks. True if the run
        exists and was still running -- False for an unknown or already
        finished id, so the caller can tell a no-op from a real request."""
        cur = self.db.execute(
            "UPDATE job_run SET cancel_requested = 1 WHERE id = ? AND status = ?",
            (run_id, JOB_RUNNING),
        )
        self.db.commit()
        return cur.rowcount > 0

    def is_job_cancel_requested(self, run_id: int) -> bool:
        row = self.db.execute(
            "SELECT cancel_requested FROM job_run WHERE id = ?", (run_id,)
        ).fetchone()
        return bool(row and row["cancel_requested"])

    def last_job_run(self) -> dict | None:
        """The most recent run, finished or not -- what the UI needs to say
        'this run was interrupted, N of M units never got a proposal' even
        after Workbench.job (in-memory) has been reset by a restart."""
        row = self.db.execute(
            "SELECT * FROM job_run ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def stats(self) -> dict:
        views = self.all_views()
        counts = {s: 0 for s in STATES}
        for v in views:
            counts[v.state] = counts.get(v.state, 0) + 1
        proposed = sum(1 for v in views if v.proposal)
        risk_counts: dict[str, int] = {}
        behavior_counts: dict[str, int] = {}
        for v in views:
            item = v.analysis or {}
            level = (item.get("risk") or {}).get("level")
            value = (item.get("behavior") or {}).get("value")
            if level:
                risk_counts[level] = risk_counts.get(level, 0) + 1
            if value:
                behavior_counts[value] = behavior_counts.get(value, 0) + 1
        return {
            "tasks": len(views),
            "proposed": proposed,
            "unproposed": len(views) - proposed,
            **counts,
            "risk": risk_counts,
            "behavior": behavior_counts,
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
                    "test_coverage": self.test_coverage(),
                    "tasks": [
                        {
                            **v.to_dict(),
                            "history": self.history(v.task["id"]),
                            "test_cases": self.test_cases(v.task["id"]),
                        }
                        for v in views
                    ],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.export_tests(out)
        self.export_compliance(out)
        return sql_path, json_path

    def export_tests(self, out_dir: Path | str) -> Path | None:
        """Write the test specification as Markdown, if there is one.

        Kept out of ``approved.sql`` on purpose: the specification describes
        the *original* behaviour and applies to every unit, approved or not.
        A reviewer who only exported what was approved would be left testing
        exactly the half that already looked fine.
        """
        units = []
        for view in self.all_views():
            cases = self.test_cases(view.task["id"])
            if not cases:
                continue
            item = view.analysis or {}
            units.append({
                "title": view.task.get("title", ""),
                "kind": view.task.get("kind", ""),
                "risk": (item.get("risk") or {}).get("level", ""),
                "behavior": (item.get("behavior") or {}).get("value", ""),
                "cases": cases,
            })
        if not units:
            return None
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "tests.md"
        path.write_text(
            testspec.render_markdown(self.session().get("title", ""), units),
            encoding="utf-8",
        )
        return path

    def export_compliance(self, out_dir: Path | str) -> Path | None:
        """Write a compliance record for this session, if there is anything to say.

        Kept beside ``tests.md``, not inside the APEX export ZIP -- the ZIP
        ships only APEX artefacts (see ``apexlang.export_apexlang``, which a
        test protects). This is the file a customer archives as evidence of
        what was found in the source and whether the provider that answered
        was allowed to see it.

        Every finding repeated here was already computed by
        :mod:`formslang.sensitive` during analysis, and repeated exactly as
        redacted then -- this method only collects and formats it, it scans
        nothing itself.
        """
        views = self.all_views()
        per_unit = []
        all_findings: list[dict] = []
        for v in views:
            findings = ((v.analysis or {}).get("sensitive") or {}).get("findings") or []
            if not findings:
                continue
            per_unit.append((v, findings))
            all_findings.extend(findings)

        providers_used = sorted(
            {(v.proposal or {}).get("provider", "") for v in views if v.proposal} - {""}
        )
        if not per_unit and not providers_used:
            return None

        counts: dict[str, int] = {}
        level = sensitive.LOW
        for f in all_findings:
            counts[f["category"]] = counts.get(f["category"], 0) + 1
            if sensitive.SEVERITY_LEVELS.index(f["severity"]) > sensitive.SEVERITY_LEVELS.index(level):
                level = f["severity"]

        enterprise = policy.enterprise_mode()
        lines = [
            f"# Compliance record -- {self.session().get('title', '')}",
            "",
            f"Exported: {_now()}",
            f"Enterprise mode: {'ON (' + policy.ENTERPRISE_ENV + '=1)' if enterprise else 'off'}",
            "",
            "## Providers that answered a proposal in this session",
            "",
        ]
        if providers_used:
            lines.append("| Provider | Egress |")
            lines.append("|---|---|")
            for type_id in providers_used:
                egress = policy.egress_for(type_id, ai_setting("base_url"))
                lines.append(f"| {type_id} | {egress} |")
        else:
            lines.append("(no proposal has been generated yet)")
        lines += [
            "",
            f"## Sensitive data found -- {len(all_findings)} finding(s), highest severity {level}",
            "",
        ]
        if counts:
            lines.append("| Category | Count |")
            lines.append("|---|---|")
            for cat in sensitive.CATEGORIES:
                if counts.get(cat):
                    lines.append(f"| {cat} | {counts[cat]} |")
            lines.append("")
        if not per_unit:
            lines.append("No sensitive data was found in any scanned unit.")
            lines.append("")
        for v, findings in per_unit:
            t = v.task
            lines.append(f"### {t['module']} :: {t['kind']} {t['title']}")
            lines.append("")
            lines.append("| Line | Category | Severity | Confidence | Excerpt |")
            lines.append("|---|---|---|---|---|")
            for f in findings:
                excerpt = str(f["excerpt"]).replace("|", chr(92) + "|")
                lines.append(
                    f"| {f['line']} | {f['category']} | {f['severity']} | "
                    f"{f['confidence']} | `{excerpt}` |"
                )
            lines.append("")
        lines.append(
            "Every excerpt above is redacted -- the raw value that was matched "
            f"never left the scan (formslang.sensitive {sensitive.VERSION})."
        )

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "compliance.md"
        path.write_text(chr(10).join(lines), encoding="utf-8")
        return path
