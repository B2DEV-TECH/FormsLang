"""WP-07A: package headers as Oracle DDL exports write them (gap G-DDL-HEADER).

The identity key stays the object name without its schema. Schema-aware identity
is G-SCHEMA-COLLIDE and waits for ADR-06; these tests only prove that the header
is recognised and that the name keeps its Oracle case semantics.
"""

from __future__ import annotations

import pytest

from formslang import blueprint, database

SPEC_BODY = " PROCEDURE X; FUNCTION Y RETURN NUMBER; END {end};"
BODY_BODY = " PROCEDURE X IS BEGIN NULL; END X; FUNCTION Y RETURN NUMBER IS BEGIN RETURN 1; END Y; END {end};"


@pytest.mark.parametrize(("header", "name"), [
    ("CREATE EDITIONABLE PACKAGE S.P AS", "P"),
    ("CREATE NONEDITIONABLE PACKAGE S.P AS", "P"),
    ("CREATE OR REPLACE EDITIONABLE PACKAGE S.P IS", "P"),
    ('CREATE PACKAGE "S"."P" AS', "P"),
    ("CREATE PACKAGE S . P AS", "P"),
    ('CREATE OR REPLACE NONEDITIONABLE PACKAGE "S" . "P" AS', "P"),
    ('CREATE EDITIONABLE PACKAGE "MySchema"."MyPackage" AS', "MyPackage"),
    ('create editionable package "MyPackage" is', "MyPackage"),
    ('CREATE PACKAGE\n  "S"\n  .\n  "P"\nAS', "P"),
    ("create package s.MyPkg as", "MYPKG"),
    # A name that starts with BODY, or ends in AS/IS, is still a specification name.
    ("CREATE OR REPLACE PACKAGE BODY_API AS", "BODY_API"),
    ("CREATE PACKAGE PAS IS", "PAS"),
])
def test_exported_package_spec_header_is_recognised(header, name):
    spec = database.parse_package_spec(header + SPEC_BODY.format(end=name))
    assert spec is not None and spec.name == name
    assert [(s.name, s.subprogram_type) for s in spec.subprograms] == [("X", "PROCEDURE"), ("Y", "FUNCTION")]
    assert database.parse_package_body(header + SPEC_BODY.format(end=name)) is None


@pytest.mark.parametrize(("header", "name"), [
    ("CREATE EDITIONABLE PACKAGE BODY S.P AS", "P"),
    ("CREATE NONEDITIONABLE PACKAGE BODY S.P AS", "P"),
    ("CREATE OR REPLACE EDITIONABLE PACKAGE BODY S.P IS", "P"),
    ('CREATE PACKAGE BODY "S"."P" AS', "P"),
    ("CREATE PACKAGE BODY S . P AS", "P"),
    ('CREATE OR REPLACE NONEDITIONABLE PACKAGE BODY "S" . "P" AS', "P"),
    ('CREATE EDITIONABLE PACKAGE BODY "MySchema"."MyPackage" AS', "MyPackage"),
    ('CREATE PACKAGE BODY\n  "S"\n  .\n  "P"\nAS', "P"),
    ("CREATE OR REPLACE PACKAGE BODY BODY_API AS", "BODY_API"),
])
def test_exported_package_body_header_is_recognised(header, name):
    body = database.parse_package_body(header + BODY_BODY.format(end=name))
    assert body is not None and body.name == name
    assert [(s.name, s.subprogram_type) for s in body.subprograms] == [("X", "PROCEDURE"), ("Y", "FUNCTION")]
    assert database.parse_package_spec(header + BODY_BODY.format(end=name)) is None


def test_quoted_name_keeps_its_case_and_an_unquoted_name_is_folded():
    # Oracle folds an unquoted name to upper case and keeps a quoted one exactly,
    # so "P" and P are the same object and "MyPackage" and MYPACKAGE are not.
    names = [database.parse_package_spec(h + SPEC_BODY.format(end="x")).name for h in (
        'CREATE PACKAGE "P" AS', "CREATE PACKAGE p AS",
        'CREATE PACKAGE "MyPackage" AS', "CREATE PACKAGE MyPackage AS")]
    assert names == ["P", "P", "MyPackage", "MYPACKAGE"]


@pytest.mark.parametrize("header", [
    'CREATE PACKAGE "S"."P"',                          # no AS/IS
    'CREATE PACKAGE "S.P AS',                          # unterminated quoted identifier
    "CREATE PACKAGE S..P AS",                          # empty name part
    "CREATE PACKAGE S.P.Q AS",                         # more than owner.name
    "CREATE EDITIONABLE NONEDITIONABLE PACKAGE P AS",  # both editioning keywords
    'CREATE PACKAGE "" AS',                            # empty quoted identifier
    "CREATE PACKAGE 1P AS",                            # an unquoted name starts with a letter
    "CREATE EDITIONING PACKAGE P AS",                  # EDITIONING applies to views only
])
def test_malformed_package_header_is_not_recognised(header):
    assert database.parse_package_spec(header + SPEC_BODY.format(end="P")) is None
    assert database.parse_package_body(header.replace("PACKAGE", "PACKAGE BODY") + BODY_BODY.format(end="P")) is None


def test_exported_package_header_keeps_its_package(tmp_path):
    # Formerly the pinned G-DDL-HEADER gap: the file parsed to nothing.
    source = tmp_path / "p.pkb"
    source.write_text('CREATE OR REPLACE EDITIONABLE PACKAGE BODY "S"."P" AS'
                      " PROCEDURE X IS BEGIN NULL; END X; END P;\n/\n", encoding="utf-8")
    project = database.parse_database_file(source)
    assert list(project.package_bodies) == ["P"]
    assert [s.name for s in project.package_bodies["P"].subprograms] == ["X"]


def test_sql_script_with_a_line_break_after_package_keeps_its_packages(tmp_path):
    # A .sql script is only searched for packages when it mentions one; the
    # keyword can be followed by a line break rather than a space.
    source = tmp_path / "api.sql"
    source.write_text('CREATE OR REPLACE EDITIONABLE PACKAGE\n"S"."P" AS PROCEDURE X; END P;\n/\n'
                      'CREATE OR REPLACE EDITIONABLE PACKAGE BODY\n"S"."P" AS'
                      " PROCEDURE X IS BEGIN NULL; END X; END P;\n/\n", encoding="utf-8")
    project = database.parse_database_file(source)
    assert (list(project.package_specs), list(project.package_bodies)) == (["P"], ["P"])


def test_exported_package_headers_reach_the_blueprint(tmp_path):
    (tmp_path / "p.pks").write_text('CREATE OR REPLACE EDITIONABLE PACKAGE "S"."P" AS PROCEDURE X; END P;\n/\n')
    (tmp_path / "p.pkb").write_text('CREATE OR REPLACE EDITIONABLE PACKAGE BODY "S"."P" AS'
                                    " PROCEDURE X IS BEGIN NULL; END X; END P;\n/\n")
    bp = blueprint.build([], title="headers", database_sources=tmp_path)
    # A saved assessment made before this engine lacks these packages.
    assert bp["engine_version"].startswith("blueprint-analysis/3+")
    kinds = sorted((e["type"], e["name"]) for e in bp["entities"]
                   if e["type"] in {"PACKAGE_SPEC", "PACKAGE_BODY", "SUBPROGRAM_BODY"})
    assert kinds == [("PACKAGE_BODY", "P"), ("PACKAGE_SPEC", "P"), ("SUBPROGRAM_BODY", "P.X")]


def test_gap_spec_header_with_a_clause_before_as_is_not_recognised():
    # Outside WP-07A: AUTHID, ACCESSIBLE BY, DEFAULT COLLATION and SHARING sit between
    # the name and AS/IS. Such a spec is still not parsed; WP-07B reports it.
    assert database.parse_package_spec("CREATE OR REPLACE PACKAGE P AUTHID DEFINER AS PROCEDURE X; END P;") is None
