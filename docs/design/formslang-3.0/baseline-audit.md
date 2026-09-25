# FormsLang 3.0 — Baseline audit (M0)

Status: **M0 evidence.** This document records what the repository contains and
does at one commit. It is not a 3.0 capability statement. Nothing here means a
3.0 requirement is implemented; see [requirements-matrix.md](requirements-matrix.md)
for the per-requirement status.

| Field | Value |
|---|---|
| Audited commit | `1d9cb4702a9f7f2990e53dda0a289357fc5dd57d` (`main`, "Merge pull request #19", 2026-09-25 09:36 -03:00) |
| Specification | FL3-MASTER-2026-09-25, revision 1.0 ([master-specification.md](master-specification.md), SHA-256 `60e1924a…401b29e`, identical to the delivered package) |
| Package version | `2.2.0` (`pyproject.toml:7`, `desktop/src-tauri/tauri.conf.json:4`); `requires-python >=3.10`; no runtime dependencies |
| Latest release | `v2.2.0`, published 2026-09-24, tag at `28d100d`; assets `FormsLang_2.2.0_x64-setup.exe`, `FormsLang_2.2.0_x64_en-US.msi` |
| Unreleased on `main` since `v2.2.0` | 2.3 phase-1 ecosystem contract (PR #17, docs/tests only), G-DML fix (PR #18), descriptor concurrency fix (PR #19) |
| Open issues | #20 (Windows `ProjectBusy` starvation under back-to-back descriptor publications), #1 (showcase record spacing vs Forms 14.1.2) |
| Open pull requests | none |
| Agent instructions | No `AGENTS.md` in the repository. Contributor instructions: `CONTRIBUTING.md`. Owner instructions for the agent are local and not part of the repository. |

## 1. Architecture map (as built)

FormsLang is a single Python package (`formslang/`, stdlib only) with a
server-rendered Workbench, a Tauri desktop shell and a CLI. There is no
frontend build step.

| Layer | Modules (verified paths) | Notes |
|---|---|---|
| Forms parsing | `parser.py`, `model.py` (dataclasses, no serializer) | Reads Forms2XML `module.xml`; FMB/FMX are not parsed |
| PL/SQL evidence | `plsql_evidence.py` (`VERSION="plsql-evidence/2"`), `plsql.py` (wrapper plus legacy `_TABLE_REFS` regex), `database.py` (package/table DDL), `depgraph.py` | Token-based READS/WRITES/CALLS extraction |
| Facts graph | `blueprint.py` (`VERSION="blueprint/1"`, `ENGINE_VERSION` includes the lexer version), `blueprint_io.py`, `modernization.py` (`modernization/1`), `hotspots.py`, `risk.py`, `rules.py`, `sensitive.py` | Entities and edges with `level` FACT/INFERENCE; references `SYMBOLIC_REFERENCE` or `RESOLVED_TO_DATABASE_OBJECT` |
| Project repository | `project_model.py` (`formslang-project/1`), `project_store.py`, `project_service.py`, `project_analysis.py`, `project_assessment.py`, `project_jobs.py`, `project_lock.py`, `project_freshness.py`, `project_discovery.py`, `project_intake.py`, `project_sources.py`, `project_migration.py`, `store.py` | See §3 for the transaction authority and write routes |
| Queries and views | `project_projection.py`, `project_visualization.py` (`formslang-lanes/1`), `dashboard.py` | Overview, System Map, Module 360, Hotspots, Inventory |
| Review and decisions | `project_review.py`, `store.py` (`blueprint_review`, `decision`) | Two separate decision stores; see §3.4 |
| Generation | `project_generation.py`, `project_generation_policy.py` (`project-generation/1`), `apexlang.py`, `apexlayout.py`, `formui.py`, `convert.py`, `adapters/generic.py` | APEX generation calls `apexlang.export_apexlang` directly |
| Validation | `project_validation.py`, `apeximport.py` | Offline SQLcl `apex validate`; package-structure check for the generic target |
| Reports | `project_reports.py`, `project_report_render.py`; legacy `report.py`, `formdoc.py`, `blueprint_io.write` | Revision-fenced project reports; legacy reports are not fenced |
| HTTP / Workbench | `workbench.py` (legacy `/api/*`, `ThreadingHTTPServer`, loopback only), `project_http.py` (`/api/v2/*`), `ui/` (HTML/CSS/JS as Python strings, 1,318-line `ui/modernization_visual.py`) | CSP `default-src 'none'`; one vendored JS library (QR code for MFA) |
| CLI | `cli.py`, `project_cli.py` | See §5 |
| Identity and access | `authstore.py` (`auth.db`, WAL), `authcrypto.py`, `rbac.py`, `totp.py`, `authui.py`, `secrets.py` (OS credential store) | Local mode by default; authenticated mode exists |
| AI | `ai.py`, `ailayout.py`, `blueprint_ai.py`, `convert.py`, `policy.py` (egress policy) | Optional |
| Experimental, not on product paths | `modernization_model.py`, `architecture_policy.py`, `target_adapter.py` registry, `adapters/apex.py` | See §4.6 |
| Packaging | `packaging/formslang-engine.spec` (PyInstaller), `desktop/` (Tauri 2, MSI and NSIS) | `build-installers.yml` (reusable), `installer-acceptance.yml` (manual upgrade test) |

## 2. Test and verification commands discovered

| Command | Where it is defined | Run in M0? |
|---|---|---|
| `python -m pytest -q` (Ubuntu and Windows × Python 3.10–3.13) | `.github/workflows/ci.yml` job `test` | CI on `1d9cb47`, see §6 |
| `python -m ruff check .` | `ci.yml` job `lint` | CI on `1d9cb47`; locally on the M0 branch |
| `python examples/verify/workbench_browser_check.py --output …` | `ci.yml` job `browser` (Edge via CDP) | CI only |
| `python examples/verify/project_browser_check.py --output …` | `ci.yml` job `project-browser` | CI only |
| Export the showcase twice and `cmp` the ZIPs | `ci.yml` job `export` | CI only |
| SQLcl `apex validate --offline` plus two negative controls | `ci.yml` job `validate` (Java 21, `sqlcl-latest.zip`) | CI only |
| Installer upgrade from the last release (NSIS and MSI) | `installer-acceptance.yml` → `examples/verify/installer_upgrade.ps1` | Not run in M0 (manual workflow) |
| `py examples/verify/ecosystem_inventory.py --check` | `docs/design/ecosystem-explorer-2.3/README.md` | Covered by `tests/test_ecosystem_phase1.py` |
| `examples/verify/project_corporate_scale.py --profile ecosystem` | ecosystem design docs | Not run in M0 |

Documentation drift found: `CONTRIBUTING.md` says `python -m formslang serve`
(the command is `workbench`) and "Python 3.11+" (the package supports 3.10).

Test layout: 112 `tests/test_*.py` files, fixtures in
`tests/fixtures/{corpus,ecosystem,estate,golden,minicase,project-generation,showcase}`.
Eight UI-behaviour test files run production JavaScript under Node and skip
without it. No pytest test drives a real browser or a real SQLcl; those run
only in CI jobs.

Local environment for this audit: Windows 11, Python 3.13.15 and 3.12.10
(3.10 and 3.11 not installed locally), Node 22.16.0, Java 21, SQLcl present,
ruff 0.16.4.

## 3. Persistence, transaction authority and write routes (§30.2 step 6)

### 3.1 Stores

| Store | Path | Mode | Authority for |
|---|---|---|---|
| Project database | `<root>/.formslang/project.session.db` | SQLite rollback journal, `busy_timeout=1000` (`project_store.py:134`) | Descriptor, configuration, assessments, discovery, jobs, analysis runs, review, annotations, target plans, artifacts, validation records |
| Descriptor mirror | `<root>/.formslang/project.json` | Replaced atomically inside the `BEGIN EXCLUSIVE` transaction that changes the descriptor (since `ce2cfdd`) | A mirror; the database is authoritative |
| Module session databases | `.formslang/modules/<sid>/<rev>.session.db` | SQLite, default 5 s timeout | Per-module review keys, conversion tasks, proposals, conversion decisions |
| Content-addressed files | `.formslang/backups/<sha>.session.db`, `.formslang/derived/<sid>/<xml_sha>/module.xml` | Written once | Backups and derived Forms2XML |
| Artifacts | `.formslang/artifacts/<uuid4>/` | Written before the database row, no fsync, no cleanup on failure | Generated packages |
| Identity | `auth.db` in the config directory | SQLite WAL, `busy_timeout=5000`, schema version 1 | Users, sessions, memberships, audit |

Writes go through `ProjectStore._write()` (`BEGIN IMMEDIATE`) and
`save_assessment` / descriptor publication (`BEGIN EXCLUSIVE`). Revision fences
(`_fence`) check analysis, review and configuration revisions. There are no
idempotency keys.

### 3.2 What exists and what does not

- **Exists:** analysis revisions, review revisions (bumped by triggers),
  configuration revisions, a finding-revision digest, a report
  `snapshot_revision` digest, append-only review history, per-run analysis
  records, revision-fenced report capture.
- **Does not exist:** whole-project checkpoints, baselines, a content-addressed
  object store for analyses, a portable history format, `.flm`, an event log
  with origin identity, idempotency keys. `blueprint_snapshot` is a single row
  overwritten by each assessment; older assessment rows are kept but no API
  lists them.

### 3.3 Routes that write project state

- Every `POST`/`PUT`/`DELETE` under `/api/v2/projects/*` and the legacy `POST /api/*` routes.
- CLI `project create|demo|relink|discover|analyze`, `project review decide|annotate`,
  `project generation prepare|plan|code|generate`, and `report` / `generation download`
  (write a new file, refuse to overwrite).
- **Reads that write** (conflicts with API-02 "no GET that mutates" and INV-05):
  `ProjectStore.open` may republish the descriptor (`sync_descriptor`) and migrate
  run tables (`_migrate_runs`); `Store.__init__` runs `executescript` and commits;
  `ProjectService.open` recovers orphaned jobs to `FAILED`; CLI `status`, `summary`
  and `inventory` call `freshness()`, which inserts a job row; `open_locator`
  writes `locators.json`.
- `ProjectService.import_session` and `project_migration` have no product callers.

### 3.4 Decisions today

- **Architectural review** (`blueprint_review`, project database): append-only
  `APPROVE`/`MODIFY`/`REJECT`/`DEFER`, displayed `STALE` when the finding
  revision changes. The actor is derived on the server.
- **Conversion approval** (`decision`, module session database):
  `pending`/`approved`/`rejected`/`needs_work`.
- Bulk review is bounded (200 items) and bound to a `preview_token`.

These two stores already keep architectural review separate from conversion
approval (DEC-03). They do not yet separate lifecycle, applicability and
eligibility as three dimensions (DEC-01, §12.1).

## 4. Recorded concerns (§3.3) — verification

| Concern | Result at `1d9cb47` | Evidence |
|---|---|---|
| **G-DML**: `UPDATE` right after `THEN` not recorded as a write | **Fixed** in `ae7091f` (PR #18, merged as `20792a5`); extractor `plsql-evidence/2` | `tests/test_blueprint.py` regressions for `IF`/`ELSIF`/`ELSE`/`EXCEPTION WHEN`/`CASE`, `MERGE` counted once, `MERGE` then `UPDATE`; `tests/test_ecosystem_phase1.py::test_case_b_update_right_after_then_is_recorded_as_a_write`. Passed locally (see §6). |
| **G-SCHEMA-BODY**: schema-qualified package body loses its subprograms | **Reproduced; open.** `database.parse_package_body` finds the body start with `tokens[i - 2] == "BODY"` (`database.py:426`); with `SCHEMA.NAME` that token is `.` | `test_gap_case_c_schema_qualified_package_body_loses_its_subprograms` pins the defect and passes (i.e. the defect is present) |
| **G-SCHEMA-COLLIDE**: same-named packages in two schemas collapse | **Reproduced; open.** Specs, bodies, tables, views and sequences are keyed by bare name (`database.py:359,419,580,628,638`); `parse_database_sources` merges with `dict.update`, last file wins | `test_gap_case_c_same_named_packages_in_two_schemas_collapse_into_one` pins it |
| **Windows ProjectBusy / descriptor timing** | **Reduced, not eliminated.** PR #19 (`f030b94`, `ce2cfdd`, `e5de525`). Windows CI repetition, 100 runs × 4 Python versions of the concurrency file: previous `main` 19/400 failures, `ce2cfdd` 4/400. Tracked as issue #20. | See §6 for the `main` CI record, including a new, different Windows failure on `1d9cb47` |
| **LEGACY_RESOLVED** | Defined by the 2.3 contract (§5.1): every 2.1/2.2 database resolution is presented as `LEGACY_RESOLVED` with caveat `SCHEMA_COLLISION_NOT_VERIFIABLE` until a schema-aware engine re-analyses. It exists only in `examples/verify/ecosystem_inventory.py`, the phase-1 tests and the contract; **no product code emits it yet**. | `test_no_2_2_database_resolution_is_presented_as_resolved`, `test_legacy_rule_lifts_only_for_a_schema_aware_engine_and_only_for_database_targets` |
| **Large aggregate map** | Measured in phase 1 (G-ESTATE-EMPTY): at 500 Forms the 2.2 ESTATE map keeps 100 of 531 nodes and 0 of 1,125 relationships. Warm projection reads 1.6–2.7 s at 500 Forms. Not re-measured in M0. | `docs/design/ecosystem-explorer-2.3/gaps-and-capture.md`, `performance-2.2-baseline.md` |
| **Experimental IR / adapters** | `modernization_model.py`, `architecture_policy.py` and the `target_adapter.py` registry are **not consulted by product paths**: `get_target_adapter`/`list_target_adapters` are called only by `tests/test_target_adapter.py`. The product imports `adapters.generic` functions directly for the target-neutral assessment package (`project_generation.py:481`, `project_validation.py:23`); APEX generation calls `apexlang.export_apexlang` directly. Blockers are plain dicts from `project_generation_policy.py`. | grep of callers at `1d9cb47` |
| **Output sanitization** | Existing controls: report `public_value` path/credential redaction, `literal_label` for integration-point names, signal IDs instead of free text, hotspot field allowlist, opt-in notes (`-sensitive` filename), CSV formula neutralisation, review excerpt suppression, SQLcl password scrub, allowlisted/aliased Blueprint AI context. Covered by e.g. `test_visual_figures_do_not_carry_host_or_url_literals`, `test_report_metadata_does_not_disclose_host_paths`, `test_source_excerpt_suppresses_credentials_and_host_paths`. **Not probed in M0:** the local System Map JSON (no literal renaming), and `convert.build_prompt`, which sends raw unit source to an AI provider gated only by the egress policy. | Scheduled as a probe in the plan (WP-05) |

## 5. Existing capabilities relevant to 3.0

| Area | Present | Absent or partial |
|---|---|---|
| CLI | `formslang project …` with `--json` on every subcommand (single-line JSON on stdout, progress on stderr); exit codes 0, 1, 2, 130; `apex validate` 0/1/2 | No JSON envelope with `schema`/`warnings`; exit codes 3–10 of §14.6 not distinguished; no `status/log/show/diff/checkpoint/baseline/verify/export/import` families |
| HTTP | `/api/v2` with 409 `PROJECT_CONFLICT` for revision conflicts and busy, 403, 404, 400; 500 is sanitised | No idempotency keys; GETs can write (§3.3) |
| Workbench | Overview, System Map, Hotspots, Inventory, Review, Dependencies, Generate, Reports, Project Settings; Executive/Technical modes | Navigation is not Explore · Decisions · Build · Validate · Reports · History; no History; no evidence inspector as a shared component |
| Reports | HTML executive/technical/risk; Markdown dossier/investigation/decision records; JSON investigation/backlog/decisions; CSV backlog; ZIP package; revision-bound and provenance-stamped; 128 MB cap | No PDF; no report definitions/catalog as data; no baseline comparison; metrics not defined as governed objects |
| Target | APEXlang export (deterministic ZIP, CI byte comparison), offline SQLcl validation, target-neutral assessment package | Neutral IR not wired; no plan object; runtime/import validation requires an owner-authorized Oracle environment |
| Migration | 1.x session import (`project_migration.import_legacy_session`, tested in `tests/test_project_migration.py`) — reachable only through `ProjectService.import_session`, which no CLI/HTTP route calls; external project registration | No 3.0 format migration; no user-facing 1.x import route |
| Security | Loopback-only server, CSRF/origin checks, MFA, RBAC, OS credential store | Authenticated mode is not part of the 3.0 local-first release boundary unless separately gated (ADR-11) |

## 6. Actual test results

| Run | Scope | Outcome |
|---|---|---|
| CI run 36135896101 on `1d9cb47` (`main`) | Full matrix | **Failed**: `pytest (windows-latest, py3.11)` — 1 failed, 1867 passed. All other jobs green (Ubuntu 3.10–3.13, Windows 3.10/3.12/3.13, ruff, both browser acceptances, deterministic export, SQLcl validate). |
| Failing test | `tests/test_project_http.py::test_overview_keeps_saved_metrics_and_reports_stale_source` | `GET /api/v2/projects/{id}/jobs/{job}` returned 500 while an analysis job was running. The 500 boundary logs no traceback, so the exception is not known from the CI log. |
| Earlier `main` CI | `6933080` (run 36065168686), `6e449a0` (run 36013639862) | Each failed one Windows pytest job on `test_concurrent_descriptor_readers_and_publication` with `ProjectBusy` (the defect PR #19 reduced) |
| Local, M0 branch (code identical to `1d9cb47`), Python 3.13 | `tests/test_ecosystem_phase1.py tests/test_blueprint.py tests/test_target_adapter.py tests/test_project_reports.py tests/test_project_review.py` | 139 passed, 1 skipped (symlinks unavailable to this Windows account), 132.9 s |
| Local reproduction of the job-status 500 | `tests/test_project_http.py` repeated on Python 3.12 and 3.13 with a plugin that records tracebacks at the 500 boundary | See [evidence-register.md](evidence-register.md) |

Local single runs are not a stability measurement. Windows stability needs the
repeated-run protocol used for PR #19.

## 7. Unavailable environments

- **Oracle Database / APEX runtime:** not used in M0. No import into any APEX
  workspace was performed; runtime acceptance (VAL level 4–5) requires an
  owner-authorized, disposable target.
- **Oracle Forms Builder / Forms2XML conversion:** not available to the agent;
  fixtures are pre-converted XML.
- **Python 3.10 and 3.11 locally:** not installed; covered only by CI.
- **Human usability sessions:** none held. The 2.3 five-professional evaluation
  remains PENDING.
- **Installed-build acceptance:** not run in M0.

## 8. Reuse / change / remove inventory

| Keep and reuse | Change behind tested contracts | Retire or quarantine (not in M0) |
|---|---|---|
| Parser and `model.py`; `plsql_evidence` token extractor (G-DML fix) | `database.py` schema handling (G-SCHEMA-BODY first, then G-SCHEMA-COLLIDE with a schema-aware identity and recorded ambiguity) | Legacy `_TABLE_REFS` regex in `plsql.py`, once no caller needs it |
| `ProjectStore` transaction discipline, revision fences, descriptor publication (PR #19) | Reads that write (§3.3) → explicit migration/recovery steps; read-after-open lock errors → `ProjectBusy` consistently (issue #20 and the `1d9cb47` job-status 500) | `target_adapter` registry and `modernization_model`/`architecture_policy`, unless ADR-10 adopts them with a real product caller |
| Append-only review history; server-derived actor; bounded bulk preview | Decision model: three dimensions (lifecycle/applicability/eligibility), `.flm` (M4) | Legacy `/api/*` routes and legacy shell, after the new Workbench covers their journeys (§16.8) |
| Revision-fenced report capture, sanitisation, deterministic generic package | Report definitions/datasets/metrics as data (ADR-09); PDF renderer | Unfenced legacy `report.py` output as a product report |
| APEXlang exporter, deterministic ZIP, offline SQLcl validation and CI controls | Plan object and closure (M6) | — |
| 2.3 ecosystem contract, fixtures, inventory and phase-1 tests | `LEGACY_RESOLVED` into product code when the schema-aware engine lands | — |
| `ui/` without a build step | `ui/modernization_visual.py` receives no new logic (ARCH-02); new shell per ADR-08 | — |

## 9. Claims that must not be made from this baseline

- That 3.0, or any 3.0 milestone beyond M0, is implemented.
- That Windows concurrency is fixed: the residual rate is measured and open (#20),
  and `main` at `1d9cb47` failed one Windows job.
- That schema-qualified or same-named packages resolve correctly.
- That generated APEX saves rows, reproduces Forms layout, or covers rules beyond
  those already recorded in `docs/quality-acceptance.md`.
- That PDF reports, checkpoints, `.flm`, History or CLI parity exist.
