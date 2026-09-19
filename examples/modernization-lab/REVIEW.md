# Modernization Lab -- Technical Audit and Hardening Pass

Date: 2026-09-18. Scope: `examples/modernization-lab/**` (primary);
`formslang/parser.py`, `formslang/model.py`, `tests/test_parser.py`,
`README.md`, `CHANGELOG.md` (secondary, only for defects the lab exposed).

This document records what was inspected, what was wrong, what was changed
and what was verified. Every claim below is either quoted from a committed
file or the output of a command listed in "Verification Performed".

Later work is appended rather than folded in, so the 2026-09-18 findings
stay readable as they were written. **2026-09-19: the SQL scripts have now
been executed against a live Oracle instance** in a disposable schema, which
the original pass could not do -- see "SQL validation status", which replaces
the "static validation only" statement that stood there, and R-21/R-22,
two defects that execution exposed in the very scripts the original pass had
hardened. Prediction results are in the "Prediction Benchmark" sections.

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

| R-21 | HIGH | `scripts/install.sql`, `scripts/seed.sql` | `@@` is not script-relative on this client. R-06 replaced 27 `@../database/...` paths with `@@` on the stated ground that "`@@` resolves relative to this file", and documented two working invocations. Measured on SQL*Plus 23.26.3.0.0, `@@` resolves against the **current directory**, exactly like `@`: only the invocation with `scripts/` as the current directory works. R-06's remediation was never executed and its premise is false. | From the lab root, `sqlplus ... @scripts/install.sql` -> 40x `SP2-0310: unable to open file "../database/..."`, 0 objects created. Identical result passing the absolute path to `install.sql` with the current directory elsewhere, which rules out "relative invocation" as the cause. | Document the one invocation that actually works and say on which client it was measured, rather than assert portable `@@` semantics a second time without running anything. | Both headers now say to run with `scripts/` as the current directory, name the client version the behaviour was measured on, and point at the new step-6 guard. Paths themselves are unchanged. |
| R-22 | BLOCKER | `scripts/install.sql`, `scripts/seed.sql` | A completely failed install reported success. `SP2-0310` is a SQL\*Plus error, not a SQL error, so `whenever sqlerror exit failure` does not see it; and step 6's only guard was `count(*) ... where status != 'VALID'`, which is vacuously satisfied by an empty schema. An install in which all 40 nested scripts failed to open printed `Install complete: every object in the schema is VALID` and **exited 0**. `seed.sql` had the same hole: no inserts ran, nothing raised, `Seed complete` printed. This made install.sql's own header claim -- "a pipeline run cannot pass with a broken package" -- false, and R-06 had claimed that property was achieved. | Observed on the first live run, against an empty `LOM_LAB_TMP`: 40x SP2-0310, `select count(*) from user_objects` -> 0, SQL\*Plus exit code 0, success banner printed. | Make the guard assert that the install *happened*, not only that nothing is broken. Keep it derived from the script's own `@@` list so it stays honest when the lab grows. | Step 6 now compares `user_objects` counts per type against the 6 sequences / 11 tables / 2 views / 5 specs / 5 bodies the script installs and raises `-20002` naming the mismatch and the likely cause; the INVALID check follows unchanged. `seed.sql` raises `-20003` if `lom_orders` is empty after seeding. Both verified: the broken invocation now exits 1 with `ORA-20002` / `ORA-20003`, the correct one still exits 0. Indexes are deliberately not counted (most are created implicitly by constraints). |

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
package body and seed file by the test suite, not by hand. Note that "every
`@@` target exists" is a check on the *files*, and it passed while the
*resolution* was broken -- see R-21.

Live SQL execution (2026-09-19), against the schema described under "SQL
validation status". The `cd` is load-bearing (R-21):

```text
cd examples/modernization-lab/scripts
sqlplus -S <user>/<password>@//localhost:1521/freepdb1 @install.sql
sqlplus -S <user>/<password>@//localhost:1521/freepdb1 @seed.sql
sqlplus -S <user>/<password>@//localhost:1521/freepdb1 @verify.sql
sqlplus -S <user>/<password>@//localhost:1521/freepdb1 @reset.sql
```

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

**EXECUTED, 2026-09-19.** All four scripts were run against a live Oracle
instance in a schema created for the run and dropped afterwards. This
replaces the "static validation only" statement that stood here after the
2026-09-18 pass.

### Environment

| | |
|---|---|
| Server | `Oracle AI Database 26ai Free Release 23.26.3.0.0` (`v$version.banner_full`) |
| Container | `FREEPDB1`, `READ WRITE` |
| Client | `SQL*Plus: Release 23.26.3.0.0 - Production` |
| Schema | `LOM_LAB_TMP` -- created for this run, dropped with `drop user ... cascade` afterwards; `dba_users` then returns 0 rows for it |
| Grants | `create session`, `create table`, `create view`, `create sequence`, `create procedure`, `quota unlimited on users`. No `dba`, no `resource`. |

The schema password existed only for the duration of the run and is not
stored in this repository or in any script in it.

### Result

Run from the `scripts/` directory, in the documented order:

| Step | Exit code | Outcome |
|---|---|---|
| `@install.sql` | 0 | 54 objects created, every one `VALID` |
| `@seed.sql` | 0 | seven seed files applied, sequences realigned |
| `@verify.sql` | 0 | 11 row counts, no INVALID object, 6/6 fixture assertions `OK` |
| `@reset.sql` | 0 | schema back to 0 objects; no error other than the expected "does not exist" noise |

Object inventory after `install.sql` (`user_objects`, 54 rows, all `VALID`):

| Object type | Count |
|---|---:|
| `INDEX` | 25 |
| `TABLE` | 11 |
| `SEQUENCE` | 6 |
| `PACKAGE` | 5 |
| `PACKAGE BODY` | 5 |
| `VIEW` | 2 |

The five package bodies compiled without warnings: every `show errors`
after a body printed `No errors.`, and the step-6 listing of non-`VALID`
objects returned `no rows selected`.

Row counts reported by `verify.sql` after `seed.sql`:

| Table | Rows |
|---|---:|
| `lom_approvals` | 3 |
| `lom_audit_log` | 6 |
| `lom_customer_types` | 3 |
| `lom_customers` | 6 |
| `lom_inventory` | 16 |
| `lom_order_lines` | 12 |
| `lom_order_status` | 8 |
| `lom_orders` | 8 |
| `lom_products` | 8 |
| `lom_shipments` | 2 |
| `lom_warehouses` | 2 |

Fixture assertions, verbatim from `verify.sql`:

```text
=== Known-fixture business assertions ===
OK   lom_customers is seeded
OK   lom_orders is seeded
OK   order 5004 fixture is still under-stocked at EAST (available=2, order needs 20)
OK   quantity_available matches quantity_on_hand - quantity_reserved for every row
OK   order 5006 reached SHIPPED
OK   order 5008's rejection carries a non-null comment
All checks passed.
```

### The showcase case, executed

`verify.sql` deliberately does not call `LOM_ORDER_API.release_order(5004)`,
because doing so consumes the under-stock fixture. It was called once, in
its own block, and rolled back:

```text
EAST/2004 available before: 2
ORA-20011: LOM_INVENTORY_API.reserve_quantity: insufficient stock for product 2004 in warehouse EAST
```

That is the exception the fixture exists to produce, raised by the package
the registry names, with the product and warehouse the seed data sets up.
The cross-package path `release_order -> reserve_quantity` therefore works
against a real database, not only on paper -- which also means the
body-level mutual dependency discussed in R-08 installs and executes.

### What this run did and did not establish

Established: the DDL compiles, the five package bodies compile clean against
each other in the order `install.sql` uses, the seed data satisfies every
constraint, the virtual column `LOM_INVENTORY.QUANTITY_AVAILABLE` computes
as documented for all 16 rows, the documented business fixtures hold, the
showcase exception fires, and `reset.sql` returns the schema to empty so the
cycle is repeatable.

Not established: behaviour on any client other than SQL*Plus 23.26.3.0.0 on
Windows, on any database version other than 26ai Free 23.26.3.0.0, or in a
schema that already contains unrelated objects -- step 6's new count check
is written for a from-empty install and would report a mismatch in a shared
schema, which is the intended reading of "run this in a disposable schema".

## Remaining Limitations

1. **No live Oracle execution** -- **closed 2026-09-19.** `install.sql`,
   `seed.sql`, `verify.sql` and `reset.sql` were run in a disposable schema
   on Oracle 26ai Free; see "SQL validation status" for the environment, the
   object inventory and the verbatim assertion output. What remains open is
   narrower than the original limitation: one client, one database version,
   and no run against a schema holding unrelated objects.
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

**READY, AND EXERCISED.** Both steps this section originally recommended
have been carried out; the paragraphs below record what each one settled.

Structurally: the fixtures parse, the registry is complete, unique,
internally consistent and test-pinned against the source it describes,
every narrative claim that was checked either matches the source or was
corrected, and the numbers in the assessment are generated from the
registry rather than typed in.

Against Oracle (recommended step 1, done 2026-09-19): `install.sql`,
`seed.sql`, `verify.sql` and `reset.sql` were executed in a disposable
schema; 54 objects, all `VALID`, 6/6 fixture assertions `OK`, and the
showcase exception raised by the package the registry names. See "SQL
validation status".

Against the ground truth (recommended step 2, done 2026-09-18/19): the
prediction protocol is `benchmark/protocol.md`, and three baselines have
been produced and frozen -- v1 (Forms only), v2 (Forms + database) and v3
(structural reasoning). See the three "Prediction Benchmark" sections
below. The answer-key stripping that limitation 3 asked for is implemented
in `benchmark/sanitize.py` and verified before every run.

What is still not claimed: runtime validation against a real Oracle Forms
or APEX instance, and any client or database version other than the single
combination named under "SQL validation status".

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
## Prediction Benchmark v3

Date: 2026-09-19. Protocol version: 1.0. Runner version: 1.0.

Read `baselines/v3/comparison-v1-v2-v3.md` before these numbers. Two facts
outrank them and are stated there in full: **the v2 figure did not measure
what it claimed to measure** (the v2 engine contained 30 references to this
laboratory's own identifiers, so it could recognise the benchmark it was
being scored on), and **v3 loses four cases that v2 answered correctly**.

- **Baseline Status**: `V3_BASELINE_COMPLETE`
- **Source Commit**: `af2d4ff977ba50ed4ff26ec3e4046d2a6129e8ff` (the commit
  the run was based on; the v3 artifacts are committed after it)
- **FormsLang Engine Path**: `formslang.parser.parse_xml -> formslang.blueprint.build` (Deterministic, AI: None, network: None)
- **Observability Counts**: unchanged from v2 -- 38 observable (92.7%), 3 not observable (`OM_SHARED.md`)
- **Measured Performance Metrics (Observable)**:
  - Exact Classification Accuracy: **73.7%** (28/38) *(vs. 68.4% in v2, +5.3 pp)*
  - Macro F1: **0.6418** *(vs. 0.6257 in v2, +0.0161)*
  - Exact Risk Accuracy: **79.0%** (30/38) *(vs. 68.4% in v2, +10.6 pp)*
  - Critical Risk Recall: **100.0%** (4/4) *(unchanged)*
  - High+Critical Risk Recall: **87.5%** (7/8) *(unchanged)*
  - Execution Verdict Exact Matches: **7/11** *(vs. 5/11 in v2)*
- **Enterprise Safety Metrics**:
  - Manual Review Recall: **80.0%** (8/10) *(unchanged from v2)*
  - False Automation Rate: **20.0%** (2/10) *(unchanged from v2: `LOM-MOD-004`, `LOM-MOD-018`)*
  - Critical Safety Misses: **0** *(unchanged)*
- **Per-Class F1 (v2 -> v3)**: `PRESERVE` 0.9412 -> 0.7143; `CONVERT` 0.5000 -> 0.8000; `REFACTOR` 0.2500 -> 0.6667; `MOVE_TO_PLSQL_API` 0.8889 -> 0.8000; `REPLACE_WITH_APEX_NATIVE` 0.0000 -> 0.7500; `MANUAL_REVIEW` 0.8000 -> 0.7619; `DROP` 1.0000 -> 0.0000
- **Regressions (must not be read past)**:
  1. `LOM-MOD-003` `PRESERVE` -> `REFACTOR`: a body-level package cycle the architect judged deliberate. Nothing in the source distinguishes a contained cycle from an accidental one.
  2. `LOM-MOD-019` `PRESERVE`/LOW -> `MOVE_TO_PLSQL_API`/HIGH: the trigger calls the API and re-reads one of its inputs; structural matching reads the re-read as duplication.
  3. `LOM-MOD-032` `PRESERVE`/LOW -> `MANUAL_REVIEW`/CRITICAL: **the largest single over-escalation in the run**, a mandatory-comment rule enforced only in PL/SQL.
  4. `LOM-MOD-038` `DROP` -> `MANUAL_REVIEW`: **accepted deliberately**. v2 answered `DROP` from a rule that named this fixture's table; the generic rule cannot prove that a column has no reader outside the analysed sources, so it asks instead of deleting.
  5. `LOM-MOD-030` risk `MEDIUM` -> *(none emitted)*: a concurrency finding without a risk grade. This one is a defect, not a judgment call.
- **Key Engineering Changes Delivered**:
  1. New module `formslang/modernization.py`: 27 prioritized signals, all written against structure rather than names.
  2. Structural signatures -- expression skeletons (identifiers and numbers erased), SELECT shapes (table, projection, filters), predicate literal sets, and leaf-name reduction that strips qualifiers and the conventional `P_`/`V_`/`G_`/`GC_`/`GV_`/`L_`/`C_` prefixes.
  3. Measured guard strength: `FOR UPDATE`, `RAISE_APPLICATION_ERROR`, `SQL%ROWCOUNT` checks and cross-package delegation each count one, and a form-layer write is scored by how many guards it *loses* relative to the API that owns the table.
  4. Native-equivalent recognition by shape for twelve idioms the target platform supplies declaratively -- the reason `REPLACE_WITH_APEX_NATIVE` goes from never predicted to 0.75 F1.
  5. Priority ordering in which safety outranks convenience, and verdict escalation that only ever tightens.
  6. **De-coupling**: every laboratory identifier removed from the product tree. `grep -rnE "LOM-MOD-|LOM_|CUSTOMERS\.xml|ORDERS\.xml|APPROVALS\.xml|INVENTORY\.xml|modernization-lab|baselines/v" formslang/` returned 30 matches against the v2 engine and returns none against v3.
  7. `tests/test_modernization.py`, 37 tests, written against a synthetic library-lending corpus that shares no table, package, column or module name with this laboratory. One test runs identical structure through two unrelated vocabularies (library and clinic) and asserts both reach the same class, risk and verdict.
- **Frozen Artifacts**:
  - Location: `examples/modernization-lab/benchmark/baselines/v3/`
  - Includes: `manifest.json`, `observability.json`, `raw-analysis.json`, `predictions.json`, `benchmark-report.json`, `benchmark-report.md`, `comparison-v1-v2-v3.md`, `failure-analysis.md`
- **Method**: the prediction run was executed **once**, frozen in the same
  command (`run_benchmark.py --freeze --baseline-name v3`), and no engine
  code, heuristic, threshold or rule was changed afterwards. The mismatches
  above are inputs to a future v4, not to this one.
- **Historical integrity**: every file under `baselines/v1/`, `baselines/v2/`
  and the ground truth was SHA256-hashed before and after the v3 work --
  16/16 byte-identical, none added, none removed, none modified.
- **Remaining Limitations**:
  1. `OM_SHARED.md` (3 cases) is still un-ingested; `.pll` ingestion is deliberately deferred.
  2. Four `ARCHITECTURAL_JUDGMENT` regressions and one missing risk grade, listed above, are open against v4.
  3. Four ground-truth cases split one Forms construct across two case IDs while the engine emits one finding per construct, so the exact-classification ceiling for this engine shape is about **35/38 (92.1%)**, not 38/38.
  4. The two false automations (`LOM-MOD-004`, `LOM-MOD-018`) are unchanged from v2; both turn on business intent the source does not carry.
