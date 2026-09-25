"""WP-07B: every supplied database source gets an explicit coverage result.

A source that was read but yielded no object must not vanish. Coverage says what
each source was: parsed, parsed with warnings, no recognized objects, or
rejected/unreadable. Unknown is not zero: a project built without a coverage
scan reports coverage as None, never as an empty, clean result.
"""

from __future__ import annotations

import json

import pytest

from formslang import blueprint, database
from formslang.database import (
    NO_RECOGNIZED_OBJECTS,
    PARSED,
    PARSED_WITH_WARNINGS,
    REJECTED_OR_UNREADABLE,
)


def coverage_of(tmp_path, name, text):
    source = tmp_path / name
    source.write_text(text, encoding="utf-8")
    [coverage] = database.parse_database_file(source).coverage
    return coverage


def kinds(entries):
    return [(e["kind"], e["name"]) for e in entries]


def test_a_source_whose_objects_are_all_extracted_is_parsed(tmp_path):
    coverage = coverage_of(tmp_path, "t.sql", "CREATE TABLE T (ID NUMBER);\nCREATE SEQUENCE S;\n")
    assert coverage.status == PARSED
    assert kinds(coverage.objects) == [("SEQUENCE", "S"), ("TABLE", "T")]
    assert coverage.not_extracted == [] and coverage.unsupported == []
    assert coverage.reason is None


def test_a_trigger_only_source_has_no_recognized_objects_and_names_what_it_holds(tmp_path):
    coverage = coverage_of(tmp_path, "audit.trg",
                           "CREATE OR REPLACE TRIGGER AUDIT_T BEFORE INSERT ON T BEGIN NULL; END;\n/\n")
    assert coverage.status == NO_RECOGNIZED_OBJECTS
    assert coverage.objects == []
    assert kinds(coverage.unsupported) == [("TRIGGER", "AUDIT_T")]
    assert coverage.unsupported[0]["line"] == 1


def test_an_empty_source_has_no_recognized_objects_and_no_create_statement(tmp_path):
    coverage = coverage_of(tmp_path, "empty.sql", "-- nothing here\n")
    assert coverage.status == NO_RECOGNIZED_OBJECTS
    assert (coverage.objects, coverage.not_extracted, coverage.unsupported) == ([], [], [])
    assert coverage.reason == "NO_CREATE_STATEMENT"


def test_an_unmodelled_statement_beside_an_object_is_informational(tmp_path):
    # FormsLang does not model indexes: that is a limit of the model, not a
    # failure to read the source, so the source is still PARSED -- but the
    # index stays visible and says why it produced nothing.
    coverage = coverage_of(tmp_path, "t.sql", "CREATE TABLE T (ID NUMBER);\nCREATE INDEX T_I ON T (ID);\n")
    assert coverage.status == PARSED
    assert kinds(coverage.objects) == [("TABLE", "T")]
    assert coverage.unsupported == [{"kind": "INDEX", "name": "T_I", "line": 2,
                                     "severity": "INFO", "reason": "UNSUPPORTED_BY_MODEL"}]


def test_a_supported_statement_not_extracted_stays_a_warning_beside_unmodelled_ones(tmp_path):
    coverage = coverage_of(tmp_path, "t.sql", "CREATE TABLE A (ID NUMBER);\nCREATE INDEX A_I ON A (ID);\n"
                                              'CREATE TABLE "T" (ID NUMBER);\n')
    assert coverage.status == PARSED_WITH_WARNINGS
    assert coverage.not_extracted == [{"kind": "TABLE", "name": "T", "line": 3,
                                       "severity": "WARNING", "reason": "NOT_EXTRACTED"}]
    assert [e["severity"] for e in coverage.unsupported] == ["INFO"]


@pytest.mark.parametrize(("name", "text", "missing"), [
    # Each is a supported kind that the extractor does not yet read (see gaps-and-capture.md).
    ("gtt.sql", "CREATE GLOBAL TEMPORARY TABLE G (ID NUMBER) ON COMMIT DELETE ROWS;", [("TABLE", "G")]),
    ("force.sql", "CREATE OR REPLACE FORCE VIEW V AS SELECT 1 X FROM DUAL;", [("VIEW", "V")]),
    ("authid.pks", "CREATE OR REPLACE PACKAGE P AUTHID DEFINER AS PROCEDURE X; END P;\n/\n", [("PACKAGE", "P")]),
    ("quoted.sql", 'CREATE TABLE "T" (ID NUMBER);', [("TABLE", "T")]),
])
def test_a_supported_statement_that_is_not_extracted_is_reported(tmp_path, name, text, missing):
    coverage = coverage_of(tmp_path, name, text)
    assert coverage.status == NO_RECOGNIZED_OBJECTS
    assert kinds(coverage.not_extracted) == missing


def test_a_second_package_in_one_file_is_reported_not_extracted(tmp_path):
    coverage = coverage_of(tmp_path, "two.pks", "CREATE PACKAGE P AS PROCEDURE X; END P;\n/\n"
                                                "CREATE PACKAGE Q AS PROCEDURE Y; END Q;\n/\n")
    assert coverage.status == PARSED_WITH_WARNINGS
    assert kinds(coverage.objects) == [("PACKAGE", "P")]
    assert kinds(coverage.not_extracted) == [("PACKAGE", "Q")]


def test_a_table_after_a_slash_terminated_statement_is_reported_not_extracted(tmp_path):
    coverage = coverage_of(tmp_path, "slash.sql", "CREATE TABLE A (ID NUMBER);\n/\nCREATE TABLE T (ID NUMBER);\n")
    assert coverage.status == PARSED_WITH_WARNINGS
    assert kinds(coverage.objects) == [("TABLE", "A")]
    assert kinds(coverage.not_extracted) == [("TABLE", "T")]
    assert coverage.not_extracted[0]["line"] == 3


def test_create_in_a_string_or_comment_or_ddl_trigger_event_is_not_a_statement(tmp_path):
    coverage = coverage_of(tmp_path, "t.sql",
                           "-- CREATE VIEW NOT_A_VIEW AS SELECT 1 FROM DUAL;\n"
                           "/* CREATE SEQUENCE NOT_A_SEQUENCE; */\n"
                           "CREATE TABLE T (ID NUMBER);\n"
                           "COMMENT ON TABLE T IS 'CREATE INDEX NOT_AN_INDEX ON T (ID)';\n"
                           "CREATE TRIGGER DDL_T AFTER CREATE ON SCHEMA BEGIN NULL; END;\n/\n")
    assert kinds(coverage.objects) == [("TABLE", "T")]
    assert kinds(coverage.unsupported) == [("TRIGGER", "DDL_T")]
    assert coverage.not_extracted == []


def test_a_package_specification_and_body_are_distinct_kinds(tmp_path):
    coverage = coverage_of(tmp_path, "api.sql",
                           'CREATE OR REPLACE EDITIONABLE PACKAGE "S"."P" AS PROCEDURE X; END P;\n/\n'
                           'CREATE OR REPLACE EDITIONABLE PACKAGE BODY "S"."P" AS'
                           " PROCEDURE X IS BEGIN NULL; END X; END P;\n/\n")
    assert coverage.status == PARSED
    assert kinds(coverage.objects) == [("PACKAGE", "P"), ("PACKAGE BODY", "P")]


def test_sources_report_every_supplied_file_including_a_missing_one(tmp_path):
    (tmp_path / "t.sql").write_text("CREATE TABLE T (ID NUMBER);\nCREATE INDEX I ON T (ID);\n")
    (tmp_path / "s.sql").write_text("CREATE SEQUENCE S;\n")
    (tmp_path / "trg.sql").write_text("CREATE TRIGGER X BEFORE INSERT ON T BEGIN NULL; END;\n/\n")
    missing = tmp_path / "gone.sql"
    project = database.parse_database_sources([tmp_path / "t.sql", tmp_path / "s.sql",
                                               tmp_path / "trg.sql", missing])
    by_file = {c.source_file: c for c in project.coverage}
    assert by_file[str(missing)].status == REJECTED_OR_UNREADABLE
    assert by_file[str(missing)].reason == "SOURCE_NOT_FOUND"
    # A missing source is never counted as a parsed file.
    assert str(missing) not in project.files
    assert project.coverage_summary() == {
        "supplied": 4, "parsed": 2, "parsed_with_warnings": 0,
        "no_recognized_objects": 1, "rejected_or_unreadable": 1,
    }


def test_summary_counts_add_up_to_what_was_supplied(tmp_path):
    for i, text in enumerate(["CREATE TABLE T (ID NUMBER);", "", "CREATE VIEW V AS SELECT 1 X FROM DUAL;",
                              "CREATE SYNONYM Y FOR T;", "CREATE TABLE A (ID NUMBER);\n/\nCREATE TABLE B (ID NUMBER);"]):
        (tmp_path / f"{i}.sql").write_text(text)
    summary = database.parse_database_sources(tmp_path).coverage_summary()
    assert summary["supplied"] == 5
    assert summary["supplied"] == sum(v for k, v in summary.items() if k != "supplied")


def test_coverage_that_was_never_computed_is_unknown_not_zero():
    project = database.DatabaseProject()
    assert project.coverage is None
    assert project.coverage_summary() is None
    assert project.to_dict()["coverage"] is None


def test_the_blueprint_carries_source_coverage(tmp_path):
    (tmp_path / "t.sql").write_text("CREATE TABLE T (ID NUMBER);\n")
    (tmp_path / "trg.sql").write_text("CREATE TRIGGER X BEFORE INSERT ON T BEGIN NULL; END;\n/\n")
    bp = blueprint.build([], title="coverage", database_sources=tmp_path)
    coverage = bp["database"]["source_coverage"]
    assert coverage["summary"] == {"supplied": 2, "parsed": 1, "parsed_with_warnings": 0,
                                   "no_recognized_objects": 1, "rejected_or_unreadable": 0}
    assert [(s["source_file"], s["status"]) for s in coverage["sources"]] == [
        (str(tmp_path / "t.sql"), PARSED), (str(tmp_path / "trg.sql"), NO_RECOGNIZED_OBJECTS)]


def test_a_blueprint_from_a_project_without_coverage_reports_it_unknown():
    bp = blueprint.build([], title="unknown", database_sources=database.DatabaseProject())
    assert bp["database"]["source_coverage"] is None


def _parse_project(project_sources):
    from formslang.project_discovery import discover_sources
    from formslang.project_sources import parse_staged, stage_sources

    access, descriptor, _ = project_sources
    discovery = discover_sources(access, descriptor, checkpoint=lambda: None,
                                 progress=lambda e: None, preview=False)
    with stage_sources(access, descriptor, discovery, checkpoint=lambda: None) as staged:
        return parse_staged(descriptor, discovery, staged, checkpoint=lambda: None, progress=lambda e: None)


def test_a_project_keeps_the_coverage_of_a_source_with_no_objects(project_sources):
    access, _, _ = project_sources
    (access.source_roots[1] / "audit.trg").write_text("create trigger audit before insert on orders begin null; end;\n/\n")
    result = _parse_project(project_sources)
    by_file = {c.source_file: c for c in result.database.coverage}
    assert by_file["database/orders.sql"].status == PARSED
    assert by_file["database/audit.trg"].status == NO_RECOGNIZED_OBJECTS
    assert kinds(by_file["database/audit.trg"].unsupported) == [("TRIGGER", "AUDIT")]
    # The existing diagnostic and the parsed-file list are unchanged.
    assert any(d.error_code == "UNSUPPORTED_SQL" and d.relative_path == "audit.trg" for d in result.diagnostics)
    assert result.database.files == ["database/orders.sql"]
    assert str(access.source_roots[1]) not in json.dumps(result.database.to_dict()["coverage"])


def test_a_project_records_a_source_that_could_not_be_staged(project_sources, monkeypatch):
    from formslang import project_sources as sources

    monkeypatch.setattr(sources, "MAX_SOURCE_BYTES", 1)
    result = _parse_project(project_sources)
    [coverage] = result.database.coverage
    assert (coverage.source_file, coverage.status, coverage.reason) == (
        "database/orders.sql", REJECTED_OR_UNREADABLE, "SOURCE_TOO_LARGE")
