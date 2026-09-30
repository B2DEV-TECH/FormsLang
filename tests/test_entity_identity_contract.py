"""ADR-06 fixture proof only; the WP-04 product projection is separate."""

from dataclasses import replace

import pytest

from examples.verify import ecosystem_inventory as inv
from examples.verify import entity_identity_contract as contract
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


def test_wp08_inventory_retains_quoted_spelling_needed_for_identity(tmp_path):
    source = tmp_path / "quoted.sql"
    source.write_text('CREATE PACKAGE "A.B" AS PROCEDURE "MiXed"; END "A.B";', encoding="utf-8")
    [declaration] = database.parse_database_file(source).package_declarations
    assert declaration.name == "A.B"
    assert declaration.qualified_name == '"A.B"'
    assert symbol_key(declaration.kind, declaration.owner, declaration.qualified_name) == (
        "PACKAGE", None, "A.B", None, None)
    assert declaration.to_dict()["members"][0]["name"] == "MiXed"


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
    ):
        assert classify(before, [changed]) == ("NOT_COMPARABLE", ())
    assert classify(before, [replace(exact, engine="engine/5")]) == ("NOT_COMPARABLE", ())
    assert classify(before, [replace(exact, source_digest="sha256:changed")]) == (
        "NOT_COMPARABLE", ())
    assert classify(before, [exact, replace(exact, path="db/duplicate.sql")]) == (
        "AMBIGUOUS", (exact, replace(exact, path="db/duplicate.sql")))


def test_correspondence_does_not_call_another_source_root_removed():
    before = Entity("analysis-a", "engine/4", "root-a", "db/p.sql", "sha256:same",
                    symbol_key("PACKAGE", "SALES", "P"))
    other_root = replace(before, analysis="analysis-b", root="root-b")
    assert classify(before, [other_root]) == ("NOT_COMPARABLE", ())


def test_correspondence_candidates_are_deduplicated_and_ordered():
    before = Entity("analysis-a", "engine/4", "root-a", "db/p.sql", "sha256:same",
                    symbol_key("PACKAGE", "SALES", "P"))
    exact = replace(before, analysis="analysis-b")
    moved = replace(exact, path="db/z.sql")
    assert classify(before, [exact, exact]) == ("EXACT", (exact,))
    assert classify(before, [moved, exact]) == ("AMBIGUOUS", (exact, moved))
    assert classify(before, [exact, moved]) == ("AMBIGUOUS", (exact, moved))


def test_quoted_declaration_keys_do_not_fold_decoded_names_again(tmp_path):
    source = tmp_path / 'quoted.sql'
    source.write_text('CREATE PACKAGE "Sales"."Api.X" AS PROCEDURE "Submit"; END;',
                      encoding='utf-8')
    [declaration] = database.parse_database_file(source).package_declarations
    assert contract.declaration_key(declaration) == (
        'PACKAGE', 'Sales', 'Api.X', None, None)
    assert contract.declaration_key(declaration, member=declaration.parsed.subprograms[0]) == (
        'PACKAGE_SUBPROGRAM', 'Sales', 'Api.X', 'Submit', ('PROCEDURE', (), None))


def test_occurrences_are_separate_from_symbols_and_analysis_ids():
    key = symbol_key('PACKAGE', 'SALES', 'P')
    first = contract.Occurrence('root', 'db/p.sql', 1, 1, key)
    second = contract.Occurrence('root', 'db/p.sql', 4, 2, key)
    assert first != second
    assert contract.entity_id('analysis-a', first) != contract.entity_id('analysis-a', second)
    assert contract.entity_id('analysis-a', first) != contract.entity_id('analysis-b', first)
    assert contract.entity_id('analysis-a', first) == contract.entity_id('analysis-a', first)
    assert replace(first, root='another') != first
    assert replace(first, path='db/P.sql') != first


@pytest.mark.parametrize('path', ['/absolute.sql', '../p.sql', 'db/../p.sql', 'C:/p.sql'])
def test_occurrence_locator_rejects_nonlogical_paths(path):
    with pytest.raises(ValueError):
        contract.Occurrence('root', path, 1, 1, symbol_key('PACKAGE', None, 'P'))


def test_real_case_c_qualified_resolution_and_bare_ambiguity():
    spec = inv.CORPORA['case_c']
    project = database.parse_database_sources(inv._paths(
        spec['database'], suffixes=inv.DATABASE_SUFFIXES))
    declarations = [d for d in project.package_declarations if d.kind == 'PACKAGE']
    candidates = [contract.Occurrence('database', d.source_file.replace('\\', '/').rsplit('/', 1)[-1],
                    s.line_number, d.order, contract.declaration_key(d, member=s))
                  for d in declarations for s in d.parsed.subprograms]
    for owner in ('SALES_OWNER', 'BILLING_OWNER'):
        query = symbol_key('PACKAGE_SUBPROGRAM', owner, 'ORDER_API', member='SUBMIT')
        result = contract.resolve(query, candidates)
        assert result.status == 'RESOLVED'
        assert len(result.candidates) == 1 and result.candidates[0].key[1] == owner
    bare = symbol_key('PACKAGE_SUBPROGRAM', None, 'ORDER_API', member='SUBMIT')
    assert contract.resolve(bare, candidates).status == 'AMBIGUOUS'
    assert contract.resolve(bare, candidates[:1]).status == 'UNRESOLVED'
    assert contract.resolve(bare, candidates).candidates == contract.resolve(
        bare, list(reversed(candidates))).candidates


@pytest.mark.parametrize('kind', ['TABLE', 'VIEW', 'SEQUENCE'])
def test_object_kinds_and_owners_cannot_collide_in_resolution(kind):
    candidates = [contract.Occurrence('db', 'ddl.sql', i + 1, i + 1,
                  symbol_key(kind, owner, 'T')) for i, owner in enumerate(('A', 'B'))]
    assert contract.resolve(symbol_key(kind, 'A', 'T'), candidates).status == 'RESOLVED'
    assert contract.resolve(symbol_key(kind, None, 'T'), candidates).status == 'AMBIGUOUS'
    assert contract.resolve(symbol_key('PACKAGE', 'A', 'T'), candidates).status == 'UNRESOLVED'


def test_duplicate_creates_do_not_become_one_resolved_symbol():
    key = symbol_key('PACKAGE', 'S', 'P')
    first = contract.Occurrence('db', 'p.sql', 1, 1, key)
    second = replace(first, line=3, ordinal=2)
    assert contract.resolve(key, [first, second]).status == 'AMBIGUOUS'
    assert contract.resolve(key, [first, first]).status == 'RESOLVED'


def test_overloads_require_signature_and_missing_body_stays_unresolved():
    key = symbol_key('PACKAGE_SUBPROGRAM', 'S', 'P', member='X')
    a = contract.Occurrence('db', 'p.sql', 2, 1, (*key[:-1], ('NUMBER',)))
    b = replace(a, line=3, ordinal=2, key=(*key[:-1], ('VARCHAR2',)))
    assert contract.resolve(key, [a, b]).status == 'AMBIGUOUS'
    assert contract.resolve(a.key, [a, b]).candidates == (a,)
    incomplete = replace(b, key=key)
    assert contract.resolve(a.key, [a, incomplete]).status == 'AMBIGUOUS'
    assert contract.resolve(symbol_key('PACKAGE BODY', 'S', 'P'), [a, b]).status == 'UNRESOLVED'


def test_unknown_owner_cannot_support_qualified_resolution():
    missing = contract.Occurrence('db', 'p.sql', 1, 1, symbol_key('PACKAGE', None, 'P'))
    assert contract.resolve(symbol_key('PACKAGE', 'S', 'P'), [missing]).status == 'UNRESOLVED'


def test_an_incomplete_member_signature_stays_explicit_without_other_candidates():
    key = symbol_key('PACKAGE_SUBPROGRAM', 'S', 'P', member='X')
    incomplete = contract.Occurrence('db', 'p.sql', 1, 1, key)
    result = contract.resolve(key, [incomplete])
    assert result.status == 'UNRESOLVED'
    assert result.reason == 'INCOMPLETE_SIGNATURE'


def test_changed_key_at_same_locator_is_not_proof_of_removal():
    before = Entity('analysis-a', 'engine/4', 'root-a', 'db/p.sql', 'sha256:old',
                    symbol_key('PACKAGE', 'SALES', 'P'))
    changed = replace(before, analysis='analysis-b', source_digest='sha256:new',
                      key=symbol_key('PACKAGE', 'BILLING', 'P'))
    assert classify(before, [changed]) == ('NOT_COMPARABLE', ())


def test_unrelated_object_in_same_file_is_not_an_automatic_rename_candidate():
    before = Entity('analysis-a', 'engine/4', 'root-a', 'db/export.sql', 'sha256:old',
                    symbol_key('PACKAGE', 'SALES', 'P'))
    unrelated = replace(before, analysis='analysis-b', source_digest='sha256:new',
                        key=symbol_key('TABLE', 'SALES', 'OTHER'))
    assert classify(before, [unrelated]) == ('NOT_COMPARABLE', ())
    assert classify(before, [replace(unrelated, path='db/other.sql')]) == ('REMOVED', ())
    assert classify(before, []) == ('REMOVED', ())
