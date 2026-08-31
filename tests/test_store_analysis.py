"""Persisted analysis: cached, versioned, and never silently stale."""

from __future__ import annotations

import sqlite3

import pytest

from formslang.analysis import ENGINE_VERSION, analyze_task
from formslang.convert import build_tasks
from formslang.parser import parse_xml
from formslang.store import APPROVED, Store


@pytest.fixture()
def store(tmp_path, sample_xml):
    s = Store(tmp_path / "s.db")
    s.init_session("DEMO_ORDER", str(sample_xml))
    s.add_tasks(build_tasks(parse_xml(sample_xml)))
    yield s
    s.close()


def analyse_all(store: Store) -> None:
    for task_id in store.task_ids():
        task = store.get_task(task_id)
        assert task is not None
        store.save_analysis(analyze_task(task))


def test_a_session_starts_with_no_analysis_and_says_so(store):
    coverage = store.analysis_coverage()
    assert coverage["analysed"] == 0
    assert coverage["missing"] == coverage["tasks"] > 0
    assert store.stale_task_ids() == store.task_ids()


def test_analysis_round_trips_through_the_database(store):
    task_id = store.task_ids()[0]
    original = analyze_task(store.get_task(task_id))
    store.save_analysis(original)
    loaded = store.get_analysis(task_id)
    assert loaded is not None
    assert loaded.risk.level == original.risk.level
    # The stored payload is what the UI reads, rounded to what it displays.
    assert loaded.risk.score == round(original.risk.score, 1)
    assert loaded.behavior.value == original.behavior.value
    assert [f.name for f in loaded.findings] == [f.name for f in original.findings]


def test_saving_twice_updates_instead_of_duplicating(store):
    task_id = store.task_ids()[0]
    store.save_analysis(analyze_task(store.get_task(task_id)))
    store.save_analysis(analyze_task(store.get_task(task_id)))
    rows = store.db.execute("SELECT COUNT(*) c FROM unit_analysis").fetchone()["c"]
    assert rows == 1


def test_coverage_reports_what_was_measured(store):
    analyse_all(store)
    coverage = store.analysis_coverage()
    assert coverage["analysed"] == coverage["tasks"]
    assert coverage["missing"] == 0 and coverage["stale"] == 0
    assert store.stale_task_ids() == []


def test_an_analysis_from_older_rules_counts_as_stale(store):
    analyse_all(store)
    task_id = store.task_ids()[0]
    store.db.execute(
        "UPDATE unit_analysis SET engine_version = 'analysis/0+old' WHERE task_id = ?",
        (task_id,),
    )
    store.db.commit()
    assert store.analysis_coverage()["stale"] == 1
    assert task_id in store.stale_task_ids()
    assert store.analysis_payload(task_id)["stale"] is True


def test_a_corrupt_payload_reads_as_missing_not_as_a_wrong_answer(store):
    analyse_all(store)
    task_id = store.task_ids()[0]
    store.db.execute(
        "UPDATE unit_analysis SET payload = '{not json' WHERE task_id = ?", (task_id,)
    )
    store.db.commit()
    assert store.analysis_payload(task_id) is None
    assert store.get_analysis(task_id) is None


def test_the_view_carries_the_analysis_to_the_ui(store):
    analyse_all(store)
    view = store.view(store.task_ids()[0]).to_dict()
    assert view["analysis"]["risk"]["level"]
    assert view["analysis"]["behavior"]["value"]


def test_stats_report_the_distributions_only_for_analysed_units(store):
    assert store.stats()["risk"] == {}
    analyse_all(store)
    stats = store.stats()
    assert sum(stats["risk"].values()) == stats["tasks"]
    assert sum(stats["behavior"].values()) == stats["tasks"]


def test_a_decision_freezes_the_risk_it_was_taken_against(store):
    analyse_all(store)
    task_id = store.task_ids()[0]
    expected = store.get_analysis(task_id)
    store.set_decision(task_id, APPROVED, code="null;", reviewer="geraldo")
    entry = store.history(task_id)[0]
    assert entry["risk_level"] == expected.risk.level
    assert entry["behavior"] == expected.behavior.value
    assert entry["engine_version"] == ENGINE_VERSION


def test_a_decision_without_an_analysis_records_blanks_not_defaults(store):
    """No analysis means no snapshot -- not a fabricated LOW."""
    task_id = store.task_ids()[0]
    store.set_decision(task_id, APPROVED, code="null;", reviewer="geraldo")
    entry = store.history(task_id)[0]
    assert entry["risk_level"] == ""
    assert entry["behavior"] == ""


def test_module_meta_round_trips(store):
    store.save_module_meta("DEMO_ORDER", {"blocks": 1, "items": 3})
    meta = store.module_meta("DEMO_ORDER")
    assert meta["blocks"] == 1 and meta["items"] == 3
    assert meta["updated_at"]
    assert store.module_meta("NOPE") is None
    assert len(store.all_module_meta()) == 1


def test_an_older_session_file_still_opens(tmp_path, sample_xml):
    """A file written before these columns existed must migrate, not fail."""
    path = tmp_path / "legacy.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE session (id INTEGER PRIMARY KEY CHECK (id = 1), title TEXT NOT NULL,
            source_path TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE task (id TEXT PRIMARY KEY, module TEXT NOT NULL, kind TEXT NOT NULL,
            name TEXT NOT NULL, owner TEXT NOT NULL DEFAULT '', verdict TEXT NOT NULL DEFAULT '',
            apex_hint TEXT NOT NULL DEFAULT '', source TEXT NOT NULL,
            lines INTEGER NOT NULL DEFAULT 0, fingerprint TEXT NOT NULL DEFAULT '',
            meta TEXT NOT NULL DEFAULT '{}', position INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE proposal (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
            created_at TEXT NOT NULL, apex_target TEXT NOT NULL DEFAULT '',
            code TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '[]',
            questions TEXT NOT NULL DEFAULT '[]', confidence REAL NOT NULL DEFAULT 0,
            provider TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '');
        CREATE TABLE decision (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
            state TEXT NOT NULL, code TEXT NOT NULL DEFAULT '', comment TEXT NOT NULL DEFAULT '',
            reviewer TEXT NOT NULL DEFAULT '', decided_at TEXT NOT NULL);
        INSERT INTO session VALUES (1, 'LEGACY', '', '2026-01-01 00:00:00');
        INSERT INTO task (id, module, kind, name, source) VALUES
            ('t1', 'LEGACY', 'trigger', 'WHEN-BUTTON-PRESSED', 'BEGIN HOST(''x''); END;');
        INSERT INTO decision (task_id, state, decided_at) VALUES ('t1', 'approved', '2026-01-01');
        """
    )
    old.commit()
    old.close()

    store = Store(path)
    try:
        assert store.session()["title"] == "LEGACY"
        assert store.history("t1")[0]["risk_level"] == ""   # column added, empty
        store.save_analysis(analyze_task(store.get_task("t1")))
        assert store.get_analysis("t1").risk.level
    finally:
        store.close()
