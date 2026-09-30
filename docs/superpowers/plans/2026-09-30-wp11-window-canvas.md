# WP-11 window/canvas declaration slice

Approved bounded design: preserve the existing parsed `Canvas.window_name` and
`Window.primary_canvas` declarations in Blueprint, with evidence-backed
`CANVAS_IN_WINDOW` and `WINDOW_PRIMARY_CANVAS` links. Conflicting declarations
remain separate observed facts; missing targets produce scoped unresolved
references. No default placement is inferred.

Initial base: WP-04 PR #39 head `c911c9d81bc1eb5d1190ae083a00eb2123967e64`.
Worktree: `.worktrees/wp11`; branch `codex/formslang-3-wp11-placement`.
The coordinator owns integration and approves this routine bounded scope.

## Steps

1. Record a clean Blueprint/Case D baseline, then real-fixture failing tests.
2. Implement only the existing window/canvas declaration projection. Keep
   unknown model provenance and missing/ambiguous targets explicit.
3. Check direct/project parity, module scoping and conflict evidence. Bump the
   analysis engine and write a new current inventory, preserving prior bytes.
4. Run related/full tests, Ruff, diff and historical inventory checks. Keep this
   branch isolated; reconcile its merge base after PR #39 integration before
   publishing a Draft PR.

## Boundaries

- SRC-08 is partial: tab/item placement and visual conflict presentation remain.
- SRC-09 raw presence/default provenance is open; parser/model are unchanged.
  Distinct raw duplicate declarations remain pending there too; this slice
  withholds their properties and links with AMBIGUOUS source state, explicit
  reason and source declaration count because legacy visual IDs collapse names.
- SRC-10 unplaced/unresolved groups for canvases without a resolved window and
  for items/tabs remain open. Full graph metadata, bounded focus/path/search
  and product `LEGACY_RESOLVED` handling remain WP-11 work.
- Do not claim `visual_hierarchy_version: 1` for this incomplete hierarchy.
- Shared matrix/evidence updates were deferred until #39 integration. The
  coordinator then authorized factual partial-slice updates; master spec and
  gate criteria remain unchanged.
- Installer agent owns browser helpers. No merge, tag, release or gate closure.

## Evidence

- Baseline: **75 passed, 1 skipped in 5.49 s** (Blueprint plus real ecosystem fixtures).
- Original Case D RED: **3 failed in 0.32 s**, missing declaration attributes,
  unresolved target relation and explicit empty-target state. Minimal GREEN:
  **3 passed in 0.42 s** without weakening assertions.
- Boundary RED after correcting XML namespaces in the new test fixtures:
  **2 failed, 6 passed in 0.39 s** (conflict when the named window is missing;
  placement module omitted from engine identity). GREEN: **8 passed in 0.28 s**.
- Direct/project persisted parity, reopen, module scoping and order stability:
  **10 passed in 0.71 s** before the final inverse-placement negative test.
- Related Blueprint/project/projection/journey/UI regression selection:
  **199 passed, 1 skipped in 41.07 s**. The initial command used two nonexistent
  filenames, exited before collection, and was corrected before this run.
- Current `inventory-wp11.json` matches regeneration. Prior inventory files,
  parser and model have no diff against the WP-04 base.
- Duplicate source declarations: **2 failed, 11 deselected in 0.32 s** before
  withholding ambiguous source properties; **13 passed in 0.69 s** afterwards.
  Both window and canvas duplicates retain a count/reason without a relation.
- Final focused suite: **202 passed, 1 skipped in 39.04 s**. Ruff and diff checks
  pass. All five prior inventories are byte-identical to their `c911c9d` Git
  blobs, including inventory-wp04; inventory-wp11 matches regeneration.
- Full suite with code frozen on Python 3.13: **2088 passed, 5 skipped,
  4 xfailed in 898.28 s (14:58)**, exit 0. Log:
  `.superpowers/sdd/wp11/full-py313.log`. No CI or PR was claimed at that checkpoint.
  WP-04 #39 was independently rebased onto ADR-02 main while this
  WP-11 worktree stayed isolated. Its production/test bytes remained identical,
  and WP-11 merge-base reconciliation was deferred until #39 integration.

## Main composition and publication

- WP-04 #39 passed exact-head 13/13 CI at `9b688ed` and was squash-merged by
  the coordinator as `066288e64c83a11c7b6d78dc26def7e2310f423b`.
- Backup `codex/backup-wp11-before-final-wp04-20260930` preserves `8c5d834`;
  rebasing the two own commits onto `9b688ed` produced identical range-diffs.
  That composed focused run passed **202 tests, 1 skipped in 37.87 s**.
- Backup `codex/backup-wp11-before-main-20260930` preserves `f84f06c`. Rebase
  onto squash main `066288e` was conflict-free; both own commits again have
  identical range-diffs. Final composed focused tests passed **202 tests,
  1 skipped in 37.91 s**. Ruff, diff and current inventory checks passed.
- All five historical inventory files are byte-identical to main; the new
  inventory and all production/test/example bytes are identical to the frozen
  full-suite product tree. The engine transition remains `/5` to `/6`. The full
  local suite was not repeated for these documentation-only base changes;
  exact-head CI is required on the Draft PR before any integration.
- This publication adds factual SRC-08 partial status and evidence only.
  SRC-09/10, the remaining WP-11 work and every product gate remain open.

## Persisted contract and limits

New analysis engine `blueprint-analysis/6` stores `window_name` and
`window_placement` on canvases, `primary_canvas` and `primary_canvas_placement`
on windows. The placement state records target `resolution`, a `conflict` flag
and the other declaration's `conflicting_evidence` IDs. Every new relation is
FACT evidence of the observed property; target resolution is independent and
may be RESOLVED, UNRESOLVED or AMBIGUOUS. References are scoped to the same form.

NOT_DECLARED means the parsed target value is empty, including explicit empty
XML attributes; it does not establish raw attribute absence. Model objects
without captured properties use UNAVAILABLE. Neither state creates a relation,
target or property evidence. A window primary-canvas property never invents an
inverse canvas-window declaration. Placement is static, not runtime visibility.

This is new-analysis persistence only. Existing saved snapshots are not
backfilled, reparsed or relabelled. The new helper participates in both project
and direct engine identity; source revision formulas remain untouched.
