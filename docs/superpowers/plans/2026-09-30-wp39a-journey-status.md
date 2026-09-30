# WP-39a Journey Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only service that says where each Form, and the project,
stands in the Understand → Decide → Build → Validate journey. It is served by
`GET /api/v2/projects/{pid}/journey` and `formslang project journey`.

**Architecture:** A new module, `formslang/project_journey_status.py`, holds:

- pure step rules and a pure composer (`build_journey`), testable without a
  project;
- a thin I/O layer (`journey_status`) that feeds the composer facts the product
  already computes (freshness, the reviewed blueprint, generation blockers,
  artifact currency, validation records).

Three small extractions give those facts one shared definition instead of
copies:

- `RESOLVED_REVIEWS` and the Decide scope;
- the artifact currency rule;
- the latest validation record.

The service writes nothing.

**Tech Stack:** Python 3.10–3.13, stdlib only, pytest, ruff. The HTTP layer is
the existing `ProjectHTTP` dispatcher. The CLI is the existing argparse
`project` command group.

**Spec:** `docs/design/formslang-3.0/journey-shell-design.md` §2 and §5, and the
WP-39a row in `docs/design/formslang-3.0/implementation-plan.md` (M5).

**Base:** `main` after PR #45, which carries the spec and this plan, is merged.
Branch `feat/formslang-3-wp39a-journey-status`, worktree
`.worktrees/wp39a-journey-status`.

## Global Constraints

- No new table, no persistence authority, no domain rule. The journey
  classifies existing facts only.
- A journey request writes nothing. Module sessions are opened with
  `read_only=True`.
- Each response uses exactly one freshness value, supplied by the caller:
  - HTTP passes `ProjectHTTP._freshness(service)`, the last saved check;
  - the CLI passes `service.freshness()`.
- The 24 generation blocker codes are classified:
  - `UNDERSTAND`: 3 codes;
  - `DECIDE`: 13 codes;
  - `LIMIT`: 8 codes.
- An unknown freshness status, blocker code or validation status yields reason
  `UNCLASSIFIED` with the raw value, and never the state `DONE`.
- Step identifiers: `UNDERSTAND`, `DECIDE`, `BUILD`, `VALIDATE`.
- States: `DONE`, `ACTION`, `WAITING`, `BLOCKED`, `STALE`.
- Payload `schema`: `formslang-journey/1`. This is an internal label, not the
  ADR-13 envelope.
- `ProjectBusy` is never absorbed. A revision change during the read raises
  `RevisionConflict` (HTTP 409).
- Existing behavior of delivery reports, the generation overview and the
  generation policy must not change. Their existing tests stay green unmodified.
- Performance gate: on the 500-Form fixture, the cold journey median must be at
  most 1.5× the cold Overview median of the same run. If the gate fails, stop
  and report to the owner.
- Plan working rules apply:
  - failing test first;
  - focused tests, then related suites, `python -m ruff check .` and the full
    `python -m pytest -q`;
  - no push, merge, tag or release without the owner's authorization for that
    operation.

## Review Focus

1. **A prepared module whose session file disappeared or whose source was
   edited.** The journey must still answer. That Form's Build becomes `BLOCKED`
   with `GENERATION_DETAIL_UNAVAILABLE`, and there is no 500. Tested in Task 4.
2. **A review recorded while the journey is being read.** The request must fail
   as a conflict (`RevisionConflict` / 409) rather than return a mix of two
   revisions. Tested in Task 4.
3. **A validated artifact whose archive was later edited.** It must not stay
   "validated": Build `STALE` (`ARTIFACT_INTEGRITY`) and Validate `WAITING`.
   Tested in Task 4.
4. **The first HTTP visit after analysis, when no source check is saved yet.**
   The journey must ask for a check (`SOURCE_CHECK_REQUIRED`, focus
   `UNDERSTAND`) instead of claiming the sources are current or failing.
   Tested in Task 5.
5. **A `form` value that is unknown, differs in case, or is a name shared by
   two Forms.**
   - unknown → 404 (HTTP), or exit 2 (CLI) with "Form not found", never "Project
     could not be opened";
   - different case → still found;
   - shared name → 400 with "ambiguous".

   Tested in Task 4 (pure) and Task 5 (HTTP).

---

## File Structure

| File | Responsibility |
|---|---|
| `formslang/review_states.py` (create) | The single `RESOLVED_REVIEWS` definition |
| `formslang/project_generation_policy.py` (modify) | `dependency_edges`, `related_scope(..., outgoing=)`, `unresolved_findings` |
| `formslang/project_projection.py`, `formslang/project_visualization.py` (modify) | Import `RESOLVED_REVIEWS` instead of redefining it |
| `formslang/project_generation.py` (modify) | `_detail(..., read_only=)`, `latest_validation`, `artifact_currency` |
| `formslang/project_reports.py` (modify) | `_artifacts` calls `artifact_currency`; behavior unchanged |
| `formslang/project_journey_status.py` (create) | Rules, `build_journey` and `journey_status` |
| `formslang/project_service.py` (modify) | `ProjectService.journey` |
| `formslang/project_http.py` (modify) | `GET …/journey` route |
| `formslang/project_cli.py` (modify) | `project journey` command |
| `examples/verify/project_overview_performance_check.py` (modify) | Cold journey measurement and gate |
| `tests/test_project_journey_status.py` (create) | Tasks 1–4 |
| `tests/test_project_journey_status_http.py` (create) | Task 5 |
| `tests/test_project_projection_scale.py` (modify) | Task 6 |
| `docs/design/formslang-3.0/evidence-register.md`, `CHANGELOG.md` (modify) | Task 7 |

---

### Task 1: One resolved-review definition and a shared Decide scope

**Files:**
- Create: `formslang/review_states.py`
- Modify: `formslang/project_generation_policy.py`. Replace `related_scope`, and
  replace the literal set in `module_blockers`.
- Modify: `formslang/project_projection.py:53` and
  `formslang/project_visualization.py:85`.
- Test: `tests/test_project_journey_status.py` (create).

**Interfaces:**
- Produces:
  - `RESOLVED_REVIEWS: frozenset[str]`;
  - `dependency_edges(blueprint) -> dict[str, list[str]]`;
  - `related_scope(blueprint, module, *, outgoing=None) -> set[str]`;
  - `unresolved_findings(blueprint, module, *, outgoing=None) -> list[dict]`,
    with findings in blueprint order.

- [ ] **Step 1: Create the worktree**

```bash
git fetch origin
git worktree add .worktrees/wp39a-journey-status -b feat/formslang-3-wp39a-journey-status origin/main
cd .worktrees/wp39a-journey-status
python -m pytest -q tests/test_project_generation.py tests/test_project_journey.py
```

Expected: all pass. Record the count in the PR notes.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_project_journey_status.py`:

```python
"""WP-39a journey status: read-only, composed from facts the product already saves."""

# ruff: noqa: F811 -- imported pytest fixtures are injected by name

import pytest

from formslang import rbac
from formslang.project_generation_policy import dependency_edges, related_scope, unresolved_findings
from formslang.project_intake import ProjectIntake
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_project_journey_status.py -q`

Expected: collection ERROR,
`ImportError: cannot import name 'dependency_edges'`.

- [ ] **Step 4: Implement**

Create `formslang/review_states.py`:

```python
"""Review actions that resolve a modernization finding, defined once for every consumer."""

RESOLVED_REVIEWS = frozenset({"APPROVE", "MODIFY"})
```

In `formslang/project_generation_policy.py`, add
`from .review_states import RESOLVED_REVIEWS` after
`from .project_model import TargetProfile`. Then replace the whole
`related_scope` function with:

```python
def dependency_edges(blueprint):
    """Observed outgoing dependencies, including resolved references, by source entity."""
    outgoing = {}
    for edge in blueprint.get('edges', []):
        outgoing.setdefault(edge['source'], []).append(edge['target'])
    for node in blueprint['entities']:
        if node.get('resolved_target'):
            outgoing.setdefault(node['id'], []).append(node['resolved_target'])
    return outgoing


def related_scope(blueprint, module, *, outgoing=None):
    """Follow observed dependencies, retaining shared API/control findings."""
    included = {n['id'] for n in blueprint['entities'] if n.get('module') == module}
    outgoing = dependency_edges(blueprint) if outgoing is None else outgoing
    pending = list(included)
    while pending:
        for target in outgoing.get(pending.pop(), []):
            if target not in included:
                included.add(target)
                pending.append(target)
    return included


def unresolved_findings(blueprint, module, *, outgoing=None):
    """Findings in the module's related scope whose current review does not resolve them.

    The same scope and review set as the UNRESOLVED_REVIEW generation blocker.
    """
    included = related_scope(blueprint, module, outgoing=outgoing)
    return [finding for finding in blueprint['findings']
            if finding['entity'] in included and finding.get('review_state') not in RESOLVED_REVIEWS]
```

In `module_blockers`, change
`if finding.get('review_state') not in {'APPROVE', 'MODIFY'}:` to
`if finding.get('review_state') not in RESOLVED_REVIEWS:`.

In `formslang/project_projection.py`, delete line 53
(`RESOLVED_REVIEWS = {"APPROVE", "MODIFY"}`). Add
`from .review_states import RESOLVED_REVIEWS` after the last `from .` import
at the top of the file. In `formslang/project_visualization.py`, delete line 85
(`RESOLVED_REVIEWS = frozenset({"APPROVE", "MODIFY"})`) and add the same
import.

- [ ] **Step 5: Run the tests to verify they pass**

Run:
`python -m pytest tests/test_project_journey_status.py tests/test_project_generation.py tests/test_project_journey.py tests/test_project_projection_scale.py -q`

Expected: all pass. Then run `python -m ruff check .`, which must be clean.

- [ ] **Step 6: Commit**

```bash
git add formslang/review_states.py formslang/project_generation_policy.py formslang/project_projection.py formslang/project_visualization.py tests/test_project_journey_status.py
git commit -m "refactor: share the resolved-review set and the Decide scope"
```

---

### Task 2: Read-only generation detail, latest validation and shared artifact currency

**Files:**
- Modify: `formslang/project_generation.py`:
  - `_detail` (line 198);
  - `overview` (line 286);
  - add `latest_validation` and `artifact_currency` after `overview`.
- Modify: `formslang/project_reports.py`, in `ProjectReportService._artifacts`,
  the `elif (snapshot['overview']…)` branch and its `else:` code checks.
- Test: `tests/test_project_journey_status.py`.

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `ProjectGenerationService._detail(assessment, fresh, source_id, *, read_only=False) -> dict`;
  - `ProjectGenerationService.latest_validation(artifact_id) -> dict | None`;
  - `ProjectGenerationService.artifact_currency(assessment, artifact, *, freshness_status, latest_plans, sessions) -> str | None`.
    The return value is one of `None`, `'ARTIFACT_REVISION_STALE'`,
    `'ARTIFACT_CODE_UNAVAILABLE'` or `'ARTIFACT_CODE_STALE'`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_project_journey_status.py`. Put the new imports at the
top with the others:

```python
import hashlib
from pathlib import Path

from formslang import apeximport
from formslang.project_review import ProjectReviewService
```

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_project_journey_status.py -q -k "read_only or currency or latest_validation"`

Expected: 3 failed.
- The first raises `TypeError: … unexpected keyword argument 'read_only'`.
- The others raise `AttributeError: 'ProjectGenerationService' object has no attribute …`.

- [ ] **Step 3: Implement in `formslang/project_generation.py`**

Change the `_detail` signature and its `_module` call:

```python
    def _detail(self, assessment, fresh, source_id, *, read_only=False):
```

```python
            with self._module(assessment, source_id, read_only=read_only) as (_, module, session):
```

In `overview`, replace the inline validation query in the artifact loop with
the new helper. Keep the rest of the loop unchanged:

```python
        for artifact in artifacts:
            validation = self.latest_validation(artifact['artifact_id'])
            if validation:
                artifact['validation'] = validation
                artifact['validation_status'] = validation['status']
                try:
                    self._artifact_bytes(artifact['artifact_id'])
                except (OSError, ProjectError):
                    artifact['validation_status'] = 'Not Validated'
                    artifact['integrity'] = 'Modified or unavailable; historical validation does not apply.'
```

Add these two methods directly after `overview`:

```python
    def latest_validation(self, artifact_id):
        """The newest validation record of one artifact, or None."""
        row = self.store.session.db.execute(
            'SELECT payload_json FROM project_artifact_validation WHERE artifact_id=? ORDER BY id DESC LIMIT 1',
            (artifact_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def artifact_currency(self, assessment, artifact, *, freshness_status, latest_plans, sessions):
        """Why a selected-module artifact no longer matches current evidence, or None when it does.

        Delivery reports and the journey status share this rule. Archive
        integrity is checked by each caller.
        """
        if (freshness_status != 'CURRENT'
                or any(artifact.get(k) != v for k, v in _binding(assessment).items())
                or latest_plans.get((artifact['source_id'], artifact['analysis_revision'])) != artifact['target_revision']):
            return 'ARTIFACT_REVISION_STALE'
        if sessions.get((artifact['source_id'], artifact['analysis_revision'])) is None:
            return 'ARTIFACT_CODE_UNAVAILABLE'
        try:
            with self._module(assessment, artifact['source_id'], read_only=True) as (_, _, session):
                if self._code_revision(session) != artifact['code_revision']:
                    return 'ARTIFACT_CODE_STALE'
        except (OSError, sqlite3.Error, ProjectError):
            return 'ARTIFACT_CODE_UNAVAILABLE'
        return None
```

`json`, `sqlite3`, `ProjectError` and `_binding` are already imported in this
module. Check with `grep -n "^import\|^from" formslang/project_generation.py`.

- [ ] **Step 4: Replace the inline rule in `formslang/project_reports.py`**

In `_artifacts`, replace this exact block:

```python
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
```

with:

```python
            else:
                reason = generation.artifact_currency(
                    assessment, artifact,
                    freshness_status=snapshot['overview']['assessment']['freshness'],
                    latest_plans=latest_plans, sessions=sessions)
                if reason is None:
```

Leave the `try: data = generation._artifact_bytes(identity)` integrity block
below it byte-for-byte unchanged. Its indentation already matches the new
`if reason is None:`. After the edit, `ruff` reports whether `sqlite3` or
`_binding` became unused in `project_reports.py`. If one did, remove only that
import.

- [ ] **Step 5: Run the tests to verify they pass**

Run:
`python -m pytest tests/test_project_journey_status.py tests/test_project_generation.py tests/test_project_reports.py tests/test_project_validation.py tests/test_project_generation_http.py -q`

Expected: all pass, and the existing report and generation tests pass
unmodified. `python -m ruff check .` must be clean.

- [ ] **Step 6: Commit**

```bash
git add formslang/project_generation.py formslang/project_reports.py tests/test_project_journey_status.py
git commit -m "refactor: share artifact currency and read generation detail read-only"
```

---

### Task 3: Journey step rules (pure)

**Files:**
- Create: `formslang/project_journey_status.py` (the rules section)
- Test: `tests/test_project_journey_status.py`

**Interfaces:**
- Produces, from `formslang.project_journey_status`:
  - constants: `SCHEMA`, `STEPS`, `BLOCKER_CLASS: dict[str, str]`;
  - `classify_blocker(code) -> str`;
  - `understand_step(freshness, *, has_sources, blockers=()) -> dict`;
  - `decide_step(freshness, *, has_sources, unresolved, blockers=()) -> dict`;
  - `build_step(*, has_scope, blockers=(), detail_error=None, artifact=None) -> dict`;
  - `validate_step(build, *, validation=None) -> dict`;
  - `project_steps(forms, understand) -> list[dict]`;
  - `focus_step(steps) -> str | None`.
- A step is `{'step': str, 'state': str, 'reasons': list[dict]}`.
- A reason is `{'code': str, 'resolved_in': str | None, **detail}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_project_journey_status.py`. Add these imports at the top:

```python
import re

from formslang import project_journey_status as journey
```

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_project_journey_status.py -q`

Expected: collection ERROR,
`ModuleNotFoundError: No module named 'formslang.project_journey_status'`.

- [ ] **Step 3: Implement the rules**

Create `formslang/project_journey_status.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_project_journey_status.py -q`

Expected: all pass. `python -m ruff check .` must be clean.

- [ ] **Step 5: Commit**

```bash
git add formslang/project_journey_status.py tests/test_project_journey_status.py
git commit -m "feat: classify journey steps from existing project facts"
```

---

### Task 4: Compose the journey and serve it from `ProjectService`

**Files:**
- Modify: `formslang/project_journey_status.py` (append the composer and the
  I/O layer)
- Modify: `formslang/project_service.py`. Add `journey` after the
  `generation_module` method (around line 240).
- Test: `tests/test_project_journey_status.py`

**Interfaces:**
- Consumes:
  - `unresolved_findings` and `dependency_edges` (Task 1);
  - `_detail(..., read_only=True)`, `artifact_currency` and
    `latest_validation` (Task 2);
  - the rules from Task 3.
- Produces:
  - `build_journey(assessment, freshness, *, has_sources, scopes=None, module_facts=None, form=None) -> dict`
    (pure);
  - `journey_status(service, *, freshness, form=None) -> dict`;
  - `ProjectService.journey(*, freshness, form=None) -> dict`.

  Payload keys: `schema`, `project_id`, `binding`, `freshness`, `focus`,
  `steps`, `forms`. Each Form entry has `entity_id`, `name`, `module`,
  `source_id` and `steps`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_project_journey_status.py`. Add these imports at the top:

```python
from formslang.project_model import ProjectError, RevisionConflict
```

```python
def _assessment(*names):
    entities = [{'id': f'form:{n.lower()}', 'type': 'FORM', 'name': n, 'module': f'forms/{n.lower()}.xml'}
                for n in names]
    return {'blueprint': {'entities': entities, 'edges': [], 'findings': []}}


def test_build_journey_selects_forms_by_id_or_name():
    assessment = _assessment('SHIPMENTS', 'CUSTOMERS')
    everything = journey.build_journey(assessment, CURRENT, has_sources=True)
    assert everything['schema'] == 'formslang-journey/1'
    assert [f['name'] for f in everything['forms']] == ['CUSTOMERS', 'SHIPMENTS']
    assert [f['name'] for f in journey.build_journey(
        assessment, CURRENT, has_sources=True, form='form:shipments')['forms']] == ['SHIPMENTS']
    assert [f['name'] for f in journey.build_journey(
        assessment, CURRENT, has_sources=True, form='customers')['forms']] == ['CUSTOMERS']
    with pytest.raises(LookupError):
        journey.build_journey(assessment, CURRENT, has_sources=True, form='GHOST')
    twins = _assessment('CUSTOMERS')
    twins['blueprint']['entities'].append(
        {'id': 'form:other', 'type': 'FORM', 'name': 'Customers', 'module': 'other/customers.xml'})
    with pytest.raises(ProjectError, match='ambiguous'):
        journey.build_journey(twins, CURRENT, has_sources=True, form='CUSTOMERS')


def test_build_journey_without_scope_or_analysis():
    unscoped = journey.build_journey(_assessment('NOTICE'), CURRENT, has_sources=True)
    assert [s['state'] for s in unscoped['forms'][0]['steps']] == ['DONE', 'DONE', 'BLOCKED', 'WAITING']
    assert unscoped['focus'] == 'BUILD'
    empty = journey.build_journey(None, {'status': 'INCOMPLETE', 'reasons': ['NOT_ANALYZED']}, has_sources=True)
    assert empty['forms'] == [] and empty['focus'] == 'UNDERSTAND'
    assert empty['steps'][0]['project']['reasons'] == [{'code': 'NOT_ANALYZED', 'resolved_in': 'UNDERSTAND'}]
    with pytest.raises(LookupError):
        journey.build_journey(None, CURRENT, has_sources=True, form='NOTICE')


def _states(service):
    return [s['state'] for s in service.journey(freshness=service.freshness())['forms'][0]['steps']]


def _validated(monkeypatch):
    monkeypatch.setattr(apeximport, 'sqlcl_version', lambda: 'SQLcl 26.2.2')
    monkeypatch.setattr(apeximport, 'run_import',
                        lambda path, **kwargs: apeximport.ImportResult(True, 0, 'Validation successful.', ''))


def test_journey_follows_the_generation_lifecycle(generation_project, monkeypatch):
    service = generation_project
    first = service.journey(freshness=service.freshness())
    assert first['project_id'] == service.open().id
    assert first['binding']['analysis_revision'] == service.open().analysis_revision
    build = first['forms'][0]['steps'][2]
    assert build['state'] == 'WAITING'
    assert 'MODULE_NOT_PREPARED' in {r['code'] for r in build['reasons']}
    detail = prepared(service)
    assert detail['ready'], detail['blockers']
    assert _states(service) == ['DONE', 'DONE', 'ACTION', 'WAITING']
    generated = service.generate({**detail['binding'], 'scopes': [detail]})
    assert _states(service) == ['DONE', 'DONE', 'DONE', 'ACTION']
    monkeypatch.setattr(apeximport, 'sqlcl_version', lambda: '')
    service.generation_validate(generated['artifact_id'])
    validate = service.journey(freshness=service.freshness())['forms'][0]['steps'][3]
    assert validate['state'] == 'ACTION' and validate['reasons'][0]['code'] == 'NOT_VALIDATED'
    _validated(monkeypatch)
    service.generation_validate(generated['artifact_id'])
    assert _states(service) == ['DONE', 'DONE', 'DONE', 'DONE']
    assert service.journey(freshness=service.freshness())['focus'] is None


def test_changed_source_makes_the_journey_wait_for_understand(generation_project):
    service = generation_project
    source = service.access.source_roots[0] / 'forms/notice.xml'
    source.write_text(source.read_text(encoding='utf-8') + '\n<!-- changed -->', encoding='utf-8')
    assert _states(service) == ['STALE', 'WAITING', 'WAITING', 'WAITING']


def test_decide_count_equals_generation_review_blockers(demo):
    payload = demo.journey(freshness=demo.freshness())
    assert [f['name'] for f in payload['forms']] == ['CUSTOMERS', 'SHIPMENTS']
    for form in payload['forms']:
        detail = demo.generation_module(form['source_id'])
        expected = sum(1 for b in detail['blockers'] if b['code'] == 'UNRESOLVED_REVIEW')
        counted = [r['count'] for r in form['steps'][1]['reasons'] if r['code'] == 'UNRESOLVED_REVIEW']
        assert counted == ([expected] if expected else [])
    assert sum(payload['steps'][1]['counts'].values()) == 2


def test_journey_writes_nothing(generation_project):
    service = generation_project
    prepared(service)
    fresh = service.freshness()
    before = _tree_digest(service.access.root)
    service.journey(freshness=fresh)
    assert _tree_digest(service.access.root) == before


def test_unavailable_prepared_session_blocks_build_without_failing_the_journey(generation_project):
    service = generation_project
    prepared(service)
    record = service._store.module_sessions()[0]
    service._generation_service()._path(record['relative_store']).unlink()
    build = service.journey(freshness=service.freshness())['forms'][0]['steps'][2]
    assert build['state'] == 'BLOCKED'
    assert build['reasons'][0]['code'] == 'GENERATION_DETAIL_UNAVAILABLE'


def test_edited_artifact_is_stale_even_after_validation(generation_project, monkeypatch):
    service = generation_project
    detail = prepared(service)
    generated = service.generate({**detail['binding'], 'scopes': [detail]})
    _validated(monkeypatch)
    service.generation_validate(generated['artifact_id'])
    archive = service._store.directory / 'artifacts' / generated['artifact_id'] / 'application.apex.zip'
    archive.write_bytes(b'edited by human')
    steps = service.journey(freshness=service.freshness())['forms'][0]['steps']
    assert [s['state'] for s in steps[2:]] == ['STALE', 'WAITING']
    assert steps[2]['reasons'][0]['code'] == 'ARTIFACT_INTEGRITY'


def test_journey_rejects_a_review_that_lands_while_it_is_read(demo, monkeypatch):
    fresh = demo.freshness()
    original = journey.build_journey

    def interleaved(*args, **kwargs):
        payload = original(*args, **kwargs)
        row = demo.review_queue()['rows'][0]
        detail = demo.review_detail(row['id'])
        demo.review_decide(row['id'], {**detail['binding'], 'action': 'DEFER'})
        return payload

    monkeypatch.setattr(journey, 'build_journey', interleaved)
    with pytest.raises(RevisionConflict):
        demo.journey(freshness=fresh)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_project_journey_status.py -q`

Expected: the new tests fail with
`AttributeError: module 'formslang.project_journey_status' has no attribute 'build_journey'`
or `AttributeError: 'ProjectService' object has no attribute 'journey'`. The
Task 1–3 tests still pass.

- [ ] **Step 3: Implement the composer and the I/O layer**

Append to `formslang/project_journey_status.py`. Put the imports at the top of
the module, below `from collections import Counter`:

```python
import json

from .project_generation_policy import dependency_edges, unresolved_findings
from .project_model import ProjectBusy, ProjectError, RevisionConflict
from .project_review import _binding
```

```python
def _select_form(entities, form):
    by_id = [e for e in entities if e['id'] == form]
    if by_id:
        return by_id
    by_name = [e for e in entities if str(e.get('name', '')).casefold() == str(form).casefold()]
    if len(by_name) > 1:
        raise ProjectError('Form name is ambiguous; use its entity id')
    if not by_name:
        raise LookupError('Form not found')
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
        if artifact.get('artifact_kind') or not artifact.get('source_id'):
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
```

In `formslang/project_service.py`, add this method directly after
`generation_module`:

```python
    def journey(self, *, freshness, form=None) -> dict:
        """Read-only journey status (WP-39a); the caller supplies one freshness value."""
        from .project_journey_status import journey_status
        self.open()
        return journey_status(self, freshness=freshness, form=form)
```

The local import follows `_generation_service` and avoids an import cycle
through `project_review`.

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`python -m pytest tests/test_project_journey_status.py tests/test_project_journey.py tests/test_project_generation.py -q`

Expected: all pass. If `test_journey_follows_the_generation_lifecycle` fails at
the first assertion because Build is `BLOCKED`, print
`first['forms'][0]['steps'][2]['reasons']`. A `LIMIT` code on an unprepared
module means a classification error. Report it; do not reclassify silently. The
spec §2 table is authoritative, and the owner changes it.

- [ ] **Step 5: Commit**

```bash
git add formslang/project_journey_status.py formslang/project_service.py tests/test_project_journey_status.py
git commit -m "feat: compose the read-only project journey status"
```

---

### Task 5: HTTP route and CLI command

**Files:**
- Modify: `formslang/project_http.py`. Insert the route immediately before
  `if tail == ['module-360'] and method == 'GET':` (line 383).
- Modify: `formslang/project_cli.py`:
  - the VIEW_PROJECT set (line 62);
  - the operations after `summary` (line 133);
  - the command loop (line 239);
  - the options after `relink` (line 256).
- Test: `tests/test_project_journey_status_http.py` (create)

**Interfaces:**
- Consumes: `ProjectService.journey` (Task 4).
- Produces:
  - `GET /api/v2/projects/{pid}/journey[?form=<id or name>]`, returning 200
    with the payload, 400 for an unknown query key or an ambiguous name, 404
    for an unknown Form, and 409 for a conflict;
  - `formslang project journey <project> [--form X] [--json]`, which exits 0,
    or 2 with `{'error': …}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_project_journey_status_http.py`:

```python
"""WP-39a journey over HTTP and the CLI: same service, same payload."""

# ruff: noqa: F811 -- imported pytest fixtures are injected by name

import json

from formslang import config
from formslang.cli import main
from tests.test_project_http import analyze_demo, project_server  # noqa: F401


def test_http_journey_without_a_saved_source_check_asks_for_one(project_server):
    client, _ = project_server
    pid = analyze_demo(client)
    response = client.get(f'/api/v2/projects/{pid}/journey')
    assert response.status == 200, response.json
    body = response.json
    assert body['schema'] == 'formslang-journey/1'
    assert body['freshness']['status'] == 'UNVERIFIED'
    assert body['focus'] == 'UNDERSTAND'
    assert body['steps'][0]['project']['reasons'] == [
        {'code': 'SOURCE_CHECK_REQUIRED', 'resolved_in': 'UNDERSTAND'}]
    assert [f['name'] for f in body['forms']] == ['CUSTOMERS', 'SHIPMENTS']


def test_http_journey_filters_and_rejects(project_server):
    client, _ = project_server
    pid = analyze_demo(client)
    everything = client.get(f'/api/v2/projects/{pid}/journey').json
    customers = everything['forms'][0]
    by_id = client.get(f"/api/v2/projects/{pid}/journey?form={customers['entity_id']}")
    assert by_id.status == 200 and [f['name'] for f in by_id.json['forms']] == ['CUSTOMERS']
    by_name = client.get(f'/api/v2/projects/{pid}/journey?form=customers')
    assert [f['name'] for f in by_name.json['forms']] == ['CUSTOMERS']
    assert client.get(f'/api/v2/projects/{pid}/journey?form=GHOST').status == 404
    assert client.get(f'/api/v2/projects/{pid}/journey?view=all').status == 400


def test_cli_journey_matches_http(project_server, capsys):
    client, _ = project_server
    pid = analyze_demo(client)
    descriptor = next((config.data_dir() / 'projects').glob('*/.formslang/project.json'))
    capsys.readouterr()
    assert main(['project', 'journey', str(descriptor), '--json']) == 0
    cli_journey = json.loads(capsys.readouterr().out)
    http_journey = client.get(f'/api/v2/projects/{pid}/journey').json
    assert cli_journey == http_journey
    assert cli_journey['freshness']['status'] == 'CURRENT'
    assert main(['project', 'journey', str(descriptor), '--form', 'SHIPMENTS', '--json']) == 0
    assert [f['name'] for f in json.loads(capsys.readouterr().out)['forms']] == ['SHIPMENTS']
    assert main(['project', 'journey', str(descriptor), '--form', 'GHOST', '--json']) == 2
    assert json.loads(capsys.readouterr().out)['error'].startswith('Form not found')
```

The CLI runs first in `test_cli_journey_matches_http`. Its `service.freshness()`
saves the check that the HTTP route then reads, which is how
`test_cli_summary_and_inventory_reconcile_with_http` reconciles.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_project_journey_status_http.py -q`

Expected:
- the HTTP tests fail with status 404 (`Project resource not found`);
- the CLI test fails with `SystemExit: 2` (argparse: invalid choice
  `'journey'`).

- [ ] **Step 3: Implement the HTTP route**

In `formslang/project_http.py`, insert immediately before
`if tail == ['module-360'] and method == 'GET':`:

```python
            if tail == ['journey'] and method == 'GET':
                if set(query) - {'form'}:
                    raise ProjectError('Journey accepts only the form query parameter')
                return 200, service.journey(freshness=self._freshness(service), form=query.get('form'))
```

- [ ] **Step 4: Implement the CLI command**

In `formslang/project_cli.py`, make four edits:

1. Change the action line to:

```python
    action = rbac.VIEW_PROJECT if operation in {'status', 'summary', 'inventory', 'search', 'journey'} else rbac.RUN_CONVERSION
```

2. Directly after the `if operation == 'summary':` block (the one that ends
   `return result, 0`), add the lines below. `run_project` reports a bare
   `LookupError` as "Project could not be opened…", which would mislead
   someone who only mistyped a Form name. Name the problem instead:

```python
        if operation == 'journey':
            try:
                return service.journey(freshness=service.freshness(), form=args.form), 0
            except LookupError as exc:
                raise ProjectError('Form not found; run project journey without --form to list Forms') from exc
```

3. Add `'journey'` to the command loop tuple:

```python
    for name in ('create', 'demo', 'discover', 'analyze', 'status', 'summary',
                 'inventory', 'info', 'open', 'relink', 'journey'):
```

4. In the same loop, after the `elif name == 'relink':` block, add:

```python
        elif name == 'journey':
            command.add_argument('--form', help='Form entity id or name; omit for every Form')
```

Before editing, confirm that no other parser named `journey` exists:
`grep -n "add_parser('journey'" formslang/*.py`. The expected result is no
match.

- [ ] **Step 5: Run the tests to verify they pass**

Run:
`python -m pytest tests/test_project_journey_status_http.py tests/test_project_http.py tests/test_cli_project.py -q`

Expected: all pass. `python -m ruff check .` must be clean.

- [ ] **Step 6: Commit**

```bash
git add formslang/project_http.py formslang/project_cli.py tests/test_project_journey_status_http.py
git commit -m "feat: serve the journey status over HTTP and the project CLI"
```

---

### Task 6: 500-Form performance gate

**Files:**
- Modify: `examples/verify/project_overview_performance_check.py`:
  - the imports;
  - `run_measurements`;
  - the `main` return.
- Modify: `tests/test_project_projection_scale.py`

**Interfaces:**
- Consumes: `build_journey` (Task 4).
- Produces: a `journey_gate` object in the result JSON, with keys
  `cold_journey_median_ms`, `cold_overview_median_ms`, `ratio`, `limit` and
  `within_limit`. The script exits with 1 when `within_limit` is false.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_project_projection_scale.py`:

```python
def test_journey_composes_500_forms_on_the_scale_fixture():
    from formslang.project_journey_status import build_journey

    _, assessment, freshness = build_fixture()
    payload = build_journey(assessment, freshness, has_sources=True)
    assert len(payload['forms']) == 500
    assert [step['counts'] for step in payload['steps']] == [
        {'DONE': 500}, {'ACTION': 500}, {'BLOCKED': 500}, {'WAITING': 500}]
    assert payload['focus'] == 'DECIDE'
```

Add `from examples.verify.project_overview_performance_check import run_measurements`
to the imports at the top, next to the existing `build_fixture` import, and
append:

```python
def test_scale_report_carries_the_journey_gate(tmp_path):
    report = run_measurements(tmp_path, iterations=1)
    gate = report['journey_gate']
    assert set(gate) == {'cold_journey_median_ms', 'cold_overview_median_ms', 'ratio', 'limit', 'within_limit'}
    assert gate['limit'] == 1.5
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_project_projection_scale.py -q`

Expected:
- the first new test passes, because it only needs Task 4;
- `test_scale_report_carries_the_journey_gate` fails with `KeyError: 'journey_gate'`.

- [ ] **Step 3: Implement the measurement**

In `examples/verify/project_overview_performance_check.py`, add to the imports:

```python
from formslang.project_journey_status import build_journey
```

In `run_measurements`, after the `measurements = {...}` dict is built, add:

```python
    journey = _measure(lambda: build_journey(assessment, freshness, has_sources=True), iterations)
    measurements["cold_journey"] = journey
    ratio = journey["median_ms"] / cold["median_ms"] if cold["median_ms"] else float("inf")
    journey_gate = {"cold_journey_median_ms": journey["median_ms"],
                    "cold_overview_median_ms": cold["median_ms"],
                    "ratio": round(ratio, 3), "limit": 1.5, "within_limit": ratio <= 1.5}
```

Add `"journey_gate": journey_gate,` to the returned dict, after
`"semantic_reconciliation": semantic_ok,`. Extend the `"limitations"` string
with:
` The journey gate has no generation scope in this fixture; per-Form generation detail is not measured.`

In `main`, change the return to:

```python
    return 0 if report["semantic_reconciliation"] and report["journey_gate"]["within_limit"] else 1
```

- [ ] **Step 4: Run the tests and the gate**

Run: `python -m pytest tests/test_project_projection_scale.py -q`

Expected: all pass.

Run:
`python -B examples/verify/project_overview_performance_check.py --output scratch_tmp/wp39a-performance`

Expected: exit 0 and `"within_limit": true`. Copy `journey_gate` and the
`run-<id>` path into the PR notes.

**If `within_limit` is false, stop.** Do not optimize past the spec, and report
the numbers to the owner. The spec (§2 Performance) makes the remedy an owner
decision.

- [ ] **Step 5: Commit**

```bash
git add examples/verify/project_overview_performance_check.py tests/test_project_projection_scale.py
git commit -m "test: gate the journey composition on the 500-Form fixture"
```

---

### Task 7: Evidence, changelog and full regression

**Files:**
- Modify: `docs/design/formslang-3.0/evidence-register.md` (append a WP-39a
  section)
- Modify: `CHANGELOG.md` (the `[Unreleased]` section)

- [ ] **Step 1: Run the full regression**

Run: `python -m pytest -q` (about 15 minutes on Windows), then
`python -m ruff check .` and `git diff --check origin/main`.

Expected: everything passes with no failures. Record the exact summary line,
for example `2140 passed, 5 skipped, 2 xfailed`.

A Windows-only failure in `test_project_descriptor_concurrency.py` (issue #20)
or a job-status HTTP 500 in `test_project_http.py` (#23) is a known flake
family, not WP-39a. Re-run **only** that test once and record both results. Do
not retry any other failure.

- [ ] **Step 2: Append the evidence**

Append to `docs/design/formslang-3.0/evidence-register.md`, filling in the
numbers measured in this branch:

```markdown
## WP-39a — read-only journey status (<date>)

Scope: `formslang/project_journey_status.py`, `GET /api/v2/projects/{pid}/journey`,
`formslang project journey`. Design: [journey-shell-design.md](journey-shell-design.md) §2.

- State rules and exhaustiveness: the 24 generation blocker codes in the
  generation modules are classified as 3 UNDERSTAND, 13 DECIDE and 8 LIMIT.
  Unknown values yield `UNCLASSIFIED`.
- Decide consistency: the unresolved count equals the `UNRESOLVED_REVIEW`
  blockers of the same Form on the bundled demo.
- Read-only: a journey read leaves the project tree byte-identical, including
  a prepared module session.
- Composition cases covered by tests:
  - a missing session gives `GENERATION_DETAIL_UNAVAILABLE`;
  - an edited validated artifact makes Build `STALE (ARTIFACT_INTEGRITY)`;
  - a review during the read gives `RevisionConflict`;
  - the first HTTP visit gives `SOURCE_CHECK_REQUIRED`.
- CLI/HTTP equality on the demo project.
- 500-Form gate: cold journey <n> ms, cold Overview <n> ms, ratio <n> (limit
  1.5), run `<run-id>`. The fixture has no generation scope, so per-Form
  generation detail is not measured.
- Full suite: <summary line>. Ruff clean.
- Finding (not changed): artifact currency binds the project-wide
  `review_revision`, so a review on any Form marks every artifact
  `ARTIFACT_REVISION_STALE`.
- Not claimed: no UI (WP-41 slice 1), no UX requirement completed, no ADR-13
  envelope.
```

- [ ] **Step 3: Add the changelog entry**

Under `## [Unreleased]` in `CHANGELOG.md`, add:

```markdown
### Added

- Read-only journey status for a saved project: for each Form, the state of the
  Understand, Decide, Build and Validate steps and the reasons, composed from
  existing freshness, review, generation, artifact and validation facts. Served
  by `GET /api/v2/projects/{pid}/journey` and `formslang project journey`. It
  writes nothing and adds no stored state.
```

- [ ] **Step 4: Commit and push the branch**

```bash
git add docs/design/formslang-3.0/evidence-register.md CHANGELOG.md
git commit -m "docs: record WP-39a evidence"
git push -u origin feat/formslang-3-wp39a-journey-status
```

Push only with the owner's authorization for this branch. Then open a **draft**
PR titled `WP-39a: read-only project journey status`. Its body lists the
evidence above and states that nothing is merged without the owner.
