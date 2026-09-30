"""WP-04: schema-aware product facts, separate from the accepted ADR probe."""

from dataclasses import replace
from pathlib import Path

import pytest

from formslang import blueprint, blueprint_io, database, database_identity
from formslang.parser import parse_xml
from formslang.project_assessment import validate_assessment
from formslang.project_model import ProjectError
from formslang.project_service import ProjectService

CASE_C = Path(__file__).parent / 'fixtures' / 'ecosystem' / 'case_c'


def test_case_c_typed_candidates_keep_each_owner_without_durable_ids():
    sources = database.parse_database_sources(CASE_C / 'database')
    candidates = database_identity.package_symbols(sources)
    for kind in ('PACKAGE', 'PACKAGE BODY', 'PACKAGE_SUBPROGRAM', 'SUBPROGRAM_BODY'):
        assert {c.key[1] for c in candidates if c.key[0] == kind} == {
            'SALES_OWNER', 'BILLING_OWNER'}
        assert len([c for c in candidates if c.key[0] == kind]) == 2
    assert all(not hasattr(c, 'id') for c in candidates)


def test_case_c_typed_resolution_selects_owner_and_withholds_bare_name():
    candidates = database_identity.package_symbols(database.parse_database_sources(CASE_C / 'database'))
    for owner in ('SALES_OWNER', 'BILLING_OWNER'):
        result = database_identity.resolve_package_reference(f'{owner}.ORDER_API.SUBMIT', candidates)
        assert result.status == 'RESOLVED'
        assert len(result.candidates) == 1
        assert result.candidates[0].key[1] == owner
    bare = database_identity.resolve_package_reference('ORDER_API.SUBMIT', candidates)
    assert bare.status == 'AMBIGUOUS'
    assert {c.key[1] for c in bare.candidates} == {'SALES_OWNER', 'BILLING_OWNER'}
    assert bare == database_identity.resolve_package_reference('ORDER_API.SUBMIT', list(reversed(candidates)))


def _symbols(tmp_path, sql):
    source = tmp_path / 'packages.sql'
    source.write_text(sql, encoding='utf-8')
    return database_identity.package_symbols(database.parse_database_file(source))


def test_typed_quoted_components_preserve_case_and_embedded_dots(tmp_path):
    candidates = _symbols(tmp_path, 'CREATE PACKAGE "Sales"."Api.X" AS PROCEDURE "Submit"; END;')
    result = database_identity.resolve_package_reference('"Sales"."Api.X"."Submit"', candidates)
    assert result.status == 'RESOLVED'
    assert result.candidates[0].key[1:4] == ('Sales', 'Api.X', 'Submit')
    assert database_identity.resolve_package_reference('SALES."Api.X"."Submit"', candidates).status == 'UNRESOLVED'


def test_typed_duplicate_declarations_and_source_roots_keep_occurrences(tmp_path):
    candidates = _symbols(tmp_path,
        'CREATE PACKAGE S.P AS PROCEDURE X; END; CREATE PACKAGE S.P AS PROCEDURE X; END;')
    result = database_identity.resolve_package_reference('S.P.X', candidates)
    assert result.status == 'AMBIGUOUS'
    assert len({c.ordinal for c in result.candidates}) == 2
    first = result.candidates[0]
    other_root = replace(first, source_file='other-root/packages.sql')
    assert database_identity.resolve_package_reference('S.P.X', [first, other_root]).status == 'AMBIGUOUS'
    assert database_identity.resolve_package_reference('S.P.X', [first, first]).status == 'RESOLVED'


def test_typed_overloads_do_not_infer_signature_and_unknown_signature_is_retained(tmp_path):
    candidates = _symbols(tmp_path,
        'CREATE PACKAGE S.P AS PROCEDURE X(a NUMBER); PROCEDURE X(a VARCHAR2); END;')
    result = database_identity.resolve_package_reference('S.P.X', candidates)
    assert result.status == 'AMBIGUOUS'
    first, second = result.candidates
    assert database_identity.resolve_package_reference('S.P.X', candidates,
        signature=first.key[4]).candidates == (first,)
    incomplete = replace(second, key=(*second.key[:4], None))
    assert database_identity.resolve_package_reference('S.P.X', [first, incomplete],
        signature=first.key[4]).status == 'AMBIGUOUS'
    assert database_identity.resolve_package_reference('S.P.X', [incomplete]).reason == 'INCOMPLETE_SIGNATURE'


def test_typed_unknown_owner_and_unique_bare_reference_do_not_invent_schema(tmp_path):
    candidates = _symbols(tmp_path, 'CREATE PACKAGE P AS PROCEDURE X; END;')
    assert database_identity.resolve_package_reference('P.X', candidates).reason == 'MISSING_SCHEMA_CONTEXT'
    assert database_identity.resolve_package_reference('S.P.X', candidates).status == 'UNRESOLVED'
    qualified = [replace(c, key=(c.key[0], 'S', *c.key[2:])) for c in candidates]
    assert database_identity.resolve_package_reference('P.X', qualified).reason == 'MISSING_SCHEMA_CONTEXT'


@pytest.mark.parametrize('reference', ['S..P.X', 'S.P.X.Y', '"S""X".P.X', 'S.P.X()', 'S.P.X -- decoy'])
def test_typed_malformed_reference_cannot_select_an_object(tmp_path, reference):
    candidates = _symbols(tmp_path, 'CREATE PACKAGE S.P AS PROCEDURE X; END;')
    assert database_identity.resolve_package_reference(reference, candidates).reason == 'UNSUPPORTED_REFERENCE'


def test_case_c_preserves_owners_and_resolves_only_qualified_package_calls(tmp_path):
    # The direct I/O boundary supplies a verified byte manifest; parsed models
    # alone cannot silently acquire a durable analysis namespace.
    result = blueprint_io.load(CASE_C / 'forms', tmp_path / 'out',
                               database_sources=[CASE_C / 'database'])
    entities = result['entities']
    owners = {'SALES_OWNER', 'BILLING_OWNER'}
    for kind in ('PACKAGE_SPEC', 'PACKAGE_BODY', 'PACKAGE_SUBPROGRAM', 'SUBPROGRAM_BODY'):
        declarations = [e for e in entities if e['type'] == kind]
        assert len(declarations) == 2
        assert {e['attributes']['owner'] for e in declarations} == owners
        assert len({e['id'] for e in declarations}) == 2
    by_id = {e['id']: e for e in entities}
    references = {e['name']: e for e in entities if e['type'] == 'ROUTINE_REFERENCE'}
    for owner in owners:
        call = references[f'{owner}.ORDER_API.SUBMIT']
        assert call['resolution'] == 'RESOLVED_TO_DATABASE_OBJECT'
        assert by_id[call['resolved_target']]['attributes']['owner'] == owner
    bare = references['ORDER_API.SUBMIT']
    assert bare['resolution'] == 'AMBIGUOUS'
    assert 'resolved_target' not in bare
    assert {by_id[nid]['attributes']['owner'] for nid in bare['resolution_candidates']} == owners
    implements = [edge for edge in result['edges'] if edge['type'] == 'IMPLEMENTS'
                  and by_id[edge['source']]['type'] == 'SUBPROGRAM_BODY']
    assert len(implements) == 2
    assert all(by_id[e['source']]['attributes']['owner'] ==
               by_id[e['target']]['attributes']['owner'] for e in implements)


def test_without_an_input_namespace_no_new_durable_package_ids_are_emitted():
    sources = database.parse_database_sources(CASE_C / 'database')
    module = parse_xml(CASE_C / 'forms' / 'SUBMIT_DESK.xml')
    result = blueprint.build([module], database_sources=sources)
    assert not [e for e in result['entities'] if e['type'] == 'PACKAGE_SPEC']
    assert result['database']['identity']['basis'] == 'UNAVAILABLE'


def test_direct_package_ids_are_deterministic_and_change_with_zero_object_bytes(tmp_path):
    source = tmp_path / 'db'
    source.mkdir()
    (source / 'p.sql').write_text('CREATE PACKAGE S.P AS PROCEDURE X; END;', encoding='utf-8')
    zero = source / 'empty.sql'
    zero.write_text('-- no objects', encoding='utf-8')
    def build():
        return blueprint_io.load(CASE_C / 'forms', tmp_path / 'out', database_sources=[source])
    first, same = build(), build()
    assert first == same
    zero.write_text('-- changed zero-object bytes', encoding='utf-8')
    changed = build()
    ids = lambda value: {e['id'] for e in value['entities'] if e['type'] == 'PACKAGE_SPEC'}
    assert ids(first) and ids(first).isdisjoint(ids(changed))


def test_duplicate_and_overloaded_package_members_stay_distinct_without_arbitrary_implements(tmp_path):
    sql = tmp_path / 'p.sql'
    sql.write_text('''CREATE PACKAGE S.P AS PROCEDURE X(a NUMBER); PROCEDURE X(a VARCHAR2); END;
CREATE PACKAGE S.P AS PROCEDURE X(a NUMBER); END;
CREATE PACKAGE BODY S.P AS PROCEDURE X(a NUMBER) IS BEGIN NULL; END; END;
''', encoding='utf-8')
    result = blueprint_io.load(CASE_C / 'forms', tmp_path / 'out', database_sources=[sql])
    specs = [e for e in result['entities'] if e['type'] == 'PACKAGE_SUBPROGRAM']
    assert len(specs) == 3 and len({e['id'] for e in specs}) == 3
    nodes = {e['id']: e for e in result['entities']}
    assert not [e for e in result['edges'] if e['type'] == 'IMPLEMENTS'
                and nodes[e['source']]['type'] == 'SUBPROGRAM_BODY']


def test_case_c_project_facts_match_direct_and_namespace_matches_published_revision(project_sources, tmp_path):
    access, descriptor, xml = project_sources
    xml.write_bytes((CASE_C / 'forms' / 'SUBMIT_DESK.xml').read_bytes())
    root = Path(descriptor.source_roots[1].path)
    for source in (CASE_C / 'database').iterdir():
        (root / source.name).write_bytes(source.read_bytes())
    service = ProjectService(access)
    service.create(descriptor.name, roots=descriptor.source_roots)
    try:
        service.analyze(expected_revision=None, expected_configuration=0)
        saved = service.assessment()
        result = saved['blueprint']
        assert result['database']['identity']['basis'] == 'PROJECT_ANALYSIS_REVISION'
        assert result['database']['identity']['analysis_identity'] == saved['analysis_revision']
        direct = blueprint_io.load(xml, tmp_path / 'out', database_sources=[root])
        def facts(value):
            return sorted((e['type'], e['name'], e['attributes'].get('owner'))
                          for e in value['entities'] if 'analysis_identity' in e['attributes'])
        assert facts(result) == facts(direct) and len(facts(result)) == 8
        for value in (result, direct):
            refs = {e['name']: e for e in value['entities'] if e['type'] == 'ROUTINE_REFERENCE'}
            assert refs['ORDER_API.SUBMIT']['resolution'] == 'AMBIGUOUS'
            assert refs['SALES_OWNER.ORDER_API.SUBMIT']['resolution'] == 'RESOLVED_TO_DATABASE_OBJECT'
        result['database']['identity']['analysis_identity'] = '0' * 64
        with pytest.raises(ProjectError, match='identity'):
            validate_assessment(replace(descriptor, id=saved['project_id']), saved)
    finally:
        service.close()


def test_quoted_package_members_keep_display_case_and_schema_association(tmp_path):
    sql = tmp_path / 'quoted.sql'
    sql.write_text('''CREATE PACKAGE "Sales"."Api.X" AS PROCEDURE "Submit"; END;
CREATE PACKAGE BODY "Sales"."Api.X" AS PROCEDURE "Submit" IS BEGIN NULL; END; END;
CREATE PACKAGE "SALES"."Api.X" AS PROCEDURE "Submit"; END;
''', encoding='utf-8')
    result = blueprint_io.load(CASE_C / 'forms', tmp_path / 'out', database_sources=[sql])
    nodes = {e['id']: e for e in result['entities']}
    members = [e for e in nodes.values() if e['type'] == 'PACKAGE_SUBPROGRAM']
    assert {e['name'] for e in members} == {'"Sales"."Api.X"."Submit"', 'SALES."Api.X"."Submit"'}
    edges = [e for e in result['edges'] if e['type'] == 'IMPLEMENTS'
             and nodes[e['source']]['type'] == 'SUBPROGRAM_BODY']
    assert len(edges) == 1
    assert nodes[edges[0]['target']]['attributes']['owner'] == 'Sales'


@pytest.mark.parametrize('boundary', ['direct', 'discovery', 'assessment'])
def test_case_c_occurrence_counts_are_additive_at_every_input_boundary(project_sources, tmp_path, boundary):
    access, descriptor, xml = project_sources
    root = Path(descriptor.source_roots[1].path)
    (root / 'packages.sql').write_text('\n'.join(p.read_text(encoding='utf-8')
        for p in sorted((CASE_C / 'database').iterdir())), encoding='utf-8')
    service = ProjectService(access)
    service.create(descriptor.name, roots=descriptor.source_roots)
    try:
        if boundary == 'direct':
            counts = blueprint_io.load(xml, tmp_path / 'out', database_sources=root)['database']
        elif boundary == 'discovery':
            counts = service.discover()['inventory']['database']
        else:
            service.analyze(expected_revision=None, expected_configuration=0)
            counts = service.assessment()['inventory']['database']
        assert counts['package_specs'] == counts['package_bodies'] == 0
        assert counts['package_spec_occurrences'] == counts['package_body_occurrences'] == 2
    finally:
        service.close()


@pytest.mark.parametrize('names', [('"Sales".P', '"sales".P'), ('S."Api"', 'S."api"')])
@pytest.mark.parametrize('projection', ['inventory', 'map'])
def test_quoted_package_case_stays_distinct_in_project_projections(project_sources, names, projection):
    access, descriptor, _ = project_sources
    root = Path(descriptor.source_roots[1].path)
    (root / 'quoted.sql').write_text('\n'.join(
        f'CREATE PACKAGE {name} AS PROCEDURE X; END;\n'
        f'CREATE PACKAGE BODY {name} AS PROCEDURE X IS BEGIN NULL; END; END;'
        for name in names), encoding='utf-8')
    service = ProjectService(access)
    service.create(descriptor.name, roots=descriptor.source_roots)
    try:
        service.analyze(expected_revision=None, expected_configuration=0)
        if projection == 'inventory':
            rows = service.inventory('packages')['rows']
        else:
            rows = [n for n in service.system_map(view='ESTATE', layer='DATABASE')['nodes']
                    if n['type'] == 'PACKAGE']
        assert len(rows) == 2
        assert {row['name'] for row in rows} == set(names)
        assert len({row['id'] for row in rows}) == 2
    finally:
        service.close()


def test_package_row_ids_are_stable_within_the_same_snapshot_and_input_order(project_sources, tmp_path):
    from formslang.project_projection import _package_rows

    access, descriptor, xml = project_sources
    root = Path(descriptor.source_roots[1].path)
    spec, body = root / 'p.pks', root / 'p.pkb'
    spec.write_text('CREATE PACKAGE S.P AS PROCEDURE X; END;', encoding='utf-8')
    body.write_text('CREATE PACKAGE BODY S.P AS PROCEDURE X IS BEGIN NULL; END; END;', encoding='utf-8')
    def direct(paths):
        result = blueprint_io.load(xml, tmp_path / 'out', database_sources=paths)
        assert [e['id'] for e in result['entities']] == sorted(e['id'] for e in result['entities'])
        return [row['id'] for row in _package_rows(
            {e['id']: e for e in result['entities']}, {}, result['edges'])]
    first = direct([spec, body])
    assert first == direct([spec, body]) == direct([body, spec])
    service = ProjectService(access)
    service.create(descriptor.name, roots=descriptor.source_roots)
    try:
        service.analyze(expected_revision=None, expected_configuration=0)
        first_rows = [row['id'] for row in service.inventory('packages')['rows']]
        revision = service.assessment()['analysis_revision']
        service.analyze(expected_revision=revision, expected_configuration=0)
        assert [row['id'] for row in service.inventory('packages')['rows']] == first_rows
        assert service.assessment()['analysis_revision'] == revision
    finally:
        service.close()
    body.write_text(body.read_text(encoding='utf-8') + '\n-- a new byte snapshot', encoding='utf-8')
    assert direct([spec, body]) != first  # No cross-snapshot continuity claim.
