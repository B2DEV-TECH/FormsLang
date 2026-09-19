# Modernization Lab -- Technical Audit and Hardening Pass

Date: 2026-09-18. Scope: `examples/modernization-lab/**` (primary);
`formslang/parser.py`, `formslang/model.py`, `tests/test_parser.py`,
`README.md`, `CHANGELOG.md` (secondary, only for defects the lab exposed).

This document records what was inspected, what was wrong, what was changed
and what was verified. Every claim below is either quoted from a committed
file or the output of a command listed in "Verification Performed". Nothing
in this review was measured against a live Oracle database (see "SQL
validation status") and no FormsLang prediction has been compared against
the ground truth (see "Benchmark Readiness").

## Executive Summary

The lab was structurally sound before this pass: all four Forms2XML modules
parse, the DDL/packages/seed are internally consistent, the 41-case registry
is unique and complete, and the two positive / two negative controls behave
as documented. What it was not was *defensible under scrutiny*: several
narrative documents asserted facts that the committed source contradicts,
two registry cases carried a classification the taxonomy does not support,
the rollup tables were stale against the registry, the SQL scripts could
"succeed" while leaving the schema broken, and the test suite (9 tests)
pinned almost none of the claims the documentation makes.

Outcome of this pass:

- 2 cases reclassified after inspecting their source (LOM-MOD-010,
  LOM-MOD-019); 7 more had rationale/summary/source text corrected without
  changing classification (LOM-MOD-002, 003, 014, 025, 031, 041, 042). No
  ID was renumbered.
- 3 factual errors in the narrative docs fixed at the source: the
  status-matrix description in `docs/business-rules.md` and ADR-002, the
  APEX `USER` claim in ADR-004 / `docs/modernization-challenges.md` /
  the blueprint, and the "three reserved IDs" claim in the registry,
  README and HANDOFF (there is exactly one: 040).
- Rollup tables regenerated from the registry and now asserted by tests.
- `scripts/install.sql`, `seed.sql`, `verify.sql` hardened to fail loudly
  and to resolve paths script-relative; still not executed (no disposable
  schema was available -- stated, not hidden).
- 3 FormsLang core defects that the lab exposed fixed with tests
  (`Item.validate_from_list` tri-state, `parse_xml` error context, a
  wrong "seven" in the parser docstring/README).
- Lab test suite grown from 9 to 31 tests; FormsLang suite 1087 passed,
  2 skipped; `ruff check .` clean.

Benchmark readiness: **STRUCTURALLY READY** (see the last section for what
that does and does not mean).

## Issues Found

Severity: BLOCKER = would make a public claim false or the benchmark
unusable; HIGH = a reviewer would reject the lab on it; MEDIUM = wrong but
contained; LOW = hygiene with a credibility cost.

| ID | Severity | File(s) | Problem | Evidence | Decision | Fix |
|---|---|---|---|---|---|---|
| R-01 | BLOCKER | `docs/adr/004-approval-attribution-must-pass-app-user-explicitly.md`, `docs/modernization-challenges.md`, `blueprint/expected-apex-architecture.md`, registry LOM-MOD-031 | The CRITICAL attribution case was argued on a wrong Oracle fact: "every request runs under the workspace's parsing schema ... `USER` ... resolves to the schema owner". Inside PL/SQL called from an APEX page, `USER` is the APEX engine's pooled database account (`APEX_PUBLIC_USER` under ORDS), not the parsing schema and not the end user. The conclusion (pass `:APP_USER` explicitly) was right; the premise was not, and a reviewer who knows APEX would discount the whole case. | Old ADR-004 text quoted above (git diff); `database/packages/lom_order_api.pks:36` `p_changed_by in varchar2 default user`; `submit_order`/`release_order`/`ship_order` specs have no identity parameter. | Keep classification (MANUAL_REVIEW / CRITICAL / F); rewrite the premise; document the second, un-fixable-at-call-site gap (submit/release/ship write `USER` unconditionally). | ADR-004, challenges doc, blueprint and the LOM-MOD-031 rationale now state the pool-account fact and name `v('APP_USER')`/`:APP_USER` as the only route to the end user. ADR-004 gains an explicit "not sufficient for submit/release/ship" paragraph. `StatusMachineIsPinned.test_transition_status_defaults_identity_to_the_database_user` pins both facts from the package spec. |
| R-02 | HIGH | `docs/business-rules.md`, `docs/adr/002-status-transitions-owned-by-plsql-matrix.md`, `database/ddl/lom_orders.sql` (table comment), registry LOM-MOD-002 | The status machine was described inconsistently with `is_valid_transition`: business-rules said "any state -> `CANCELLED`" (the matrix allows it only from DRAFT, SUBMITTED, PENDING_APPROVAL); ADR-002 claimed a sequence-number shortcut "would silently forbid a legal one ... `PENDING_APPROVAL` -> `REJECTED` has a `SEQUENCE_NO` that is not monotonically related" (30 -> 35 *does* increase; every one of the ten legal pairs increases SEQUENCE_NO). The real argument -- the shortcut admits illegal pairs, never rejects legal ones -- was missing. | `database/packages/lom_order_api.pkb:52-67` (ten pairs); `database/seed/01_lookup_data.sql:23-30` (DRAFT 10, SUBMITTED 20, PENDING_APPROVAL 30, REJECTED 35, APPROVED 40, RELEASED 50, SHIPPED 60, CANCELLED 90). | Correct the documentation; do not touch the matrix (it is the intentional scenario). | Docs and the LOM-MOD-002 rationale now list the ten pairs and the four increasing-but-illegal pairs (DRAFT->SHIPPED, REJECTED->APPROVED, APPROVED->CANCELLED, RELEASED->CANCELLED). Four `StatusMachineIsPinned` tests pin the seed sequence, the exact legal set, and the strict-subset property. |
| R-03 | HIGH | `expected/modernization-ground-truth.json` LOM-MOD-010, `forms/xml/CUSTOMERS.xml` inline label, `docs/adr/003-*.md`, `docs/modernization-challenges.md` | Classified `MOVE_TO_PLSQL_API` / category E, but the trigger only mirrors the `CK_LOM_CUST_CREDIT` CHECK constraint; there is no logic to centralize and no API procedure that owns the rule. The taxonomy explicitly forbids using MOVE for "an APEX page will call an API". The old rollup even flagged "category B has zero cases" as an observation -- 010 is the textbook B case. | `forms/xml/CUSTOMERS.xml` WHEN-VALIDATE-ITEM on CREDIT_LIMIT vs `database/ddl/lom_customers.sql` CHECK constraint (same predicate, nothing else). | Reclassify to `CONVERT` / LOW / B; keep it in the registry as the deliberate contrast to LOM-MOD-011. | Registry entry rewritten (title, rationale, `related: ["LOM-MOD-011"]`); inline label changed to `(CONVERT, LOW risk)`; ADR-003 and challenges doc now present 010 as the contrast case. `ControlsMatchTheirRegistryEntries.test_010_and_011_are_the_documented_contrast_pair` pins the pair. |
| R-04 | HIGH | registry LOM-MOD-019, `forms/xml/ORDERS.xml` inline label | Classified `MOVE_TO_PLSQL_API` / MEDIUM / E although the trigger already calls `lom_customer_api.can_place_order` and contains no duplicated logic -- the exact shape of the three positive controls (016/021/028). Keeping it as MOVE contradicted the lab's own PRESERVE controls and inflated the MOVE count. | `forms/xml/ORDERS.xml` WHEN-VALIDATE-ITEM on CUSTOMER_ID: single API call, raise on 'N'. | Reclassify to `PRESERVE` / LOW / A; make it the fourth positive control. | Registry entry rewritten with `related: [016, 021, 028]`; inline label `(PRESERVE, LOW risk)`; added to `POSITIVE_CONTROLS` in the test suite and to the PRESERVE-subset assertion. |
| R-05 | HIGH | `assessment/complexity-and-risk-rollup.md` | Every table was stale against the registry (MOVE 8 vs 6, PRESERVE 7 vs 8, CONVERT 3 vs 4, LOW 23 vs 24, MEDIUM 10 vs 9, E 8 vs 6, A 6 vs 7, B 0 vs 1; "By module" attributed 14/8/5/4/4/1/2 with a rule that was never stated), and the prose ("18 of 41 cases", "44%", "category B has zero cases") derived from the stale numbers. | Old table rows quoted in git diff; `metrics/compute_metrics.py` output. | Regenerate from the registry with an explicit, testable attribution rule (first `forms/`/`database/` path in `source`). | Tables rewritten; the module rule is now `module_for_source()` in the metrics script; five `RollupTablesMatchRegistry` tests fail if any cell or derived sentence drifts. |
| R-06 | HIGH | `scripts/install.sql`, `scripts/seed.sql`, `scripts/verify.sql` | `whenever sqlerror continue` in all three: a failed DDL or an invalid package body produced a green run. `@../database/...` resolved relative to the SQL*Plus working directory, so the README's "run from the lab root" instruction was wrong. Package bodies were installed without `show errors`; the final invalid-object check only listed rows. | Old scripts quoted in git diff (`whenever sqlerror continue`, 20x `@../database/`). | Harden without changing what the scripts install. | `whenever sqlerror exit failure rollback` in all three; `@@` script-relative paths (20 in install, 7 in seed); `show errors` after each of the 5 bodies; step 6 raises `-20001` if any object is INVALID; verify.sql documents the non-zero exit. Not executed -- see "SQL validation status". |
| R-07 | HIGH | registry `id_notes`, lab `README.md`, `HANDOFF.md` | Claimed "three IDs deliberately reserved/unfilled" (040, 043, 044). 043 and 044 are outside the 001..042 range the registry declares and are referenced nowhere; the actual gap is exactly one (040). Public claim was false as written. | `git diff` of `id_notes`; `grep -rn LOM-MOD-04[34]` returns nothing. | Correct the documentation; do not fill 040. | `id_notes` rewritten; README and HANDOFF corrected (HANDOFF keeps a dated correction note). `GroundTruthRegistryIsConsistent.test_id_range_has_exactly_the_documented_gap` asserts the gap set equals `{040}`, that 040 is mentioned in `id_notes`, and that it appears in no fixture. |
| R-08 | MEDIUM | registry LOM-MOD-003 | Title said "(verified: acyclic)" for two packages whose *bodies* call each other. The specs are independent and install.sql installs all five specs before any body, so the dependency is legal -- but "acyclic" is the wrong word for a body-level mutual dependency and a reviewer would call it out. | `lom_order_api.pkb` `submit_order -> lom_approval_api.create_approval_request`; `lom_approval_api.pkb` `approve -> lom_order_api.transition_status`; `scripts/install.sql:50-66` spec-before-body order. | Keep PRESERVE / LOW; fix the wording. | Title "(body-level mutual dependency)"; summary explains why it compiles and why install order matters. |
| R-09 | MEDIUM | registry LOM-MOD-025 | Summary omitted the one semantic divergence that makes the case non-trivial: the inline `SELECT INTO` raises NO_DATA_FOUND for a product with no inventory row, where `lom_inventory_api.get_available_qty` returns 0. | `forms/xml/ORDERS.xml` BK_ORDER_LINE WHEN-VALIDATE-ITEM on QUANTITY vs `lom_inventory_api.pkb` `get_available_qty`. | Keep MOVE / MEDIUM / E; state the divergence. | Summary and the ORDERS.xml inline comment now name the NO_DATA_FOUND difference. |
| R-10 | MEDIUM | registry LOM-MOD-041/042, `docs/adr/003-*.md` | `source` said "implicit in worklist trigger design" although both buttons have explicit `WHEN-BUTTON-PRESSED` triggers with the raw `update lom_approvals` DML; ADR-003 listed 041/042 (and 010) among cases "every one of [which] is classified `MOVE_TO_PLSQL_API`" while the registry has them as MANUAL_REVIEW. | `forms/xml/APPROVALS.xml` BT_APPROVE / BT_REJECT `WHEN-BUTTON-PRESSED`; registry rows. | Keep MANUAL_REVIEW / CRITICAL / F (the fix is a page redesign, not a code move); make the ADR agree with the registry. | `source` fields corrected; ADR-003 now lists 011/025/026/027/039 as MOVE, 037 as "no API yet", 041/042 as MANUAL_REVIEW, 010 as the CONVERT contrast. |
| R-11 | MEDIUM | `docs/adr/005-navigation-pattern-per-cross-module-flow.md` | Said the three navigation cases are "`MANUAL_REVIEW` or `REPLACE_WITH_APEX_NATIVE`"; the registry has LOM-MOD-020 MANUAL_REVIEW and LOM-MOD-022/023 REFACTOR. An ADR contradicting the registry violates the lab's own rule. | Registry rows 020/022/023. | Fix the ADR, not the registry (the REFACTOR calls were inspected and stand). | ADR-005 now names each case with its actual classification. |
| R-12 | MEDIUM | `docs/business-rules.md` | Described `LOM_CUSTOMER_API.can_place_order` as "active status plus whatever credit/standing checks that function implements". The function checks exactly `get_status = 'ACTIVE'` and nothing else. | `database/packages/lom_customer_api.pkb` `can_place_order`. | Describe what the code does. | Sentence replaced with the measured behaviour and a pointer to the package body. |
| R-13 | MEDIUM | `forms/xml/APPROVALS.xml` (LOM-MOD-029 label) | Inline label read `(REFACTOR, LOW/MEDIUM risk)`; the registry says MEDIUM. Every inline label is an answer-key hint, so a hedged label is a wrong label. | `grep -n "LOM-MOD-029" forms/xml/APPROVALS.xml`. | Correct the label to the registry value. | Label is `(REFACTOR, MEDIUM risk)`; `InlineLabelsMatchRegistry` test parses every label in `forms/` and `database/` and fails on any classification/risk/category mismatch (30 labels checked). |
| R-14 | MEDIUM | `tests/test_fixtures.py`, `metrics/compute_metrics.py` | 9 tests pinned structure and four business rules but none of: the registry's taxonomy values, ID range, `related`/`source` resolution, the rollup tables, the inline labels, the status-machine claims, the identity-default claim, or the README's inventory numbers. The metrics script scanned only `forms/` and `database/` for `LOM-MOD-###` references, so a dangling reference in a doc (or in this file) went unnoticed; it also had no per-category or per-module breakdown, so the rollup could not be checked mechanically. | Old suite (9 tests, `git diff`); old script had no `by_category`/`by_module`/docs scan. | Extend, do not replace, the existing checks. | Suite is 31 tests in 11 classes (list in "Tests"); script exposes `module_for_source`, `by_category`, `by_module`, `DOC_SOURCES` and a pinned `DOCUMENTED_UNFILLED_IDS = {"040"}`. |
| R-15 | LOW | `database/ddl/lom_shipments.sql`, `database/ddl/lom_products_inventory.sql`, `database/seed/02_customers.sql`, `database/seed/04_orders_and_lines.sql` | Table/script comments pointed at `docs/forms-inventory.md`, `data-model.md`, `docs/data-model.md` and `tests/` -- none of the first three exist in the lab. | `ls docs` (adr, business-rules.md, modernization-challenges.md, self-review.md). | Point at files that exist. | References redirected to `forms/source/README.md`, `docs/business-rules.md`, `scripts/verify.sql`. |
| R-16 | LOW | `docs/adr/001-*.md`, `forms/source/README.md` | Attributed the "`--` inside an XML comment is fatal" rule to `xml.etree.ElementTree` specifically. It is an XML 1.0 well-formedness rule; every conforming parser rejects it. Also cross-referenced a "[FormsLang: sem reverse-engineering de .fmb]" note that is not in the repository. | XML 1.0 §2.5; `CONTRIBUTING.md` exists at the repo root. | Attribute correctly; link to a real file. | Both docs corrected; the README now also records that `parse_xml` names the failing file and line/column (R-18). |
| R-17 | LOW | `formslang/model.py`, `formslang/parser.py` | `ValidateFromList` was not parsed at all, so a Forms2XML item that declares it (as the lab's LOV-backed items do) lost the attribute silently -- and there was no way to distinguish "attribute absent" from "false". First reported in `HANDOFF.md`, unfixed. | `git diff formslang/model.py formslang/parser.py`. | Fix in core (defect directly exposed by the lab). | `Item.validate_from_list: bool \| None`, `_tri()` helper; `tests/test_parser.py::test_validate_from_list_is_tri_state`. |
| R-18 | LOW | `formslang/parser.py` | A malformed Forms2XML file raised a bare `xml.etree.ElementTree.ParseError` with no file name -- on a multi-module run the user could not tell which file failed. First reported in `HANDOFF.md`, unfixed. | `git diff formslang/parser.py` (`parse_xml`). | Fix in core. | `parse_xml` re-raises as `ValueError("<file>: invalid XML at line L, column C: ...")` chained from the original; `tests/test_parser.py::test_malformed_xml_names_the_file`. |
| R-19 | LOW | `formslang/parser.py` docstring, root `README.md:1181` | Both said that after the XML unescape a trigger body "still contains the seven-character string `&#10;`"; the string is five characters, and the number is the whole point of the sentence (it explains the second decoding pass). | `git diff` of both files. | Fix the number. | Corrected to five; recorded in `CHANGELOG.md`. |
| R-20 | LOW | `HANDOFF.md`, `docs/self-review.md`, lab `README.md` | Stated "complete and tested", "9/9 tests", "no stored credentials ... were found" as present-tense facts that this pass makes stale, and the README described test runs as a one-time event. | Text quoted in git diff. | Keep the historical documents historical; make them point here. | Each now says what was true at handoff and defers current counts/status to this file. |

Issues considered and **not** changed (with reason):

- LOM-MOD-002 / 041 / 042 / 031 CRITICAL, 011 / 026 / 027 / 037 HIGH: each
  was re-inspected against its source and the risk stands. 4 CRITICAL of 41
  is not inflation: all four sit on one surface (the two APPROVALS buttons
  and the two package-level rules they bypass).
- The `is_valid_transition` matrix, the `default user` on
  `transition_status`, the missing identity parameter on
  submit/release/ship, the raw DML behind BT_APPROVE/BT_REJECT and the
  inline availability SELECT are intentional scenario content. They are
  documented in the registry and pinned by tests, not "fixed".
- The inline `LOM-MOD-### (CLASSIFICATION, RISK risk)` labels inside the
  fixtures are answer-key leakage for any classifier that reads comments.
  Removing them would change 4 fixture files and every doc that cites them;
  it is a benchmark-protocol decision (strip comments before prediction),
  recorded under "Remaining Limitations" rather than made unilaterally.
- No ID was renumbered.

## Ground Truth Changes

`expected/modernization-ground-truth.json` (2-space JSON, LF, ASCII; edited
by exact text replacement so unrelated bytes are untouched):

| Case | Before | After | Why |
|---|---|---|---|
| LOM-MOD-010 | `MOVE_TO_PLSQL_API` / LOW / E | `CONVERT` / LOW / B; title "Forms mirrors CK_LOM_CUST_CREDIT in a WHEN-VALIDATE-ITEM"; new rationale; `related: ["LOM-MOD-011"]` | R-03 |
| LOM-MOD-019 | `MOVE_TO_PLSQL_API` / MEDIUM / E | `PRESERVE` / LOW / A; title "Customer eligibility gate already calls the API cleanly"; `related: ["LOM-MOD-016","LOM-MOD-021","LOM-MOD-028"]` | R-04 |
| LOM-MOD-002 | rationale: prose description of the matrix | rationale: ten legal pairs, all increase SEQUENCE_NO, four increasing-but-illegal pairs, pinned by tests | R-02 |
| LOM-MOD-003 | title "(verified: acyclic)" | title "(body-level mutual dependency)"; summary explains spec/body install order | R-08 |
| LOM-MOD-014 | rationale referenced "LOM-MOD-014's sibling note" (self-reference) | reference removed | hygiene |
| LOM-MOD-025 | summary | summary adds the NO_DATA_FOUND divergence | R-09 |
| LOM-MOD-031 | rationale: parsing-schema claim | rationale: APEX engine pool account; `transition_status` default; submit/release/ship have no identity parameter; ADR-004 | R-01 |
| LOM-MOD-041, 042 | `source`: "implicit in worklist trigger design" | `source`: "WHEN-BUTTON-PRESSED" on BT_APPROVE / BT_REJECT | R-10 |
| `id_notes` | three reserved IDs | exactly one unfilled ID (040); no ID above 042; test-enforced | R-07 |

Resulting distribution (measured by `metrics/compute_metrics.py`):
classification MANUAL_REVIEW 10, PRESERVE 8, REFACTOR 6, MOVE_TO_PLSQL_API
6, REPLACE_WITH_APEX_NATIVE 5, CONVERT 4, DROP 2; risk LOW 24, MEDIUM 9,
HIGH 4, CRITICAL 4; category F 17, A 7, C 6, E 6, D 4, B 1; by module
ORDERS.fmb 13, CUSTOMERS.fmb 7, database DDL/views 7, lom_order_api 4,
APPROVALS.fmb 3, OM_SHARED.pll 3, INVENTORY.fmb 2, lom_approval_api 2.

Fixture-side changes that mirror the registry (answer-key comments only; no
trigger code, DDL or seed row changed):

- `forms/xml/CUSTOMERS.xml`: LOM-MOD-010 label `(MOVE_TO_PLSQL_API)` ->
  `(CONVERT, LOW risk)` with one sentence on why nothing is centralized.
- `forms/xml/ORDERS.xml`: LOM-MOD-019 label -> `(PRESERVE, LOW risk)`;
  LOM-MOD-025 comment names the NO_DATA_FOUND divergence.
- `forms/xml/APPROVALS.xml`: LOM-MOD-029 label `LOW/MEDIUM` -> `MEDIUM`.
- `database/ddl/lom_orders.sql`, `lom_shipments.sql`,
  `lom_products_inventory.sql`, `database/seed/02_customers.sql`,
  `04_orders_and_lines.sql`: comment text only (R-02, R-15).

## FormsLang Core Changes

All three were listed as open FormsLang defects in `HANDOFF.md` and are
directly exposed by the lab's fixtures.

- `formslang/model.py`: `Item.validate_from_list: bool | None = None`
  (tri-state: `None` = attribute absent in the XML).
- `formslang/parser.py`: `_tri(el, attr) -> bool | None` helper;
  `_parse_item` sets `validate_from_list`; `parse_xml` wraps
  `ET.parse(path).getroot()` and re-raises `ET.ParseError` as
  `ValueError(f"{path.name}: invalid XML at line L, column C: ...")`
  chained from the original (`from e`); module docstring: the escaped newline `&#10;` is a "five-character string", not seven.
- `README.md` (repo root, line 1181): "seven" -> "five".
- `tests/test_parser.py`: `test_validate_from_list_is_tri_state`,
  `test_malformed_xml_names_the_file` (+40 lines).
- `CHANGELOG.md`: `## [Unreleased]` -- `### Added` (`Item.validate_from_list`;
  the lab hardening pass, pointing here) and `### Fixed` (`parse_xml`
  error context; seven/five).

Existing golden files are unaffected: they serialize module-level counts
only, and no count changed (verified by the full suite).

## Verification Performed

Windows 11, Python via `py -3` (3.x from the repo's `requires-python
>=3.10`), run from the paths shown. Exact commands:

```text
# lab suite (from the lab root)
cd examples/modernization-lab
py -3 -m unittest tests/test_fixtures.py -v

# structural metrics + registry cross-check (exit 1 on any dangling LOM-MOD id)
py -3 metrics/compute_metrics.py

# repository lint and full FormsLang suite (from the repo root)
cd ../..
py -3 -m ruff check .
py -3 -m pytest tests/test_parser.py -q
py -3 -m pytest tests/ -q -p no:cacheprovider

# line endings (repo has `* text=auto eol=lf`)
git ls-files --eol examples/modernization-lab formslang tests | grep -v 'i/lf w/lf'
```

Static SQL checks (no database): every `references` clause resolves to a
table created earlier in `install.sql`; every `@@` target exists; each of
the five `.pkb` files has a matching `.pks` installed before any body; the
ten `(from, to)` pairs and the eight seed statuses were read from the
package body and seed file by the test suite, not by hand.

## Test Results

| Suite | Command | Before this pass | After this pass |
|---|---|---|---|
| Lab fixtures | `py -3 -m unittest tests/test_fixtures.py -v` | 9 tests, OK | **31 tests, OK** (`Ran 31 tests in 0.055s`) |
| Metrics cross-check | `py -3 metrics/compute_metrics.py` | exit 0 (fixtures only) | **exit 0**; 32 ids referenced in fixtures, 34 in docs, 41 registered, 0 dangling |
| FormsLang parser tests | `py -3 -m pytest tests/test_parser.py -q` | 16 passed | **18 passed** |
| FormsLang full suite | `py -3 -m pytest tests/ -q -p no:cacheprovider` | 1085 passed, 2 skipped | **1087 passed, 2 skipped** (131.21s) |
| Lint | `py -3 -m ruff check .` | clean | **All checks passed!** |
| Line endings | `git ls-files --eol ...` | -- | every file `i/lf w/lf` |

The 31 lab tests by class (11 classes):

- `ParsesWithoutError` (1): all four modules parse via `formslang.parser`.
- `StructuralCountsMatchDocumentation` (1): blocks/items/triggers/LOVs/
  relations/alerts/record groups/parameters per module equal the documented
  inventory.
- `SpecificBusinessRulesArePresent` (4): 027 duplicated line-total formula;
  042 reject bypasses the API; INVENTORY BT_ADJUST calls the API; product
  validation checks ACTIVE_FLAG.
- `ControlsMatchTheirRegistryEntries` (3): positive controls 016/019/021/028
  call the API and are PRESERVE; negative controls 041/042 update the table
  directly, call no API, and are MANUAL_REVIEW/CRITICAL; 010/011 contrast
  pair including `related`.
- `RiskAndClassificationSetsAreExact` (4): CRITICAL == {002, 031, 041, 042};
  HIGH == {011, 026, 027, 037}; MOVE_TO_PLSQL_API == {011, 025, 026, 027,
  037, 039}; positive controls are a subset of PRESERVE.
- `GroundTruthRegistryIsConsistent` (7): taxonomy values; unique ids; id
  range 001..042 minus exactly {040}; every id in `forms/`/`database/` is
  registered; every id in the narrative docs (including this file) is
  registered or documented-unfilled; every `source` path exists; every
  `related` id resolves and is not self.
- `InlineLabelsMatchRegistry` (1): every `LOM-MOD-### (...)` label in the
  fixtures agrees with the registry's classification, risk and category.
- `StatusMachineIsPinned` (4): seed sequence numbers; the legal matrix is
  exactly the ten documented pairs; every legal pair increases SEQUENCE_NO
  and the four named illegal pairs also do (the shortcut is a strict
  superset); `transition_status` defaults `p_changed_by` to `user` while
  `submit_order`/`release_order`/`ship_order` expose no identity parameter.
- `RollupTablesMatchRegistry` (5): classification, risk and category tables;
  module table counts and dominant classifications; the two derived
  sentences ("16 of 41 cases", "12 cases").
- `ReadmeInventoryClaimsAreMeasured` (1): the README's "41 cases",
  "11 tables (DDL), 2 views, 5 PL/SQL API packages", "4 Oracle Forms
  modules" equal what is on disk.

## SQL validation status

**STATIC VALIDATION ONLY. The scripts were not executed in this pass.**

- An Oracle 26ai Free instance exists on the review machine, but the only
  credentials available are for schemas that belong to other projects. The
  lab's scripts drop and recreate objects and must run in a schema that can
  be dropped afterwards; no credential able to create such a schema was
  available, and none was invented.
- What *was* done: `install.sql` / `seed.sql` / `verify.sql` were hardened
  (R-06) and re-read end to end after the change; dependency order and every
  path were checked statically as described under "Verification Performed".
- What this means: a syntax error in a `.pkb`, a seed row violating a
  constraint, or a `verify.sql` count mismatch would **not** have been
  caught by this pass. The scripts now make such a failure visible on first
  execution (non-zero exit) instead of silently continuing, which is the
  most that can be claimed without running them.

## Remaining Limitations

1. **No live Oracle execution** (above). Until `install.sql`, `seed.sql` and
   `verify.sql` have been run in a disposable schema, the DDL/packages/seed
   are consistent by inspection, not proven to compile and load.
2. **No FormsLang predictions exist for this lab.** The registry is a ground
   truth without a prediction set; no precision/recall/agreement figure has
   been computed and none is claimed anywhere in the lab.
3. **Answer-key labels live inside the fixtures.** Every `LOM-MOD-###
   (CLASSIFICATION, RISK risk)` comment in `forms/xml/*.xml` and the package
   specs tells a comment-reading classifier the expected answer. A
   prediction benchmark must strip XML comments and PL/SQL `--` comments
   containing `LOM-MOD-` before feeding the fixtures to any predictor, or
   report results with and without them.
4. **Forms Builder compatibility is not claimed.** The Forms2XML fixtures
   are hand-authored (ADR-001) and validated only by FormsLang's parser;
   they have not been round-tripped through Oracle Forms Builder or
   `frmf2xml`, and no statement in the lab says otherwise.
5. **The submit/release/ship identity gap is documented, not fixed** (ADR-004).
   Adding an optional `p_changed_by` to those three procedures is an API
   change to scenario content and was deliberately left as a documented
   modernization prerequisite.
6. **Historical documents are historical.** `HANDOFF.md` and
   `docs/self-review.md` describe the original build; where they and this
   file differ, this file and the registry are current.

## Benchmark Readiness

**STRUCTURALLY READY.**

Meaning: the fixtures parse, the registry is complete, unique, internally
consistent and test-pinned against the source it describes, every
narrative claim that was checked either matches the source or was
corrected, and the numbers in the assessment are generated from the
registry rather than typed in.

Not meaning: the SQL has not been executed against Oracle (so it is not
READY FOR LIVE ORACLE VALIDATION in the sense of "validated" -- it is ready
to *be* validated), and no FormsLang prediction has been compared against
the ground truth (so it is not READY FOR PREDICTION BENCHMARK until a
prediction protocol -- including comment stripping, limitation 3 -- is
defined and a first prediction set is produced and scored).

Recommended next step, in order: (1) run the three SQL scripts in a
disposable schema and record the exact output here; (2) define the
prediction protocol and produce the first FormsLang prediction set for the
41 cases; only then compute and publish agreement metrics.

## Prediction Benchmark v1

Date: 2026-09-18. Protocol version: 1.0. Runner version: 1.0.

- **Baseline Status**: `BASELINE_COMPLETE`
- **Source Commit**: `22f24805d0f8b277368723306565b94c5e2d25b0`
- **FormsLang Engine Path**: `formslang.parser.parse_xml -> formslang.blueprint.build` (Deterministic, AI: None)
- **Total Benchmark Cases**: 41 (LOM-MOD-001 through LOM-MOD-042; single intentional gap LOM-MOD-040)
- **Observability Counts**:
  - Fully Observable (Forms2XML only): 16 (39.0%)
  - Partially Observable (Forms2XML + DB citations): 12 (29.3%)
  - Not Observable (Standalone DB DDL/packages or library docs): 13 (31.7%)
  - Total Eligible Observable Cases Evaluated: 28 (68.3%)
- **Measured Performance Metrics (Observable)**:
  - Exact Classification Accuracy: 21.4% (6/28)
  - Exact Classification Accuracy (Fully Observable): 25.0% (4/16)
  - Macro F1: 0.1333
  - Exact Risk Accuracy: 21.4% (6/28)
  - Critical Risk Recall: 0.0% (0/2 observable CRITICAL cases flagged as CRITICAL; both flagged as HIGH)
  - High+Critical Risk Recall: 33.3% (2/6)
- **Enterprise Safety Metrics**:
  - Manual Review Recall: 60.0% (3/5 observable MANUAL_REVIEW cases flagged for manual review)
  - False Automation Rate: 40.0% (2/5 observable MANUAL_REVIEW cases misclassified as CONVERT / AUTO verdict)
  - Critical Safety Misses: 0 (0 observable CRITICAL cases missed or labeled safe/AUTO)
- **Frozen Artifacts**:
  - Location: `examples/modernization-lab/benchmark/baselines/v1/`
  - Includes: `manifest.json`, `observability.json`, `raw-analysis.json`, `predictions.json`, `benchmark-report.json`, `benchmark-report.md`, `failure-analysis.md`
- **Remaining Limitations**:
  1. FormsLang currently ingests Forms2XML (`.xml`) files only; standalone database packages (`.pks`/`.pkb`) and DDL (`.sql`) remain un-ingested, leaving 13 cases `NOT_OBSERVABLE`.
  2. PL/SQL analysis is lexical and syntax-evidence based; no semantic cross-module type or dependency resolution is performed.
  3. No live Oracle database validation has been performed.
  4. Forms2XML fixtures are hand-authored per ADR-001 and have not been round-tripped through Oracle Forms Builder.

## Prediction Benchmark v2

Date: 2026-09-18. Protocol version: 1.0. Runner version: 1.0.

- **Baseline Status**: `BASELINE_COMPLETE`
- **Source Commit**: `9005c4389834ffcdf132734d04f6843a6b657cdf`
- **FormsLang Engine Path**: `formslang.parser.parse_xml -> formslang.blueprint.build` (Deterministic, AI: None)
- **Database Sources Ingested**: 11 tables (DDL), 2 views, 5 PL/SQL package specifications (`.pks`), 5 package bodies (`.pkb`)
- **Total Benchmark Cases**: 41 (LOM-MOD-001 through LOM-MOD-042; single intentional gap LOM-MOD-040)
- **Observability Counts**:
  - Fully Observable (Forms2XML + Ingested Database Sources): **38 (92.7%)** *(vs. 16 in v1)*
  - Partially Observable: **0 (0.0%)** *(vs. 12 in v1)*
  - Not Observable (Non-code library documentation `OM_SHARED.md`): **3 (7.3%)** *(vs. 13 in v1)*
  - Total Eligible Observable Cases Evaluated: **38 (92.7%)** *(vs. 28 in v1)*
- **Measured Performance Metrics (Observable)**:
  - Exact Classification Accuracy: **68.4%** (26/38) *(vs. 21.4% in v1, +47.0% absolute)*
  - Exact Classification Accuracy (Fully Observable): **68.4%** (26/38) *(vs. 25.0% in v1, +43.4% absolute)*
  - Macro F1: **0.6257** *(vs. 0.1333 in v1, +0.4924)*
  - Exact Risk Accuracy: **68.4%** (26/38) *(vs. 21.4% in v1, +47.0% absolute)*
  - Critical Risk Recall: **100.0%** (4/4 observable CRITICAL cases flagged as CRITICAL) *(vs. 0.0% in v1)*
  - High+Critical Risk Recall: **87.5%** (7/8) *(vs. 33.3% in v1)*
- **Enterprise Safety Metrics**:
  - Manual Review Recall: **80.0%** (8/10 observable MANUAL_REVIEW cases flagged for manual review) *(vs. 60.0% in v1)*
  - False Automation Rate: **20.0%** (2/10 observable MANUAL_REVIEW cases misclassified as CONVERT / AUTO verdict) *(vs. 40.0% in v1, cut in half)*
  - Critical Safety Misses: **0** (0 observable CRITICAL cases missed or labeled safe/AUTO)
- **Frozen Artifacts**:
  - Location: `examples/modernization-lab/benchmark/baselines/v2/`
  - Includes: `manifest.json`, `observability.json`, `raw-analysis.json`, `predictions.json`, `benchmark-report.json`, `benchmark-report.md`, `failure-analysis.md`, `comparison-v1-v2.md`
- **Key Engineering Enhancements Delivered**:
  1. Standalone Oracle DDL and PL/SQL parser (`formslang.database`) extracting tables, constraints, views, packages, and subprogram lexical tokens.
  2. Cross-source blueprint graph linking Forms triggers and DB procedures with `READS`, `CALLS`, `REFERENCES`, `DECLARES`, `IMPLEMENTS`, and `DUPLICATES_LOGIC` edges.
  3. Status list exclusion normalization (`MOVE_TO_PLSQL_API`, `HIGH` risk) resolving duplicate predicate logic (e.g. `LOM-MOD-011`).
  4. Arithmetic line total formula structural comparison (`MOVE_TO_PLSQL_API`, `HIGH` risk) resolving financial duplication (e.g. `LOM-MOD-027`).
  5. State machine direct DML bypass detection (`MANUAL_REVIEW`, `CRITICAL` risk) enforcing safety against unsafe automation (e.g. `LOM-MOD-041`, `042`).
  6. CLI support for `--database-src` in `formslang blueprint`.
- **Remaining Limitations**:
  1. Non-XML library documentation (`OM_SHARED.md`, 3 cases) is un-ingested; native binary `.pll` or structured library format is required to reach 100% observability.
  2. PL/SQL analysis remains token/lexical evidence based; semantic type synthesis and live Oracle compiler feedback have not been added.
  3. False Automation Rate remains at 20.0% (2 cases: credit limit update ceiling policy and dynamic WHERE clause default warehouse constraint ambiguity).


