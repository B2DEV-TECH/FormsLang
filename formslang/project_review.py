"""Revision-bound governance over the existing assessment and review history."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone

from . import plsql_evidence, rbac
from .project_freshness import check_freshness
from .project_lock import project_worker_lock
from .project_model import ProjectError, RevisionConflict, canonical_json, descriptor_to_dict
from .project_projection import inventory_detail, inventory_page, prepare_projection

DECISIONS = frozenset({'PRESERVE', 'CONVERT', 'REFACTOR', 'MOVE_TO_PLSQL_API',
                      'REPLACE_WITH_APEX_NATIVE', 'MANUAL_REVIEW', 'DROP'})
ANNOTATIONS = frozenset({'CONFIRMED_BUSINESS_RULE', 'PRESENTATION_ONLY',
                       'DATABASE_API_AUTHORITATIVE', 'LEGACY_LOGIC_OBSOLETE',
                       'NEEDS_BUSINESS_OWNER_DECISION'})
REASONS = frozenset({'BUSINESS_OWNER_INPUT', 'ARCHITECTURE_DECISION',
                    'INSUFFICIENT_DATABASE_CONTEXT', 'UNCLEAR_LEGACY_INTENT', 'OTHER'})
STATES = {'PENDING': 'Pending', 'APPROVE': 'Accepted', 'MODIFY': 'Changed',
          'REJECT': 'Needs Review', 'DEFER': 'Deferred', 'STALE': 'Needs Revalidation'}
POLICY_VERSION = 'project-bulk/1'
MECHANICAL_SIGNALS = frozenset({'NATIVE_FORMAT_VALIDATION', 'NATIVE_DEFAULT_SUGGESTION',
    'NATIVE_DISPLAY_DERIVATION', 'NATIVE_CONFIRMATION', 'NATIVE_ITEM_STATE', 'NAVIGATION_TOOLBAR'})
MECHANICAL_BUILTINS = {'NATIVE_CONFIRMATION': frozenset({'SHOW_ALERT'}),
                      'NATIVE_ITEM_STATE': frozenset({'SET_ITEM_PROPERTY'})}


def safe_excerpt(source):
    """Conservative structural excerpt; literals/comments are not review evidence here."""
    if re.search(r"(?i)\b(?:logon|password|passwd|pwd|secret|token|identified|connect)\b|[a-z]:[\\/]|\\\\|\bq'", source):
        return '[Sensitive or unsupported literal context omitted; inspect the authorized local source.]'
    # Start empty and copy only lexical words/symbols. Comments, literals, quoted
    # identifiers and incomplete tokens can never become visible through overlap.
    redacted = ['\n' if char == '\n' else ' ' for char in source]
    for token in plsql_evidence.tokens(source):
        if token.kind in {'word', 'symbol'}:
            redacted[token.start:token.end] = source[token.start:token.end]
    return '\n'.join(''.join(redacted).splitlines()[:80])[:8000]


def _provenance(assessment, finding):
    return {**_binding(assessment, finding), 'engine_recommendation': finding['recommendation'],
            'engine_version': assessment['blueprint']['engine_version'], 'target': assessment['target']}


def _text(value, name, *, required=False, limit=4000):
    if not isinstance(value, str) or len(value) > limit or '\0' in value:
        raise ProjectError(f'{name} must be text of at most {limit} characters')
    value = value.strip()
    if required and not value:
        raise ProjectError(f'{name} is required')
    return value


def _binding(assessment, finding=None):
    result = {key: assessment[key] for key in ('project_id', 'analysis_revision',
                                             'source_revision', 'review_revision')}
    if finding is not None:
        result['finding_revision'] = finding['revision']
    return result


def _fence(assessment, request, finding=None):
    if not isinstance(request, dict):
        raise ProjectError('Review request must be an object')
    for key, expected in _binding(assessment, finding).items():
        if type(request.get(key)) is not type(expected) or request.get(key) != expected:
            raise RevisionConflict('Review evidence changed; reload current evidence')


def _finding(assessment, finding_id):
    if not isinstance(finding_id, str) or len(finding_id) > 500:
        raise ProjectError('Invalid finding identity')
    result = next((f for f in assessment['blueprint']['findings'] if f['id'] == finding_id), None)
    if result is None:
        raise LookupError(finding_id)
    return result


class ProjectReviewService:
    """One facade-owned connection; policy and persistence shared by every adapter."""

    def __init__(self, service):
        self.service = service
        self.store = service._store

    def _freshness(self):
        self.service._job_authority(rbac.VIEW_PROJECT)
        return check_freshness(self.service.access, self.store.descriptor(),
            self.store.load_assessment(), checkpoint=lambda: self.service._require(rbac.VIEW_PROJECT))

    def _read(self):
        fresh = self._freshness()
        assessment = self.service.assessment(freshness=fresh)
        if assessment is None:
            raise ProjectError('Analyze the project before reviewing findings')
        prepared = prepare_projection(descriptor_to_dict(self.store.descriptor()), assessment, fresh,
                                      store_scope=str(self.store.session.path))
        return assessment, prepared

    def queue(self, *, expected_review=None, **query):
        assessment, prepared = self._read()
        if expected_review is not None and expected_review != assessment['review_revision']:
            raise RevisionConflict('Review queue changed; reload the first page')
        query.setdefault('sort', 'priority')
        page = inventory_page(prepared, 'findings', **query)
        findings = {f['id']: f for f in assessment['blueprint']['findings']}
        for row in page['rows']:
            row['finding_revision'] = findings[row['id']]['revision']
            row['review_label'] = STATES.get(row['review_state'], 'Needs Review')
        return {**page, 'project_id': assessment['project_id']}

    def detail(self, finding_id, *, expected_revision=None, expected_review=None,
               history_offset=0, history_limit=50):
        if (type(history_offset) is not int or history_offset < 0 or
                type(history_limit) is not int or not 1 <= history_limit <= 200):
            raise ProjectError('Use a nonnegative history offset and limit between 1 and 200')
        assessment, prepared = self._read()
        if expected_review is not None and expected_review != assessment['review_revision']:
            raise RevisionConflict('Review evidence changed; reload current evidence')
        finding = _finding(assessment, finding_id)
        result = inventory_detail(prepared, 'findings', finding_id, expected_revision=expected_revision)
        history = finding.get('review_history', [])
        events = [{'action': e['action'], 'recommendation': e['recommendation'],
                   'rationale': e['comment'], 'timestamp': e['decided_at'],
                   'reviewer': 'Authenticated reviewer' if self.service.access.org_id else e['reviewer'],
                   'binding': e.get('finding_snapshot', {}).get('project_binding'),
                   'human_context': e.get('finding_snapshot', {}).get('human_context', {}),
                   'applicable': e['revision'] == finding['revision'] and assessment['status'] == 'Current'}
                  for e in history[history_offset:history_offset + history_limit]]
        db = self.store.session.db
        db.execute('BEGIN')
        try:
            revision = db.execute('SELECT analysis_revision,review_revision FROM modernization_project WHERE id=1').fetchone()
            if (revision[0], revision[1]) != (assessment['analysis_revision'], assessment['review_revision']):
                raise RevisionConflict('Review history changed; reload current evidence')
            annotations = db.execute(
                'SELECT kind,note,revision,created_at,reviewer,binding_json FROM blueprint_annotation WHERE entity=? ORDER BY id DESC LIMIT ? OFFSET ?',
                (finding['entity'], history_limit, history_offset)).fetchall()
            annotation_count = db.execute('SELECT count(*) FROM blueprint_annotation WHERE entity=?', (finding['entity'],)).fetchone()[0]
        finally:
            db.rollback()
        annotations = [{'kind': a['kind'], 'note': a['note'], 'timestamp': a['created_at'],
                        'reviewer': 'Authenticated reviewer' if self.service.access.org_id else a['reviewer'],
                        'binding': json.loads(a['binding_json']),
                        'applicable': a['revision'] == finding['revision'] and assessment['status'] == 'Current'}
                       for a in annotations]
        nodes = {n['id']: n for n in assessment['blueprint']['entities']}
        evidence = []
        for identity in [finding['entity'], *finding.get('dependencies', [])][:20]:
            node = nodes.get(identity, {})
            attributes = node.get('attributes', {})
            source = attributes.get('source_text', '')
            if isinstance(source, str) and source:
                evidence.append({'kind': 'Observed Fact', 'name': str(node.get('name', ''))[:500],
                                 'excerpt': safe_excerpt(source),
                                 'truncated': len(source.splitlines()) > 80 or len(source) > 8000})
        statements = [{'kind': 'Observed Fact' if s.get('level') == 'FACT' else 'Engine Inference',
                       'text': str(s.get('text', ''))[:2000]}
                      for s in finding.get('statements', [])[:50]]
        return {**result, 'binding': _binding(assessment, finding),
                'engine_recommendation': finding['recommendation'],
                'human_decision': copy.deepcopy(finding.get('human_decision')),
                'target_suggestion': str(finding.get('suggested_target', ''))[:2000],
                'evidence': evidence, 'statements': statements, 'history': events,
                'history_total': len(history), 'history_offset': history_offset, 'history_limit': history_limit,
                'annotations': annotations, 'annotations_total': annotation_count,
                'unresolved_questions': [str(q)[:1000] for q in finding.get('unresolved_questions', [])[:30]],
                'code_approval': 'Not assessed', 'generation_authorization': 'Not assessed'}

    @contextmanager
    def _write(self, request):
        self.service._job_authority(rbac.RUN_CONVERSION)
        with project_worker_lock(self.service.access.root):
            fresh = self._freshness()
            if fresh['status'] != 'CURRENT':
                raise RevisionConflict('Source or assessment is not current; refresh analysis before reviewing')
            # Intake authorization validates the descriptor through a separate connection.
            # Reauthorize before BEGIN IMMEDIATE, never recursively acquire its writer lock.
            self.service._job_authority(rbac.RUN_CONVERSION)
            with self.store._write():
                assessment = self.store.load_assessment()
                if assessment is None:
                    raise ProjectError('Analyze the project before reviewing findings')
                assessment = copy.deepcopy(assessment)
                assessment['blueprint'] = self.store.session.blueprint()
                assessment['review_revision'] = self.store.session.db.execute(
                    'SELECT review_revision FROM modernization_project WHERE id=1').fetchone()[0]
                _fence(assessment, request)
                if fresh['analysis_revision'] != assessment['analysis_revision']:
                    raise RevisionConflict('Assessment changed during source verification')
                yield assessment
                verified = check_freshness(self.service.access, self.store.descriptor(), assessment,
                                           checkpoint=lambda: None, store=self.store)
                if verified['status'] != 'CURRENT':
                    raise RevisionConflict('Source changed while reviewing; no decision was committed')

    def _validate_decision(self, assessment, finding, request):
        action = request.get('action')
        if action not in {'APPROVE', 'MODIFY', 'REJECT', 'DEFER'}:
            raise ProjectError('Unknown review action')
        rationale = _text(request.get('rationale', ''), 'Rationale', required=action == 'MODIFY')
        recommendation = finding['recommendation']
        if action == 'APPROVE' and recommendation not in DECISIONS:
            raise ProjectError('Unsupported recommendation requires an explicit supported Change')
        if action == 'MODIFY':
            recommendation = request.get('recommendation')
            if recommendation not in DECISIONS or recommendation == finding['recommendation']:
                raise ProjectError('Choose a different supported direction or Accept the recommendation')
            node = next(n for n in assessment['blueprint']['entities'] if n['id'] == finding['entity'])
            if (node.get('attributes', {}).get('risk', {}).get('level') == 'CRITICAL'
                    and request.get('critical_confirmed') is not True):
                raise ProjectError('Confirm that you reviewed the current CRITICAL evidence')
        reason = request.get('reason_code', '')
        if reason and reason not in REASONS:
            raise ProjectError('Unknown human review reason')
        if action == 'REJECT' and not reason:
            raise ProjectError('Select why this finding needs review')
        return action, recommendation, rationale or {
            'APPROVE': 'Accepted engine recommendation.', 'REJECT': reason,
            'DEFER': 'Decision deferred.',
        }.get(action, '')

    def _append(self, assessment, finding, request):
        action, recommendation, rationale = self._validate_decision(assessment, finding, request)
        snapshot = {'project_binding': _provenance(assessment, finding),
                    'human_context': {'reason_code': request.get('reason_code', ''),
                    'owner': _text(request.get('owner', ''), 'Owner', limit=200),
                    'note': _text(request.get('note', ''), 'Note'),
                    'critical_evidence_confirmed': request.get('critical_confirmed') is True}}
        self.store.session.db.execute(
            'INSERT INTO blueprint_review (entity,revision,action,recommendation,target,comment,reviewer,'
            'coverage,coverage_evidence,finding_snapshot,decided_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (finding['entity'], finding['revision'], action, recommendation,
             finding.get('suggested_target', '') if action != 'MODIFY' else recommendation,
             rationale, self.service.access.actor, 'REQUIRES_REVIEW', '', canonical_json(snapshot),
             datetime.now(timezone.utc).isoformat()))

    def mutate(self, finding_id, request, *, annotation=False):
        with self._write(request) as assessment:
            finding = _finding(assessment, finding_id)
            _fence(assessment, request, finding)
            if annotation:
                if request.get('kind') not in ANNOTATIONS:
                    raise ProjectError('Unknown annotation kind')
                note = _text(request.get('note', ''), 'Annotation note')
                self.store.session.db.execute(
                    'INSERT INTO blueprint_annotation (entity,revision,kind,note,reviewer,created_at,binding_json) VALUES (?,?,?,?,?,?,?)',
                    (finding['entity'], finding['revision'], request['kind'], note, self.service.access.actor,
                     datetime.now(timezone.utc).isoformat(), canonical_json(_provenance(assessment, finding))))
            else:
                self._append(assessment, finding, request)
        return {**_binding(assessment), 'finding_id': finding_id, 'saved': True,
                'review_revision': assessment['review_revision'] + 1}

    def _preview(self, assessment, request):
        selected = request.get('findings')
        if not isinstance(selected, list) or not 1 <= len(selected) <= 200:
            raise ProjectError('Select between 1 and 200 findings')
        if request.get('action') not in {'APPROVE', 'DEFER', 'REJECT'}:
            raise ProjectError('Unsupported bulk action')
        nodes = {n['id']: n for n in assessment['blueprint']['entities']}
        eligible, excluded, seen = [], [], set()
        for item in selected:
            if not isinstance(item, dict) or set(item) != {'id', 'revision'}:
                raise ProjectError('Every selected finding needs its identity and revision')
            finding = _finding(assessment, item['id'])
            if item['id'] in seen:
                raise ProjectError('Duplicate finding selection')
            seen.add(item['id'])
            if item['revision'] != finding['revision']:
                raise RevisionConflict('Selected finding changed; refresh bulk preview')
            reasons = []
            if request['action'] == 'APPROVE':
                node = nodes.get(finding['entity'], {})
                if node.get('attributes', {}).get('risk', {}).get('level') != 'LOW':
                    reasons.append('RISK_NOT_LOW')
                if finding.get('execution_verdict') != 'AUTO':
                    reasons.append('NOT_MECHANICAL')
                if finding.get('review_state') != 'PENDING':
                    reasons.append('NOT_PENDING')
                if finding['recommendation'] not in {'PRESERVE', 'CONVERT', 'REPLACE_WITH_APEX_NATIVE'}:
                    reasons.append('UNSUPPORTED_BULK_DIRECTION')
                codes = {code for statement in finding.get('statements', [])
                         for code in re.findall(r'\[([A-Z][A-Z0-9_]+)\]', statement.get('text', ''))}
                allowed_builtins = set().union(*(MECHANICAL_BUILTINS.get(code, ()) for code in codes))
                dependencies_safe = all(nodes.get(identity, {}).get('type') in {'ALERT', 'BUILTIN'}
                                        and not nodes[identity].get('attributes', {}).get('missing')
                                        and (nodes[identity]['type'] != 'BUILTIN' or
                                             nodes[identity].get('name') in allowed_builtins)
                                        for identity in finding.get('dependencies', []))
                unsafe_edges = any(e.get('type') not in {'CONTAINS', 'INVOKES_BUILTIN', 'REFERENCES'}
                                   or any(nodes.get(e.get(endpoint), {}).get('module') not in
                                          {None, '', node.get('module')} for endpoint in ('source', 'target'))
                                   for e in assessment['blueprint'].get('edges', [])
                                   if finding['entity'] in {e.get('source'), e.get('target')})
                if (finding.get('unresolved_questions') or not dependencies_safe or unsafe_edges or
                        not codes or not codes <= MECHANICAL_SIGNALS or
                        not set(finding.get('classification', [])) <= {'UI_BEHAVIOR', 'PRESENTATION'}):
                    reasons.append('REQUIRES_INDIVIDUAL_EVIDENCE_REVIEW')
            if reasons:
                excluded.append({'id': item['id'], 'reasons': reasons})
            else:
                self._validate_decision(assessment, finding, request)
                eligible.append(item['id'])
        content = {'binding': _binding(assessment), 'policy': POLICY_VERSION,
                   'action': request['action'], 'findings': sorted(selected, key=lambda x: x['id']),
                   'eligible': sorted(eligible), 'excluded': sorted(excluded, key=lambda x: x['id'])}
        return {**_binding(assessment), 'selected': len(selected), 'eligible': eligible,
                'excluded': excluded, 'policy': POLICY_VERSION,
                'preview_token': hashlib.sha256(canonical_json(content).encode()).hexdigest()}

    def bulk(self, request, *, apply):
        with self._write(request) as assessment:
            preview = self._preview(assessment, request)
            if apply:
                if request.get('preview_token') != preview['preview_token']:
                    raise RevisionConflict('Bulk preview changed; refresh before committing')
                for finding_id in preview['eligible']:
                    self._append(assessment, _finding(assessment, finding_id), request)
        return {**preview, 'applied': len(preview['eligible']) if apply else 0,
                'review_revision': assessment['review_revision'] + (len(preview['eligible']) if apply else 0)}
