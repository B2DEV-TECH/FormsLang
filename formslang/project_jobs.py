"""Durable local jobs over ProjectStore, with live OS ownership and safe recovery."""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from . import rbac
from .project_lock import project_worker_lock
from .project_model import ProjectBusy, ProjectError, RevisionConflict, canonical_json
from .project_store import ProjectStore

ACTIVE = {'QUEUED', 'RUNNING'}
TERMINAL = {'COMPLETED', 'COMPLETED_WITH_WARNINGS', 'FAILED', 'CANCELLED'}
PHASES = {'DISCOVERY', 'FORMS_PARSING', 'DATABASE_PARSING', 'DEPENDENCY_RESOLUTION',
          'MODERNIZATION_ANALYSIS', 'BLUEPRINT', 'ASSESSMENT', 'PERSISTING', 'FRESHNESS', 'CONVERSION'}


class AnalysisCancelled(ProjectError):
    """Cooperative cancellation leaves the last committed assessment unchanged."""


def now():
    return datetime.now(timezone.utc).isoformat()


def _safe_failure(code='OPERATION_FAILED'):
    return {'error_code': code, 'safe_message': 'The local operation did not complete.',
            'remediation': 'View the saved assessment and retry the operation.'}


def _job(store, job_id):
    row = store.session.db.execute('SELECT * FROM project_job WHERE job_id=? AND project_id=?',
                                  (job_id, store.descriptor().id)).fetchone()
    if row is None:
        raise LookupError('Project job not found')
    return dict(row)


class JobLease:
    def __init__(self, manager, store, job_id, owner_token):
        self.manager, self.store = manager, store
        self.job_id, self.owner_token = job_id, owner_token

    def checkpoint(self):
        self.manager._authorize(rbac.RUN_CONVERSION if _job(self.store, self.job_id)['operation'] != 'FRESHNESS'
                                else rbac.VIEW_PROJECT)
        row = _job(self.store, self.job_id)
        if row['owner_token'] != self.owner_token or row['status'] not in ACTIVE:
            raise RevisionConflict('Project worker ownership changed')
        if row['cancellation_requested']:
            raise AnalysisCancelled('Analysis cancellation requested')

    def publish(self, assessment):
        self.checkpoint()
        row = _job(self.store, self.job_id)
        self.store.save_assessment(assessment, expected_revision=row['requested_revision'],
            expected_configuration=row['requested_configuration'], job_id=self.job_id,
            owner_token=self.owner_token)

    def progress(self, event):
        self.checkpoint()
        phase = event.get('phase')
        processed, total = event.get('processed', 0), event.get('total')
        warnings, errors = event.get('warnings_count', 0), event.get('errors_count', 0)
        if (phase not in PHASES or any(type(v) is not int or v < 0 for v in (processed, warnings, errors))
                or (total is not None and (type(total) is not int or total < processed))):
            raise ProjectError('Invalid job progress')
        with self.store._write() as db:
            row = _job(self.store, self.job_id)
            if row['owner_token'] != self.owner_token or row['status'] not in ACTIVE:
                raise RevisionConflict('Project worker ownership changed')
            db.execute('UPDATE project_job SET phase=?,processed=?,total=?,warnings_count=?,errors_count=?,heartbeat=? WHERE job_id=?',
                       (phase, processed, total, warnings, errors, now(), self.job_id))

    def finish(self, status, safe_failure=None):
        if status not in TERMINAL:
            raise ProjectError('Invalid job terminal state')
        with self.store._write() as db:
            row = _job(self.store, self.job_id)
            if row['owner_token'] != self.owner_token:
                raise RevisionConflict('Project worker ownership changed')
            if row['status'] in TERMINAL:
                return
            if row['cancellation_requested']:
                status, safe_failure = 'CANCELLED', None
            db.execute('UPDATE project_job SET status=?,finished_at=?,heartbeat=?,safe_failure_json=? WHERE job_id=?',
                       (status, now(), now(), canonical_json(safe_failure) if safe_failure else None, self.job_id))


class ProjectJobManager:
    def __init__(self, access, authorize):
        self.access, self.authorize = access, authorize

    def _authorize(self, action):
        fresh = self.authorize()
        if (fresh.root != self.access.root or fresh.actor != self.access.actor or fresh.org_id != self.access.org_id
                or action not in fresh.actions or fresh.root.resolve() != fresh.root):
            raise PermissionError('Project access is no longer authorized')
        return fresh

    @staticmethod
    def _recover_locked(store):
        with store._write() as db:
            rows = db.execute("SELECT job_id FROM project_job WHERE status IN ('QUEUED','RUNNING')").fetchall()
            ids = [r[0] for r in rows]
            for identity in ids:
                db.execute("UPDATE project_job SET status='FAILED',finished_at=?,safe_failure_json=? WHERE job_id=?",
                           (now(), canonical_json(_safe_failure('PROCESS_INTERRUPTED')), identity))
        return ids

    def recover(self):
        fresh = self._authorize(rbac.VIEW_PROJECT)
        try:
            with project_worker_lock(fresh.root):
                store = ProjectStore.open(fresh.root)
                try:
                    return self._recover_locked(store)
                finally:
                    store.close()
        except ProjectBusy:
            return []

    @contextmanager
    def claim(self, operation, *, expected_revision, expected_configuration):
        if operation not in {'ANALYZE', 'DISCOVER', 'FRESHNESS', 'CONVERT'}:
            raise ProjectError('Unknown project operation')
        fresh = self._authorize(rbac.VIEW_PROJECT if operation == 'FRESHNESS' else rbac.RUN_CONVERSION)
        with project_worker_lock(fresh.root):
            store = ProjectStore.open(fresh.root)
            lease = None
            try:
                self._recover_locked(store)
                with store._write() as db:
                    if store.descriptor().analysis_revision != expected_revision or store.configuration_revision() != expected_configuration:
                        raise RevisionConflict('Project changed; reload before starting analysis')
                    job_id, token, started = uuid.uuid4().hex, uuid.uuid4().hex, now()
                    db.execute('''INSERT INTO project_job(job_id,project_id,operation,requested_revision,
                        requested_configuration,status,phase,started_at,owner_token,owner_pid,heartbeat)
                        VALUES (?,?,?,?,?,'QUEUED','DISCOVERY',?,?,?,?)''',
                        (job_id, store.descriptor().id, operation, expected_revision, expected_configuration,
                         started, token, os.getpid(), started))
                lease = JobLease(self, store, job_id, token)
                with store._write() as db:
                    db.execute("UPDATE project_job SET status='RUNNING' WHERE job_id=?", (job_id,))
                yield lease
            except AnalysisCancelled:
                if lease:
                    lease.finish('CANCELLED')
                raise
            except BaseException:
                if lease:
                    lease.finish('FAILED', _safe_failure())
                raise
            finally:
                try:
                    if lease:
                        lease.finish('FAILED', _safe_failure('OPERATION_INCOMPLETE'))
                finally:
                    store.close()

    def get(self, job_id):
        fresh = self._authorize(rbac.VIEW_PROJECT)
        store = ProjectStore.open(fresh.root)
        try:
            row = _job(store, job_id)
            for key in ('owner_token', 'owner_pid'):
                row.pop(key)
            row['safe_failure'] = json.loads(row.pop('safe_failure_json') or 'null')
            row['outcome'] = json.loads(row.pop('outcome_json') or '{}')
            end = datetime.fromisoformat(row['finished_at'] or now())
            row['elapsed_ms'] = max(0, int((end - datetime.fromisoformat(row['started_at'])).total_seconds() * 1000))
            return row
        finally:
            store.close()

    def cancel(self, job_id):
        fresh = self._authorize(rbac.RUN_CONVERSION)
        store = ProjectStore.open(fresh.root)
        try:
            with store._write() as db:
                row = _job(store, job_id)
                if row['status'] in ACTIVE:
                    db.execute('UPDATE project_job SET cancellation_requested=1 WHERE job_id=?', (job_id,))
        finally:
            store.close()
        return self.get(job_id)
