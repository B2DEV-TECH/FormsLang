import json

from examples.verify.project_overview_performance_check import build_fixture
from formslang.project_projection import inventory_page, overview, prepare_projection


def test_large_projection_reconciles_500_forms_and_thousands_of_rows(tmp_path):
    descriptor, assessment, freshness = build_fixture()
    persisted = tmp_path / 'assessment.json'
    persisted.write_text(json.dumps(assessment), encoding='utf-8')
    loaded = json.loads(persisted.read_text(encoding='utf-8'))

    prepared = prepare_projection(descriptor, loaded, freshness, store_scope='scale-test')
    summary = overview(prepared)
    findings = inventory_page(prepared, 'findings', limit=50)
    dependencies = inventory_page(prepared, 'dependencies', limit=50)

    assert summary['inventory']['forms_modules'] == 500 == len(prepared.rows['forms'])
    assert summary['inventory']['modernization_findings'] == 5_000 == findings['total']
    assert summary['inventory']['dependencies'] == 5_000 == dependencies['total']
    assert sum(summary['risk_distribution'].values()) == findings['total']
    assert sum(summary['recommendation_distribution'].values()) == findings['total']
    assert sum(summary['intervention_distribution'].values()) == findings['total']
    assert len(findings['rows']) == len(dependencies['rows']) == 50


def test_large_projection_filters_searches_and_pages_by_one_revision():
    descriptor, assessment, freshness = build_fixture()
    prepared = prepare_projection(descriptor, assessment, freshness, store_scope='scale-test')
    critical = inventory_page(
        prepared, 'findings', filters={'risk': 'CRITICAL', 'intervention': 'MANUAL'},
        limit=50,
    )
    searched = inventory_page(prepared, 'findings', query='TRIGGER_04999', limit=50)
    second = inventory_page(
        prepared, 'forms', offset=50, limit=50,
        expected_revision=assessment['analysis_revision'],
    )

    assert critical['total'] > 0
    assert all(row['risk'] == 'CRITICAL' and row['intervention'] == 'MANUAL'
               for row in critical['rows'])
    assert searched['total'] == 1 and searched['rows'][0]['name'] == 'TRIGGER_04999'
    assert second['offset'] == 50 and len(second['rows']) == 50
