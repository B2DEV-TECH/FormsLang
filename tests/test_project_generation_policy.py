"""Generation authorization is not implied by review or AUTO classification."""

import copy

import pytest


def fixture():
    return {
        'status': 'Current', 'target': {'platform': 'Oracle APEX', 'version': '26.1', 'representation': 'APEXlang'},
        'blueprint': {'entities': [
            {'id': 'module', 'module': 'forms/entry.xml', 'type': 'FORM', 'attributes': {}},
            {'id': 'trigger', 'module': 'forms/entry.xml', 'type': 'TRIGGER',
             'attributes': {'risk': {'level': 'LOW'}}}], 'edges': [], 'findings': [
            {'id': 'finding', 'entity': 'trigger', 'module': 'forms/entry.xml', 'revision': 'r',
             'recommendation': 'CONVERT', 'execution_verdict': 'AUTO', 'review_state': 'PENDING',
             'dependencies': [], 'unresolved_questions': [], 'human_decision': None}]}}, {
        'security_confirmed': True, 'database_confirmed': True,
        'rationale': 'Reviewed authentication and dependencies for the disposable target.'}


def policy(assessment, plan, **options):
    from formslang.project_generation_policy import module_blockers
    return module_blockers(assessment, 'forms/entry.xml', plan,
                           freshness=options.get('freshness', 'CURRENT'),
                           code_blockers=options.get('code_blockers', []))


def resolve(assessment, recommendation='CONVERT'):
    finding = assessment['blueprint']['findings'][0]
    finding['review_state'] = 'APPROVE'
    finding['human_decision'] = {'recommendation': recommendation}


def test_auto_is_not_generation_authorization():
    assessment, plan = fixture()
    assert 'UNRESOLVED_REVIEW' in {b['code'] for b in policy(assessment, plan)}
    resolve(assessment)
    assert policy(assessment, plan) == []


@pytest.mark.parametrize('status', ['STALE', 'MISSING_SOURCE', 'INCOMPLETE', 'UNVERIFIED'])
def test_noncurrent_source_blocks_even_accepted_critical(status):
    assessment, plan = fixture()
    resolve(assessment)
    assessment['blueprint']['entities'][1]['attributes']['risk']['level'] = 'CRITICAL'
    assert 'SOURCE_NOT_CURRENT' in {b['code'] for b in policy(assessment, plan, freshness=status)}


def test_architectural_acceptance_never_approves_code():
    assessment, plan = fixture()
    resolve(assessment)
    blockers = [{'code': 'CODE_NOT_APPROVED', 'id': 'task'}]
    assert blockers[0] in policy(assessment, plan, code_blockers=blockers)


@pytest.mark.parametrize('recommendation', ['MANUAL_REVIEW', 'UNKNOWN', 'FUTURE_DIRECTION'])
def test_unresolved_target_is_not_made_safe_by_human_acceptance(recommendation):
    assessment, plan = fixture()
    resolve(assessment, recommendation)
    assert 'UNSUPPORTED_TARGET_DECISION' in {b['code'] for b in policy(assessment, plan)}


def test_prerequisite_confirmations_require_explicit_boolean():
    assessment, plan = fixture()
    resolve(assessment)
    for field in ('security_confirmed', 'database_confirmed'):
        changed = {**plan, field: 'true'}
        assert 'PREREQUISITE_NOT_CONFIRMED' in {b['code'] for b in policy(assessment, changed)}


def test_unsafe_related_database_finding_blocks_module():
    assessment, plan = fixture()
    resolve(assessment)
    assessment['blueprint']['entities'].append({'id': 'db', 'module': 'database/pkg.sql', 'type': 'PACKAGE_BODY'})
    assessment['blueprint']['edges'].append({'source': 'trigger', 'target': 'db', 'type': 'CALLS'})
    unsafe = copy.deepcopy(assessment['blueprint']['findings'][0])
    unsafe.update(id='db-finding', entity='db', module='database/pkg.sql', review_state='PENDING')
    assessment['blueprint']['findings'].append(unsafe)
    assert any(b['id'] == 'db-finding' for b in policy(assessment, plan))


def test_unrelated_blocked_module_does_not_prevent_partial_scope():
    assessment, plan = fixture()
    resolve(assessment)
    assessment['blueprint']['entities'].append({'id': 'other', 'module': 'forms/other.xml', 'type': 'TRIGGER'})
    unsafe = copy.deepcopy(assessment['blueprint']['findings'][0])
    unsafe.update(id='other-finding', entity='other', module='forms/other.xml', review_state='PENDING')
    assessment['blueprint']['findings'].append(unsafe)
    assert policy(assessment, plan) == []


def test_generic_structure_question_requires_explicit_mapping_confirmation():
    assessment, plan = fixture()
    resolve(assessment)
    finding = assessment['blueprint']['findings'][0]
    finding['entity'] = 'module'
    finding['unresolved_questions'] = ['Confirm target behavior and ownership.']
    assert 'UNRESOLVED_ARCHITECTURE' in {b['code'] for b in policy(assessment, plan)}
    plan['mapping_confirmed'] = True
    assert policy(assessment, plan) == []
    finding['unresolved_questions'].append('Approval identity propagation needs an explicit design.')
    assert 'UNRESOLVED_ARCHITECTURE' in {b['code'] for b in policy(assessment, plan)}


def test_resolved_reference_retains_database_safety_findings():
    assessment, plan = fixture()
    resolve(assessment)
    assessment['blueprint']['entities'][1]['resolved_target'] = 'database-target'
    assessment['blueprint']['entities'].append({'id': 'database-target', 'module': 'database/api.sql', 'type': 'TABLE'})
    assessment['blueprint']['findings'].append({'id': 'unsafe-db', 'entity': 'database-target', 'review_state': 'PENDING'})
    assert any(b['id'] == 'unsafe-db' for b in policy(assessment, plan))
