"""Durable job ownership cannot be inferred from a PID or elapsed heartbeat."""

import multiprocessing
import os

import pytest

from formslang.project_model import ProjectBusy, ProjectDescriptor, RevisionConflict
from formslang.project_store import ProjectStore
from formslang.projects import local_project_access


@pytest.fixture
def job_manager(tmp_path):
    from formslang.project_jobs import ProjectJobManager

    access = local_project_access(tmp_path / 'project', approved_roots=(tmp_path,))
    ProjectStore.create(access.root, ProjectDescriptor(id='a'*32, name='Jobs')).close()
    return ProjectJobManager(access, authorize=lambda: access)


def test_cancel_is_durable_and_terminal(job_manager):
    from formslang.project_jobs import AnalysisCancelled

    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        assert job_manager.get(lease.job_id)['status'] == 'RUNNING'
        job_manager.cancel(lease.job_id)
        with pytest.raises(AnalysisCancelled):
            lease.checkpoint()
    assert job_manager.get(lease.job_id)['status'] == 'CANCELLED'
    assert job_manager.cancel(lease.job_id)['status'] == 'CANCELLED'


def test_open_or_recover_cannot_cancel_live_worker(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        reader = ProjectStore.open(job_manager.access.root)
        reader.close()
        assert job_manager.recover() == []
        assert job_manager.get(lease.job_id)['status'] == 'RUNNING'
        with pytest.raises(ProjectBusy), job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0):
            pytest.fail('another writer acquired live ownership')
        lease.finish('COMPLETED')
    assert job_manager.get(lease.job_id)['status'] == 'COMPLETED'


def test_foreign_job_is_not_readable_or_cancellable(job_manager):
    with pytest.raises(LookupError):
        job_manager.get('b'*32)
    with pytest.raises(LookupError):
        job_manager.cancel('b'*32)


def test_exception_finishes_failed_without_source_leak(job_manager):
    with pytest.raises(RuntimeError), job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        raise RuntimeError('secret body and password')
    job = job_manager.get(lease.job_id)
    assert job['status'] == 'FAILED'
    assert 'secret' not in str(job)


def test_stale_configuration_cannot_claim_job(job_manager):
    with pytest.raises(RevisionConflict), job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=7):
        pytest.fail('stale configuration acquired job')


def test_progress_is_persisted_and_does_not_require_shared_connection(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        lease.progress({'phase':'FORMS_PARSING', 'processed':2, 'total':5, 'warnings_count':1})
        state = job_manager.get(lease.job_id)
        assert state['phase'] == 'FORMS_PARSING'
        assert state['processed'] == 2 and state['total'] == 5
        assert state['warnings_count'] == 1
        assert state['started_at'] and state['elapsed_ms'] >= 0
        lease.finish('COMPLETED_WITH_WARNINGS')


def test_relink_refused_while_job_active(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        observer = ProjectStore.open(job_manager.access.root)
        try:
            with pytest.raises(ProjectBusy):
                observer.replace_roots((), expected_configuration=0)
        finally:
            observer.close()
        lease.finish('COMPLETED')


def _worker(root, started, release, outcome, crash):
    from formslang.project_jobs import ProjectJobManager

    access = local_project_access(root, approved_roots=(root,))
    manager = ProjectJobManager(access, authorize=lambda: access)
    try:
        with manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
            started.put(lease.job_id)
            if not release.wait(15):
                raise RuntimeError('test synchronization timeout')
            if crash:
                os._exit(17)
            lease.finish('COMPLETED')
            outcome.put('completed')
    except ProjectBusy:
        started.put('busy')
        outcome.put('busy')


@pytest.mark.parametrize('crash', [False, True])
def test_process_lock_distinguishes_live_and_interrupted(job_manager, crash):
    ctx = multiprocessing.get_context('spawn')
    started, outcome, release = ctx.Queue(), ctx.Queue(), ctx.Event()
    worker = ctx.Process(target=_worker, args=(job_manager.access.root, started, release, outcome, crash))
    worker.start()
    try:
        job_id = started.get(timeout=20)
        assert job_id != 'busy'
        assert job_manager.recover() == []
        assert job_manager.get(job_id)['status'] == 'RUNNING'
        with pytest.raises(ProjectBusy), job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0):
            pytest.fail('second process acquired live writer')
        release.set()
        worker.join(timeout=20)
        assert worker.exitcode == (17 if crash else 0)
        recovered = job_manager.recover()
        if crash:
            assert recovered == [job_id]
            assert job_manager.get(job_id)['safe_failure']['error_code'] == 'PROCESS_INTERRUPTED'
        else:
            assert recovered == []
            assert job_manager.get(job_id)['status'] == 'COMPLETED'
    finally:
        release.set()
        if worker.is_alive():
            worker.terminate()
        worker.join(timeout=5)
        started.close()
        outcome.close()


def assessment(store):
    from formslang import blueprint
    from formslang.project_assessment import bind_assessment
    from formslang.project_manifest import ManifestEntry, source_id

    entry = ManifestEntry(source_id('f', 'orders.xml'), 'f', 'orders.xml', 'xml', True,
                          'available', 10, 'a'*64)
    return bind_assessment(store.descriptor(), (entry,), blueprint.build([]),
                           engines={'test':'1'}, options={}, analyzed_at='2026-09-19T00:00:00Z', status='Current')


def test_cancel_before_publication_keeps_pointer(job_manager):
    from formslang.project_jobs import AnalysisCancelled

    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        value = assessment(lease.store)
        job_manager.cancel(lease.job_id)
        with pytest.raises(AnalysisCancelled):
            lease.store.save_assessment(value, expected_revision=None, job_id=lease.job_id,
                owner_token=lease.owner_token, expected_configuration=0)
        assert lease.store.load_assessment() is None
    assert job_manager.get(lease.job_id)['status'] == 'CANCELLED'


def test_publish_and_job_completion_are_one_transaction(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        value = assessment(lease.store)
        lease.publish(value)
        assert lease.store.load_assessment()['analysis_revision'] == value['analysis_revision']
        job = job_manager.get(lease.job_id)
        assert job['status'] == 'COMPLETED'
        assert job['outcome']['analysis_revision'] == value['analysis_revision']
        assert job_manager.cancel(lease.job_id)['status'] == 'COMPLETED'


def test_invalid_fence_cannot_publish(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        with pytest.raises(RevisionConflict):
            lease.store.save_assessment(assessment(lease.store), expected_revision=None,
                job_id=lease.job_id, owner_token='old-owner', expected_configuration=0)
        assert lease.store.load_assessment() is None
        lease.finish('FAILED')


def test_job_completion_failure_rolls_back_assessment(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        lease.store.session.db.execute("CREATE TRIGGER reject_job_complete BEFORE UPDATE ON project_job WHEN NEW.status='COMPLETED' BEGIN SELECT RAISE(ABORT,'injected'); END")
        lease.store.session.db.commit()
        from formslang.project_model import ProjectError
        with pytest.raises(ProjectError):
            lease.publish(assessment(lease.store))
        assert lease.store.load_assessment() is None
        assert job_manager.get(lease.job_id)['status'] == 'RUNNING'
        lease.finish('FAILED')


def test_revocation_rechecked_before_publish(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        value = assessment(lease.store)
        def revoked():
            raise PermissionError('Membership revoked')
        job_manager.authorize = revoked
        with pytest.raises(PermissionError):
            lease.publish(value)
        assert lease.store.load_assessment() is None
        lease.finish('FAILED')


def test_fake_pid_never_replaces_live_lock_evidence(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        with lease.store.session.db:
            lease.store.session.db.execute("UPDATE project_job SET owner_pid=-1,heartbeat='1970-01-01T00:00:00Z' WHERE job_id=?", (lease.job_id,))
        assert job_manager.recover() == []
        assert job_manager.get(lease.job_id)['status'] == 'RUNNING'
        lease.finish('COMPLETED')


def test_unfenced_legacy_write_cannot_bypass_active_job(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        with pytest.raises(ProjectBusy):
            lease.store.save_assessment(assessment(lease.store), expected_revision=None)
        lease.finish('COMPLETED')


def test_old_worker_cannot_publish_after_configuration_changed(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        with lease.store.session.db:
            lease.store.session.db.execute('UPDATE project_configuration SET revision=1')
        with pytest.raises(RevisionConflict):
            lease.publish(assessment(lease.store))
        assert lease.store.load_assessment() is None
        lease.finish('FAILED')


def test_cancel_keeps_previously_committed_assessment(job_manager):
    store = ProjectStore.open(job_manager.access.root)
    try:
        previous = assessment(store)
        store.save_assessment(previous, expected_revision=None)
    finally:
        store.close()
    with job_manager.claim('ANALYZE', expected_revision=previous['analysis_revision'], expected_configuration=0) as lease:
        job_manager.cancel(lease.job_id)
    reopened = ProjectStore.open(job_manager.access.root)
    try:
        assert reopened.load_assessment() == previous
    finally:
        reopened.close()


def test_busy_sqlite_does_not_corrupt_job_state(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        observer = ProjectStore.open(job_manager.access.root)
        try:
            observer.session.db.execute('BEGIN IMMEDIATE')
            with pytest.raises(ProjectBusy):
                lease.progress({'phase':'BLUEPRINT', 'processed':0, 'total':None})
        finally:
            observer.session.db.rollback()
            observer.close()
        assert job_manager.get(lease.job_id)['status'] == 'RUNNING'
        lease.finish('COMPLETED')


def test_cancel_job_from_other_project_denied(job_manager, tmp_path):
    from formslang.project_jobs import ProjectJobManager

    other = local_project_access(tmp_path/'other', approved_roots=(tmp_path,))
    ProjectStore.create(other.root, ProjectDescriptor(id='b'*32, name='Other')).close()
    foreign = ProjectJobManager(other, authorize=lambda: other)
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        with pytest.raises(LookupError):
            foreign.cancel(lease.job_id)
        assert not job_manager.get(lease.job_id)['cancellation_requested']
        lease.finish('COMPLETED')


def test_live_pid_without_lock_does_not_prevent_orphan_recovery(job_manager):
    with job_manager.claim('ANALYZE', expected_revision=None, expected_configuration=0) as lease:
        lease.finish('COMPLETED')
    store = ProjectStore.open(job_manager.access.root)
    try:
        with store.session.db:
            store.session.db.execute("UPDATE project_job SET status='RUNNING',finished_at=NULL,owner_pid=? WHERE job_id=?", (os.getpid(), lease.job_id))
    finally:
        store.close()
    assert job_manager.recover() == [lease.job_id]
    assert job_manager.get(lease.job_id)['status'] == 'FAILED'
