"""Project-scoped orchestration over the existing conversion Store and exporter."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from . import apexlang, apexlayout, parser, rbac
from .analysis import analyze_task
from .convert import build_tasks
from .project_conversion import discover_project_sources, intake_options
from .project_freshness import check_freshness
from .project_generation_policy import (
    POLICY_VERSION,
    module_blockers,
    table_mapping_blockers,
    target_code_supported,
)
from .project_jobs import now
from .project_lock import project_worker_lock
from .project_manifest import source_revision
from .project_model import ProjectError, RevisionConflict, canonical_json
from .project_review import ProjectReviewService, _binding, _fence, safe_excerpt
from .project_sources import stage_sources
from .project_store import contained_path
from .store import APPROVED, STATES, Store

MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class ProjectGenerationService:
    def __init__(self, service):
        self.service, self.store = service, service._store
        self.review = ProjectReviewService(service)

    def _snapshot(self):
        fresh = self.review._freshness()
        assessment = self.service.assessment(freshness=fresh)
        if assessment is None:
            raise ProjectError('Analyze the project before preparing generation.')
        return assessment, fresh

    @contextmanager
    def _operation(self, request, action=rbac.RUN_CONVERSION):
        self.service._job_authority(action)
        with project_worker_lock(self.service.access.root):
            assessment, fresh = self._snapshot()
            _fence(assessment, request)
            if fresh['status'] != 'CURRENT':
                raise RevisionConflict('Refresh the source assessment before generating or approving code.')
            yield assessment

    @contextmanager
    def _publication(self, assessment, request, action=rbac.RUN_CONVERSION, *, commit=None):
        self.service._job_authority(action)
        with self.store._write() as db:
            current = dict(self.store.load_assessment())
            current['review_revision'] = db.execute('SELECT review_revision FROM modernization_project WHERE id=1').fetchone()[0]
            _fence(current, request)
            yield db
            fresh = check_freshness(self.service.access, self.store.descriptor(), current,
                                   checkpoint=lambda: None, store=self.store)
            if fresh['status'] != 'CURRENT':
                raise RevisionConflict('Sources changed during publication; the previous state is preserved.')
            if commit is not None:
                commit()

    def _verify(self, assessment, request, action=rbac.RUN_CONVERSION):
        self.service._job_authority(action)
        current, fresh = self._snapshot()
        _fence(current, request)
        if fresh['status'] != 'CURRENT' or current['analysis_revision'] != assessment['analysis_revision']:
            raise RevisionConflict('Evidence changed during generation; no artifact is current.')

    @staticmethod
    def _sources(assessment):
        modules = {n['module'] for n in assessment['blueprint']['entities'] if n['type'] == 'FORM'}
        return [{**e, 'module': e['root_id'] + '/' + e['relative_path']}
                for e in assessment['source_manifest']
                if e['selected'] and e['representation'] == 'xml'
                and e['root_id'] + '/' + e['relative_path'] in modules]

    def _entry(self, assessment, source_id):
        entry = next((e for e in self._sources(assessment) if e['source_id'] == source_id), None)
        if entry is None:
            raise LookupError('Analyzed module not found')
        return entry

    def _session_record(self, assessment, source_id):
        return next((s for s in self.store.module_sessions() if s['source_id'] == source_id
                     and s['revision'] == assessment['analysis_revision']), None)

    def _path(self, relative):
        path = contained_path(self.store.directory, relative)
        if path.absolute() != path.resolve():
            raise ProjectError('Generation storage path was redirected.')
        return path

    @contextmanager
    def _module(self, assessment, source_id, *, read_only=False):
        entry = self._entry(assessment, source_id)
        record = self._session_record(assessment, source_id)
        if record is None:
            raise ProjectError('Prepare this module before reviewing code or generating.')
        xml = self._path(record['provenance']['xml'])
        if hashlib.sha256(xml.read_bytes()).hexdigest() != entry['sha256']:
            raise RevisionConflict('Prepared source was edited; refresh its source-bound session.')
        module = parser.parse_xml(xml)
        module.source_path = entry['module']
        try:
            session = Store(self._path(record['relative_store']), existing_only=True, read_only=read_only)
        except (OSError, sqlite3.Error) as exc:
            raise ProjectError('Prepared code session is unavailable; restore it before generation.') from exc
        try:
            metadata = session.session()
            if metadata.get('title') != module.name or metadata.get('source_path') != record['provenance']['xml']:
                raise ProjectError('Prepared code session identity changed; restore its source-bound state.')
            fields = ('id', 'module', 'kind', 'name', 'owner', 'source', 'fingerprint')
            expected = sorted(tuple(task.to_dict()[key] for key in fields) for task in build_tasks(module))
            actual = sorted(tuple(view.task[key] for key in fields) for view in session.all_views())
            if actual != expected:
                raise ProjectError('Prepared code tasks differ from source; restore the complete review session.')
            yield entry, module, session
        except sqlite3.Error as exc:
            raise ProjectError('Prepared code session is invalid; preserve it for diagnostics and restore its state.') from exc
        finally:
            session.close()

    def _plan(self, assessment, source_id):
        row = self.store.session.db.execute(
            'SELECT revision,payload_json FROM project_target_plan WHERE source_id=? AND analysis_revision=? ORDER BY id DESC LIMIT 1',
            (source_id, assessment['analysis_revision'])).fetchone()
        return (row['revision'], json.loads(row['payload_json'])) if row else (None, {})

    @staticmethod
    def _code_revision(session):
        views = session.all_views()
        return digest({'tasks': [v.to_dict() for v in views], 'keys': session.block_keys(),
                       'decisions': [session.latest_decision(v.task['id']) for v in views]})

    def prepare(self, source_id, request):
        with self._operation(request) as assessment:
            entry = self._entry(assessment, source_id)
            if self._session_record(assessment, source_id) is None:
                descriptor = self.store.descriptor()
                discovery = discover_project_sources(self.service.access, descriptor, self.store,
                    checkpoint=lambda: self.service._job_authority(), progress=lambda e: None, preview=False)
                with stage_sources(self.service.access, descriptor, discovery,
                                   checkpoint=lambda: self.service._job_authority()) as staged:
                    if source_revision(staged.manifest, intake_options(discovery)) != assessment['source_revision']:
                        raise RevisionConflict('Source changed while preparing conversion review.')
                    module = parser.parse_xml(staged.paths[source_id])
                    prefix = f"modules/{source_id}/{assessment['analysis_revision']}"
                    destination = self._path(prefix + '.session.db')
                    xml = self._path(prefix + '.xml')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists() or xml.exists():
                        raise ProjectError('An unregistered preparation exists; preserve it and inspect diagnostics.')
                    with xml.open('xb') as output:
                        output.write(staged.paths[source_id].read_bytes())
                    session = Store(destination, reconcile_jobs=False)
                    try:
                        session.init_session(module.name, prefix + '.xml')
                        tasks = build_tasks(module)
                        session.add_tasks(tasks)
                        session.save_analyses([analyze_task(t) for t in tasks])
                        apexlang.checksum_salt(session)
                    finally:
                        session.close()
                    self._verify(assessment, request)
                    self.store.add_module_session(source_id, assessment['analysis_revision'], prefix + '.session.db',
                        {'xml': prefix + '.xml', 'source_sha256': entry['sha256'], **_binding(assessment)})
        return self.module(source_id)

    def _detail(self, assessment, fresh, source_id):
        entry = self._entry(assessment, source_id)
        revision, plan = self._plan(assessment, source_id)
        code, tasks, bindings = None, [], []
        extra = []
        if self._session_record(assessment, source_id):
            with self._module(assessment, source_id) as (_, module, session):
                code = self._code_revision(session)
                layout = apexlayout.build_layout(module, 1)
                extra.extend(table_mapping_blockers(module, assessment['blueprint']))
                report = apexlayout.layout_report(layout)
                hidden_items = {item['source'] for item in report['hidden']}
                names = list(layout.names.values())
                lovs = [lov.id for lov in layout.lovs]
                if len(names) != len(set(names)) or len(lovs) != len(set(lovs)):
                    extra.append({'code': 'TARGET_NAME_COLLISION', 'id': source_id,
                                  'message': 'Target item or shared LOV names collide; resolve the source naming scope.'})
                if (report['totals']['skipped'] or report['totals']['controls'].get(apexlayout.UNSUPPORTED)
                        or report['totals']['groups'].get(apexlayout.UNSUPPORTED)):
                    extra.append({'code': 'UNSUPPORTED_LAYOUT', 'id': source_id,
                                  'message': 'The layout contains unsupported or omitted behavior; this module is blocked.'})
                actual_keys = {k: v['key_column'] for k, v in session.block_keys().items()}
                planned_keys = {k.strip().upper(): v.strip().upper() for k, v in plan.get('keys', {}).items()}
                if actual_keys != planned_keys:
                    extra.append({'code': 'TARGET_KEYS_CHANGED', 'id': source_id,
                                  'message': 'Row keys differ from the reviewed target plan; reconfirm the plan.'})
                emitted = apexlang._emitted_page_items(apexlang._layout_chunks(layout))
                for view in session.all_views():
                    tasks.append({'id': view.task['id'], 'title': view.task['title'], 'state': view.state})
                    if view.state != APPROVED or not view.code.strip():
                        extra.append({'code': 'CODE_NOT_APPROVED', 'id': view.task['id'],
                                      'message': 'Review the target code separately from the modernization decision.'})
                    if view.state == APPROVED:
                        decision = session.latest_decision(view.task['id']) or {}
                        expected = {**_binding(assessment), 'target_revision': revision, 'source_id': source_id}
                        if json.loads(decision.get('project_binding', '{}')) != expected:
                            extra.append({'code': 'CODE_NEEDS_REVALIDATION', 'id': view.task['id'],
                                          'message': 'Code approval belongs to earlier project/target evidence; review it again.'})
                    if view.code.strip() and not target_code_supported(view.code, emitted):
                        extra.append({'code': 'UNSUPPORTED_TARGET_CODE', 'id': view.task['id'],
                                      'message': 'Target code retains Forms runtime behavior or references unmapped page items.'})
                    if view.task['name'] not in {'WHEN-VALIDATE-ITEM', 'WHEN-VALIDATE-RECORD'}:
                        extra.append({'code': 'UNSUPPORTED_EXECUTION_MAPPING', 'id': view.task['id'],
                                      'message': 'The exporter only parks this code as a disabled process; usable page generation is blocked.'})
                bindings = apexlang.binding_options(session, module)
                _, binding_manifest = apexlang.confirmed_bindings(session, layout)
                bound = {b['block'] for b in binding_manifest if b['bound']}
                for option in bindings:
                    if option['block'] not in bound:
                        extra.append({'code': 'ROW_KEY_NOT_CONFIRMED', 'id': option['block'],
                                      'message': 'Confirm the row key before generating data-bound behavior.'})
                candidates = {b['block'] for b in bindings}
                for block in module.blocks:
                    for item in block.items:
                        hidden = not item.visible or f'{block.name}.{item.name}' in hidden_items
                        if (not item.insert_allowed or not item.update_allowed or item.query_only
                                or item.minimum_value or item.maximum_value
                                or item.subclassed or apexlayout._FORMS_EXPRESSION.search(item.initial_value)
                                or (hidden and (item.required or item.max_length or item.initial_value))
                                or (block.database_block and hidden
                                    and (not item.enabled or 'display' in item.item_type.lower()))):
                            extra.append({'code': 'UNSUPPORTED_ITEM_CONTROL', 'id': f'{block.name}.{item.name}',
                                          'message': 'This item has a restriction, inherited behavior or dynamic default not preserved by the exporter.'})
                    if block.database_block and (not block.insert_allowed or not block.update_allowed
                                                  or block.where_clause or block.order_by_clause):
                        extra.append({'code': 'UNSUPPORTED_DATA_CONTROL', 'id': block.name,
                                      'message': 'The exporter does not preserve this block restriction or query clause; data-bound generation is blocked.'})
                    if block.database_block and block.name not in candidates:
                        extra.append({'code': 'UNSUPPORTED_DATABASE_MAPPING', 'id': block.name,
                                      'message': 'This database block has no supported reviewed single-record binding.'})
        else:
            extra.append({'code': 'MODULE_NOT_PREPARED', 'id': source_id, 'message': 'Prepare the source-bound code review session.'})
        blockers = module_blockers(assessment, entry['module'], plan, freshness=fresh['status'], code_blockers=extra)
        return {'source_id': source_id, 'module': entry['module'], 'binding': _binding(assessment),
                'target_revision': revision, 'code_revision': code, 'plan': plan,
                'tasks': tasks, 'bindings': bindings, 'blockers': blockers, 'ready': not blockers}

    def module(self, source_id):
        assessment, fresh = self._snapshot()
        return self._detail(assessment, fresh, source_id)

    def overview(self):
        assessment, fresh = self._snapshot()
        modules = []
        for entry in self._sources(assessment):
            modules.append({'source_id': entry['source_id'], 'module': entry['module'],
                            'prepared': bool(self._session_record(assessment, entry['source_id']))})
        artifacts = [json.loads(row[0]) for row in self.store.session.db.execute(
            'SELECT metadata_json FROM project_artifact ORDER BY created_at DESC LIMIT 50')]
        for artifact in artifacts:
            validation = self.store.session.db.execute(
                'SELECT payload_json FROM project_artifact_validation WHERE artifact_id=? ORDER BY id DESC LIMIT 1',
                (artifact['artifact_id'],)).fetchone()
            if validation:
                artifact['validation'] = json.loads(validation[0])
                artifact['validation_status'] = artifact['validation']['status']
                try:
                    self._artifact_bytes(artifact['artifact_id'])
                except (OSError, ProjectError):
                    artifact['validation_status'] = 'Not Validated'
                    artifact['integrity'] = 'Modified or unavailable; historical validation does not apply.'
        return {'binding': _binding(assessment), 'target': assessment['target'], 'freshness': fresh['status'],
                'modules': modules, 'artifacts': artifacts, 'policy': POLICY_VERSION}

    def configure(self, source_id, request):
        with self._operation(request) as assessment:
            detail = self._detail(assessment, {'status': 'CURRENT'}, source_id)
            for key in ('target_revision', 'code_revision'):
                if request.get(key) != detail[key]:
                    raise RevisionConflict('Target or code review changed; reload the scope.')
            plan = request.get('plan')
            if (not isinstance(plan, dict) or set(plan) - {'security_confirmed', 'database_confirmed', 'mapping_confirmed', 'rationale', 'keys'}
                    or any(type(plan.get(k)) is not bool for k in ('security_confirmed', 'database_confirmed'))
                    or type(plan.get('mapping_confirmed', False)) is not bool
                    or not isinstance(plan.get('rationale'), str) or not 1 <= len(plan['rationale'].strip()) <= 4000
                    or not isinstance(plan.get('keys', {}), dict)):
                raise ProjectError('Confirm target prerequisites explicitly and provide rationale.')
            with self._module(assessment, source_id) as (_, module, session):
                keys = plan.get('keys', {})
                if any(not isinstance(k, str) or not isinstance(v, str) for k, v in keys.items()):
                    raise ProjectError('Row keys must map block names to column names.')
                session.db.execute('BEGIN IMMEDIATE')
                try:
                    if self._code_revision(session) != detail['code_revision']:
                        raise RevisionConflict('Code or row keys changed while saving the plan.')
                    apexlang.apply_block_keys(session, module, keys,
                        set(session.block_keys()) - {k.strip().upper() for k in keys},
                        by=self.service.access.actor, commit=False)
                    self._verify(assessment, request)
                    revision = digest({'plan': plan, 'binding': _binding(assessment), 'source_id': source_id})
                    with self._publication(assessment, request) as db:
                        db.execute('INSERT INTO project_target_plan(source_id,analysis_revision,revision,payload_json,reviewer,created_at) VALUES (?,?,?,?,?,?)',
                            (source_id, assessment['analysis_revision'], revision, canonical_json(plan), self.service.access.actor, now()))
                    # Crash between the two existing stores fails closed via
                    # TARGET_KEYS_CHANGED; it never authorizes a different key.
                    session.db.commit()
                except BaseException:
                    session.db.rollback()
                    raise
        return self.module(source_id)

    def task(self, source_id, task_id):
        assessment, _ = self._snapshot()
        with self._module(assessment, source_id) as (_, _, session):
            view = session.view(task_id)
            if view is None:
                raise LookupError('Code unit not found in this module')
            return {'binding': _binding(assessment), 'source_id': source_id, 'task_id': task_id,
                    'target_revision': self._plan(assessment, source_id)[0],
                    'code_revision': self._code_revision(session), 'title': view.task['title'],
                    'source_excerpt': safe_excerpt(view.task['source']), 'source_truncated': len(view.task['source']) > 8000,
                    'state': view.state, 'code': view.code[:64000], 'comment': view.comment[:4000],
                    'history': [{'state': e['state'], 'comment': e['comment'], 'decided_at': e['decided_at'],
                                 'binding': json.loads(e['project_binding'])}
                                for e in session.db.execute('SELECT state,comment,decided_at,project_binding FROM decision WHERE task_id=? ORDER BY id DESC LIMIT 50', (task_id,))],
                    'notice': 'Review the exact authorized local source before approving target code. No AI ran.'}

    def code(self, source_id, task_id, request):
        with (self._operation(request, rbac.APPROVE_AI_PROPOSAL) as assessment,
              self._module(assessment, source_id) as (_, _, session)):
            session.db.execute('BEGIN IMMEDIATE')
            try:
                if request.get('code_revision') != self._code_revision(session):
                    raise RevisionConflict('Code review changed; reload before approving.')
                if session.get_task(task_id) is None:
                    raise LookupError('Code unit not found in this module')
                state, code, rationale = request.get('state'), request.get('code'), request.get('rationale')
                if (state not in STATES or not isinstance(code, str) or len(code) > 64000 or '\0' in code
                        or not isinstance(rationale, str) or not 1 <= len(rationale.strip()) <= 4000):
                    raise ProjectError('Choose a supported state and provide bounded code and rationale.')
                if state == APPROVED and (request.get('code_confirmed') is not True or not code.strip()):
                    raise ProjectError('Explicitly confirm review of nonempty target code before approval.')
                with self._publication(assessment, request, rbac.APPROVE_AI_PROPOSAL, commit=session.db.commit):
                    if request.get('target_revision') != self._plan(assessment, source_id)[0]:
                        raise RevisionConflict('Target plan changed; reload before approving code.')
                    session.set_decision(task_id, state, code=code, comment=rationale,
                                         reviewer=self.service.access.actor, commit=False,
                                         project_binding={**_binding(assessment), 'source_id': source_id,
                                                          'target_revision': request.get('target_revision')})
            except BaseException:
                session.db.rollback()
                raise
        return self.task(source_id, task_id)

    def generate(self, request):
        with self._operation(request, rbac.EXPORT_PROJECT) as assessment:
            scopes = request.get('scopes')
            if not isinstance(scopes, list) or len(scopes) != 1 or not isinstance(scopes[0], dict):
                raise ProjectError('Select one independent module application for this generation run.')
            scope = scopes[0]
            detail = self._detail(assessment, {'status': 'CURRENT'}, scope.get('source_id'))
            if any(scope.get(k) != detail[k] for k in ('target_revision', 'code_revision')):
                raise RevisionConflict('Target or approved code changed; refresh generation readiness.')
            if detail['blockers']:
                raise ProjectError('Generation is blocked. Resolve the listed scope prerequisites first.')
            directory = self._path('artifacts')
            directory.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='stage-', dir=directory) as staging:
                with self._module(assessment, detail['source_id']) as (_, module, session):
                    copied = Store(Path(staging) / 'export.session.db', reconcile_jobs=False)
                    try:
                        session.db.backup(copied.db)
                        result = apexlang.export_apexlang(copied, module, Path(staging) / 'output',
                            {'alias': 'module-' + detail['source_id'][:20], 'ai_layout': False})
                    finally:
                        copied.close()
                    if self._code_revision(session) != detail['code_revision']:
                        raise RevisionConflict('Code changed during export; generated files were not published.')
                mapping = json.loads(result.manifest_path.read_text(encoding='utf-8'))
                if any(not e.get('enabled') for e in mapping.get('approved_components', [])):
                    raise ProjectError('An execution mapping is disabled or unsupported; this page cannot be published safely.')
                data = result.zip_path.read_bytes()
                if len(data) > MAX_ARTIFACT_BYTES:
                    raise ProjectError('Generated artifact exceeds the supported download size.')
                self._verify(assessment, request, rbac.EXPORT_PROJECT)
                artifact_id = uuid.uuid4().hex
                destination = self._path('artifacts/' + artifact_id)
                metadata = {**_binding(assessment), 'artifact_id': artifact_id, 'status': 'Generated',
                    'validation_status': 'Not Validated', 'created_at': now(), 'target': assessment['target'],
                    'source_id': detail['source_id'], 'target_revision': detail['target_revision'],
                    'code_revision': detail['code_revision'], 'sha256': hashlib.sha256(data).hexdigest(),
                    'size_bytes': len(data), 'policy': POLICY_VERSION,
                    'mode': 'selected-module',
                    'excluded_source_ids': [e['source_id'] for e in self._sources(assessment)
                                            if e['source_id'] != detail['source_id']],
                    'files': {p.relative_to(result.project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(result.project.rglob('*')) if p.is_file()},
                    'limitations': ['Validation is not runtime equivalence.', 'One independent module application; no automatic deployment.']}
                # Unique destination, never the user's earlier artifact directory.
                destination.mkdir()
                shutil.copytree(result.project, destination / 'apexlang')
                with (destination / 'application.apex.zip').open('xb') as output:
                    output.write(data)
                # Fence legacy session writers too: their Store does not take the
                # project worker lock. Hold this snapshot through publication.
                with self._module(assessment, detail['source_id']) as (_, _, session):
                    session.db.execute('BEGIN IMMEDIATE')
                    try:
                        if self._code_revision(session) != detail['code_revision']:
                            raise RevisionConflict('Code changed during publication; artifact was not published.')
                        with self._publication(assessment, request, rbac.EXPORT_PROJECT) as db:
                            db.execute('INSERT INTO project_artifact VALUES (?,?,?)',
                                (artifact_id, metadata['created_at'], canonical_json(metadata)))
                    finally:
                        session.db.rollback()
            return metadata

    def download(self, artifact_id):
        self.service._job_authority(rbac.EXPORT_PROJECT)
        return self._artifact_bytes(artifact_id)

    def _artifact_bytes(self, artifact_id):
        """Caller authorizes before acquiring a write transaction."""
        if not isinstance(artifact_id, str) or not re.fullmatch('[a-f0-9]{32}', artifact_id):
            raise LookupError('Artifact not found')
        row = self.store.session.db.execute('SELECT metadata_json FROM project_artifact WHERE artifact_id=?', (artifact_id,)).fetchone()
        if row is None:
            raise LookupError('Artifact not found')
        metadata = json.loads(row[0])
        root = self._path('artifacts/' + artifact_id)
        actual = {p.relative_to(root / 'apexlang').as_posix()
                  for p in (root / 'apexlang').rglob('*') if p.is_file()}
        if actual != set(metadata['files']):
            raise RevisionConflict('Generated files were added or removed; validation no longer applies.')
        for name, expected in metadata['files'].items():
            path = self._path(f'artifacts/{artifact_id}/apexlang/{name}')
            if (not path.is_file() or path.stat().st_size > MAX_ARTIFACT_BYTES
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
                raise RevisionConflict('Generated files were edited. Prior validation no longer applies; original files are preserved.')
        archive = self._path(f'artifacts/{artifact_id}/application.apex.zip')
        if not archive.is_file() or archive.stat().st_size > MAX_ARTIFACT_BYTES:
            raise RevisionConflict('Artifact size changed; prior validation no longer applies.')
        data = archive.read_bytes()
        if len(data) > MAX_ARTIFACT_BYTES or hashlib.sha256(data).hexdigest() != metadata['sha256']:
            raise RevisionConflict('Artifact bytes changed; prior validation no longer applies.')
        return data
