"""Corporate Phase B lifecycle on ordinary synthetic projects and the real engine."""

from pathlib import Path

from formslang import blueprint, rbac
from formslang.project_intake import ProjectIntake
from formslang.project_service import ProjectService


def test_assessment_and_review_survive_reopen_without_reanalysis(tmp_path, monkeypatch):
    intake = ProjectIntake(tmp_path / 'data', tmp_path / 'config')
    created = intake.create_demo()
    pid = created['project']['id']
    authorize = lambda: intake.access(pid, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    result = service.analyze(expected_revision=None, expected_configuration=0)
    assert result['status'] == 'COMPLETED'
    finding = service.assessment()['blueprint']['findings'][0]
    service._store.session.review_blueprint(entity=finding['entity'], revision=finding['revision'],
        action='DEFER', reviewer='Synthetic architect', comment='Confirm business intent before generation')
    before = service.assessment(freshness=service.freshness())
    service.close()

    def no_reanalysis(*args, **kwargs):
        raise AssertionError('Reopening and freshness must not run the analysis engine')

    monkeypatch.setattr(blueprint, 'build', no_reanalysis)
    reopened_intake = ProjectIntake(tmp_path / 'data', tmp_path / 'config')
    authorize = lambda: reopened_intake.access(pid, rbac.RUN_CONVERSION)
    reopened = ProjectService(authorize(), authorize=authorize)
    try:
        fresh = reopened.freshness()
        assert fresh['status'] == 'CURRENT'
        saved = reopened.assessment(freshness=fresh)
        assert saved['analysis_revision'] == before['analysis_revision']
        assert saved['analyzed_at'] == before['analyzed_at']
        assert saved['blueprint']['findings'] == before['blueprint']['findings']
        reviewed = next(f for f in saved['blueprint']['findings'] if f['entity'] == finding['entity'])
        assert reviewed['review_history'][0]['reviewer'] == 'Synthetic architect'
        assert reviewed['review_state'] == 'DEFER'
        source = Path(created['project']['source_roots'][0]['path']) / 'shipments.xml'
        source.write_bytes(source.read_bytes() + b'\n<!-- changed synthetic source -->\n')
        stale = reopened.freshness()
        assert stale['status'] == 'STALE'
        stale_view = reopened.assessment(freshness=stale)
        stale_review = next(f for f in stale_view['blueprint']['findings'] if f['entity'] == finding['entity'])
        assert stale_review['review_state'] == 'STALE'
        assert stale_review['review_history'] == reviewed['review_history']
        assert stale_view['analysis_revision'] == saved['analysis_revision']
    finally:
        reopened.close()
