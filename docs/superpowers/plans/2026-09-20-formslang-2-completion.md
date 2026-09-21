# FormsLang 2.0 Completion Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task. The owner authorizes unattended execution and integration after phase gates; no routine approval pause is required.

**Goal:** Complete review, safe generation, delivery and release acceptance on the existing project architecture.

**Architecture:** ProjectService delegates to focused services over ProjectAssessment and the existing Store. Human decisions remain append-only; generation reuses existing APEXlang/conversion approval. All adapters consume the same services.

**Tech Stack:** Python standard library, SQLite, existing HTML/JS Workbench, Tauri, pytest and existing browser harnesses.

**Spec:** `docs/superpowers/specs/2026-09-20-formslang-2-phase-d-design.md`; owner completion brief for E-H; `docs/formsLang-2-product-architecture.md`.

## Global constraints

- Base `262361e263ec3b3c4b74b607f3e2f8a7c7a1fa09`; specification `d87d99968a43a32fb20c9381d9e30daa046ff68f`.
- Keep 1.6.0 until candidate gates permit release preparation.
- No persistent projection tables; scale evidence gates optimization.
- Preserve frozen benchmark and ground truth. Initial check: 24 tracked artifacts match base Git object hashes.
- No proprietary/customer fixtures, production Oracle access or automatic deployment.
- Every phase needs focused tests, full regression, independent review, fixes, evidence and a coherent checkpoint.

## Review focus

- Forged revision/finding IDs must fail before any history event is appended.
- Source bytes changing after a UI freshness check must prevent applicable decisions/generation.
- Malicious notes and labels remain inert text; list views omit source and private identities.
- A bulk set with one changed member must not partly commit.
- Human-edited artifacts and legacy approvals survive reopen/upgrade without silent replacement.

## D1: Shared review service and transactional governance

**Files:** create `formslang/project_review.py`, `tests/test_project_review.py`; extend `project_service.py`, `project_store.py`, and the existing Store review transaction support where needed.

**Interfaces:** `ProjectService.review_queue(**query)`, `review_detail(finding_id, **query)`, `review_decide(finding_id, command)`, `review_annotate(finding_id, command)`, `review_bulk_preview(command)`, `review_bulk_apply(command)`. Responses carry source/analysis/review revisions. Commands carry those revisions plus exact finding revision(s).

- [ ] Write real demo-project regressions for accept, immutable engine recommendation, replay conflict, mandatory override rationale, CRITICAL confirmation, defer/needs-review unresolved counts, annotation separation and reopen.
- [ ] Run `pytest tests/test_project_review.py -q`; observe missing service failures before implementation.
- [ ] Implement `ProjectReviewService`, reusing Phase C priority/filter projections and `blueprint_review`. Add only append-only annotation storage. Keep server identity and existing write permission.
- [ ] Add bulk policy regressions: LOW/AUTO is insufficient when sensitive/unknown evidence exists; preview uses exact set and revisions; concurrent mutation rejects whole set.
- [ ] Verify foreign finding/project, revoked authorization, stale sources, simultaneous connections and bounded history. Run focused service/store/assessment/projection tests.

Example invariant:

```python
before = service.assessment()
detail = service.review_detail(finding_id)
service.review_decide(finding_id, {**detail['binding'], 'action': 'APPROVE'})
after = service.assessment()
assert after['review_revision'] == before['review_revision'] + 1
assert after['blueprint']['findings'][0]['recommendation'] == before['blueprint']['findings'][0]['recommendation']
```

## D2: API, CLI and Workbench

**Files:** `project_http.py`, `project_cli.py`, `ui/modernization_project.py`, new `ui/modernization_review.py`, UI assembler/styles; API/CLI/DOM/browser tests.

- [ ] Write API tests for list/detail/decision/annotation/bulk routes, authorization, 409 and pagination.
- [ ] Add thin `/api/v2/projects/:id/review` adapters and nested `project review` CLI commands using D1 signatures.
- [ ] Add real-browser/DOM RED coverage for priority navigation, split-pane context, critical override, conflict, history, safe bulk preview and inert hostile text.
- [ ] Implement UI with existing guards, semantic forms, focus restoration and server counts.
- [ ] Run focused tests and full pytest/JS/Phase D, C and legacy browser suites; measure 5,000 findings/history. Independent review then fixes. Update modernization-review/workflows/acceptance and commit D.

## E: Shared gated generation

**Files:** focused `project_generation.py`, ProjectStore additive artifact metadata, ProjectService facade, API/CLI/UI generation adapters; reuse existing APEXlayout/APEXlang/SQLcl modules after inspecting their exact contracts.

- [ ] Read existing exporter, layout, code approval and validator contracts; record supported scope modes and prerequisites.
- [ ] Write failing tests for stale/unresolved critical/manual findings, code approval/key/security prerequisites, deterministic bytes, collision detection, safe partial scope, immutable artifacts and concurrent revision changes.
- [ ] Implement one server eligibility policy and generation service invoking the existing exporter. Unsupported executable DB changes remain descriptive candidates.
- [ ] Implement hash-bound validation metadata and explicit validation action; generation never imports.
- [ ] Add API/CLI/real browser generation/validation coverage. Run full regression and independent generation/security review; fix and commit E with exact acceptance.

## F: Snapshot reports and delivery

**Files:** focused `project_reports.py`, service/API/CLI/UI report adapters, report/package tests.

- [ ] Write RED fixtures for escaped HTML, CSV formula injection, executive source/privacy exclusion, manifest hashes, deterministic snapshot bytes, stale labeling and partial generation disclosure.
- [ ] Implement printable executive/technical HTML, CSV/JSON backlog and supported package contents from one consistent persisted snapshot.
- [ ] Reuse generation artifacts by verified hashes. Do not emit misleading SQL or unsupported empty folders.
- [ ] Exercise browser downloads and CLI parity, full regression and independent privacy/package review. Commit F with acceptance.

## G: Candidate acceptance

**Files:** corporate browser/upgrade/scale/stress tests, CI/installer harness only as needed, `docs/quality-acceptance.md`.

- [ ] Run complete real corporate journey and synthetic 100/500-Form scale measurements.
- [ ] Stress descriptor/locator reads, analysis/review/generation/report concurrency without sleep/retry fixes.
- [ ] Run independent security and five-persona product review. Add RED regressions for material findings and fix.
- [ ] Test 1.6.0 saved state migration and actual candidate EXE/MSI install/upgrade/reopen/uninstall/reinstall via existing CI conventions.
- [ ] Run strongest available offline/disposable Oracle/APEX validation and distinguish unavailable runtime evidence.
- [ ] Record exact hardware, fixture, commit, test and installer evidence; commit G fixes/acceptance.

## H: Documentation and release

**Files:** README, CHANGELOG, user guide, forms-to-apex, apex-26-modernization, architecture/project docs, manual-validation-2.0 and canonical version declarations discovered from `docs/releasing.md`.

- [ ] Document only implemented behavior and capture real synthetic-product screenshots.
- [ ] Create executable manual validation checklist with expected results.
- [ ] If all release gates pass, prepare 2.0.0 through repository release contract; run exact candidate Python matrix, Ruff, JS/browser, deterministic export, APEXlang and installers/upgrade.
- [ ] Integrate accepted state according to repository workflow; annotated v2.0.0 and published release only after exact candidate gates pass.
- [ ] Verify remote main/tag/release/assets/download hashes and docs links. If a gate fails, preserve candidate and explicitly report RELEASE BLOCKED.

## Execution evidence

- Initial focused baseline: 42 passed / 1 symlink skip (Python 3.12, Windows); full base previously verified 1,497 passed / 5 skipped.
- Initial frozen artifact check: 24 files, zero Git object hash mismatches against base.
- No implementation gate has passed yet.
