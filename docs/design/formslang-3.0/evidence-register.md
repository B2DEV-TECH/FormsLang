# FormsLang 3.0 — Gate evidence register

This file records **actual** results only (§28.2). A gate is never marked passed
because a document says it should pass. A blocked Oracle or human gate is never
marked passed because the local unit tests are green. Planned work is in
[implementation-plan.md](implementation-plan.md), and requirement status is in
[requirements-matrix.md](requirements-matrix.md).

Specification: FL3-MASTER-2026-09-25 revision 1.0. Historical planning baseline:
`main` at `1d9cb47`. The #21 → #22 → #24 foundation is merged; subsequent
work spans several milestones. PR #23 remains separate diagnostic instrumentation.
This register records evidence through the 2026-09-30 ADR review; current heads
and CI must be checked in GitHub before integration.

## Summary

| Gate | Status | Evidence so far |
|---|---|---|
| G-01 Baseline truth | **In progress** | Baseline audit written against `1d9cb47`, and the §3.3 concerns verified in code (see below) |
| G-02 Repository integrity | Not assessed | ADR-01..03 accepted as architecture; whole-state product checkpoints, object verification and recovery remain WP-20 work |
| G-03 Portability and Git exchange | Not assessed | ADR-04/07 accepted as architecture in this PR; product import, origin-trust and clean-workspace exchange remain WP-20 work |
| G-04 Facts and evidence | **In progress** | M0, WP-07 and WP-08 are merged with focused evidence. Schema identity, graph coverage and documented extraction gaps remain open. |
| G-05 Language and decisions | Not started | — |
| G-06 Workbench and CLI | Not started | — |
| G-07 Target delivery | Not started | 2.2 generator behaviour recorded in the baseline audit only |
| G-08 Validation | Not started | Offline SQLcl `apex validate` runs in CI for the 2.2 path; this is not a 3.0 gate result |
| G-09 Reporting | Not started | 2.2 revision-fenced reports recorded in the baseline audit only |
| G-10 Migration and packaging | Not assessed | Existing 2.2 installer harness and a separate beta candidate do not prove 3.0 migration, restore or final same-commit assets |
| G-11 Security | Not assessed | WP-05 sanitization probe is merged; the full threat and privacy criteria remain unverified |
| G-12 Performance and usability | Not assessed | Issue #20 covers ProjectBusy/409. The intermittent Windows HTTP 500 has unknown cause; ratified performance and five-person acceptance remain unverified. |
| G-13 Documentation | Not started | — |

No gate is **passed**. The full 3.0 release is not complete.

## G-01 — Baseline truth

- **Links:** DOC-01, AGENT-01..04; §30.2.
- **Scope:** the repository at `main` `1d9cb47` and branch `codex/formslang-3-m0`, local Windows 11 with Python 3.12 and 3.13, and GitHub Actions CI.
- **Implementation commits:** the M0 documents commit on `codex/formslang-3-m0` (see [session-handoff.md](session-handoff.md)).
- **Environment:** Windows 11 Pro 10.0.26200, Python 3.12 and 3.13. Oracle Database, APEX and SQLcl were **not used** in M0.
- **Commands and outcomes:**

  | Evidence | Command or source | Outcome |
  |---|---|---|
  | Specification identity | SHA-256 of `master-specification.md` against the delivered package | Identical (`60e1924a…401b29e`) |
  | CI on `main` `1d9cb47` | GitHub Actions run 36135896101 | **Failed**: `pytest (windows-latest, py3.11)` — 1 failed, 1867 passed. The job-status `GET` returned HTTP 500. All other jobs were green. |
  | Windows concurrency repetition | Run 36084327274 (100 runs × py3.10–3.13 of `tests/test_project_descriptor_concurrency.py`) | Previous `main` 19/400 failures; `ce2cfdd` 4/400 failures. Reduced, not eliminated (issue #20). |
  | Local reproduction of the 500 | `tests/test_project_http.py` repeated 20× each on py3.12 and py3.13 with a traceback-capture plugin | 40/40 runs passed (py3.12 20/20, py3.13 20/20). All 40 captured tracebacks come from `test_unknown_server_error_is_sanitized`, which raises on purpose. **The 500 was not reproduced locally.** |

- **Evidence locations:** [baseline-audit.md](baseline-audit.md) §2–§6, and the CI run pages.
- **Independent review:** none yet.
- **Known limitations:**
  - The cause of the `1d9cb47` 500 is **unknown**. The HTTP boundary sanitised the error without logging its type. WP-02 (Draft PR #23) adds that logging; its CI did not reproduce the failure (see WP-02 below).
  - Python 3.10 and 3.11 were not run locally.
- **Status:** in progress. **Owner/reviewer:** Geraldo Viana Jr, not yet reviewed.

## G-04 — Facts and evidence

- **Links:** SRC-11 (partial), SRC-14, INV-07; gaps G-SCHEMA-BODY, G-SCHEMA-COLLIDE, G-DDL-HEADER and G-DDL-EXTRACT in [../ecosystem-explorer-2.3/gaps-and-capture.md](../ecosystem-explorer-2.3/gaps-and-capture.md).
- **Scope:** static database-source extraction (`formslang/database.py`) and blueprint analysis (`formslang/blueprint.py`), offline, on synthetic fixtures.
- **Implementation commits:** WP-03 commit `e104b33` on `codex/formslang-3-m0`, on Draft PR #21, not merged.
- **Fixtures:** the synthetic Case C corpus from the 2.3 ecosystem inventory and inline `tmp_path` sources. No customer source is used.
- **Commands and outcomes (Python 3.13, local):**

  | Step | Command | Outcome |
  |---|---|---|
  | Failing test first | `py -3.13 -m pytest -q tests/test_ecosystem_phase1.py -k "schema_qualified"` before the fix | 3 failed, 1 passed (the unqualified header already worked) |
  | After the fix | `py -3.13 -m pytest -q tests/test_ecosystem_phase1.py` | 29 passed |
  | Related suites | `py -3.13 -m pytest -q tests/test_database.py tests/test_blueprint.py tests/test_blueprint_backend.py tests/test_ecosystem_phase1.py tests/test_estate_hotspots.py tests/test_depgraph.py tests/test_modernization.py tests/test_project_analysis.py` | 206 passed, 1 skipped (symlinks unavailable to this Windows account) |
  | Inventory | `py -3.13 examples/verify/ecosystem_inventory.py --check docs/design/ecosystem-explorer-2.3/inventory-m0.json` | Passes. The new M0 snapshot changes the engine version in the four corpora, plus Case C: +1 `SUBPROGRAM_BODY`, +2 `IMPLEMENTS`, +1 `WRITES`, +1 symbolic table reference, and findings 22 → 24. The original `inventory-2.2.json` stays unchanged. |
  | Lint | `py -3.13 -m ruff check .` | All checks passed |
  | Full suite | `py -3.13 -m pytest -q -p no:cacheprovider` | 1868 passed, 5 skipped in 836 s at `e104b33`. The skip count matches the pre-M0 baseline; this run did not list the reasons. |

- **Behaviour now proven:** a `CREATE [OR REPLACE] PACKAGE BODY OWNER.NAME AS|IS` body keeps its subprograms, its `IMPLEMENTS` links, and its writes. The engine version is `blueprint-analysis/2`, so saved assessments from the previous engine are reported as stale.
- **Behaviour still not proven (open defects, pinned by `test_gap_*` tests):**
  - **G-SCHEMA-COLLIDE:** same-named objects in two schemas merge into one, and the last file wins. This needs ADR-06, then WP-04.
  - **G-DDL-HEADER (found in M0):** fixed in WP-07; see below.

### WP-07 — DDL-export headers and database source coverage

- **Branch:** `codex/formslang-3-wp07`, from `70f8596`. Draft PR #22, stacked on #21 (base `codex/formslang-3-m0`).
- **Commands and outcomes (Python 3.13, local):**

  | Step | Command | Outcome |
  |---|---|---|
  | Header tests, before the fix | `py -3.13 -m pytest -q tests/test_database_headers.py` | 24 failed, 9 passed |
  | After the header pattern | same | 32 passed, 2 failed: the `.sql` pre-filter (`"PACKAGE BODY "` followed by a line break) and the engine version |
  | After the pre-filter and the engine bump | `py -3.13 -m pytest -q tests/test_database_headers.py tests/test_ecosystem_phase1.py` | 60 passed, 1 failed (the committed inventory, as expected before regeneration) |
  | Coverage tests, before the implementation | `py -3.13 -m pytest -q tests/test_database_coverage.py`, with only the status constants defined | 19 failed, 0 passed |
  | After the implementation | `py -3.13 -m pytest -q tests/test_database_coverage.py tests/test_database_headers.py` | 53 passed |
  | Related suites | `py -3.13 -m pytest -q tests/test_database.py tests/test_database_headers.py tests/test_database_coverage.py tests/test_blueprint.py tests/test_blueprint_backend.py tests/test_ecosystem_phase1.py tests/test_estate_hotspots.py tests/test_depgraph.py tests/test_modernization.py tests/test_project_analysis.py tests/test_project_sources.py tests/test_project_discovery.py` | 310 passed, 2 skipped, after the inventory regeneration |
  | Inventory | `py -3.13 examples/verify/ecosystem_inventory.py --check docs/design/ecosystem-explorer-2.3/inventory-wp07.json` | Passes. The WP-07 snapshot changes only the engine version relative to M0; the 2.2 baseline remains historical. |
  | Lint | `py -3.13 -m ruff check .` | All checks passed |
  | Full suite | `py -3.13 -m pytest -q -p no:cacheprovider` | 1919 passed, 5 skipped in 832 s (the M0 run was 1868 passed; this adds 34 header and 19 coverage tests and removes the 2 cases of the old gap test). The skip count is unchanged. |
  | Coverage on repository corpora (first commit) | `parse_database_sources` on `examples/modernization-lab/database` and on Case C | Lab: 27 supplied, 13 parsed, 7 parsed with warnings (unmodelled `CREATE INDEX`), 7 with no recognized objects (the DML-only seed scripts, `NO_CREATE_STATEMENT`), 0 rejected. Case C: 6 supplied, 6 parsed. |
  | Unmodelled kinds made informational: tests, before the change | `py -3.13 -m pytest -q tests/test_database_coverage.py` | 3 failed, 17 passed: the index beside a table expected `PARSED` with `severity: INFO`, the not-extracted entry expected `severity: WARNING`, and the four-source summary expected 2 parsed and 0 with warnings |
  | After the change | same | 20 passed |
  | Related suites, after the change | the related-suites command above | 311 passed, 2 skipped |
  | Full suite, after the change | `py -3.13 -m pytest -q -p no:cacheprovider` | 1920 passed, 5 skipped in 837 s (one test more than at `bfbaf70`; the skip count is unchanged) |
  | Coverage on repository corpora (after the change) | same probe | Lab: 27 supplied, 20 parsed, 0 parsed with warnings, 7 with no recognized objects (`NO_CREATE_STATEMENT`), 0 rejected; the 12 `CREATE INDEX` statements are listed as `INFO`. The inventory's database selection for the lab (20 sources): 20 parsed. Case C: 6 supplied, 6 parsed. |

- **Behaviour now proven:**
  - Package specs and bodies with `EDITIONABLE`/`NONEDITIONABLE`, quoted owner and name, and spaces or line breaks around the dot are parsed, subprograms included. A quoted name keeps its case, and an unquoted one is folded to upper case. The identity key is still the bare name.
  - Malformed headers (`S..P`, `S.P.Q`, `1P`, an unterminated quote, an empty quoted name, both editioning keywords) are not recognised. The old pattern accepted the first three.
  - Every supplied database source has a coverage entry with one of four statuses. The entry lists the objects extracted, the CREATE statements of a supported kind that yielded no object (`WARNING`, `NOT_EXTRACTED`; they make the source `PARSED_WITH_WARNINGS`), and the CREATE statements of an unmodelled kind (`INFO`, `UNSUPPORTED_BY_MODEL`; listed, but they do not change the status). A missing path in a source list is `REJECTED_OR_UNREADABLE` (`SOURCE_NOT_FOUND`), and in the project pipeline every rejecting diagnostic becomes such an entry. When coverage was never computed it is `None`, never an empty result.
  - The Blueprint carries `database.source_coverage` (summary and per-source entries, logical paths only in the project pipeline). The engine is `blueprint-analysis/3`, so earlier saved assessments are reported as stale.
- **Behaviour still not proven:**
  - **G-DDL-EXTRACT:** the statements coverage reports as `not_extracted` are still missing from the Blueprint (see the gap document).
  - No report, UI or CLI output shows coverage yet.
  - The CREATE scan is lexical. A SQL*Plus `REM` line that contains `CREATE TABLE x` is counted as a statement; the error only ever adds a warning, never hides one.
  - **G-SOURCE-REVISION (follow-up, not changed here):** `source_revision` is derived from `files` only, so a supplied source that yields no object does not change it. Invariant to hold: "Two repository states with materially different supplied source sets must not silently appear identical merely because one source produced zero extracted objects." Owned by ADR-02 (WP-10, WP-20).
  - Quoted names are not resolved against unquoted ones (`"MyPackage"` is not `MYPACKAGE`, as in Oracle). Quoted subprogram names are separate work.
  - CI does not run on this branch: `ci.yml` triggers only on pushes and pull requests to `main`, and the PR is stacked on `codex/formslang-3-m0`. Python 3.10, 3.11 and 3.12 were not run for this slice.
- **Independent review:** none yet.
- **Status:** in progress. **Owner/reviewer:** Geraldo Viana Jr, not yet reviewed.

### WP-02 — instrumentation of the HTTP 500 boundary

- **Branch:** `codex/formslang-3-wp02`, from `main` at `1d9cb47`, independent of #21 and #22. Draft PR #23 against `main`. Commit `b83ade2`.
- **Change:** the generic `except Exception` in `ProjectHTTP.dispatch` logs one ERROR message with the correlation id returned to the client, the method, the route with every data segment replaced by `{…}`, and each exception of the cause/context chain with its type, a safe code (`sqlite_errorname` from Python 3.11, `errno`) and its frames (`file:line in function`). It never logs the exception message, the query string, the body or credentials, and passes no `exc_info`. The response, the status, retries, locks, busy timeouts and the journal mode are unchanged.
- **Commands and outcomes:**

  | Step | Command | Outcome |
  |---|---|---|
  | New tests, before the change (Python 3.13, local) | `py -3.13 -m pytest -q tests/test_project_http.py -k "logged or sanitized"` | 3 failed, 1 passed (the log message had no correlation id, type or route) |
  | After the change | same | 4 passed |
  | HTTP and project suites | `py -3.13 -m pytest -q tests/test_project_http.py tests/test_project_generation_http.py tests/test_project_reports_http.py tests/test_workbench.py tests/test_workbench_mfa.py tests/test_project_jobs.py tests/test_project_service.py tests/test_project_intake.py` | 199 passed, 1 skipped |
  | Lint | `py -3.13 -m ruff check .` | All checks passed |
  | Full suite | `py -3.13 -m pytest -q -p no:cacheprovider` | 1866 passed, 5 skipped in 829 s |
  | CI of Draft PR #23 | GitHub Actions run 36176591379 at `b83ade2` | `pytest (windows-latest, py3.11)`: **1871 passed, 0 failed** in 1904 s. All 13 checks passed: the other Windows jobs (py3.10, py3.12, py3.13) 1871 passed each, the four Ubuntu jobs, ruff, the export, SQLcl `apex validate` and both Edge acceptances. |

- **Windows py3.11 500: not reproduced.** The job that failed on `1d9cb47` passed on the instrumented branch, so there is no new evidence of its cause. One green run proves only that it did not recur; the failure is intermittent. No fix was written, as the owner required.
- **Correction:** the #21 description says the `1d9cb47` failure happened during setup. The job log shows it in the test call (`analyze_demo` → `wait_job`, `tests/test_project_http.py:52`).
- **Status:** instrumentation done and tested; cause unknown. **Owner/reviewer:** Geraldo Viana Jr, not yet reviewed.

### WP-08A/B/C — independent audit of Draft PR #24

- **Branch and scope:** `codex/formslang-3-wp08`, stacked on Draft PR #22. The independent read-only review compared `9d08e1e..e94e7e6` with the master specification, requirements matrix, plan, handoff, and #21/#22 invariants. The correction commit is `22751e8` on #24. PR #23 is unchanged.
- **Important regression found:** when two same-name tables in one file had already been withheld, a third table in another file could be published under that bare name. The review compared base and head: base withheld the table and reported two `DUPLICATE_DB_OBJECT` diagnostics; the pre-audit WP-08 head published the third table without a diagnostic. The same path covered views and sequences. Both direct `parse_database_sources` and the project pipeline now count coverage occurrences before projecting a bare name. A supported but not extracted quoted homonym also withholds the bare projection; the direct case failed first, and direct/project cases now pass.
- **Other WP-08 findings:** package spec member regex accepted procedure/function decoys from comments and string literals; a `COMMENT ON TABLE` literal containing `CREATE TABLE` fabricated a table; quoted member names vanished; a quoted dot in a package name made `qualified_name` indistinguishable from an owner/name separator; Blueprint's declaration projection reduced overloaded members to identical names; package `SHARING=DATA` and `SHARING=EXTENDED DATA` were accepted even though [Oracle's SHARING table](https://docs.oracle.com/en/database/oracle/oracle-database/26/lnpls/SHARING-clause.html) lists only `METADATA` and `NONE` for packages. These paths have minimal failing-first tests and corrections.
- **Red/green evidence, Windows 11 / Python 3.13.15:** member decoy and overload projection: 2 failed then 2 passed; cross-source table collision in direct and project pipelines: 2 failed then 2 passed; invalid package sharing (spec/body, two attributes): 4 failed then passed; quoted member and literal CREATE decoy: 2 failed then passed; parsed plus unextracted quoted homonym: 1 failed then passed; quoted dot in qualified name: 1 failed then passed. Three out-of-scope gaps also failed as expected before being marked strict `xfail`.
- **Final verification:** `py -3.13 -m pytest -q tests/test_database.py tests/test_database_headers.py tests/test_database_coverage.py tests/test_database_wp08.py tests/test_blueprint.py tests/test_blueprint_backend.py tests/test_ecosystem_phase1.py tests/test_project_analysis.py tests/test_project_sources.py` — **237 passed, 1 skipped, 3 xfailed** in 18.18 s. `py -3.12 -m pytest -q tests/test_database_wp08.py tests/test_database_coverage.py tests/test_database_headers.py` — **100 passed, 3 xfailed** in 1.42 s. `py -3.13 -m pytest -q -p no:cacheprovider` — **1967 passed, 5 skipped, 3 xfailed** in 846.26 s. Repository-wide `py -3.13 -m ruff check .`, `git diff --check`, and the `inventory-wp08.json` generator check passed. Two earlier full-suite attempts were discarded after code files were edited during execution; one then raised `RevisionConflict` because `engine_identity` hashes those files. The isolated journey test passed, and the final suite ran with code files stable.
- **CI limit:** #24 is stacked on #22 and `ci.yml` triggers pull requests only when based on `main`; GitHub reports zero checks for #24. Local Windows testing does not substitute for the Ubuntu/Windows Python 3.10–3.13 matrix, browser checks, export, or SQLcl. Oracle runtime validation was not performed.
- **Pinned gaps outside this slice:** three minimal tests failed before being marked strict `xfail`: a supported CREATE warning in source coverage can leave a project assessment `COMPLETE` (WP-07/project integration); direct `blueprint.build` hashes database file paths rather than changed SQL bytes for its local `source_revision` (ADR-02; the manifest-bound project path does hash source content); documented `CREATE PACKAGE IF NOT EXISTS` is not recognized (future DDL grammar, target-version policy required). Full schema-aware identity and qualified call resolution still belong to ADR-06/WP-04. Oracle runtime validation was not performed.
- **Gate status:** G-04 remains **in progress**. No release gate is passed by this audit.

### WP-05 — synthetic disclosure probe

- **Branch:** `codex/formslang-3-wp05-sanitization-probe`, based on merged `main` at `b09be2d`.
- **Evidence:** [wp05-disclosure-probe.md](wp05-disclosure-probe.md) and `tests/test_wp05_disclosure_probe.py`. The local System Map kept the symbolic target name but excluded the synthetic host-path components. `convert.build_prompt` included the exact selected source body, including a synthetic credential and host path; the desired no-disclosure assertion failed before being pinned as strict `xfail`. No provider was called and no production behavior changed.
- **Validation:** Windows 11, Python 3.13.15: targeted probe/policy/conversion tests, **39 passed, 1 xfailed**; `py -3.13 -m pytest -q -p no:cacheprovider`, **1970 passed, 5 skipped, 4 xfailed** in 846.41 s; `py -3.13 -m ruff check .` and `git diff --check` passed. CI run `36617867680` on `91ba4ad` passed all **13/13** checks across Ubuntu/Windows Python 3.10–3.13, Ruff, both Edge acceptances, deterministic export and SQLcl/APEX validation.
- **Remaining work:** define context preview, consent and retention before optional AI orchestration (WP-47), with SEC-05/SEC-06 and AI-01..03. The probe does not close G-11.

### WP-06 — reads that write inventory

- **Branch:** `codex/formslang-3-wp06-read-write-inventory`, based on merged `main` at `b09be2d`.
- **Evidence:** [wp06-read-write-inventory.md](wp06-read-write-inventory.md) classifies the implicit migration, mirror repair, job recovery, freshness-job and locator-registration paths from the actual callers. Existing store/job/service tests: Windows 11 / Python 3.13.15, **43 passed, 1 skipped**. This audit changes no behavior.
- **Dependency result:** ADR-01/WP-10 must define an explicit read, migration, recovery and publication contract before changing persistence. The inventory does not attribute the intermittent HTTP 500 to SQLite or issue #20 and closes no gate.

### WP-10 — repository transaction and checkpoint spike

- **Branch:** `codex/formslang-3-wp10-repository-spike`, stacked on the reconciled WP-06 commit `024b088` and WP-05 commit `5e34693`. The two own WP-10 commits were replayed without conflicts; `range-diff` marks both equivalent.
- **Contracts introduced as drafts:** [ADR-01](adr/ADR-01-repository-authority.md), [ADR-02](adr/ADR-02-object-identity.md), [ADR-03](adr/ADR-03-checkpoint-schema.md), and the [portable-state schema draft](wp10-portable-state-schema-draft.md). The architectural contracts were accepted after independent review; the portable example remains a draft, not a product format.
- **Executable evidence:** `examples/verify/repository_spike.py` stays outside the product path. `tests/test_repository_spike.py` proves exact-byte and kind-separated IDs, canonical manifests across different input orders, rollback before commit, pending and idempotent recovery after commit, missing-object refusal, interrupted object flush and one winner under two concurrent publishers. The recovery missing-object test failed first because recovery published a manifest with an unavailable accepted object. A second red test found that a new event was accepted despite a missing object inherited from the previous checkpoint. Both repairs passed. Focused local run: **9 passed** on Windows 11 / Python 3.13.15.
- **Local verification:** Windows 11 / Python 3.12.10 on the final composed head: **1979 passed, 5 skipped, 4 xfailed** in 918.63 s. Focused WP-10 plus WP-05 suite: **10 passed, 1 xfailed**. Ruff and `git diff --check` passed. The extra xfail is the WP-05 egress probe; the three prior strict xfails remain. PR #31 (`55b81c3`) passed 13/13 checks in CI run `36654894144` and merged as `7dbda54`.
- **Limits:** This is not a product migration or a complete crash/power-loss, portability, authorization or export proof. G-02 and G-03 remain open.

### ADR-06 — identity contract probe on PR #32

- The probe is outside the product path. It cannot change entity IDs, reference
  resolution, decision binding or historical snapshots. Its first four focused
  tests and the original full suite passed; CI run `36625615586` passed all
  13 checks on head `1ed32f2` before the following probe correction.
- Two additional focused tests failed first: a matching symbol in a different
  logical source root was labelled `REMOVED`, and duplicate candidate rows were
  labelled `AMBIGUOUS`. The corrected probe returns `NOT_COMPARABLE` for the
  changed root, deduplicates candidates and orders them deterministically with
  the exact locator first. The six focused tests pass; the full suite on
  Windows 11 / Python 3.12.10 returned **1975 passed, 5 skipped, 3 xfailed** in
  916.64 s. Ruff and `git diff --check` pass. CI run `36633010065` passed all
  13 checks on corrected head `360ab80`; this predates the additional evidence
  below.
- The 29 September follow-up separates architecture acceptance from the product
  exit criteria of WP-04/G-04, removing a circular prerequisite without passing
  either gate. The outside-product probe now exercises typed symbols, distinct
  source occurrences, analysis-bound IDs, quoted spelling, qualified Case C
  member selection, bare-name withholding, overload limits and missing bodies.
  Thirteen new cases failed before implementation; one further failing case
  exposed a false resolution with a lone incomplete signature. Independent
  review then found false `REMOVED` results when the key changed at the same
  source locator: two tests failed first, and now yield `NOT_COMPARABLE` with
  no inferred rename target, including an unrelated object in the same file.
- Further independent review reproduced a false `REMOVED` when both logical
  root and key changed. One new case failed first; a nonempty scope lacking the
  original root now returns `NOT_COMPARABLE`. A complete empty scope, or an
  original-root scope with no matching key/locator, still permits `REMOVED`.
- Final focused evidence: **122 passed, 1 xfailed** in 6.46 s across identity,
  WP-08, Case C, project-source and assessment tests on Windows 11 /
  Python 3.13.15; **23 passed** in 0.29 s for the contract on Python 3.12.10.
  Repository Ruff, `git diff --check` and the `inventory-wp08.json` generator
  check pass. The product and historical `inventory-2.2.json` have no diff from
  `360ab80`. Before the root-plus-key correction, the full suite at `07c3f6f`
  (`py -3.13 -m pytest -q -p no:cacheprovider`), with code held stable, returned
  **1991 passed, 5 skipped, 3 xfailed** in 903.85 s. After the correction,
  the final full run returned **1992 passed, 5 skipped, 3 xfailed** in 847.99 s,
  again with code held stable.
  An earlier full run was interrupted before the review correction and is
  discarded. The coordinating reviewer subsequently approved the architecture
  after independent review of the corrected contract and three conservative
  correspondence regressions.
- The authorized rebase onto `main` at `7dbda54` preserved WP-10 and ADR-06
  evidence. At `78599b5`, the composed focused suite returned **132 passed,
  2 xfailed** in 8.77 s; Ruff and diff checks passed. CI run `36658549367`
  began normally after the documentation conflict was resolved and was still
  running when acceptance was authorized. The accepted head `f04561a` later
  passed 13/13 checks in run `36658930446` and merged as `01ee926`.
- ADR-06 is **Accepted (architecture only)** by a separate authorized commit
  on 29 September 2026. Case C product entities, qualified call resolution,
  Blueprint/project parity, engine versioning and legacy compatibility are
  still WP-04 work on a separate branch. WP-04/G-04 remain open, and historical
  inventories are unchanged. No product gate is closed by this acceptance.

### ADR-01/02/03 architecture acceptance

- **Decision (2026-09-30):** Accept the SQLite-coordinated, verified-object and root-last publication contract, versioned kind-separated object identity with exact source bytes, and an acyclic whole-state checkpoint with declared omissions. WP-06's read/write inventory and WP-10's nine failure-injection/golden-byte tests support the architectural choice. Alternatives and failure paths are recorded in the three ADRs.
- **Boundary:** The WP-10 script is outside the product path. Its example JSON is not a product exchange schema. WP-20 must test real migration, durable recovery, no-write reads, source-set closure, collision handling, full/review export, import trust, origin conflicts and clean-workspace reopen before G-02 or G-03 can close. The direct Blueprint `source_revision` strict xfail stays open.

### ADR-04/07 architecture acceptance

- **Decision (2026-09-30):** An imported package's integrity, origin trust, decision applicability and receiving authorization are separate. A trusted clean restore needs an independently retained exact-root receipt and authorized custodian; ordinary Git/review exchange cannot activate a claimed approval. Git is an explicit transport for portable files, with separate operational stores per worktree and content-identity reconciliation. The documented threat/outcome tables and the existing legacy migration preservation behavior support this boundary choice; no product 3.0 import route exists yet.
- **Boundary:** WP-20 must prove forged claim rejection, trusted versus unverified imports, retained receipt recovery, separate worktrees, external-change detection, preview/apply fences and conflict behavior. WP-22 must preserve legacy history without inventing current authorization. G-02 and G-03 remain open.

## WP-04 package identity slice (separate product branch)

- Built from architecture acceptance `f04561a`, under the
  [WP-04 product plan](../../superpowers/plans/2026-09-29-wp04-product.md).
  Ordered package occurrences supply typed owner/name/member/signature keys;
  duplicate declarations and overloads stay distinct. Case C retains both
  schemas, resolves the explicit schema calls and records bare ambiguity.
- The original Case C end-to-end test failed with zero package specifications
  instead of two. Separate namespace and input-capture tests also failed before
  implementation. The same Case C assertions now pass through the direct I/O
  boundary, which supplies the bytes required for new identity. Model-only and
  missing-byte negative tests still forbid new analysis-bound IDs.
- Project IDs use the validated project `analysis_revision`. Direct loading
  stages and hashes all supplied bytes, including zero-object SQL and Forms,
  and includes analysis context and engine identity. A changed zero-object file
  changes the namespace; repeated builds remain deterministic. A real project
  fixture verifies namespace equality with the published assessment and the
  same eight Case C package facts as direct loading. Tampered namespaces fail
  assessment validation.
- The engine is `blueprint-analysis/5`; the new current characterization is
  `inventory-wp04.json`. Historical inventories for 2.2, M0, WP-07 and WP-08
  compare byte for byte with the accepted ADR branch. No historical assessment
  or inventory is rewritten, and the existing `source_revision` formula and
  three pinned WP-08 gap tests are unchanged.
- Final focused Blueprint/project/database regressions: **285 passed, 1 skipped,
  3 xfailed in 22.55 s** on Windows 11 / Python 3.13.15. Estate, synthetic review
  scale and direct-input shape regressions: **24 passed in 79.17 s**. Ruff,
  `git diff --check` and the current inventory generator check pass.
- The first frozen full run returned **3 failed, 2028 passed, 5 skipped,
  4 xfailed in 860.36 s**. Two positive estate fixtures lacked the schema evidence
  now required for a resolved package bridge; their positive assertions now use
  explicit owners, with a separate ownerless negative. A synthetic scale fixture
  incorrectly retained the prior namespace after replacing its entire graph;
  that unrelated metadata is no longer copied. No product validation was weakened.
  The next frozen full run passed **2039 tests, with 5 skipped and 4 xfailed in
  854.63 s**. The fourth xfail is inherited from the composed main baseline.
- Further consumer/revision review added ten failing tests before corrections:
  occurrence totals across direct/discovery/assessment, onboarding statistics,
  quoted owner/package case in inventory and System Map, and separation of
  direct-only engine module hashes from project engine identity. The ten tests
  then passed in 2.78 s. Occurrence counters are additive and old snapshots keep
  their fallback. Typed projection groups use exact root/owner/name components;
  row IDs derive from existing analysis-bound entity IDs. Direct-only module
  changes no longer invalidate project assessments. The 2039-test full result
  predates these corrections.
- Expanded focused regressions for those changes returned **423 passed, 3 skipped,
  3 xfailed in 108.25 s**. A further test confirms stable package row IDs for
  repeated direct/project analysis and reversed spec/body input order, using the
  engine's existing sorted entity output. Row IDs belong to one analysis
  snapshot; changed bytes create new IDs, without a cross-revision correspondence
  claim. This additional test passed in 0.96 s.
- The final frozen full run after these corrections and the stability test passed
  **2050 tests, with 5 skipped and 4 xfailed in 861.28 s** on Python 3.13.15.
  This validates the product tree based on accepted ADR head `f04561a`, before
  the coordinator-authorized rebase onto main; composed verification is separate.
- Both authorized own-commit rebases, first onto accepted ADR main `01ee926`
  and then onto WP-12 main `8fa55f9`, were conflict-free with identical
  range-diffs. Backups preserve `d804f0f` and `35f2317`. Final composed focused
  regressions including journey/UI passed **433 tests, with 3 skipped and
  3 xfailed in 128.05 s**. Ruff, diff and current inventory checks pass.
  Historical inventory worktree bytes and Git blobs are identical. The merged
  WP-12 project service is unchanged; final exact-head PR CI is still required
  before integration. Post-rebase evidence updates change only documentation.
- After ADR-02 PR #37 merged as `dc16e006`, the coordinator authorized another
  own-commit rebase. Backup `codex/backup-wp04-product-before-adr02-20260930`
  preserves `c911c9d`. The sole conflict appended evidence to this register;
  both the ADR-01/02/03 acceptance and WP-04 sections were retained. Range-diff
  changes only the documentation context. Production, tests, example scripts
  and inventories are identical to `c911c9d`. Composed identity/project/journey
  regressions passed **103 tests in 34.89 s**; Ruff, diff and current inventory
  checks pass, and all five inventory files are byte-identical to their backup
  Git blobs. A new exact-head PR CI run remains required before integration.
- After ADR-04/07 PR #35 merged as `4debafa`, another authorized own-commit
  rebase preserved `c75b234` at
  `codex/backup-wp04-product-before-adr04-07-20260930`. The sole evidence-register
  conflict retained the merged main text exactly outside this WP-04 section,
  including ADR-04/07 acceptance and the corrected open-gate statement.
  Production, tests, examples and all five inventory bytes remain identical to
  `c75b234`; range-diff changes only documentation context and this evidence.
  Focused identity/project/journey tests passed **103 tests in 34.44 s**. Ruff,
  diff and current inventory checks passed. Exact-head CI on the newly composed
  PR head is required; earlier CI does not validate this final composition.
- This is a package-only slice. Tables, views and sequences, additional parser
  grammar, quoted-call extraction and the remaining ADR-06 product exit still
  require work. WP-04/G-04 remain open. No runtime Oracle proof or release claim
  is made by this evidence.

## WP-07 follow-up — coverage completeness and direct Blueprint revision (Draft)

- Branch `codex/formslang-3-wp07-gap-composition` replays the coverage commit
  `cf167477` and the three direct revision commits `2341a8c`, `f954ca0`,
  `99767b5` on main `066288e`. Backup refs preserve the original heads. The
  only cherry-pick conflict was adjacent tests in `test_database_coverage.py`;
  both positive regressions were retained. Range-diff changes are context from
  WP-04 and that test placement, with no lost commit.
- Coverage RED: a supported `CREATE TABLE` present in `not_extracted` left the
  project assessment `COMPLETE`. GREEN: it is `INCOMPLETE`, while an unmodelled
  informational `CREATE INDEX` does not demote a complete assessment. The
  strict coverage `xfail` became a positive regression.
- Direct revision RED: changed SQL bytes at the same path kept the same
  `source_revision`. GREEN: raw SHA-256 digests distinguish changed bytes,
  including SQL with no extracted objects; absent supplied paths contribute a
  marker; sorting the revision inputs preserves source-order independence. The
  strict direct revision `xfail` became a positive regression.
- Composition with WP-04 exposed one more RED in the existing repeat-build
  regression: a temporary staging path entered `source_digests`, making identical
  builds differ. Remapping it to the logical source path made that test GREEN.
  A new direct `blueprint_io.load` test was RED because an unavailable supplied
  SQL path left `source_revision` unchanged; adding an explicit unavailable
  marker made it GREEN. No source bytes or temporary paths are serialized in
  the database inventory. Project manifest revision semantics are unchanged.
- Focused composed suite: `python -m pytest tests/test_database_coverage.py
  tests/test_blueprint_identity_inputs.py tests/test_database_wp04.py
  tests/test_database_wp08.py tests/test_blueprint.py
  tests/test_blueprint_backend.py tests/test_project_analysis.py
  tests/test_project_service.py tests/test_project_sources.py
  tests/test_project_discovery.py -q` returned **257 passed, 3 skipped,
  1 xfailed**. Three repeated Python 3.13 revision/ID/order checks returned
  **3 passed** each. Frozen full suite on Python 3.13:
  `py -3.13 -m pytest -q -p no:cacheprovider` returned **2082 passed,
  5 skipped, 2 xfailed in 884.60 s**. Ruff, `git diff --check` and the current
  `inventory-wp04.json` generator check passed. Historical inventories have no
  diff against main. Hosted CI remains required for this Draft head.
- The `CREATE PACKAGE IF NOT EXISTS` strict `xfail` remains open; the other
  inherited expected failure is outside these two fixes. No 3.0 gate closes.

## Gates still open

No gate listed above has met its complete 3.0 release criterion. Architecture
decisions, partial product slices, probes and 2.2 behavior do not close the
remaining product, portability, external-system or human acceptance work.
The 2.2 behavior described in [baseline-audit.md](baseline-audit.md) is a
baseline, not a gate result.
