"""WP-08: SQL export declarations must be accounted for in source order."""

from __future__ import annotations

import pytest

from formslang import blueprint, database


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


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


def test_blueprint_reports_homonyms_without_resolving_an_arbitrary_package(tmp_path):
    _write(tmp_path, "a.sql", "CREATE PACKAGE SALES.P AS PROCEDURE A; END P;\n/\n")
    _write(tmp_path, "b.sql", "CREATE PACKAGE BILLING.P AS PROCEDURE B; END P;\n/\n")
    bp = blueprint.build([], title="ambiguous", database_sources=tmp_path)
    assert [d["qualified_name"] for d in bp["database"]["package_declarations"]] == [
        "SALES.P", "BILLING.P"]
    assert not [e for e in bp["entities"] if e["type"] == "PACKAGE_SPEC"]


@pytest.mark.parametrize("header", [
    "CREATE PACKAGE P AUTHID DEFINER AS",
    "CREATE OR REPLACE PACKAGE P AUTHID CURRENT_USER IS",
    "CREATE PACKAGE P ACCESSIBLE BY (PACKAGE APP.API, PROCEDURE APP.RUN) AS",
    'CREATE PACKAGE "S"."P" DEFAULT COLLATION "BINARY_CI" AS',
    "CREATE PACKAGE P DEFAULT COLLATION USING_NLS_COMP AS",
    "CREATE PACKAGE P SHARING = METADATA AS",
    "CREATE PACKAGE P SHARING = EXTENDED DATA AS",
    ("CREATE PACKAGE P SHARING=DATA AUTHID DEFINER ACCESSIBLE BY (PACKAGE APP.API) "
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
