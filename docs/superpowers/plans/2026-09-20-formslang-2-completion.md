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

### E contract refinement (base 3251c04)

Ruling: retain this tracked plan as the execution ledger. The skill's Bash workspace
helper failed Windows path creation and was stopped; no correctness gate depends
on that bookkeeping script. D is already committed and verified; do not repeat it.

Pre-flight interfaces: D returns immutable engine evidence plus human overlays;
E consumes exact source/analysis/review binding. Existing APEXlang consumes one
FormModule and one conversion Store, not an estate graph. F will consume E's
immutable artifact metadata and the same assessment snapshot, never rerun analysis.

Ruling: initial project generation supports selected independent modules (one
APEX application per module). Empty skeleton and multi-module modes are deferred:
an empty shell would not demonstrate modernization and the existing
exporter does not merge multiple modules into one application; fabricating a merger
would violate the one-generation-path constraint. Names include stable source
identity; collisions fail. A reviewed-pages scope can select eligible modules,
not split a module's safety controls across independently generated pages.

Ruling: module conversion sessions use the existing `project_module_session`
registry and Store code decisions. Architecture review never populates APPROVED
code automatically. Source/review/target/code revisions fence preparation,
code approval and generation. A target plan records explicit database/security
prerequisites and row keys; credentials never belong in it.

Ruling: unsupported/disabled execution mappings block usable module generation;
in particular a disabled approval process must not coexist with an enabled save
process. Unsafe scope is omitted with blockers,
not represented as converted. Cost: conservative scope, more individual work.

Artifact publication is staged/versioned and never overwrites an earlier run.
Every output file is hashed; validation binds exact bytes and records tool/mode.
Missing SQLcl means Not Validated, never successful validation. Import is not an
automatic next step. Reads/downloads reauthorize project and path containment.

E implementation sequence: policy RED tests; source-bound module session/code
approval bridge; immutable generator/validation; API+CLI+Generate UI; real browser,
full regression and independent generation review. E gates now passed; exact
acceptance is in quality-acceptance.md (1,598 Python, 130 focused, 74 JS/DOM,
48 project-browser and 101 legacy-browser checks; five known Python skips).

- [ ] Read existing exporter, layout, code approval and validator contracts; record supported scope modes and prerequisites.
- [ ] Write failing tests for stale/unresolved critical/manual findings, code approval/key/security prerequisites, deterministic bytes, collision detection, safe partial scope, immutable artifacts and concurrent revision changes.
- [ ] Implement one server eligibility policy and generation service invoking the existing exporter. Unsupported executable DB changes remain descriptive candidates.
- [ ] Implement hash-bound validation metadata and explicit validation action; generation never imports.
- [ ] Add API/CLI/real browser generation/validation coverage. Run full regression and independent generation/security review; fix and commit E with exact acceptance.

## F: Snapshot reports and delivery

**Files:** focused `project_reports.py`, service/API/CLI/UI report adapters, report/package tests.

Contract refinement: reports use a revision-fenced, read-only snapshot of the
existing assessment/review Store, then reuse Phase C projections. Capture target
plans/artifact/validation metadata from the same checked parent-store transaction.
Do not call the analysis engine or create report/projection tables. Concurrent
changes produce a conflict or an internally consistent historical snapshot, never
mixed revisions. Freshness is checked without reasoning; stale saved assessments
remain exportable with explicit status.

Default executive/technical/backlog outputs exclude source bodies, host paths,
private identity IDs and human notes. Optional notes are an explicitly labeled
sensitive export, separate from executive HTML. Generated APEXlang inclusion is an
explicit package option because it can contain business logic. Verify exact files
and hashes through the existing generation service; unavailable/modified/stale
artifacts are exclusions, not replacement generation. An artifact's validation is
syntax evidence for its bytes, never a new generation authorization.

Output names are fixed/allowlisted and ZIP entries are deterministic with fixed
timestamps. Package manifest hashes every included file except itself; snapshot
identity includes analysis/review/target/artifact/validation state. Export wall time
does not alter bytes. Capture actual assessment/generation/validation timestamps
from persisted records. No fake SQL, empty unsupported directories, estimated
effort, full-source dump or runtime-parity claims.

Interface: one Reports page with executive/technical/risk HTML, backlog CSV/JSON,
decisions JSON and package ZIP downloads. API returns typed attachment bytes with
fixed filenames; CLI uses the same service and exclusive output creation. Browser
downloads carry exact revision preconditions, retain response guards and do not
render exported HTML inside the privileged application origin.

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
- Phase D checkpoint: `8aa534b574bbc868e6b2a119de1051ede1cea9d8`; full Python 1,531 passed / 5 skipped, focused 70, JS/DOM 71, project browser 41/41, legacy 101/101; Ruff/diff clean and 24 frozen hashes unchanged. Independent final review: no Critical/Important findings. See quality-acceptance.md for exact evidence and limits. D1/D2 complete; E-H remain.
