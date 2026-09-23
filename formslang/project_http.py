"""Versioned, request-authorized project adapter for the existing Workbench."""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from urllib.parse import unquote

from . import authstore, config, rbac
from .project_intake import ProjectIdentity, ProjectIntake
from .project_model import (
    TARGET_CHOICE_DETAILS,
    TARGET_CHOICES,
    ProjectBusy,
    ProjectError,
    RevisionConflict,
    TargetProfile,
    target_from_choice,
)
from .project_projection import ProjectionCache
from .project_service import ProjectService

logger = logging.getLogger(__name__)


def _page(values):
    if any(type(values.get(key, default)) not in {int, str} for key, default in (('offset', 0), ('limit', 50))):
        raise ProjectError('Pagination requires integer offset and limit')
    try:
        offset, limit = int(values.get('offset', 0)), int(values.get('limit', 50))
    except (TypeError, ValueError) as exc:
        raise ProjectError('Pagination requires integer offset and limit') from exc
    if not 0 <= offset <= 2147483647 or not 1 <= limit <= 200:
        raise ProjectError('Use a nonnegative offset and limit between 1 and 200')
    return offset, limit


def _preconditions(body):
    if 'expected_revision' not in body or 'expected_configuration' not in body:
        raise ProjectError('Reload the project and supply its revision preconditions')
    revision, configuration = body['expected_revision'], body['expected_configuration']
    if ((revision is not None and (not isinstance(revision, str) or not re.fullmatch('[a-f0-9]{64}', revision))) or
            type(configuration) is not int or configuration < 0):
        raise ProjectError('Invalid project revision preconditions')
    return {'expected_revision': revision, 'expected_configuration': configuration}


def _inventory_query(query):
    if not isinstance(query, dict) or any(not isinstance(value, str) for value in query.values()):
        raise ProjectError('Inventory query values must be text')
    allowed = {'category', 'query', 'sort', 'revision', 'offset', 'limit', 'risk',
               'recommendation', 'intervention', 'module', 'source_type', 'review',
               'priority'}
    if set(query) - allowed:
        raise ProjectError('Unknown inventory query parameter')
    offset, limit = _page(query)
    revision = query.get('revision') or None
    if revision is not None and not re.fullmatch('[a-f0-9]{64}', revision):
        raise ProjectError('Invalid assessment revision')
    filters = {key: query[key] for key in (
        'risk', 'recommendation', 'intervention', 'module', 'source_type', 'review',
        'priority',
    ) if key in query}
    return {
        'category': query.get('category', 'forms'),
        'query': query.get('query', ''),
        'filters': filters,
        'sort': query.get('sort', 'name'),
        'offset': offset,
        'limit': limit,
        'expected_revision': revision,
    }


class ProjectHTTP:
    def __init__(self, workbench):
        self.workbench = workbench
        self._lock = threading.Lock()
        self._workers = {}
        self._closed = False
        self._projection_cache = ProjectionCache()

    def _intake(self, auth):
        identity = ProjectIdentity(auth[0], auth[1]['user_id'], auth[1]['active_org_id']) if auth else None
        return ProjectIntake(self.workbench.auth_data_dir or config.data_dir(), config.config_dir(), identity=identity,
                             auth_db_path=self.workbench.auth_store.path if self.workbench.auth_store else None)

    @contextmanager
    def _service(self, intake, pid, action=rbac.VIEW_PROJECT):
        authorize = lambda: intake.access(pid, action)
        service = ProjectService(authorize(), authorize=authorize,
                                 projection_cache=self._projection_cache)
        try:
            service.open()
            yield service
        finally:
            service.close()

    def _start(self, intake, pid, operation, preconditions):
        acknowledgement = queue.Queue(maxsize=1)
        stop = threading.Event()
        accepted = threading.Event()
        record = {'stop': stop, 'intake': intake, 'pid': pid, 'job_id': None}

        def started(job_id):
            record['job_id'] = job_id
            accepted.set()
            acknowledgement.put((job_id, None))

        def run():
            try:
                action = rbac.VIEW_PROJECT if operation == 'freshness' else rbac.RUN_CONVERSION
                with self._service(intake, pid, action) as service:
                    if operation == 'analyze':
                        service.analyze(**preconditions, started=started, cancellation=stop.is_set)
                    else:
                        service.freshness(started=started)
            except Exception as exc:  # noqa: BLE001 - sanitized at dispatch, never leak worker source
                if not accepted.is_set():
                    acknowledgement.put((None, exc))
                else:
                    logger.warning('Project worker stopped', extra={'project_id': pid, 'job_id': record['job_id']})
            finally:
                with self._lock:
                    self._workers.pop(threading.current_thread(), None)

        worker = threading.Thread(target=run, daemon=True, name='formslang-project-job')
        with self._lock:
            if self._closed:
                raise ProjectBusy('Workbench is shutting down')
            self._workers[worker] = record
            worker.start()
        try:
            job_id, error = acknowledgement.get(timeout=25)
        except queue.Empty as exc:
            stop.set()
            raise ProjectBusy('Project worker could not start promptly; reload its status') from exc
        if error is not None:
            raise error
        return {'job_id': job_id, 'project_id': pid}

    def close(self):
        with self._lock:
            self._closed = True
            workers = list(self._workers.items())
        for _, record in workers:
            record['stop'].set()
            if record['job_id']:
                try:
                    with self._service(record['intake'], record['pid'], rbac.RUN_CONVERSION) as service:
                        service.cancel(record['job_id'])
                except (PermissionError, ProjectError, LookupError):
                    pass
        for worker, _ in workers:
            worker.join(timeout=1)

    @staticmethod
    def _freshness(service):
        descriptor = service.open()
        row = service._store.session.db.execute("SELECT outcome_json,requested_configuration FROM project_job WHERE operation='FRESHNESS' AND status IN ('COMPLETED','COMPLETED_WITH_WARNINGS') ORDER BY rowid DESC LIMIT 1").fetchone()
        if row and row['requested_configuration'] == service._store.configuration_revision():
            result = json.loads(row['outcome_json'] or '{}')
            if result.get('analysis_revision') == descriptor.analysis_revision:
                return result
        return {'status': 'UNVERIFIED', 'reasons': ['SOURCE_CHECK_REQUIRED'], 'analysis_revision': descriptor.analysis_revision}

    def dispatch(self, method, path, query, body, auth):
        try:
            return self._dispatch(method, path, query, body, self._intake(auth))
        except authstore.ProjectNotFound:
            return 404, {'error': 'Project not found'}
        except (RevisionConflict, ProjectBusy) as exc:
            return 409, {'error': str(exc), 'code': 'PROJECT_CONFLICT'}
        except PermissionError as exc:
            return 403, {'error': str(exc)}
        except ProjectError as exc:
            return 400, {'error': str(exc)}
        except LookupError:
            return 404, {'error': 'Project resource not found'}
        except (TypeError, ValueError):
            return 400, {'error': 'Invalid project request; check the supplied fields'}
        except Exception:  # noqa: BLE001 - one safe boundary; no raw paths/source/credentials
            correlation = uuid.uuid4().hex
            logger.error('Project request failed', extra={'correlation_id': correlation})
            return 500, {'error': 'Project operation failed. View saved evidence and retry.', 'correlation_id': correlation}

    def _dispatch(self, method, path, query, body, intake):
        parts = path.removeprefix('/api/v2/').strip('/').split('/')
        if parts == ['source-selections'] and method == 'POST':
            return 200, {'selection': intake.select_source(body.get('path', ''), body.get('kind', 'forms'))}
        if parts == ['source-areas'] and method == 'GET':
            target = asdict(TargetProfile())
            choices = [{**item, 'profile': asdict(TARGET_CHOICES[item['id']])} for item in TARGET_CHOICE_DETAILS]
            if intake.identity:
                return 200, {'local': False, 'target_profile': target, 'target_choices': choices,
                             'areas': [{'id': key, 'name': key} for key in intake._host_areas()]}
            intake._local()
            with intake._metadata() as metadata:
                areas = [{'id': key, 'name': value['path']} for key, value in metadata['areas'].items()
                         if value['actor'] == intake._local()]
            return 200, {'local': True, 'target_profile': target, 'target_choices': choices, 'areas': areas,
                         'browse_root': str(self.workbench.browse_root)}
        if len(parts) == 3 and parts[0] == 'source-areas' and parts[2] == 'browse' and method == 'GET':
            return 200, intake.browse(parts[1], query.get('relative', ''))
        if parts == ['discovery-preview'] and method == 'POST':
            offset, limit = _page(body)
            result = intake.preview(body.get('sources'))
            return 200, {'inventory': result.inventory, 'entries': [asdict(e) for e in result.entries[offset:offset+limit]],
                'diagnostics': [asdict(d) for d in result.diagnostics[offset:offset+limit]], 'total': len(result.entries),
                'diagnostics_total': len(result.diagnostics), 'offset': offset, 'limit': limit}
        if parts == ['projects']:
            if method == 'GET':
                return 200, {'projects': intake.list_recent()}
            if method == 'POST':
                # Historical clients omit the target and keep the 2.0 APEX default;
                # the onboarding UI always sends an explicit, server-validated choice.
                return 201, intake.create(body.get('name', ''), body.get('sources'),
                    description=body.get('description', ''), client_label=body.get('client_label', ''),
                    target=target_from_choice(body.get('target')))
        if parts == ['projects', 'open'] and method == 'POST':
            if intake.identity:
                return 200, intake._summary(body.get('project_id'))
            return 200, intake.open_locator(body.get('locator', ''))
        if parts == ['projects', 'demo'] and method == 'POST':
            return 201, intake.create_demo(target=target_from_choice(body.get('target')))
        if len(parts) < 2 or parts[0] != 'projects' or not re.fullmatch('[a-f0-9]{32}', parts[1]):
            return 404, {'error': 'Project route not found'}
        pid = parts[1]
        try:
            intake.access(pid, rbac.VIEW_PROJECT)
        except PermissionError:
            if intake.identity is None:
                raise authstore.ProjectNotFound(pid) from None
            raise
        tail = parts[2:]
        if not tail and method == 'GET':
            with self._service(intake, pid) as service:
                row = service._store.session.db.execute('SELECT job_id FROM project_job ORDER BY rowid DESC LIMIT 1').fetchone()
                last = service.job(row[0]) if row else None
                return 200, {**intake._summary(pid), 'freshness': self._freshness(service), 'last_job': last}
        if tail == ['analyze'] and method == 'POST':
            return 202, self._start(intake, pid, 'analyze', _preconditions(body))
        if tail == ['freshness'] and method == 'POST':
            return 202, self._start(intake, pid, 'freshness', {})
        if tail == ['relink'] and method == 'POST':
            return 200, intake.relink(pid, body.get('root_id'), body.get('selection'),
                                     expected_configuration=body.get('expected_configuration'))
        if tail == ['convert'] and method == 'POST':
            return 200, intake.convert(pid, body.get('source_id'), expected_configuration=body.get('expected_configuration'),
                                      confirmed=body.get('confirmed', False))
        action = rbac.RUN_CONVERSION if method == 'POST' else rbac.VIEW_PROJECT
        if len(tail) == 2 and tail[0] == 'reports' and method == 'GET':
            action = rbac.EXPORT_PROJECT
        if ((tail == ['generation'] and method == 'POST')
                or (len(tail) == 3 and tail[0] == 'artifacts'
                    and (tail[2], method) in {('download', 'GET'), ('validate', 'POST')})):
            action = rbac.EXPORT_PROJECT
        elif (len(tail) == 5 and tail[:2] == ['generation', 'modules']
              and tail[3] == 'code' and method == 'POST'):
            action = rbac.APPROVE_AI_PROPOSAL
        with self._service(intake, pid, action) as service:
            if tail == ['reports'] and method == 'GET':
                return 200, service.report_overview()
            if len(tail) == 2 and tail[0] == 'reports' and method == 'GET':
                fields = {'project_id', 'source_revision', 'analysis_revision', 'review_revision', 'snapshot_revision'}
                if set(query) - fields - {'include_notes', 'include_artifacts'}:
                    raise ProjectError('Unknown report query parameter')
                binding = {k: query.get(k) for k in fields}
                binding['review_revision'] = int(binding['review_revision'])
                options = {}
                for key in ('include_notes', 'include_artifacts'):
                    if query.get(key, '0') not in {'0', '1'}:
                        raise ProjectError('Report disclosure options must be 0 or 1')
                    options[key] = query.get(key) == '1'
                return 200, service.report_export(tail[1], binding, **options)
            if tail == ['generation']:
                if method == 'GET':
                    return 200, service.generation_overview()
                if method == 'POST':
                    return 201, service.generate(body)
            if len(tail) >= 3 and tail[:2] == ['generation', 'modules']:
                source_id = tail[2]
                if len(tail) == 3 and method == 'GET':
                    return 200, service.generation_module(source_id)
                if tail[3:] == ['prepare'] and method == 'POST':
                    return 200, service.generation_prepare(source_id, body)
                if tail[3:] == ['plan'] and method == 'POST':
                    return 200, service.generation_configure(source_id, body)
                if len(tail) == 5 and tail[3] == 'code':
                    task_id = unquote(tail[4], errors='strict')
                    if method == 'GET':
                        return 200, service.generation_task(source_id, task_id)
                    if method == 'POST':
                        return 200, service.generation_code(source_id, task_id, body)
            if len(tail) == 3 and tail[0] == 'artifacts':
                if tail[2] == 'download' and method == 'GET':
                    return 200, service.generation_download(tail[1])
                if tail[2] == 'validate' and method == 'POST':
                    return 200, service.generation_validate(tail[1])
            if tail and tail[0] == 'review':
                if len(tail) == 1 and method == 'GET':
                    values = _inventory_query({k: v for k, v in query.items() if k != 'review_revision'})
                    values.pop('category')
                    values['sort'] = query.get('sort', 'priority')
                    expected_review = int(query['review_revision']) if 'review_revision' in query else None
                    return 200, service.review_queue(**values, expected_review=expected_review)
                if tail == ['review', 'bulk-preview'] and method == 'POST':
                    return 200, service.review_bulk_preview(body)
                if tail == ['review', 'bulk'] and method == 'POST':
                    return 200, service.review_bulk_apply(body)
                if len(tail) == 2:
                    finding_id = unquote(tail[1], errors='strict')
                    if method == 'GET':
                        if set(query) - {'revision', 'review_revision', 'offset', 'limit'}:
                            raise ProjectError('Unknown review detail query')
                        offset, limit = _page(query)
                        return 200, service.review_detail(finding_id,
                            expected_revision=query.get('revision'),
                            expected_review=int(query['review_revision']) if 'review_revision' in query else None,
                            history_offset=offset, history_limit=limit)
                    if method == 'POST':
                        operation = body.get('operation', 'DECIDE')
                        if operation == 'ANNOTATE':
                            return 200, service.review_annotate(finding_id, body)
                        if operation == 'DECIDE':
                            return 200, service.review_decide(finding_id, body)
                        raise ProjectError('Unknown review operation')
            if tail == ['freshness'] and method == 'GET':
                return 200, self._freshness(service)
            if tail == ['assessment'] and method == 'GET':
                return 200, {'assessment': service.assessment(freshness=self._freshness(service))}
            if tail == ['overview'] and method == 'GET':
                freshness = self._freshness(service)
                return 200, {'overview': service.overview(freshness=freshness)}
            if tail == ['system-map'] and method == 'GET':
                focus = query.get('focus') or None
                if set(query) - {'focus', 'depth', 'limit', 'edge_limit', 'layer', 'edge_type'}:
                    raise ProjectError('Unknown System Map query')
                try:
                    depth = int(query.get('depth', 2))
                    limit = int(query.get('limit', 100))
                    edge_limit = int(query.get('edge_limit', 200))
                except (TypeError, ValueError) as exc:
                    raise ProjectError('System map requires integer depth and limits') from exc
                layer = query.get('layer') or None
                edge_type = query.get('edge_type') or None
                freshness = self._freshness(service)
                return 200, service.system_map(
                    focus=focus, depth=depth, layer=layer, edge_type=edge_type,
                    limit=limit, edge_limit=edge_limit, freshness=freshness,
                )
            if tail == ['search'] and method == 'GET':
                if set(query) - {'query', 'q', 'limit'} or {'query', 'q'} <= set(query):
                    raise ProjectError('Use one search query parameter and an optional limit')
                search_query = query.get('query') or query.get('q') or ''
                try:
                    limit = int(query.get('limit', 20))
                except (TypeError, ValueError) as exc:
                    raise ProjectError('Search requires integer limit') from exc
                freshness = self._freshness(service)
                return 200, service.search(search_query, limit=limit, freshness=freshness)
            if tail == ['inventory'] and method == 'GET':
                freshness = self._freshness(service)
                return 200, service.inventory(**_inventory_query(query), freshness=freshness)
            if len(tail) == 3 and tail[0] == 'inventory' and method == 'GET':
                values = _inventory_query(query)
                if 'category' in query and query['category'] != tail[1]:
                    raise ProjectError('Inventory category conflicts with the route')
                if values['offset'] or values['limit'] != 50 or values['query'] or values['filters'] or values['sort'] != 'name':
                    raise ProjectError('Inventory detail accepts only an assessment revision')
                try:
                    item_id = unquote(tail[2], errors='strict')
                except UnicodeError as exc:
                    raise ProjectError('Invalid inventory identity encoding') from exc
                if '\0' in item_id:
                    raise ProjectError('Invalid inventory identity encoding')
                freshness = self._freshness(service)
                return 200, service.inventory_detail(
                    tail[1], item_id, expected_revision=values['expected_revision'],
                    freshness=freshness,
                )
            if tail == ['discover'] and method == 'POST':
                return 200, service.discover(**_preconditions(body))
            if tail == ['discovery'] and method == 'GET':
                offset, limit = _page(query)
                return 200, service._store.discovery(None, offset=offset, limit=limit)
            if len(tail) >= 2 and tail[0] == 'jobs':
                job_id = tail[1]
                if len(tail) == 2 and method == 'GET':
                    result = service.job(job_id)
                    offset, limit = _page(query)
                    row = service._store.session.db.execute('SELECT metadata_json FROM project_analysis_run WHERE job_id=?', (job_id,)).fetchone()
                    if row:
                        metadata = json.loads(row[0])
                        diagnostics = metadata.pop('diagnostics', [])
                        result.update(metadata, diagnostics=diagnostics[offset:offset+limit], diagnostics_total=len(diagnostics))
                    return 200, result
                if tail[2:] == ['cancel'] and method == 'POST':
                    return 200, service.cancel(job_id)
        return 404, {'error': 'Project route not found'}
