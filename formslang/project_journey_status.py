"""Read-only journey status: where each Form stands in Understand, Decide, Build and Validate.

The rules classify facts the product already saves or computes. They add no table,
no persistence authority and no domain rule. Design:
docs/design/formslang-3.0/journey-shell-design.md §2.
"""

from collections import Counter

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
