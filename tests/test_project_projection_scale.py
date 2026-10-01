import json

from examples.verify import project_overview_performance_check as perf_check
from examples.verify.project_overview_performance_check import build_fixture, run_measurements
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


def test_journey_composes_500_forms_on_the_scale_fixture():
    from formslang.project_journey_status import build_journey

    _, assessment, freshness = build_fixture()
    payload = build_journey(assessment, freshness, has_sources=True)
    assert len(payload['forms']) == 500
    assert [step['counts'] for step in payload['steps']] == [
        {'DONE': 500}, {'ACTION': 500}, {'BLOCKED': 500}, {'WAITING': 500}]
    assert payload['focus'] == 'DECIDE'


def test_scale_report_carries_the_journey_gate(tmp_path, monkeypatch):
    # run_measurements shells out to `git rev-parse HEAD` only to stamp the report;
    # a fixed string keeps this test independent of a git binary being on PATH.
    monkeypatch.setattr(perf_check.subprocess, 'check_output', lambda *a, **k: 'deadbeefcafe')
    report = run_measurements(tmp_path, iterations=1)
    assert report['commit'] == 'deadbeefcafe'
    gate = report['journey_gate']
    assert set(gate) == {'cold_journey_median_ms', 'cold_overview_median_ms', 'ratio', 'limit', 'within_limit'}
    assert gate['limit'] == 1.5
