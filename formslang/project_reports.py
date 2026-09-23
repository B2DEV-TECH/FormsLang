"""Revision-fenced delivery over persisted assessment, review and artifact records."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

from . import __version__, rbac
from .estate_triage import investigation_groups
from .project_generation import ProjectGenerationService, digest
from .project_lock import project_worker_lock
from .project_model import ProjectError, RevisionConflict, canonical_json, descriptor_to_dict
from .project_projection import module_relationships, prepare_projection
from .project_review import STATES, ProjectReviewService, _binding, _fence

MAX_DELIVERY_BYTES = 128 * 1024 * 1024
SNAPSHOT_SCHEMA = 'project-delivery/1'
GENERIC_ARTIFACT_KIND = 'generic-assessment-package'
# Where each single-file format lives inside the full package.
FORMAT_PATHS = {
    'executive': 'assessment/', 'technical': 'assessment/', 'risk': 'assessment/',
    'dossier-md': 'dossier/', 'investigation-md': 'architecture/', 'investigation-json': 'architecture/',
    'decision-records-md': 'review/', 'decisions': 'review/',
    'backlog-csv': 'backlog/', 'backlog-json': 'backlog/',
}
LITERAL_NAMED_TYPES = frozenset({'INTEGRATION_POINT'})


def literal_label(identity):
    return 'Integration target (literal omitted; ref ' + str(identity).rsplit(':', 1)[-1][:8] + ')'


HOTSPOT_FIELDS = ('id', 'hotspot_type', 'label', 'classification', 'severity', 'title', 'statement',
                  'module', 'finding_ids', 'evidence', 'evidence_refs', 'edge_refs', 'uncertainty',
                  'recommended_action')
FORMATS = {
    'executive': ('executive-summary.html', 'text/html; charset=utf-8'),
    'technical': ('technical-assessment.html', 'text/html; charset=utf-8'),
    'risk': ('risk-report.html', 'text/html; charset=utf-8'),
    'dossier-md': ('modernization-dossier.md', 'text/markdown; charset=utf-8'),
    'investigation-md': ('investigation-groups.md', 'text/markdown; charset=utf-8'),
    'investigation-json': ('investigation-groups.json', 'application/json; charset=utf-8'),
    'decision-records-md': ('decision-records.md', 'text/markdown; charset=utf-8'),
    'backlog-csv': ('modernization-backlog.csv', 'text/csv; charset=utf-8'),
    'backlog-json': ('modernization-backlog.json', 'application/json; charset=utf-8'),
    'decisions': ('decisions.json', 'application/json; charset=utf-8'),
    'package': ('modernization-package.zip', 'application/zip'),
}


@dataclass(frozen=True)
class ProjectDownload:
    body: bytes
    filename: str
    content_type: str


def json_bytes(value):
    return (canonical_json(value) + '\n').encode('utf-8')


def _decisions(assessment, annotations):
    result = []
    for finding in assessment['blueprint']['findings']:
        events = []
        for event in finding.get('review_history', []):
            events.append({'action': event['action'], 'recommendation': event['recommendation'],
                'timestamp': event['decided_at'], 'rationale': event['comment'],
                'binding': event.get('finding_snapshot', {}).get('project_binding'),
                'applicable': event['revision'] == finding['revision'] and assessment['status'] == 'Current'})
        notes = [{'kind': a['kind'], 'note': a['note'], 'timestamp': a['created_at'],
                  'binding': json.loads(a['binding_json']),
                  'applicable': a['revision'] == finding['revision'] and assessment['status'] == 'Current'}
                 for a in annotations.get(finding['entity'], [])]
        result.append({'finding_id': finding['id'], 'finding_revision': finding['revision'],
            'engine_recommendation': finding['recommendation'],
            'human_decision': finding.get('human_decision', {}).get('recommendation'),
            'review_status': STATES.get(finding.get('review_state'), 'Pending'),
            'history': events, 'annotations': notes})
    return sorted(result, key=lambda d: d['finding_id'])


class ProjectReportService:
    def __init__(self, service):
        self.service, self.store = service, service._store

    def _records(self):
        db = self.store.session.db
        plans = [dict(r) for r in db.execute('SELECT source_id,analysis_revision,revision,payload_json,created_at FROM project_target_plan ORDER BY id')]
        artifacts = [json.loads(r[0]) for r in db.execute('SELECT metadata_json FROM project_artifact ORDER BY artifact_id')]
        validations = [json.loads(r[0]) for r in db.execute('SELECT payload_json FROM project_artifact_validation ORDER BY id')]
        annotations = {}
        for row in db.execute('SELECT entity,kind,note,revision,created_at,binding_json FROM blueprint_annotation ORDER BY id DESC'):
            annotations.setdefault(row['entity'], []).append(dict(row))
        return plans, artifacts, validations, annotations

    def capture(self):
        """The one normalized delivery snapshot shared by Reports and the Generic package.

        Callers hold the project worker lock.
        """
        return self._capture()

    def _capture(self):
        fresh = ProjectReviewService(self.service)._freshness()
        assessment = self.service.assessment(freshness=fresh)
        if assessment is None:
            raise ProjectError('Analyze the project before exporting an assessment.')
        db = self.store.session.db
        db.execute('BEGIN')
        try:
            row = db.execute('SELECT analysis_revision,review_revision FROM modernization_project WHERE id=1').fetchone()
            if tuple(row) != (assessment['analysis_revision'], assessment['review_revision']):
                raise RevisionConflict('Assessment or review changed while capturing the report; reload.')
            descriptor = descriptor_to_dict(self.store.descriptor())
            plans, artifacts, validations, annotations = self._records()
        finally:
            db.rollback()
        prepared = prepare_projection(descriptor, assessment, fresh, store_scope='delivery')
        rows = copy.deepcopy(prepared.rows)
        findings = {f['id']: f for f in assessment['blueprint']['findings']}
        for row in (*rows['findings'], *rows['business_rules']):
            finding = findings[row['id']]
            row['target'] = str(finding.get('suggested_target', ''))[:2000]
            # Free-form engine reasons can interpolate source literals. Delivery
            # uses structural signal identities; exact explanation stays in Review.
            signals = list(row.get('signals', ()))
            row['reason'] = ('Engine evidence signals: ' + ', '.join(signals) if signals else
                             'Engine recommendation based on observed structure; inspect authorized Review evidence.')
            row['dependencies'] = list(finding.get('dependencies', []))
            row['finding_revision'] = finding['revision']
            row['evidence_refs'] = sorted(e for e in finding.get('evidence', []) if isinstance(e, str))[:20]
        # Some entities are named after a source literal (OS commands, URLs,
        # user exits). Their names stay in the authorized local UI only.
        literal = {e['id']: literal_label(e['id']) for e in assessment['blueprint']['entities']
                   if e.get('type') in LITERAL_NAMED_TYPES}
        for row in (*rows['findings'], *rows['business_rules']):
            if row.get('entity_id') in literal:
                row['name'] = literal[row['entity_id']]
        rows['dependencies'] = tuple(
            {**row, 'source': literal.get(row['source_id'], row['source']),
             'target': literal.get(row['target_id'], row['target'])} for row in rows['dependencies'])
        overview_data = copy.deepcopy(prepared.overview_data)
        by_id = {row['id']: row['name'] for row in rows['findings']}
        for item in overview_data['priority']['start_here']:
            item['name'] = by_id.get(item['id'], item['name'])
        # Hotspots cross the delivery boundary through an explicit allowlist.
        rows['hotspots'] = tuple({key: copy.deepcopy(h[key]) for key in HOTSPOT_FIELDS}
                                 for h in rows['hotspots'])
        snapshot = {'schema': SNAPSHOT_SCHEMA, 'formslang_version': __version__,
            'overview': overview_data, 'inventory': rows,
            'relationships': module_relationships(prepared, rename=literal),
            'investigation_groups': investigation_groups(rows['findings'], rows['hotspots']),
            'decisions': _decisions(assessment, annotations), 'artifacts': artifacts,
            'validation_evidence': validations, 'target_plans': plans,
            'engine_identity': assessment['engine_identity'],
            'source_manifest': [{k: e[k] for k in ('source_id', 'root_id', 'relative_path', 'sha256', 'status') if k in e}
                                for e in assessment['source_manifest']]}
        return snapshot, assessment, fresh

    def overview(self):
        self.service._job_authority(rbac.VIEW_PROJECT)
        with project_worker_lock(self.service.access.root):
            snapshot, assessment, fresh = self._capture()
        return {'binding': {**_binding(assessment), 'snapshot_revision': digest(snapshot)},
                'freshness': fresh['status'], 'assessment_timestamp': assessment['analyzed_at'],
                'formats': [{'id': key, 'filename': value[0]} for key, value in FORMATS.items()],
                'notice': 'Reports use saved evidence. Source bodies and private notes are excluded by default.'}

    def _artifacts(self, snapshot, assessment, include):
        generation = ProjectGenerationService(self.service)
        files, excluded = {}, []
        latest_plans = {(p['source_id'], p['analysis_revision']): p['revision'] for p in snapshot['target_plans']}
        sessions = {(s['source_id'], s['revision']): s for s in self.store.module_sessions()}
        for artifact in snapshot['artifacts']:
            identity = artifact['artifact_id']
            reason = None
            if artifact.get('artifact_kind') == GENERIC_ARTIFACT_KIND:
                reason = self._generic_artifact(generation, snapshot, assessment, artifact, include, files)
            elif artifact.get('artifact_kind') or not all(
                    key in artifact for key in ('source_id', 'target_revision', 'code_revision')):
                reason = 'ARTIFACT_KIND_UNSUPPORTED'
            elif not include:
                reason = 'ARTIFACTS_NOT_REQUESTED'
            elif (snapshot['overview']['assessment']['freshness'] != 'CURRENT'
                  or any(artifact.get(k) != v for k, v in _binding(assessment).items())
                  or latest_plans.get((artifact['source_id'], artifact['analysis_revision'])) != artifact['target_revision']):
                reason = 'ARTIFACT_REVISION_STALE'
            else:
                record = sessions.get((artifact['source_id'], artifact['analysis_revision']))
                if record is None:
                    reason = 'ARTIFACT_CODE_UNAVAILABLE'
                else:
                    try:
                        with generation._module(assessment, artifact['source_id'], read_only=True) as (_, _, session):
                            if generation._code_revision(session) != artifact['code_revision']:
                                reason = 'ARTIFACT_CODE_STALE'
                    except (OSError, sqlite3.Error, ProjectError):
                        reason = 'ARTIFACT_CODE_UNAVAILABLE'
                if reason is None:
                    try:
                        data = generation._artifact_bytes(identity)
                        with zipfile.ZipFile(io.BytesIO(data)) as archive:
                            entries = archive.infolist()
                            if (len({e.filename for e in entries}) != len(entries)
                                    or {e.filename for e in entries} != set(artifact['files'])
                                    or sum(e.file_size for e in entries) > MAX_DELIVERY_BYTES):
                                raise ProjectError('Artifact archive layout changed.')
                            if sum(map(len, files.values())) + sum(e.file_size for e in entries) > MAX_DELIVERY_BYTES:
                                reason = 'PACKAGE_SIZE_LIMIT'
                            else:
                                content = {}
                                for entry in entries:
                                    path = PurePosixPath(entry.filename)
                                    if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename:
                                        raise ProjectError('Unsafe artifact member.')
                                    value = archive.read(entry)
                                    if hashlib.sha256(value).hexdigest() != artifact['files'][entry.filename]:
                                        raise ProjectError('Artifact archive content changed.')
                                    content[f'apexlang/{identity}/{entry.filename}'] = value
                                files.update(content)
                    except (OSError, ProjectError, zipfile.BadZipFile):
                        reason = 'ARTIFACT_INTEGRITY'
            if reason:
                excluded.append({'artifact_id': identity, 'reason': reason})
        return files, excluded

    def _generic_artifact(self, generation, snapshot, assessment, artifact, include, files):
        """Include a target-neutral assessment package only when it is current and intact.

        Generic packages have no module scope, target plan or code revision; their
        binding is the analysis, source and review revisions they were built from.
        """
        if not include:
            return 'ARTIFACTS_NOT_REQUESTED'
        binding = _binding(assessment)
        if (snapshot['overview']['assessment']['freshness'] != 'CURRENT'
                or any(artifact.get(k) != v for k, v in binding.items())):
            return 'ARTIFACT_REVISION_STALE'
        try:
            data = generation._artifact_bytes(artifact['artifact_id'])
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                names = [e.filename for e in entries]
                if len(set(names)) != len(names) or set(names) != set(artifact['files']):
                    raise ProjectError('Assessment package layout changed.')
                if sum(map(len, files.values())) + sum(e.file_size for e in entries) > MAX_DELIVERY_BYTES:
                    return 'PACKAGE_SIZE_LIMIT'
                content = {}
                for entry in entries:
                    value = archive.read(entry)
                    if hashlib.sha256(value).hexdigest() != artifact['files'][entry.filename]:
                        raise ProjectError('Assessment package content changed.')
                    content[f"assessment-package/{artifact['artifact_id']}/{entry.filename}"] = value
        except (OSError, ProjectError, zipfile.BadZipFile):
            return 'ARTIFACT_INTEGRITY'
        files.update(content)
        return None

    def export(self, kind, request, *, include_notes=False, include_artifacts=False):
        if kind not in FORMATS or type(include_notes) is not bool or type(include_artifacts) is not bool:
            raise ProjectError('Choose a supported report and explicit boolean disclosure options.')
        self.service._job_authority(rbac.EXPORT_PROJECT)
        with project_worker_lock(self.service.access.root):
            snapshot, assessment, fresh = self._capture()
            _fence(assessment, request)
            revision = digest(snapshot)
            if request.get('snapshot_revision') != revision:
                raise RevisionConflict('Delivery snapshot changed; reload Reports before downloading.')
            snapshot['snapshot_revision'] = revision
            artifact_files, exclusions = self._artifacts(snapshot, assessment, include_artifacts and kind == 'package')
            snapshot['exclusions'] = exclusions
            from .project_report_render import build_files
            files = build_files(copy.deepcopy(snapshot), include_notes=include_notes, artifact_files=artifact_files)
            if sum(map(len, files.values())) > MAX_DELIVERY_BYTES:
                raise ProjectError('Delivery exceeds 128 MB. Export reports separately or exclude generated artifacts.')
            if kind == 'package':
                stream = io.BytesIO()
                with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                    for name, data in sorted(files.items()):
                        entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                        entry.compress_type = zipfile.ZIP_DEFLATED
                        entry.external_attr = 0o644 << 16
                        archive.writestr(entry, data)
                body = stream.getvalue()
            else:
                body = files[FORMAT_PATHS[kind] + FORMATS[kind][0]]
            self.service._job_authority(rbac.EXPORT_PROJECT)
            current_fresh = ProjectReviewService(self.service)._freshness()
            if current_fresh['status'] != fresh['status'] or current_fresh['source_revision'] != fresh['source_revision']:
                raise RevisionConflict('Source changed during export; reload its freshness status.')
            filename, content_type = FORMATS[kind]
            if include_notes and kind in {'decisions', 'backlog-csv', 'backlog-json'}:
                stem, suffix = filename.rsplit('.', 1)
                filename = stem + '-sensitive.' + suffix
            if kind == 'backlog-csv' and not snapshot['inventory']['findings']:
                filename = filename.replace('.csv', '-' + revision + '.csv')
            return ProjectDownload(body, filename, content_type)
