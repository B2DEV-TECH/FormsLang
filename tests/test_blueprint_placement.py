"""WP-11: preserve declared window/canvas facts without choosing a layout."""

from pathlib import Path

import pytest

from formslang import blueprint
from formslang.parser import parse_xml

VISUAL = Path(__file__).parent / 'fixtures' / 'ecosystem' / 'visual_hierarchy'


def build(path):
    return blueprint.build([parse_xml(path)], source_keys=[path.name])


def visual_nodes(result):
    return {e['name']: e for e in result['entities'] if e['type'] in {'CANVAS', 'WINDOW'}}


def test_case_d_keeps_both_conflicting_window_canvas_declarations():
    result = build(VISUAL / 'SCREENS.xml')
    nodes = visual_nodes(result)
    assert nodes['CV_SHARED']['attributes']['window_name'] == 'WIN_MAIN'
    assert nodes['WIN_SIDE']['attributes']['primary_canvas'] == 'CV_SHARED'
    facts = {(e['source'], e['type'], e['target']): e for e in result['edges']}
    canvas = facts[nodes['CV_SHARED']['id'], 'CANVAS_IN_WINDOW', nodes['WIN_MAIN']['id']]
    primary = facts[nodes['WIN_SIDE']['id'], 'WINDOW_PRIMARY_CANVAS', nodes['CV_SHARED']['id']]
    assert canvas['level'] == primary['level'] == 'FACT'
    assert canvas['placement']['conflict'] is primary['placement']['conflict'] is True
    assert canvas['placement']['resolution'] == primary['placement']['resolution'] == 'RESOLVED'
    evidence = {p['id']: p for p in result['evidence']}
    assert any('WindowName: WIN_MAIN' in evidence[p]['text'] for p in canvas['evidence'])
    assert any('PrimaryCanvas: CV_SHARED' in evidence[p]['text'] for p in primary['evidence'])
    assert set(canvas['placement']['conflicting_evidence']) == set(primary['evidence'])
    assert set(primary['placement']['conflicting_evidence']) == set(canvas['evidence'])
    assert not facts[nodes['CV_MAIN']['id'], 'CANVAS_IN_WINDOW', nodes['WIN_MAIN']['id']]['placement']['conflict']


def test_case_d_undeclared_window_stays_a_scoped_unresolved_target():
    result = build(VISUAL / 'SCREENS.xml')
    nodes = visual_nodes(result)
    orphan = nodes['CV_ORPHAN']
    edges = [e for e in result['edges'] if e['source'] == orphan['id'] and e['type'] == 'CANVAS_IN_WINDOW']
    assert len(edges) == 1
    target = next(e for e in result['entities'] if e['id'] == edges[0]['target'])
    assert target['type'] == 'WINDOW_REFERENCE' and target['name'] == 'WIN_NOT_DECLARED'
    assert target['module'] == orphan['module']
    assert edges[0]['placement']['resolution'] == 'UNRESOLVED'
    assert orphan['attributes']['window_placement']['resolution'] == 'UNRESOLVED'
    assert not any(e['type'] == 'WINDOW' and e['name'] == 'WIN_NOT_DECLARED' for e in result['entities'])


def test_empty_target_and_missing_primary_canvas_are_not_inferred(tmp_path):
    path = tmp_path / 'placement.xml'
    path.write_text('''<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="F">
      <Canvas Name="UNPLACED"/><Window Name="W" PrimaryCanvas="NOT_DECLARED"/>
      <Window Name="NO_PRIMARY"/></FormModule></Module>''', encoding='utf-8')
    result = build(path)
    nodes = visual_nodes(result)
    assert nodes['UNPLACED']['attributes']['window_placement']['resolution'] == 'NOT_DECLARED'
    assert nodes['NO_PRIMARY']['attributes']['primary_canvas_placement']['resolution'] == 'NOT_DECLARED'
    assert not [e for e in result['edges'] if e['source'] == nodes['UNPLACED']['id'] and e['type'] == 'CANVAS_IN_WINDOW']
    [edge] = [e for e in result['edges'] if e['source'] == nodes['W']['id'] and e['type'] == 'WINDOW_PRIMARY_CANVAS']
    assert edge['placement']['resolution'] == 'UNRESOLVED'
    target = next(e for e in result['entities'] if e['id'] == edge['target'])
    assert target['type'] == 'CANVAS_REFERENCE' and target['name'] == 'NOT_DECLARED'


def test_conflicting_declarations_remain_conflicting_when_window_is_missing(tmp_path):
    path = tmp_path / 'missing.xml'
    path.write_text('''<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="F"><Canvas Name="C" WindowName="ABSENT"/>
      <Window Name="W" PrimaryCanvas="C"/></FormModule></Module>''', encoding='utf-8')
    result = build(path)
    edges = [e for e in result['edges'] if e['type'] in {'CANVAS_IN_WINDOW', 'WINDOW_PRIMARY_CANVAS'}]
    assert len(edges) == 2
    assert all(e['placement']['conflict'] for e in edges)
    assert {e['placement']['resolution'] for e in edges} == {'RESOLVED', 'UNRESOLVED'}


@pytest.mark.parametrize('declarations', ['<Window Name="W"/><Window Name="w"/>',
                                         '<Window Name="W"/><Window Name="W"/>'])
def test_duplicate_or_case_colliding_targets_are_ambiguous(tmp_path, declarations):
    path = tmp_path / 'ambiguous.xml'
    path.write_text(f'<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="F"><Canvas Name="C" WindowName="W"/>{declarations}</FormModule></Module>', encoding='utf-8')
    result = build(path)
    [edge] = [e for e in result['edges'] if e['type'] == 'CANVAS_IN_WINDOW']
    assert edge['placement']['resolution'] == 'AMBIGUOUS'
    target = next(e for e in result['entities'] if e['id'] == edge['target'])
    assert target['type'] == 'WINDOW_REFERENCE'


def test_legacy_model_without_window_details_does_not_claim_no_primary_canvas():
    module = parse_xml(VISUAL / 'SCREENS.xml')
    module.window_details = {}
    result = blueprint.build([module])
    windows = [e for e in result['entities'] if e['type'] == 'WINDOW']
    assert all(e['attributes']['primary_canvas_placement']['resolution'] == 'UNAVAILABLE' for e in windows)
    assert not any(e['type'] == 'WINDOW_PRIMARY_CANVAS' for e in result['edges'])


def test_shared_placement_module_participates_in_engine_identity(monkeypatch):
    from formslang.project_manifest import engine_identity

    before = engine_identity()
    read_bytes = Path.read_bytes
    def changed(path):
        result = read_bytes(path)
        return result + b'\n# synthetic placement engine change\n' if path.name == 'blueprint_placement.py' else result
    monkeypatch.setattr(Path, 'read_bytes', changed)
    after = engine_identity()
    assert before != after
    assert before['blueprint_placement.sha256'] != after['blueprint_placement.sha256']


def placement_facts(result):
    nodes = {e['id']: e for e in result['entities']}
    proofs = {p['id']: p['text'] for p in result['evidence']}
    return sorted((nodes[e['source']]['name'], e['type'], nodes[e['target']]['type'],
                   nodes[e['target']]['name'], e['placement']['resolution'],
                   e['placement']['conflict'], tuple(sorted(proofs[p] for p in e['evidence'])),
                   tuple(sorted(proofs[p] for p in e['placement']['conflicting_evidence'])))
                  for e in result['edges'] if 'placement' in e)


def test_real_fixture_direct_and_saved_project_have_the_same_placement(project_sources, tmp_path):
    from formslang import blueprint_io
    from formslang.project_service import ProjectService

    access, descriptor, xml = project_sources
    xml.write_bytes((VISUAL / 'SCREENS.xml').read_bytes())
    direct = blueprint_io.load(xml, tmp_path / 'out')
    service = ProjectService(access)
    service.create(descriptor.name, roots=descriptor.source_roots)
    try:
        service.analyze(expected_revision=None, expected_configuration=0)
        saved = service.assessment()
        assert placement_facts(saved['blueprint']) == placement_facts(direct)
        assert any(row[5] for row in placement_facts(direct))
    finally:
        service.close()
    reopened = ProjectService(access)
    try:
        assert reopened.assessment()['blueprint'] == saved['blueprint']
    finally:
        reopened.close()


def test_visual_references_never_resolve_across_forms_and_order_is_deterministic(tmp_path):
    first = parse_xml(VISUAL / 'SCREENS.xml')
    path = tmp_path / 'other.xml'
    path.write_text('''<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="OTHER">
      <Window Name="WIN_NOT_DECLARED"/></FormModule></Module>''', encoding='utf-8')
    second = parse_xml(path)
    forward = blueprint.build([first, second], source_keys=['first.xml', 'second.xml'])
    reverse = blueprint.build([second, first], source_keys=['second.xml', 'first.xml'])
    assert forward['entities'] == reverse['entities']
    assert forward['edges'] == reverse['edges']
    assert forward['evidence'] == reverse['evidence']
    [orphan] = [r for r in placement_facts(forward) if r[0] == 'CV_ORPHAN']
    assert orphan[2:5] == ('WINDOW_REFERENCE', 'WIN_NOT_DECLARED', 'UNRESOLVED')


def test_primary_canvas_never_invents_the_inverse_placement(tmp_path):
    path = tmp_path / 'one_way.xml'
    path.write_text('''<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="F">
      <Canvas Name="C"/><Window Name="W" PrimaryCanvas="C"/></FormModule></Module>''', encoding='utf-8')
    result = build(path)
    facts = placement_facts(result)
    assert len(facts) == 1
    assert facts[0][:6] == ('W', 'WINDOW_PRIMARY_CANVAS', 'CANVAS', 'C', 'RESOLVED', False)
    assert not any(p['text'].startswith('WindowName:') for p in result['evidence'])
    assert visual_nodes(result)['C']['attributes']['window_placement']['resolution'] == 'NOT_DECLARED'


@pytest.mark.parametrize('declarations,kind,attribute', [
    ('<Canvas Name="C" WindowName="W1"/><Canvas Name="C" WindowName="W2"/>',
     'CANVAS', 'window_placement'),
    ('<Window Name="W" PrimaryCanvas="C1"/><Window Name="W" PrimaryCanvas="C2"/>',
     'WINDOW', 'primary_canvas_placement'),
])
def test_ambiguous_source_declarations_do_not_choose_a_property(tmp_path, declarations, kind, attribute):
    path = tmp_path / 'duplicate.xml'
    path.write_text(f'<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="F">{declarations}</FormModule></Module>', encoding='utf-8')
    result = build(path)
    [node] = [e for e in result['entities'] if e['type'] == kind]
    assert node['attributes'][attribute]['resolution'] == 'AMBIGUOUS'
    assert node['attributes'][attribute]['reason'] == 'SOURCE_DECLARATION_AMBIGUOUS'
    assert node['attributes'][attribute]['source_declaration_count'] == 2
    assert not placement_facts(result)
