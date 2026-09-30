"""Read-only journey status: where each Form stands in Understand, Decide, Build and Validate.

The rules classify facts the product already saves or computes. They add no table,
no persistence authority and no domain rule. Design:
docs/design/formslang-3.0/journey-shell-design.md §2.
"""

import json
from collections import Counter

from .project_generation_policy import dependency_edges, unresolved_findings
from .project_model import ProjectBusy, ProjectError, RevisionConflict
from .project_review import _binding

SCHEMA = 'formslang-journey/1'
STEPS = ('UNDERSTAND', 'DECIDE', 'BUILD', 'VALIDATE')

# The step whose action resolves each generation blocker; LIMIT is outside supported scope.
BLOCKER_CLASS = {
    **dict.fromkeys(('SOURCE_NOT_CURRENT', 'MODULE_NOT_OBSERVED', 'UNRESOLVED_DEPENDENCY'), 'UNDERSTAND'),
    **dict.fromkeys((
        'UNRESOLVED_REVIEW', 'UNSUPPORTED_TARGET_DECISION', 'UNRESOLVED_ARCHITECTURE',
        'PREREQUISITE_NOT_CONFIRMED', 'UNSUPPORTED_TARGET', 'TARGET_STRATEGY_UNSELECTED',
        'TARGET_NOT_GENERATING', 'TARGET_KEYS_CHANGED', 'ROW_KEY_NOT_CONFIRMED',
        'MODULE_NOT_PREPARED', 'CODE_NOT_APPROVED', 'CODE_NEEDS_REVALIDATION',
        'UNSUPPORTED_TARGET_CODE'), 'DECIDE'),
    **dict.fromkeys((
        'UNSUPPORTED_TABLE_IDENTITY', 'UNSUPPORTED_COLUMN_IDENTITY', 'UNSUPPORTED_LAYOUT',
        'UNSUPPORTED_EXECUTION_MAPPING', 'UNSUPPORTED_ITEM_CONTROL', 'UNSUPPORTED_DATA_CONTROL',
        'UNSUPPORTED_DATABASE_MAPPING', 'TARGET_NAME_COLLISION'), 'LIMIT'),
}

FRESHNESS_STATES = {'CURRENT': 'DONE', 'INCOMPLETE': 'ACTION', 'UNVERIFIED': 'ACTION',
                    'STALE': 'STALE', 'MISSING_SOURCE': 'BLOCKED'}

# Validation status -> (state, reason code, step that resolves it).
VALIDATION_STATES = {'Validated': ('DONE', None, None),
                     'Not Validated': ('ACTION', 'NOT_VALIDATED', 'VALIDATE'),
                     'Validation Failed': ('ACTION', 'VALIDATION_FAILED', 'DECIDE')}

OPEN_STATES = frozenset({'ACTION', 'BLOCKED', 'STALE'})


class FormNotFound(LookupError):
    """No Form in the project matches the requested entity id or name."""


def classify_blocker(code):
    """The step that resolves a generation blocker: UNDERSTAND, DECIDE, LIMIT or UNCLASSIFIED."""
    return BLOCKER_CLASS.get(code, 'UNCLASSIFIED')


def _reason(code, resolved_in, **detail):
    return {'code': code, 'resolved_in': resolved_in, **detail}


def _step(step, state, reasons=()):
    return {'step': step, 'state': state, 'reasons': list(reasons)}


def understand_step(freshness, *, has_sources, blockers=()):
    """Project freshness decides the step; a Form's own Understand blockers keep it open."""
    if not has_sources:
        return _step('UNDERSTAND', 'ACTION', [_reason('NO_SOURCES', 'UNDERSTAND')])
    status = freshness.get('status')
    state = FRESHNESS_STATES.get(status)
    if state is None:
        return _step('UNDERSTAND', 'ACTION', [_reason('UNCLASSIFIED', 'UNDERSTAND', value=str(status))])
    if state != 'DONE':
        codes = list(freshness.get('reasons') or []) or [status]
        return _step('UNDERSTAND', state, [_reason(code, 'UNDERSTAND') for code in codes])
    own = [_reason(b['code'], 'UNDERSTAND', id=b['id'])
           for b in blockers if classify_blocker(b['code']) == 'UNDERSTAND']
    return _step('UNDERSTAND', 'ACTION' if own else 'DONE', own)


def decide_step(freshness, *, has_sources, unresolved, blockers=()):
    """Reviews can be recorded only on CURRENT evidence, so only that makes Decide wait."""
    if not has_sources or freshness.get('status') != 'CURRENT':
        return _step('DECIDE', 'WAITING', [_reason('NEEDS_CURRENT_ANALYSIS', 'UNDERSTAND')])
    reasons = [_reason('UNRESOLVED_REVIEW', 'DECIDE', count=unresolved)] if unresolved else []
    reasons += [_reason(b['code'], 'DECIDE', id=b['id']) for b in blockers
                if classify_blocker(b['code']) == 'DECIDE' and b['code'] != 'UNRESOLVED_REVIEW']
    return _step('DECIDE', 'ACTION' if reasons else 'DONE', reasons)


def _blocker_reason(kind, blocker):
    if kind == 'UNCLASSIFIED':
        return _reason('UNCLASSIFIED', None, id=blocker['id'], value=blocker['code'])
    return _reason(blocker['code'], None if kind == 'LIMIT' else kind, id=blocker['id'])


def build_step(*, has_scope, blockers=(), detail_error=None, artifact=None):
    """The first matching rule wins (journey-shell-design.md §2, Build)."""
    if not has_scope:
        return _step('BUILD', 'BLOCKED', [_reason('NO_GENERATION_SCOPE', 'UNDERSTAND')])
    if detail_error is not None:
        return _step('BUILD', 'BLOCKED', [_reason('GENERATION_DETAIL_UNAVAILABLE', 'BUILD', message=detail_error)])
    classified = [(classify_blocker(b['code']), b) for b in blockers]
    reasons = [_blocker_reason(kind, b) for kind, b in classified]
    kinds = {kind for kind, _ in classified}
    if 'LIMIT' in kinds:
        return _step('BUILD', 'BLOCKED', reasons)
    if kinds & {'UNDERSTAND', 'DECIDE'}:
        return _step('BUILD', 'WAITING', reasons)
    if kinds:
        return _step('BUILD', 'ACTION', reasons)
    if artifact is None:
        return _step('BUILD', 'ACTION', [_reason('READY_TO_GENERATE', 'BUILD')])
    if artifact['reason'] is None:
        return _step('BUILD', 'DONE')
    return _step('BUILD', 'STALE', [_reason(artifact['reason'], 'BUILD', artifact_id=artifact['artifact_id'])])


def validate_step(build, *, validation=None):
    """Validation applies only to a current artifact."""
    if build['state'] != 'DONE':
        return _step('VALIDATE', 'WAITING', [_reason('NEEDS_CURRENT_ARTIFACT', 'BUILD')])
    if validation is None:
        return _step('VALIDATE', 'ACTION', [_reason('NOT_RUN', 'VALIDATE')])
    status = validation.get('status')
    rule = VALIDATION_STATES.get(status)
    if rule is None:
        return _step('VALIDATE', 'ACTION', [_reason('UNCLASSIFIED', 'VALIDATE', value=str(status))])
    state, code, resolved_in = rule
    if state == 'DONE':
        return _step('VALIDATE', 'DONE')
    return _step('VALIDATE', state, [_reason(code, resolved_in, message=str(validation.get('message', '')))])


def project_steps(forms, understand):
    """Form counts per step; the project's own Understand comes from freshness and sources."""
    steps = []
    for index, name in enumerate(STEPS):
        counts = Counter(form['steps'][index]['state'] for form in forms)
        step = {'step': name, 'counts': dict(sorted(counts.items()))}
        if name == 'UNDERSTAND':
            step['project'] = understand
        steps.append(step)
    return steps


def focus_step(steps):
    """The first step, in order, with work to do; None when every Form is done."""
    for step in steps:
        if step['counts'].keys() & OPEN_STATES:
            return step['step']
        if step['step'] == 'UNDERSTAND' and step['project']['state'] != 'DONE':
            return 'UNDERSTAND'
    return None


def _select_form(entities, form):
    by_id = [e for e in entities if e['id'] == form]
    if by_id:
        return by_id
    by_name = [e for e in entities if str(e.get('name', '')).casefold() == str(form).casefold()]
    if len(by_name) > 1:
        raise ProjectError('Form name is ambiguous; use its entity id')
    if not by_name:
        raise FormNotFound('Form not found')
    return by_name


def build_journey(assessment, freshness, *, has_sources, scopes=None, module_facts=None, form=None):
    """Compose the journey from saved facts; module_facts(source_id) supplies Build and Validate inputs."""
    scopes = scopes or {}
    blueprint = assessment['blueprint'] if assessment else {'entities': [], 'edges': [], 'findings': []}
    entities = sorted((e for e in blueprint['entities'] if e.get('type') == 'FORM'),
                      key=lambda e: (str(e.get('name', '')).casefold(), e['id']))
    if form is not None:
        entities = _select_form(entities, form)
    outgoing = dependency_edges(blueprint)
    forms = []
    for entity in entities:
        module = entity.get('module')
        source_id = scopes.get(module)
        facts = module_facts(source_id) if (source_id and module_facts) else {}
        blockers = facts.get('blockers', [])
        unresolved = len(unresolved_findings(blueprint, module, outgoing=outgoing)) if module else 0
        build = build_step(has_scope=source_id is not None, blockers=blockers,
                           detail_error=facts.get('detail_error'), artifact=facts.get('artifact'))
        forms.append({'entity_id': entity['id'], 'name': entity.get('name'), 'module': module,
                      'source_id': source_id, 'steps': [
                          understand_step(freshness, has_sources=has_sources, blockers=blockers),
                          decide_step(freshness, has_sources=has_sources, unresolved=unresolved, blockers=blockers),
                          build,
                          validate_step(build, validation=facts.get('validation'))]})
    steps = project_steps(forms, understand_step(freshness, has_sources=has_sources))
    return {'schema': SCHEMA, 'freshness': freshness, 'focus': focus_step(steps),
            'steps': steps, 'forms': forms}


def _latest_module_artifacts(db):
    """The newest selected-module artifact per source_id; generic packages have no Form."""
    latest = {}
    for (metadata,) in db.execute('SELECT metadata_json FROM project_artifact ORDER BY created_at, artifact_id'):
        artifact = json.loads(metadata)
        if artifact.get('artifact_kind') or not all(
                key in artifact for key in ('source_id', 'target_revision', 'code_revision')):
            continue
        latest[artifact['source_id']] = artifact
    return latest


def journey_status(service, *, freshness, form=None):
    """The project's journey, read without writing; the caller supplies one freshness value."""
    descriptor = service.open()
    has_sources = bool(descriptor.source_roots)
    assessment = service.assessment(freshness=freshness)
    if assessment is None:
        payload = build_journey(None, freshness, has_sources=has_sources, form=form)
        return {**payload, 'project_id': descriptor.id, 'binding': None}
    generation = service._generation_service()
    db = service._store.session.db
    scopes = {entry['module']: entry['source_id'] for entry in generation._sources(assessment)}
    artifacts = _latest_module_artifacts(db)
    latest_plans = {(row[0], row[1]): row[2] for row in db.execute(
        'SELECT source_id,analysis_revision,revision FROM project_target_plan ORDER BY id')}
    sessions = {(s['source_id'], s['revision']): s for s in service._store.module_sessions()}

    def module_facts(source_id):
        try:
            facts = {'blockers': generation._detail(assessment, freshness, source_id, read_only=True)['blockers']}
        except ProjectBusy:
            raise
        except ProjectError as exc:
            return {'detail_error': str(exc)}
        except OSError:
            # OSError messages carry absolute server paths; never surface them.
            return {'detail_error': 'Prepared generation files are unavailable; restore them before generation.'}
        artifact = artifacts.get(source_id)
        if artifact is None:
            return facts
        reason = generation.artifact_currency(assessment, artifact, freshness_status=freshness.get('status'),
                                              latest_plans=latest_plans, sessions=sessions)
        if reason is None:
            try:
                generation._artifact_bytes(artifact['artifact_id'])
            except (OSError, ProjectError):
                reason = 'ARTIFACT_INTEGRITY'
        facts['artifact'] = {'artifact_id': artifact['artifact_id'], 'reason': reason}
        if reason is None:
            facts['validation'] = generation.latest_validation(artifact['artifact_id'])
        return facts

    payload = build_journey(assessment, freshness, has_sources=has_sources, scopes=scopes,
                            module_facts=module_facts, form=form)
    row = db.execute('SELECT analysis_revision,review_revision FROM modernization_project WHERE id=1').fetchone()
    if tuple(row) != (assessment['analysis_revision'], assessment['review_revision']):
        raise RevisionConflict('The project changed while its journey was read; reload.')
    return {**payload, 'project_id': descriptor.id, 'binding': _binding(assessment)}
