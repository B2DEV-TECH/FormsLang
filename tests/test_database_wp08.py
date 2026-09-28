"""WP-08: SQL export declarations must be accounted for in source order."""

from __future__ import annotations

import pytest

from formslang import blueprint, database


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_database_project_legacy_positional_constructor_keeps_sequences_and_files():
    sequence = database.Sequence(name="S", source_file="legacy.sql")
    project = database.DatabaseProject({}, {}, {}, {}, {"S": sequence}, ["legacy.sql"], [])
    serialized = project.to_dict()
    assert serialized["sequences"] == {"S": sequence.to_dict()}
    assert serialized["files"] == ["legacy.sql"]
    assert serialized["package_declarations"] == []


def test_multiple_package_spec_and_body_declarations_keep_owner_order_and_source(tmp_path):
    source = _write(tmp_path, "packages.sql", """-- CREATE PACKAGE FAKE AS END FAKE;
CREATE PACKAGE SALES.P AS PROCEDURE A; END P;
/
CREATE PACKAGE BILLING.P AS PROCEDURE B; END P;
/
CREATE PACKAGE BODY SALES.P AS PROCEDURE A IS BEGIN NULL; END A; END P;
/
CREATE PACKAGE BODY BILLING.P AS PROCEDURE B IS BEGIN NULL; END B; END P;
/
""")
    project = database.parse_database_file(source)
    declarations = project.package_declarations
    assert [(d.kind, d.owner, d.name, d.qualified_name, d.line, d.order)
            for d in declarations] == [
        ("PACKAGE", "SALES", "P", "SALES.P", 2, 1),
        ("PACKAGE", "BILLING", "P", "BILLING.P", 4, 2),
        ("PACKAGE BODY", "SALES", "P", "SALES.P", 6, 3),
        ("PACKAGE BODY", "BILLING", "P", "BILLING.P", 8, 4),
    ]
    assert [d.source_file for d in declarations] == [str(source)] * 4
    assert [[s.name for s in d.parsed.subprograms] for d in declarations] == [
        ["A"], ["B"], ["A"], ["B"]]
    assert project.package_specs == {} and project.package_bodies == {}
    assert [d.to_dict()["projection_status"] for d in declarations] == [
        "AMBIGUOUS_BARE_NAME"] * 4
    [coverage] = project.coverage
    assert coverage.status == database.PARSED
    assert [(o["kind"], o["name"]) for o in coverage.objects] == [
        ("PACKAGE", "P"), ("PACKAGE", "P"),
        ("PACKAGE BODY", "P"), ("PACKAGE BODY", "P")]
    assert coverage.not_extracted == []
    assert len(project.to_dict()["package_declarations"]) == 4


def test_same_name_packages_in_separate_sources_do_not_get_arbitrary_bare_name(tmp_path):
    first = _write(tmp_path, "a.sql", "CREATE PACKAGE SALES.P AS PROCEDURE A; END P;\n/\n")
    second = _write(tmp_path, "b.sql", "CREATE PACKAGE BILLING.P AS PROCEDURE B; END P;\n/\n")
    project = database.parse_database_sources([second, first])
    assert [d.qualified_name for d in project.package_declarations] == ["BILLING.P", "SALES.P"]
    assert "P" not in project.package_specs
    assert [d.to_dict()["projection_status"] for d in project.package_declarations] == [
        "AMBIGUOUS_BARE_NAME", "AMBIGUOUS_BARE_NAME"]
    assert all(c.status == database.PARSED for c in project.coverage)


def test_repeated_create_of_one_package_is_counted_twice_without_claiming_effective_version(tmp_path):
    source = _write(tmp_path, "repeat.sql", "CREATE PACKAGE P AS PROCEDURE A; END P;\n/\n"
                    "CREATE OR REPLACE PACKAGE P AS PROCEDURE B; END P;\n/\n")
    project = database.parse_database_file(source)
    assert [[s.name for s in d.parsed.subprograms] for d in project.package_declarations] == [
        ["A"], ["B"]]
    assert project.package_specs == {}
    assert len(project.coverage[0].objects) == 2


def test_lexical_create_decoys_do_not_appear_in_package_inventory(tmp_path):
    source = _write(tmp_path, "decoys.sql", """/* CREATE PACKAGE FAKE AS END FAKE; */
CREATE TABLE T (ID NUMBER);
COMMENT ON TABLE T IS 'CREATE PACKAGE ALSO_FAKE AS END ALSO_FAKE;';
CREATE PACKAGE REAL AS PROCEDURE X; END REAL;
/
""")
    project = database.parse_database_file(source)
    assert [d.name for d in project.package_declarations] == ["REAL"]
    assert [s.name for s in project.package_specs["REAL"].subprograms] == ["X"]


def test_package_member_inventory_ignores_comment_and_string_decoys(tmp_path):
    source = _write(tmp_path, "members.sql", """CREATE PACKAGE P AS
  -- PROCEDURE COMMENT_DECOY;
  C CONSTANT VARCHAR2(80) := 'PROCEDURE STRING_DECOY;';
  /* FUNCTION BLOCK_DECOY RETURN NUMBER; */
  PROCEDURE REAL_MEMBER;
END P;
/
""")
    project = database.parse_database_file(source)
    [declaration] = project.package_declarations
    assert [s.name for s in declaration.parsed.subprograms] == ["REAL_MEMBER"]
    assert [c.name for c in declaration.parsed.constants] == ["C"]
    assert declaration.to_dict()["subprograms"] == ["REAL_MEMBER"]


def test_package_member_inventory_preserves_overload_evidence_in_blueprint(tmp_path):
    source = _write(tmp_path, "overloads.sql", """CREATE PACKAGE P AS
  PROCEDURE RUN(P_ID NUMBER);
  PROCEDURE RUN(P_NAME VARCHAR2);
END P;
/
""")
    bp = blueprint.build([], title="overloads", database_sources=source)
    [declaration] = bp["database"]["package_declarations"]
    assert [(m["name"], m["kind"], m["line"], m["parameters"][0]["data_type"])
            for m in declaration["members"]] == [
        ("RUN", "PROCEDURE", 2, "NUMBER"),
        ("RUN", "PROCEDURE", 3, "VARCHAR2"),
    ]


def test_quoted_package_members_keep_case_in_spec_and_body(tmp_path):
    source = _write(tmp_path, "quoted_members.sql", """CREATE PACKAGE P AS
  PROCEDURE "Run Job";
END P;
/
CREATE PACKAGE BODY P AS
  PROCEDURE "Run Job" IS BEGIN NULL; END "Run Job";
END P;
/
""")
    project = database.parse_database_file(source)
    assert [[s.name for s in d.parsed.subprograms] for d in project.package_declarations] == [
        ["Run Job"], ["Run Job"]]
    assert [[m["name"] for m in d.to_dict()["members"]] for d in project.package_declarations] == [
        ["Run Job"], ["Run Job"]]


def test_quoted_dot_in_package_name_keeps_qualified_name_unambiguous(tmp_path):
    source = _write(tmp_path, "qualified.sql", """CREATE PACKAGE "A.B" AS PROCEDURE X; END "A.B";
/
CREATE PACKAGE A.B AS PROCEDURE Y; END B;
/
""")
    project = database.parse_database_file(source)
    assert [(d.owner, d.name, d.qualified_name) for d in project.package_declarations] == [
        (None, "A.B", '"A.B"'), ("A", "B", "A.B")]


def test_comment_literal_cannot_fabricate_table_or_coverage_object(tmp_path):
    source = _write(tmp_path, "comment_table.sql", "CREATE TABLE T (ID NUMBER);\n"
                    "COMMENT ON TABLE T IS ' CREATE TABLE FAKE (ID NUMBER)';\n")
    project = database.parse_database_file(source)
    assert set(project.tables) == {"T"}
    assert [(o["kind"], o["name"]) for o in project.coverage[0].objects] == [("TABLE", "T")]


def test_blueprint_reports_homonyms_without_resolving_an_arbitrary_package(tmp_path):
    _write(tmp_path, "a.sql", "CREATE PACKAGE SALES.P AS PROCEDURE A; END P;\n/\n")
    _write(tmp_path, "b.sql", "CREATE PACKAGE BILLING.P AS PROCEDURE B; END P;\n/\n")
    bp = blueprint.build([], title="ambiguous", database_sources=tmp_path)
    assert [d["qualified_name"] for d in bp["database"]["package_declarations"]] == [
        "SALES.P", "BILLING.P"]
    assert not [e for e in bp["entities"] if e["type"] == "PACKAGE_SPEC"]


def test_spec_and_body_from_different_owners_do_not_form_false_implementation(tmp_path):
    source = _write(tmp_path, "cross_owner.sql", """CREATE PACKAGE SALES.P AS
  PROCEDURE X;
END P;
/
CREATE PACKAGE BODY BILLING.P AS
  PROCEDURE X IS BEGIN NULL; END X;
END P;
/
""")
    project = database.parse_database_file(source)
    assert [d.qualified_name for d in project.package_declarations] == ["SALES.P", "BILLING.P"]
    assert project.package_specs == {} and project.package_bodies == {}
    assert [d.projection_status for d in project.package_declarations] == [
        "AMBIGUOUS_BARE_NAME", "AMBIGUOUS_BARE_NAME"]

    bp = blueprint.build([], title="cross owner", database_sources=source)
    assert not [e for e in bp["edges"] if e["type"] == "IMPLEMENTS"]


def test_package_member_lines_are_absolute_in_multi_create_export(tmp_path):
    source = _write(tmp_path, "lines.sql", """CREATE TABLE T (ID NUMBER);
/
CREATE PACKAGE S.P AS
  K CONSTANT NUMBER := 1;
  PROCEDURE X;
END P;
/
CREATE PACKAGE BODY S.P AS
  PROCEDURE X IS BEGIN NULL; END X;
END P;
/
""")
    project = database.parse_database_file(source)
    spec, body = [d.parsed for d in project.package_declarations]
    assert spec.constants[0].line_number == 4
    assert spec.subprograms[0].line_number == 5
    assert body.subprograms[0].line_number == 9


def test_adjacent_create_after_package_without_slash_stays_visible(tmp_path):
    source = _write(tmp_path, "adjacent.sql", """CREATE PACKAGE P AS PROCEDURE X; END P;
CREATE VIEW V AS SELECT 1 FROM DUAL;
CREATE SEQUENCE S;
""")
    project = database.parse_database_file(source)
    assert set(project.package_specs) == {"P"}
    assert set(project.views) == {"V"}
    assert set(project.sequences) == {"S"}
    assert project.coverage[0].not_extracted == []


def test_package_slash_prevents_later_anonymous_block_members(tmp_path):
    source = _write(tmp_path, "block.sql", """CREATE PACKAGE BODY P AS
  PROCEDURE X IS BEGIN NULL; END X;
END P;
/
DECLARE
  PROCEDURE FAKE IS BEGIN NULL; END FAKE;
BEGIN NULL; END;
/
""")
    project = database.parse_database_file(source)
    assert [s.name for s in project.package_bodies["P"].subprograms] == ["X"]


def test_comment_cannot_supply_package_header_closing_tokens(tmp_path):
    source = _write(tmp_path, "comment.sql", """CREATE PACKAGE P ACCESSIBLE BY (PACKAGE S.Q /* ) AS
  PROCEDURE FAKE;
  */) AS
  PROCEDURE REAL;
END P;
/
""")
    project = database.parse_database_file(source)
    assert [s.name for s in project.package_specs["P"].subprograms] == ["REAL"]


def test_quoted_package_name_can_touch_as_keyword(tmp_path):
    source = _write(tmp_path, "quoted.sql", 'CREATE PACKAGE "P"AS PROCEDURE X; END P;\n/\n')
    project = database.parse_database_file(source)
    assert [s.name for s in project.package_specs["P"].subprograms] == ["X"]


def test_quoted_accessible_by_identifier_does_not_end_header(tmp_path):
    source = _write(tmp_path, "quoted_accessor.sql", 'CREATE PACKAGE P ACCESSIBLE BY '
                    '(PACKAGE "Q) AS PROCEDURE FAKE;") AS PROCEDURE REAL; END P;\n/\n')
    project = database.parse_database_file(source)
    assert [s.name for s in project.package_specs["P"].subprograms] == ["REAL"]


def test_as_suffix_inside_package_name_is_not_header_keyword(tmp_path):
    source = _write(tmp_path, "missing_as.sql", 'CREATE PACKAGE PAS PROCEDURE X; END PAS;\n/\n')
    project = database.parse_database_file(source)
    assert project.package_declarations == []
    assert project.coverage[0].not_extracted[0]["name"] == "PAS"


def test_same_bare_name_nonpackage_creates_are_visible_and_not_projected(tmp_path):
    source = _write(tmp_path, "tables.sql", """CREATE TABLE SALES.T (A NUMBER);
CREATE TABLE BILLING.T (B NUMBER);
""")
    project = database.parse_database_file(source)
    assert project.tables == {}
    [coverage] = project.coverage
    assert coverage.status == database.PARSED_WITH_WARNINGS
    assert [(o["kind"], o["name"], o["line"]) for o in coverage.objects] == [
        ("TABLE", "T", 1), ("TABLE", "T", 2)]
    assert [(e["line"], e["reason"]) for e in coverage.not_extracted] == [
        (1, "COLLIDING_BARE_NAME"), (2, "COLLIDING_BARE_NAME")]


def test_colliding_tables_across_sources_never_reappear_as_one_projection(tmp_path):
    first = _write(tmp_path, "a.sql", "CREATE TABLE A.T (A NUMBER);\n"
                   "CREATE TABLE B.T (B NUMBER);\n")
    second = _write(tmp_path, "b.sql", "CREATE TABLE C.T (C NUMBER);\n")
    project = database.parse_database_sources([first, second])
    assert project.tables == {}
    assert sum(len(c.objects) for c in project.coverage) == 3


def test_supported_but_unextracted_homonym_withholds_bare_table(tmp_path):
    source = _write(tmp_path, "mixed.sql", "CREATE TABLE A.T (A NUMBER);\n"
                    'CREATE TABLE "B"."T" (B NUMBER);\n')
    project = database.parse_database_file(source)
    assert project.tables == {}
    [coverage] = project.coverage
    assert [(o["kind"], o["name"]) for o in coverage.objects] == [("TABLE", "T")]
    assert [(o["kind"], o["name"], o["reason"]) for o in coverage.not_extracted] == [
        ("TABLE", "T", "NOT_EXTRACTED")]


@pytest.mark.parametrize("header", [
    "CREATE PACKAGE P AUTHID DEFINER AS",
    "CREATE OR REPLACE PACKAGE P AUTHID CURRENT_USER IS",
    "CREATE PACKAGE P ACCESSIBLE BY (PACKAGE APP.API, PROCEDURE APP.RUN) AS",
    'CREATE PACKAGE "S"."P" DEFAULT COLLATION "BINARY_CI" AS',
    "CREATE PACKAGE P DEFAULT COLLATION USING_NLS_COMP AS",
    "CREATE PACKAGE P SHARING = METADATA AS",
    "CREATE PACKAGE P SHARING = NONE AS",
    ("CREATE PACKAGE P SHARING=NONE AUTHID DEFINER ACCESSIBLE BY (PACKAGE APP.API) "
     "DEFAULT COLLATION USING_NLS_COMP AS"),
])
def test_package_spec_header_clauses_are_bounded_and_preserved(tmp_path, header):
    source = _write(tmp_path, "clauses.sql", header + " PROCEDURE X; END P;\n/\n"
                    "CREATE PACKAGE Q AS PROCEDURE Y; END Q;\n/\n")
    project = database.parse_database_file(source)
    first, second = project.package_declarations
    assert first.header_text == header
    assert (first.source_file, first.line, first.name) == (str(source), 1, "P")
    assert [s.name for s in first.parsed.subprograms] == ["X"]
    assert [s.name for s in second.parsed.subprograms] == ["Y"]
    assert project.coverage[0].not_extracted == []


def test_package_body_sharing_clause_is_preserved(tmp_path):
    source = _write(tmp_path, "body.sql", "CREATE PACKAGE BODY S.P SHARING = METADATA AS "
                    "PROCEDURE X IS BEGIN NULL; END X; END P;\n/\n")
    [declaration] = database.parse_database_file(source).package_declarations
    assert declaration.kind == "PACKAGE BODY"
    assert declaration.header_text == "CREATE PACKAGE BODY S.P SHARING = METADATA AS"
    assert [s.name for s in declaration.parsed.subprograms] == ["X"]


@pytest.mark.parametrize("kind", ["PACKAGE", "PACKAGE BODY"])
@pytest.mark.parametrize("attribute", ["DATA", "EXTENDED DATA"])
def test_package_sharing_rejects_attributes_reserved_for_other_object_kinds(tmp_path, kind, attribute):
    source = _write(tmp_path, "sharing.sql", f"CREATE {kind} P SHARING = {attribute} AS "
                    "PROCEDURE X; END P;\n/\n")
    project = database.parse_database_file(source)
    assert project.package_declarations == []
    assert [(entry["kind"], entry["reason"]) for entry in project.coverage[0].not_extracted] == [
        (kind, "NOT_EXTRACTED")]


@pytest.mark.xfail(strict=True, reason="Future DDL grammar: IF NOT EXISTS is outside WP-08B clauses")
def test_known_gap_documented_if_not_exists_package_header(tmp_path):
    source = _write(tmp_path, "if_not_exists.sql",
                    "CREATE PACKAGE IF NOT EXISTS P AS PROCEDURE X; END P;\n/\n")
    project = database.parse_database_file(source)
    assert [d.name for d in project.package_declarations] == ["P"]


@pytest.mark.parametrize("header", [
    "CREATE PACKAGE P AUTHID OTHER AS",
    "CREATE PACKAGE P ACCESSIBLE BY (PACKAGE APP.API AS",
    "CREATE PACKAGE P SHARING = UNKNOWN AS",
    "CREATE PACKAGE BODY P AUTHID DEFINER AS",
])
def test_unrecognised_or_invalid_clause_is_reported_not_extracted(tmp_path, header):
    source = _write(tmp_path, "bad.sql", header + " PROCEDURE X; END P;\n/\n")
    project = database.parse_database_file(source)
    assert project.package_declarations == []
    assert project.coverage[0].status == database.NO_RECOGNIZED_OBJECTS
    assert [(e["kind"], e["name"]) for e in project.coverage[0].not_extracted] == [
        ("PACKAGE BODY" if "BODY" in header else "PACKAGE", "P")]


@pytest.mark.parametrize("separator", ["/\n", "   /   \n", "\n\t/\r\n\r\n"])
def test_isolated_slash_keeps_consecutive_table_statements(separator, tmp_path):
    source = _write(tmp_path, "tables.sql", "CREATE TABLE A (ID NUMBER);\n"
                    + separator + "CREATE TABLE B (ID NUMBER);\n")
    project = database.parse_database_file(source)
    assert set(project.tables) == {"A", "B"}
    assert project.coverage[0].not_extracted == []


def test_slash_ends_view_without_semicolon_before_next_create(tmp_path):
    source = _write(tmp_path, "views.sql", "CREATE VIEW V AS SELECT '/' AS PATH FROM DUAL\n"
                    "  /  \nCREATE TABLE T (ID NUMBER);\n")
    project = database.parse_database_file(source)
    assert set(project.views) == {"V"}
    assert set(project.tables) == {"T"}
    assert "CREATE TABLE" not in project.views["V"].query_text
    assert project.coverage[0].not_extracted == []


def test_slash_inside_q_string_and_comment_is_not_a_delimiter(tmp_path):
    source = _write(tmp_path, "literals.sql", """CREATE VIEW V AS SELECT q'[
/
]' AS PATH FROM DUAL
-- /
/
CREATE TABLE T (ID NUMBER);
""")
    project = database.parse_database_file(source)
    assert set(project.views) == {"V"}
    assert set(project.tables) == {"T"}
    assert "q'[\n/\n]'" in project.views["V"].query_text
    assert project.coverage[0].not_extracted == []


def test_package_clauses_multiple_creates_and_slash_work_together(tmp_path):
    source = _write(tmp_path, "combined.sql", """CREATE PACKAGE S.P AUTHID CURRENT_USER AS
  PROCEDURE X;
END P;
   /
CREATE PACKAGE BODY S.P SHARING = METADATA AS
  PROCEDURE X IS BEGIN
    IF 1 = 1 THEN NULL; END IF;
  END X;
END P;
/
CREATE VIEW V AS SELECT 8 / 2 AS HALF FROM DUAL
/
CREATE TABLE T (ID NUMBER);
""")
    project = database.parse_database_file(source)
    assert [(d.kind, d.qualified_name, d.line) for d in project.package_declarations] == [
        ("PACKAGE", "S.P", 1), ("PACKAGE BODY", "S.P", 5)]
    assert [[s.name for s in d.parsed.subprograms] for d in project.package_declarations] == [
        ["X"], ["X"]]
    assert set(project.views) == {"V"}
    assert set(project.tables) == {"T"}
    assert len(project.coverage[0].objects) == 4
    assert project.coverage[0].not_extracted == []
