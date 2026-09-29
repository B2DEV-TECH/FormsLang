"""ADR-06 fixture proof only; the WP-04 product projection is separate."""

from dataclasses import replace

import pytest

from examples.verify import ecosystem_inventory as inv
from examples.verify.entity_identity_contract import (
    Entity,
    classify,
    oracle_identifier,
    symbol_key,
)
from formslang import database


def test_oracle_identifier_parts_preserve_owner_case_and_quoted_dots():
    assert oracle_identifier("orders") == oracle_identifier('"ORDERS"') == "ORDERS"
    assert oracle_identifier('"Orders"') == "Orders"
    assert oracle_identifier('"A.B"') == "A.B"
    with pytest.raises(ValueError):
        oracle_identifier('"A""B"')
    with pytest.raises(ValueError):
        oracle_identifier("SALES.P")
    assert symbol_key("PACKAGE", "SALES", '"A.B"') != symbol_key("PACKAGE", '"SALES.A"', "B")
    assert symbol_key("PACKAGE", None, "P") != symbol_key("PACKAGE", "PUBLIC", "P")
    assert symbol_key("PACKAGE", "SALES", "P") != symbol_key("PACKAGE", "BILLING", "P")
    assert symbol_key("PACKAGE", "SALES", "P") != symbol_key("TABLE", "SALES", "P")


def test_real_case_c_package_declarations_keep_two_owner_keys():
    spec = inv.CORPORA["case_c"]
    sources = inv._paths(spec["database"], suffixes=inv.DATABASE_SUFFIXES,
                         exclude_parts=spec.get("exclude_database_parts", ()))
    project = database.parse_database_sources(sources)
    keys = {symbol_key(d.kind, d.owner, d.name) for d in project.package_declarations}
    assert len(keys) == 4
    assert {d.owner for d in project.package_declarations} == {"SALES_OWNER", "BILLING_OWNER"}


def test_correspondence_never_rebinds_after_move_or_changed_context():
    before = Entity("analysis-a", "engine/4", "root-a", "db/p.sql", "sha256:same",
                    symbol_key("PACKAGE", "SALES", "P"))
    exact = replace(before, analysis="analysis-b")
    moved = replace(exact, path="db/archive/p.sql")
    assert classify(before, [exact]) == ("EXACT", (exact,))
    assert classify(before, [moved]) == ("MOVED_CANDIDATE", (moved,))
    for changed in (
        replace(exact, key=symbol_key("PACKAGE", "SALES", "P2")),
        replace(exact, key=symbol_key("PACKAGE", "BILLING", "P")),
        replace(exact, key=symbol_key("PACKAGE", "SALES", "P", signature="NUMBER")),
        replace(exact, root="root-b"),
    ):
        assert classify(before, [changed]) == ("REMOVED", ())
    assert classify(before, [replace(exact, engine="engine/5")]) == ("NOT_COMPARABLE", ())
    assert classify(before, [replace(exact, source_digest="sha256:changed")]) == (
        "NOT_COMPARABLE", ())
    assert classify(before, [exact, replace(exact, path="db/duplicate.sql")]) == (
        "AMBIGUOUS", (exact, replace(exact, path="db/duplicate.sql")))
