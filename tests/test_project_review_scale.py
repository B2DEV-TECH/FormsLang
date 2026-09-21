"""Synthetic persisted read/write scale; not an engine or customer benchmark."""

import json
import time

from test_project_review import reviewed_project as _reviewed_project

from examples.verify.project_overview_performance_check import build_fixture
from formslang import blueprint
from formslang.project_assessment import bind_assessment
from formslang.project_manifest import ManifestEntry
from formslang.project_review import ProjectReviewService

reviewed_project = _reviewed_project


def test_5000_findings_and_history_preserve_bounded_reads(reviewed_project, capsys):
    service = reviewed_project
    saved = service.assessment()
    _, synthetic, _ = build_fixture()
    payload = {**saved['blueprint'], **synthetic['blueprint']}
    for finding in payload['findings']:
        finding['revision'] = blueprint.digest(finding['id'])
        finding['coverage'] = {'status': 'REQUIRES_REVIEW', 'target': '', 'evidence': ''}
        finding['suggested_target'] = 'Human architecture review'
    options = {k: v for k, v in saved['analysis_options'].items() if k != '_target'}
    options['synthetic_read_scale'] = True
    assessment = bind_assessment(service.open(), tuple(ManifestEntry(**e) for e in saved['source_manifest']),
        payload, engines=saved['engine_identity'], options=options, analyzed_at=saved['analyzed_at'], status='Current')
    service._store.save_assessment(assessment, expected_revision=saved['analysis_revision'])
    review = ProjectReviewService(service)
    timings = {}

    def measure(name, fn):
        start = time.perf_counter()
        result = fn()
        timings[name + '_ms'] = round((time.perf_counter() - start) * 1000, 3)
        return result

    queue = measure('queue_first_page', service.review_queue)
    assert queue['total'] == 5000 and len(queue['rows']) == 50
    detail = measure('detail', lambda: service.review_detail(queue['rows'][0]['id']))
    measure('single_mutation', lambda: service.review_decide(detail['item']['id'], {**detail['binding'], 'action': 'DEFER'}))
    current = service.review_detail(detail['item']['id'])
    # Seed thousands of synthetic append-only events through the same transaction writer.
    with review._write(current['binding']) as snapshot:
        for finding in snapshot['blueprint']['findings']:
            review._append(snapshot, finding, {'action': 'DEFER'})
    page = measure('queue_with_5001_reviews', service.review_queue)
    assert page['total'] == 5000 and all(r['review_state'] == 'DEFER' for r in page['rows'])
    filtered = measure('priority_filter', lambda: service.review_queue(filters={'risk': 'CRITICAL', 'review': 'DEFER'}))
    assert filtered['total'] == 1000
    detail = measure('history', lambda: service.review_detail(current['item']['id']))
    assert detail['history_total'] == 2
    request = {**detail['binding'], 'action': 'REJECT', 'reason_code': 'ARCHITECTURE_DECISION',
               'findings': [{'id': r['id'], 'revision': r['finding_revision']} for r in page['rows']]}
    preview = measure('bulk_preview', lambda: service.review_bulk_preview(request))
    assert len(preview['eligible']) == 50
    applied = measure('bulk_commit', lambda: service.review_bulk_apply({**request, 'preview_token': preview['preview_token']}))
    assert applied['applied'] == 50
    assert service._store.session.db.execute('SELECT count(*) FROM blueprint_review').fetchone()[0] == 5051
    with capsys.disabled():
        print('\nPHASE_D_SYNTHETIC_SCALE ' + json.dumps(timings, sort_keys=True))
