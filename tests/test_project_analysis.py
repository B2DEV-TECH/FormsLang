"""One deterministic pipeline powers all project interfaces without external setup."""

import multiprocessing
import os

import pytest

from formslang import ai, oracle
from formslang.project_model import ProjectBusy
from formslang.project_service import ProjectService


@pytest.fixture
def project_service(project_sources):
    access, descriptor, _ = project_sources
    service = ProjectService(access)
    service.create(descriptor.name, roots=descriptor.source_roots)
    try:
        yield service
    finally:
        service.close()


def test_analysis_is_offline_and_repeatable(project_service, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('external provider/tool must not be initialized')
    monkeypatch.setattr(ai, 'provider_from_env', forbidden)
    monkeypatch.setattr(oracle, 'detect_toolchain', forbidden)
    first = project_service.analyze(expected_revision=None, expected_configuration=0)
    saved = project_service.assessment()
    second = project_service.analyze(expected_revision=first['analysis_revision'], expected_configuration=0)
    assert second['analysis_revision'] == first['analysis_revision']
    assert project_service.assessment()['analyzed_at'] == saved['analyzed_at']
    assert saved['completion_state'] == 'COMPLETE'
    assert saved['inventory']['forms']['analyzed'] == 1
    assert saved['inventory']['database']['tables'] == 1


def test_partial_failure_persists_honest_incomplete_result(project_service, project_sources):
    xml = project_sources[2]
    for name in ('two.xml', 'three.xml'):
        (xml.parent / name).write_bytes(xml.read_bytes())
    (xml.parent / 'bad.xml').write_text('<broken>')
    result = project_service.analyze(expected_revision=None, expected_configuration=0)
    assert result['status'] == 'COMPLETED_WITH_WARNINGS'
    saved = project_service.assessment()
    assert saved['status'] == 'Incomplete'
    assert saved['completion_state'] == 'INCOMPLETE'
    assert saved['inventory']['forms']['analyzed'] == 3
    assert any(d['error_code'] == 'INVALID_XML' for d in saved['diagnostics'])
    assert result['warnings_count'] >= 1 and result['errors_count'] >= 1
    assert saved['inventory']['forms']['parseable'] == 3


def test_unsupported_only_is_not_empty_success(project_service, project_sources):
    access, _, xml = project_sources
    xml.write_text('<Module><MenuModule/></Module>')
    (access.source_roots[1] / 'orders.sql').write_text('select 1 from dual;')
    result = project_service.analyze(expected_revision=None, expected_configuration=0)
    assert result['status'] == 'FAILED'
    assert result['safe_failure']['error_code'] == 'NO_SUPPORTED_SOURCES'
    assert project_service.assessment() is None
    metadata = project_service._store.session.db.execute(
        'SELECT metadata_json FROM project_analysis_run WHERE job_id=?', (result['job_id'],)).fetchone()[0]
    assert 'UNSUPPORTED_XML' in metadata and 'UNSUPPORTED_SQL' in metadata


@pytest.mark.parametrize('phase', ['DISCOVERY', 'FORMS_PARSING', 'BLUEPRINT', 'PERSISTING'])
def test_cancel_each_boundary_keeps_previous_assessment(project_service, phase):
    first = project_service.analyze(expected_revision=None, expected_configuration=0)
    cancelled = False
    def progress(event):
        nonlocal cancelled
        if event['phase'] == phase:
            cancelled = True
    result = project_service.analyze(expected_revision=first['analysis_revision'], expected_configuration=0,
                                     progress=progress, cancellation=lambda: cancelled)
    assert result['status'] == 'CANCELLED'
    assert project_service.assessment()['analysis_revision'] == first['analysis_revision']


@pytest.mark.parametrize('change', ['edit', 'add', 'delete', 'same_size_mtime'])
def test_changed_source_not_published_current(project_service, project_sources, change):
    xml = project_sources[2]
    def progress(event):
        if event['phase'] != 'BLUEPRINT':
            return
        if change == 'add':
            (xml.parent / 'new.xml').write_bytes(xml.read_bytes())
        elif change == 'delete':
            xml.unlink()
        elif change == 'same_size_mtime':
            info = xml.stat()
            xml.write_bytes(xml.read_bytes().replace(b'DEMO_ORDER', b'DEMO_OTHER'))
            os.utime(xml, ns=(info.st_atime_ns, info.st_mtime_ns))
        else:
            xml.write_text('<changed/>')
    result = project_service.analyze(expected_revision=None, expected_configuration=0, progress=progress)
    assert result['status'] == 'FAILED'
    assert result['safe_failure']['error_code'] == 'INCOMPLETE_SOURCE_CHANGED'
    assert project_service.assessment() is None


def test_paired_xml_used_without_automatic_oracle_conversion(project_service, project_sources, monkeypatch):
    xml = project_sources[2]
    (xml.parent / 'orders.fmb').write_bytes(b'synthetic binary')
    def forbidden(*a, **k):
        raise AssertionError('conversion must require explicit action')
    monkeypatch.setattr(oracle, 'convert_module', forbidden)
    result = project_service.analyze(expected_revision=None, expected_configuration=0)
    assert result['status'] in {'COMPLETED', 'COMPLETED_WITH_WARNINGS'}
    assert project_service.assessment()['inventory']['forms']['analyzed'] == 1


def test_unpaired_binary_is_coverage_gap(project_service, project_sources):
    xml = project_sources[2]
    (xml.parent / 'unobserved.fmb').write_bytes(b'synthetic')
    project_service.analyze(expected_revision=None, expected_configuration=0)
    saved = project_service.assessment()
    assert saved['status'] == 'Incomplete'
    assert any(d['error_code'] == 'FORMS2XML_REQUIRED' for d in saved['diagnostics'])


def test_changed_source_marks_previous_reviews_stale(project_service, project_sources):
    first = project_service.analyze(expected_revision=None, expected_configuration=0)
    saved = project_service.assessment()
    finding = saved['blueprint']['findings'][0]
    store = project_service._store.session
    store.review_blueprint(entity=finding['entity'], revision=finding['revision'], action='APPROVE',
                           reviewer='Analyst', comment='Reviewed')
    xml = project_sources[2]
    xml.write_bytes(xml.read_bytes() + b'\n')
    project_service.analyze(expected_revision=first['analysis_revision'], expected_configuration=0)
    fresh = project_service.assessment()
    assert fresh['analysis_revision'] != first['analysis_revision']
    reviewed = next(f for f in fresh['blueprint']['findings'] if f['entity'] == finding['entity'])
    assert reviewed['review_state'] == 'STALE'
    assert reviewed['review_history'][0]['reviewer'] == 'Analyst'
    assert 'human_decision' not in reviewed


def test_reopen_does_not_reanalyze(project_service):
    result = project_service.analyze(expected_revision=None, expected_configuration=0)
    access = project_service.access
    project_service.close()
    reopened = ProjectService(access)
    try:
        assert reopened.assessment()['analysis_revision'] == result['analysis_revision']
    finally:
        reopened.close()


def test_revoked_authority_during_analysis_cannot_publish(project_service):
    access = project_service.access
    revoked = False
    def authorize():
        if revoked:
            raise PermissionError('revoked')
        return access
    def progress(event):
        nonlocal revoked
        if event['phase'] == 'PERSISTING':
            revoked = True
    project_service._authorize_callback = authorize
    result = project_service.analyze(expected_revision=None, expected_configuration=0, progress=progress)
    assert result['safe_failure']['error_code'] == 'ACCESS_REVOKED'
    assert project_service._store.load_assessment() is None


def test_edit_and_restore_during_parse_uses_original_staged_bytes(project_service, project_sources):
    xml = project_sources[2]
    original = xml.read_bytes()
    def progress(event):
        if event['phase'] == 'FORMS_PARSING' and event['processed'] == 0:
            xml.write_text('<temporarily-changed>')
        if event['phase'] == 'BLUEPRINT':
            xml.write_bytes(original)
    result = project_service.analyze(expected_revision=None, expected_configuration=0, progress=progress)
    assert result['status'] == 'COMPLETED'
    assert project_service.assessment()['inventory']['forms']['analyzed'] == 1


def test_duplicate_database_definition_is_not_silently_selected(project_service, project_sources):
    database = project_sources[0].source_roots[1]
    (database / 'duplicate.sql').write_text('CREATE TABLE orders (other_id NUMBER);')
    result = project_service.analyze(expected_revision=None, expected_configuration=0)
    assert result['status'] == 'COMPLETED_WITH_WARNINGS'
    saved = project_service.assessment()
    assert saved['completion_state'] == 'INCOMPLETE'
    assert saved['inventory']['database']['tables'] == 0
    assert any(d['error_code'] == 'DUPLICATE_DB_OBJECT' for d in saved['diagnostics'])


def _analyze_worker(access, started, release, outcome):
    service = ProjectService(access)
    def progress(event):
        if event['phase'] == 'DISCOVERY':
            started.put(event['job_id'])
            if not release.wait(20):
                raise RuntimeError('test synchronization timeout')
    try:
        result = service.analyze(expected_revision=None, expected_configuration=0, progress=progress)
        outcome.put(result['status'])
    finally:
        service.close()


def test_two_service_processes_have_only_one_publication_owner(project_service):
    ctx = multiprocessing.get_context('spawn')
    started, outcome, release = ctx.Queue(), ctx.Queue(), ctx.Event()
    worker = ctx.Process(target=_analyze_worker, args=(project_service.access, started, release, outcome))
    worker.start()
    try:
        job_id = started.get(timeout=20)
        assert project_service.job(job_id)['status'] == 'RUNNING'
        with pytest.raises(ProjectBusy):
            project_service.analyze(expected_revision=None, expected_configuration=0)
        release.set()
        worker.join(timeout=20)
        assert worker.exitcode == 0
        assert outcome.get(timeout=5) == 'COMPLETED'
        assert project_service.assessment()['completion_state'] == 'COMPLETE'
        assert project_service._store.session.db.execute('SELECT COUNT(*) FROM project_assessment').fetchone()[0] == 1
    finally:
        release.set()
        worker.join(timeout=5)
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
