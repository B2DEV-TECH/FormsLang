"""WP-39a journey status: read-only, composed from facts the product already saves."""
# ruff: noqa: F811 -- imported pytest fixtures are injected by name

import hashlib
import re
from pathlib import Path

import pytest

from formslang import apeximport, rbac
from formslang import project_journey_status as journey
from formslang.project_generation_policy import (
    dependency_edges,
    related_scope,
    unresolved_findings,
)
from formslang.project_intake import ProjectIntake
from formslang.project_review import ProjectReviewService
from formslang.project_service import ProjectService
from tests.test_project_generation import generation_project, prepared  # noqa: F401


@pytest.fixture
def demo(tmp_path, monkeypatch):
    monkeypatch.setenv('FORMSLANG_AUTH', '0')
    intake = ProjectIntake(tmp_path / 'data', tmp_path / 'config')
    project_id = intake.create_demo()['project']['id']
    authorize = lambda: intake.access(project_id, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    assert service.analyze(expected_revision=None, expected_configuration=0)['status'] == 'COMPLETED'
    yield service
    service.close()


def test_related_scope_is_unchanged_by_precomputed_edges(demo):
    blueprint = demo.assessment()['blueprint']
    edges = dependency_edges(blueprint)
    forms = [e for e in blueprint['entities'] if e['type'] == 'FORM']
    assert forms
    for form in forms:
        assert related_scope(blueprint, form['module'], outgoing=edges) == related_scope(blueprint, form['module'])


def test_unresolved_findings_match_generation_review_blockers(demo):
    assessment = demo.assessment()
    checked = 0
    for module in demo.generation_overview()['modules']:
        detail = demo.generation_module(module['source_id'])
        blocked = sorted(b['id'] for b in detail['blockers'] if b['code'] == 'UNRESOLVED_REVIEW')
        unresolved = sorted(f['id'] for f in unresolved_findings(assessment['blueprint'], module['module']))
        assert unresolved == blocked
        checked += len(blocked)
    assert checked > 0


def _tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in Path(root).rglob('*') if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _currency_inputs(service):
    db = service._store.session.db
    plans = {(row[0], row[1]): row[2] for row in db.execute(
        'SELECT source_id,analysis_revision,revision FROM project_target_plan ORDER BY id')}
    sessions = {(s['source_id'], s['revision']): s for s in service._store.module_sessions()}
    return plans, sessions


def test_read_only_generation_detail_writes_nothing(generation_project):
    service = generation_project
    detail = prepared(service)
    generation = service._generation_service()
    fresh = ProjectReviewService(service)._freshness()
    assessment = service.assessment(freshness=fresh)
    before = _tree_digest(service.access.root)
    again = generation._detail(assessment, fresh, detail['source_id'], read_only=True)
    assert again['blockers'] == detail['blockers'] == []
    assert _tree_digest(service.access.root) == before


def test_artifact_currency_is_the_report_rule(generation_project):
    service = generation_project
    detail = prepared(service)
    generated = service.generate({**detail['binding'], 'scopes': [detail]})
    generation = service._generation_service()
    fresh = ProjectReviewService(service)._freshness()
    assessment = service.assessment(freshness=fresh)
    artifact = next(a for a in service.generation_overview()['artifacts']
                    if a['artifact_id'] == generated['artifact_id'])
    plans, sessions = _currency_inputs(service)
    current = {'freshness_status': fresh['status'], 'latest_plans': plans, 'sessions': sessions}
    assert generation.artifact_currency(assessment, artifact, **current) is None
    assert generation.artifact_currency(
        assessment, artifact, **{**current, 'freshness_status': 'STALE'}) == 'ARTIFACT_REVISION_STALE'
    assert generation.artifact_currency(
        assessment, artifact, **{**current, 'latest_plans': {}}) == 'ARTIFACT_REVISION_STALE'
    assert generation.artifact_currency(
        assessment, artifact, **{**current, 'sessions': {}}) == 'ARTIFACT_CODE_UNAVAILABLE'


def test_latest_validation_reads_the_newest_record(generation_project, monkeypatch):
    service = generation_project
    detail = prepared(service)
    generated = service.generate({**detail['binding'], 'scopes': [detail]})
    generation = service._generation_service()
    assert generation.latest_validation(generated['artifact_id']) is None
    monkeypatch.setattr(apeximport, 'sqlcl_version', lambda: '')
    service.generation_validate(generated['artifact_id'])
    assert generation.latest_validation(generated['artifact_id'])['status'] == 'Not Validated'


REPO = Path(__file__).resolve().parents[1]
BLOCKER_LITERAL = re.compile(
    r"['\"](SOURCE_NOT_CURRENT|MODULE_[A-Z_]+|UNRESOLVED_[A-Z_]+|UNSUPPORTED_[A-Z_]+"
    r"|PREREQUISITE_[A-Z_]+|TARGET_[A-Z_]+|CODE_[A-Z_]+|ROW_KEY_[A-Z_]+)['\"]")
CURRENT = {'status': 'CURRENT', 'reasons': []}
DONE_BUILD = {'step': 'BUILD', 'state': 'DONE', 'reasons': []}


def _blocker(code, identity='x'):
    return {'code': code, 'id': identity, 'message': 'm'}


def test_every_generation_blocker_code_has_exactly_one_class():
    found = set()
    for name in ('project_generation_policy.py', 'project_generation.py'):
        found |= set(BLOCKER_LITERAL.findall((REPO / 'formslang' / name).read_text(encoding='utf-8')))
    assert len(found) == 24
    assert found == set(journey.BLOCKER_CLASS)
    classes = list(journey.BLOCKER_CLASS.values())
    assert (classes.count('UNDERSTAND'), classes.count('DECIDE'), classes.count('LIMIT')) == (3, 13, 8)
    assert journey.classify_blocker('NEW_RULE') == 'UNCLASSIFIED'


def test_understand_follows_project_freshness():
    assert journey.understand_step(CURRENT, has_sources=False) == {
        'step': 'UNDERSTAND', 'state': 'ACTION', 'reasons': [{'code': 'NO_SOURCES', 'resolved_in': 'UNDERSTAND'}]}
    cases = {'CURRENT': 'DONE', 'INCOMPLETE': 'ACTION', 'UNVERIFIED': 'ACTION',
             'STALE': 'STALE', 'MISSING_SOURCE': 'BLOCKED'}
    for status, state in cases.items():
        assert journey.understand_step({'status': status, 'reasons': []}, has_sources=True)['state'] == state
    stale = journey.understand_step({'status': 'STALE', 'reasons': ['SOURCE_CHANGED']}, has_sources=True)
    assert stale['reasons'] == [{'code': 'SOURCE_CHANGED', 'resolved_in': 'UNDERSTAND'}]
    bare = journey.understand_step({'status': 'INCOMPLETE', 'reasons': []}, has_sources=True)
    assert bare['reasons'] == [{'code': 'INCOMPLETE', 'resolved_in': 'UNDERSTAND'}]
    assert journey.understand_step({'status': 'LATER', 'reasons': []}, has_sources=True) == {
        'step': 'UNDERSTAND', 'state': 'ACTION',
        'reasons': [{'code': 'UNCLASSIFIED', 'resolved_in': 'UNDERSTAND', 'value': 'LATER'}]}


def test_understand_keeps_a_form_open_for_its_own_blockers():
    step = journey.understand_step(CURRENT, has_sources=True, blockers=[
        _blocker('UNRESOLVED_DEPENDENCY', 'package:x'), _blocker('CODE_NOT_APPROVED')])
    assert step == {'step': 'UNDERSTAND', 'state': 'ACTION', 'reasons': [
        {'code': 'UNRESOLVED_DEPENDENCY', 'resolved_in': 'UNDERSTAND', 'id': 'package:x'}]}


def test_decide_waits_only_for_current_evidence():
    stale = journey.decide_step({'status': 'STALE', 'reasons': []}, has_sources=True, unresolved=3)
    assert stale == {'step': 'DECIDE', 'state': 'WAITING', 'reasons': [
        {'code': 'NEEDS_CURRENT_ANALYSIS', 'resolved_in': 'UNDERSTAND'}]}
    assert journey.decide_step(CURRENT, has_sources=False, unresolved=0)['state'] == 'WAITING'
    dependency = journey.decide_step(CURRENT, has_sources=True, unresolved=0,
                                     blockers=[_blocker('UNRESOLVED_DEPENDENCY')])
    assert dependency == {'step': 'DECIDE', 'state': 'DONE', 'reasons': []}
    work = journey.decide_step(CURRENT, has_sources=True, unresolved=2, blockers=[
        _blocker('UNRESOLVED_REVIEW', 'f1'), _blocker('MODULE_NOT_PREPARED', 'sid')])
    assert work == {'step': 'DECIDE', 'state': 'ACTION', 'reasons': [
        {'code': 'UNRESOLVED_REVIEW', 'resolved_in': 'DECIDE', 'count': 2},
        {'code': 'MODULE_NOT_PREPARED', 'resolved_in': 'DECIDE', 'id': 'sid'}]}


def test_build_rules_apply_in_order():
    assert journey.build_step(has_scope=False) == {'step': 'BUILD', 'state': 'BLOCKED', 'reasons': [
        {'code': 'NO_GENERATION_SCOPE', 'resolved_in': 'UNDERSTAND'}]}
    assert journey.build_step(has_scope=True, detail_error='Prepared code session is unavailable.') == {
        'step': 'BUILD', 'state': 'BLOCKED', 'reasons': [
            {'code': 'GENERATION_DETAIL_UNAVAILABLE', 'resolved_in': 'BUILD',
             'message': 'Prepared code session is unavailable.'}]}
    limit = journey.build_step(has_scope=True, blockers=[
        _blocker('CODE_NOT_APPROVED', 't'), _blocker('UNSUPPORTED_LAYOUT', 's')])
    assert limit == {'step': 'BUILD', 'state': 'BLOCKED', 'reasons': [
        {'code': 'CODE_NOT_APPROVED', 'resolved_in': 'DECIDE', 'id': 't'},
        {'code': 'UNSUPPORTED_LAYOUT', 'resolved_in': None, 'id': 's'}]}
    waiting = journey.build_step(has_scope=True, blockers=[
        _blocker('SOURCE_NOT_CURRENT'), _blocker('UNSUPPORTED_TARGET_DECISION', 'f')])
    assert waiting['state'] == 'WAITING'
    assert journey.build_step(has_scope=True, blockers=[_blocker('NEW_RULE', 'n')]) == {
        'step': 'BUILD', 'state': 'ACTION', 'reasons': [
            {'code': 'UNCLASSIFIED', 'resolved_in': None, 'id': 'n', 'value': 'NEW_RULE'}]}
    assert journey.build_step(has_scope=True) == {'step': 'BUILD', 'state': 'ACTION', 'reasons': [
        {'code': 'READY_TO_GENERATE', 'resolved_in': 'BUILD'}]}
    assert journey.build_step(has_scope=True, artifact={'artifact_id': 'a1', 'reason': None}) == DONE_BUILD
    assert journey.build_step(has_scope=True, artifact={'artifact_id': 'a1', 'reason': 'ARTIFACT_CODE_STALE'}) == {
        'step': 'BUILD', 'state': 'STALE', 'reasons': [
            {'code': 'ARTIFACT_CODE_STALE', 'resolved_in': 'BUILD', 'artifact_id': 'a1'}]}


def test_validate_rules():
    stale_build = {'step': 'BUILD', 'state': 'STALE', 'reasons': []}
    assert journey.validate_step(stale_build) == {'step': 'VALIDATE', 'state': 'WAITING', 'reasons': [
        {'code': 'NEEDS_CURRENT_ARTIFACT', 'resolved_in': 'BUILD'}]}
    assert journey.validate_step(DONE_BUILD)['reasons'] == [{'code': 'NOT_RUN', 'resolved_in': 'VALIDATE'}]
    assert journey.validate_step(DONE_BUILD, validation={'status': 'Validated'}) == {
        'step': 'VALIDATE', 'state': 'DONE', 'reasons': []}
    assert journey.validate_step(DONE_BUILD, validation={
        'status': 'Not Validated', 'message': 'SQLcl unavailable'})['reasons'] == [
        {'code': 'NOT_VALIDATED', 'resolved_in': 'VALIDATE', 'message': 'SQLcl unavailable'}]
    assert journey.validate_step(DONE_BUILD, validation={
        'status': 'Validation Failed', 'message': 'bad region'})['reasons'] == [
        {'code': 'VALIDATION_FAILED', 'resolved_in': 'DECIDE', 'message': 'bad region'}]
    assert journey.validate_step(DONE_BUILD, validation={'status': 'Package Verified'})['reasons'] == [
        {'code': 'UNCLASSIFIED', 'resolved_in': 'VALIDATE', 'value': 'Package Verified'}]


def test_project_focus_is_the_first_step_with_work():
    def form(*states):
        return {'steps': [{'step': s, 'state': st, 'reasons': []} for s, st in zip(journey.STEPS, states)]}

    done = {'step': 'UNDERSTAND', 'state': 'DONE', 'reasons': []}
    steps = journey.project_steps([form('DONE', 'ACTION', 'WAITING', 'WAITING'),
                                   form('DONE', 'DONE', 'BLOCKED', 'WAITING')], done)
    assert [s['counts'] for s in steps] == [{'DONE': 2}, {'ACTION': 1, 'DONE': 1},
                                           {'BLOCKED': 1, 'WAITING': 1}, {'WAITING': 2}]
    assert steps[0]['project'] == done
    assert journey.focus_step(steps) == 'DECIDE'
    assert journey.focus_step(journey.project_steps([form('DONE', 'DONE', 'DONE', 'DONE')], done)) is None
    no_sources = journey.understand_step(CURRENT, has_sources=False)
    assert journey.focus_step(journey.project_steps([], no_sources)) == 'UNDERSTAND'
