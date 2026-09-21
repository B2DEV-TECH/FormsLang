"""Real project governance: engine evidence, human overlay and revision safety."""

from dataclasses import replace

import pytest

from formslang import rbac
from formslang.project_intake import ProjectIntake
from formslang.project_model import ProjectError, RevisionConflict
from formslang.project_service import ProjectService


@pytest.fixture
def reviewed_project(tmp_path, monkeypatch):
    monkeypatch.setenv('FORMSLANG_AUTH', '0')
    intake = ProjectIntake(tmp_path / 'data', tmp_path / 'config')
    created = intake.create_demo(destination=tmp_path / 'demo')
    project_id = created['project']['id']
    authorize = lambda: intake.access(project_id, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    descriptor = service.open()
    service.analyze(expected_revision=descriptor.analysis_revision,
                    expected_configuration=service._store.configuration_revision())
    yield service
    service.close()


def first_detail(service, **filters):
    rows = service.review_queue(filters=filters)['rows']
    assert rows, 'synthetic demo must expose the requested real findings'
    return service.review_detail(rows[0]['id'])


def command(detail, **values):
    return {**detail['binding'], **values}


def test_accept_preserves_engine_and_replay_conflicts(reviewed_project):
    service = reviewed_project
    detail = first_detail(service)
    original = detail['engine_recommendation']
    service.review_decide(detail['item']['id'], command(detail, action='APPROVE'))
    current = service.review_detail(detail['item']['id'])
    assert current['item']['review_state'] == 'APPROVE'
    assert current['engine_recommendation'] == original
    assert current['binding']['review_revision'] == detail['binding']['review_revision'] + 1
    assert current['history'][0]['rationale'] == 'Accepted engine recommendation.'
    with pytest.raises(RevisionConflict):
        service.review_decide(detail['item']['id'], command(detail, action='APPROVE'))
    assert len(service.review_detail(detail['item']['id'])['history']) == 1
    progress = service.overview(freshness=service.freshness())['review_progress']
    assert progress['reviewed'] == 1
    assert progress['critical_resolved'] == 1
    assert progress['critical_total'] >= 1
    assert progress['manual_total'] >= progress['manual_resolved']


def test_critical_override_requires_rationale_and_explicit_confirmation(reviewed_project):
    service = reviewed_project
    detail = first_detail(service, risk='CRITICAL')
    for values in ({'rationale': 'Reviewed ownership'}, {'critical_confirmed': True},
                   {'rationale': 'Reviewed ownership', 'critical_confirmed': 'true'}):
        with pytest.raises(ProjectError):
            service.review_decide(detail['item']['id'], command(
                detail, action='MODIFY', recommendation='PRESERVE', **values))
    service.review_decide(detail['item']['id'], command(detail, action='MODIFY',
        recommendation='PRESERVE', rationale='Reviewed ownership', critical_confirmed=True))
    current = service.review_detail(detail['item']['id'])
    assert current['human_decision']['recommendation'] == 'PRESERVE'
    assert current['engine_recommendation'] == detail['engine_recommendation']


@pytest.mark.parametrize('action', ['REJECT', 'DEFER'])
def test_unresolved_actions_do_not_count_as_resolved(reviewed_project, action):
    service = reviewed_project
    detail = first_detail(service)
    service.review_decide(detail['item']['id'], command(detail, action=action,
                          reason_code='BUSINESS_OWNER_INPUT'))
    assert service.review_detail(detail['item']['id'])['item']['review_state'] == action
    assert service.overview(freshness=service.freshness())['review_progress']['reviewed'] == 0


def test_annotations_are_separate_and_survive_reopen(reviewed_project):
    service = reviewed_project
    detail = first_detail(service)
    service.review_annotate(detail['item']['id'], command(detail,
        kind='CONFIRMED_BUSINESS_RULE', note='<script>alert(1)</script>'))
    service.close()
    current = service.review_detail(detail['item']['id'])
    assert current['item']['review_state'] == 'PENDING'
    assert current['history'] == []
    assert current['annotations'][0]['note'] == '<script>alert(1)</script>'
    assert current['binding']['review_revision'] == detail['binding']['review_revision'] + 1


def test_viewer_and_foreign_finding_cannot_mutate(reviewed_project):
    service = reviewed_project
    detail = first_detail(service)
    with pytest.raises(LookupError):
        service.review_decide('foreign-finding', command(detail, action='APPROVE'))
    viewer = ProjectService(replace(service.access, actions=frozenset({rbac.VIEW_PROJECT})))
    try:
        with pytest.raises(PermissionError):
            viewer.review_decide(detail['item']['id'], command(detail, action='APPROVE'))
    finally:
        viewer.close()
    assert service.review_detail(detail['item']['id'])['history'] == []


def test_source_change_rejects_old_decision_and_retains_history(reviewed_project):
    service = reviewed_project
    detail = first_detail(service)
    service.review_decide(detail['item']['id'], command(detail, action='APPROVE'))
    current = service.review_detail(detail['item']['id'])
    root = service.open().source_roots[0]
    source = next((service.access.root / root.path).rglob('*.xml'))
    source.write_bytes(source.read_bytes() + b'\n<!-- changed -->\n')
    with pytest.raises(RevisionConflict):
        service.review_decide(detail['item']['id'], command(current, action='DEFER'))
    stale = service.review_detail(detail['item']['id'])
    assert stale['item']['review_state'] == 'STALE'
    assert len(stale['history']) == 1


def test_bulk_preview_excludes_critical_and_rejects_stale_preview(reviewed_project):
    service = reviewed_project
    detail = first_detail(service, risk='CRITICAL')
    request = {**detail['binding'], 'action': 'APPROVE',
               'findings': [{'id': detail['item']['id'], 'revision': detail['binding']['finding_revision']}]}
    preview = service.review_bulk_preview(request)
    assert preview['eligible'] == []
    assert 'RISK_NOT_LOW' in preview['excluded'][0]['reasons']
    service.review_decide(detail['item']['id'], command(detail, action='DEFER'))
    with pytest.raises(RevisionConflict):
        service.review_bulk_apply({**request, 'preview_token': preview['preview_token']})
    assert len(service.review_detail(detail['item']['id'])['history']) == 1


def test_real_native_confirmation_is_bulk_eligible(reviewed_project):
    service = reviewed_project
    page = service.review_queue(filters={'risk': 'LOW', 'intervention': 'AUTO'})
    rows = [r for r in page['rows'] if r['recommendation'] == 'REPLACE_WITH_APEX_NATIVE']
    assert rows
    detail = service.review_detail(rows[0]['id'])
    request = {**detail['binding'], 'action': 'APPROVE',
               'findings': [{'id': rows[0]['id'], 'revision': detail['binding']['finding_revision']}]}
    preview = service.review_bulk_preview(request)
    assert preview['eligible'] == [rows[0]['id']]
    result = service.review_bulk_apply({**request, 'preview_token': preview['preview_token']})
    assert result['applied'] == 1
    assert service.review_detail(rows[0]['id'])['item']['review_state'] == 'APPROVE'


def test_unsupported_recommendation_cannot_be_accepted():
    from formslang.project_review import ProjectReviewService
    review = ProjectReviewService.__new__(ProjectReviewService)
    for value in ('UNKNOWN', 'WRAP_AS_API', 'FUTURE_ENUM'):
        with pytest.raises(ProjectError):
            review._validate_decision({}, {'recommendation': value}, {'action': 'APPROVE'})


def test_annotation_is_fully_bound_and_stale_after_source_change(reviewed_project):
    import json
    service = reviewed_project
    detail = first_detail(service)
    service.review_annotate(detail['item']['id'], command(detail, kind='DATABASE_API_AUTHORITATIVE'))
    saved = service._store.session.db.execute('SELECT binding_json FROM blueprint_annotation').fetchone()[0]
    binding = json.loads(saved)
    assert binding['engine_recommendation'] == detail['engine_recommendation']
    assert binding['target']['version'] == '26.1'
    assert binding['engine_version']
    root = service.open().source_roots[0]
    source = next((service.access.root / root.path).rglob('*.xml'))
    source.write_bytes(source.read_bytes() + b'\n<!-- changed -->')
    assert service.review_detail(detail['item']['id'])['annotations'][0]['applicable'] is False


def test_source_excerpt_suppresses_credentials_and_host_paths():
    from formslang import project_review
    for source in ("BEGIN LOGON('APP_USER', 'EXAMPLE_PASSWORD_123'); END;",
                   "-- password: PRIVATE_SECRET\nbegin null; end;",
                   "BEGIN HOST('C:\\private\\client.exe'); END;",
                   "BEGIN x := q'[PRIVATE_SECRET]'; END;"):
        result = project_review.safe_excerpt(source)
        assert 'EXAMPLE_PASSWORD_123' not in result
        assert 'PRIVATE_SECRET' not in result
        assert 'C:\\private' not in result


@pytest.mark.parametrize('source', [
    "BEGIN x := '/*'; -- */\ny := 'PRIVATE_VALUE_123'; END;",
    "BEGIN x := 'PRIVATE_VALUE_123",
    'BEGIN x := "PRIVATE_VALUE_123"; END;',
])
def test_structural_excerpt_never_leaks_literal_tokens(source):
    from formslang.project_review import safe_excerpt
    assert 'PRIVATE_VALUE_123' not in safe_excerpt(source)


def test_bulk_excludes_incoming_cross_module_impact(reviewed_project):
    from formslang.project_review import ProjectReviewService
    review = ProjectReviewService(reviewed_project)
    assessment, _ = review._read()
    finding = next(f for f in assessment['blueprint']['findings']
                   if f['recommendation'] == 'REPLACE_WITH_APEX_NATIVE')
    request = {**first_detail(reviewed_project)['binding'], 'action': 'APPROVE',
               'findings': [{'id': finding['id'], 'revision': finding['revision']}]}
    assert review._preview(assessment, request)['eligible'] == [finding['id']]
    assessment['blueprint']['entities'].append({'id': 'external-caller', 'module': 'other.xml'})
    assessment['blueprint']['edges'].append({'source': 'external-caller',
        'target': finding['entity'], 'type': 'USES_PROGRAM_UNIT'})
    assert review._preview(assessment, request)['eligible'] == []


def test_annotation_between_read_snapshots_returns_conflict(reviewed_project, monkeypatch):
    from formslang.project_review import ProjectReviewService
    service = reviewed_project
    detail = first_detail(service)
    original = ProjectReviewService._read

    def interleaved(review):
        result = original(review)
        service.review_annotate(detail['item']['id'], command(detail,
            kind='CONFIRMED_BUSINESS_RULE', note='Concurrent annotation'))
        return result

    monkeypatch.setattr(ProjectReviewService, '_read', interleaved)
    with pytest.raises(RevisionConflict):
        service.review_detail(detail['item']['id'])


def test_defer_history_preserves_structured_context(reviewed_project):
    service = reviewed_project
    detail = first_detail(service)
    service.review_decide(detail['item']['id'], command(detail, action='DEFER',
        reason_code='BUSINESS_OWNER_INPUT', owner='Architecture team', note='Confirm approval owner'))
    event = service.review_detail(detail['item']['id'])['history'][0]
    assert event['human_context']['owner'] == 'Architecture team'
    assert event['human_context']['note'] == 'Confirm approval owner'


def test_source_change_during_review_rolls_back_event(reviewed_project, monkeypatch):
    from formslang.project_review import ProjectReviewService
    service = reviewed_project
    detail = first_detail(service)
    original = ProjectReviewService._append
    root = service.open().source_roots[0]
    source = next((service.access.root / root.path).rglob('*.xml'))

    def interleaved(review, assessment, finding, request):
        original(review, assessment, finding, request)
        source.write_bytes(source.read_bytes() + b'\n<!-- concurrent change -->')

    monkeypatch.setattr(ProjectReviewService, '_append', interleaved)
    with pytest.raises(RevisionConflict):
        service.review_decide(detail['item']['id'], command(detail, action='APPROVE'))
    assert service._store.session.db.execute('SELECT count(*) FROM blueprint_review').fetchone()[0] == 0


def test_bulk_excludes_manual_builtin_even_with_native_confirmation_signal(reviewed_project):
    service = reviewed_project
    root = service.open().source_roots[0]
    source = next(p for p in (service.access.root / root.path).rglob('*.xml') if 'SHOW_ALERT' in p.read_text())
    original = source.read_text(encoding='utf-8')
    changed = original.replace('IF SHOW_ALERT', 'LOCK_RECORD; IF SHOW_ALERT')
    assert changed != original
    source.write_text(changed, encoding='utf-8')
    descriptor = service.open()
    service.analyze(expected_revision=descriptor.analysis_revision,
                    expected_configuration=service._store.configuration_revision())
    page = service.review_queue(filters={'risk': 'LOW', 'intervention': 'AUTO'})
    row = next(r for r in page['rows'] if r['recommendation'] == 'REPLACE_WITH_APEX_NATIVE')
    detail = service.review_detail(row['id'])
    request = {**detail['binding'], 'action': 'APPROVE',
               'findings': [{'id': row['id'], 'revision': detail['binding']['finding_revision']}]}
    preview = service.review_bulk_preview(request)
    assert preview['eligible'] == []
    assert 'REQUIRES_INDIVIDUAL_EVIDENCE_REVIEW' in preview['excluded'][0]['reasons']


def test_two_connections_cannot_overwrite_a_newer_review(reviewed_project):
    service = reviewed_project
    detail = first_detail(service)
    second = ProjectService(service.access, authorize=service._authorize_callback)
    try:
        old = second.review_detail(detail['item']['id'])
        service.review_decide(detail['item']['id'], command(detail, action='DEFER'))
        with pytest.raises(RevisionConflict):
            second.review_decide(detail['item']['id'], command(old, action='APPROVE'))
        assert len(second.review_detail(detail['item']['id'])['history']) == 1
    finally:
        second.close()


def test_cross_project_same_finding_identity_rejects_foreign_binding(reviewed_project, tmp_path):
    service = reviewed_project
    detail = first_detail(service)
    intake = ProjectIntake(tmp_path / 'other-data', tmp_path / 'other-config')
    created = intake.create_demo(destination=tmp_path / 'other-demo')
    authorize = lambda: intake.access(created['project']['id'], rbac.RUN_CONVERSION)
    second = ProjectService(authorize(), authorize=authorize)
    try:
        descriptor = second.open()
        second.analyze(expected_revision=descriptor.analysis_revision,
                       expected_configuration=second._store.configuration_revision())
        with pytest.raises(RevisionConflict):
            second.review_decide(detail['item']['id'], command(detail, action='APPROVE'))
        assert second._store.session.db.execute('SELECT count(*) FROM blueprint_review').fetchone()[0] == 0
    finally:
        second.close()


def test_simultaneous_reviewers_have_exactly_one_winner(reviewed_project):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from formslang.project_model import ProjectBusy
    service = reviewed_project
    detail = first_detail(service)
    barrier = Barrier(2)

    def decide():
        other = ProjectService(service.access, authorize=service._authorize_callback)
        try:
            other.open()
            barrier.wait(timeout=10)
            try:
                other.review_decide(detail['item']['id'], command(detail, action='APPROVE'))
                return 'saved'
            except (ProjectBusy, RevisionConflict):
                return 'conflict'
        finally:
            other.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: decide(), range(2)))
    assert sorted(results) == ['conflict', 'saved']
    assert len(service.review_detail(detail['item']['id'])['history']) == 1


def test_analysis_worker_blocks_review_without_history(reviewed_project):
    from formslang.project_lock import project_worker_lock
    from formslang.project_model import ProjectBusy
    service = reviewed_project
    detail = first_detail(service)
    with project_worker_lock(service.access.root), pytest.raises(ProjectBusy):
        service.review_decide(detail['item']['id'], command(detail, action='APPROVE'))
    assert service.review_detail(detail['item']['id'])['history'] == []


def test_bulk_failure_rolls_back_all_events_and_revision(reviewed_project, monkeypatch):
    from formslang.project_review import ProjectReviewService
    service = reviewed_project
    page = service.review_queue()
    rows = page['rows'][:2]
    detail = service.review_detail(rows[0]['id'])
    request = {**detail['binding'], 'action': 'DEFER',
               'findings': [{'id': row['id'], 'revision': row['finding_revision']} for row in rows]}
    preview = service.review_bulk_preview(request)
    original = ProjectReviewService._append
    calls = 0

    def failing(review, assessment, finding, command):
        nonlocal calls
        calls += 1
        original(review, assessment, finding, command)
        if calls == 2:
            raise ProjectError('Injected failure after second append')

    monkeypatch.setattr(ProjectReviewService, '_append', failing)
    with pytest.raises(ProjectError, match='Injected failure'):
        service.review_bulk_apply({**request, 'preview_token': preview['preview_token']})
    assert service._store.session.db.execute('SELECT count(*) FROM blueprint_review').fetchone()[0] == 0
    assert service.review_detail(rows[0]['id'])['binding']['review_revision'] == detail['binding']['review_revision']
