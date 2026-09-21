# Oracle Forms to APEX with FormsLang

FormsLang is an open-source modernization workbench for Oracle teams receiving an
unfamiliar Forms estate. Its purpose is less manual discovery and better reviewed
decisions, not magical one-click conversion or unmeasured migration-cost promises.

## Inputs

Select supported Forms2XML and related packages, procedures, functions, views,
tables/DDL and other supported SQL sources. FMB, PLL, MMB and OLB are discovered
with representation warnings; Forms2XML conversion requires separately installed
Oracle tooling and explicit action. Neither AI nor a live database is required.

## Process

Create Project → Discover → Analyze → Overview/Inventory → Review → Generate
eligible APEXlang → Validate explicitly → Deliver reports/package.

The same persistent assessment drives UI, API and CLI. Source fingerprints explain
which inputs were assessed. Partial failures, incomplete database context, dynamic
SQL and stale sources remain visible. Review history does not overwrite engine
evidence or silently transfer to changed source.

## What is automated

Source inventory, deterministic parsing/correlation, dependency evidence, risk and
modernization triage, transparent priority ordering, safe supported structural
generation, and snapshot reports/backlog packaging.

## What is assisted

Cross-layer ownership, candidate business rules, duplicate logic, native APEX
mapping and target prerequisites. The engine proposes; evidence explains; a human
reviews architecture and code independently. Unsupported behavior stays blocked.

## What requires people

Undocumented intent, business-owner decisions, approval/identity/security behavior,
transaction/navigation design, executable code review, database prerequisites,
target runtime tests and UAT. Accepting a recommendation does not prove functional
equivalence or authorize deployment.

## Outputs

Inventory, risk/direction/intervention distributions, priority review history,
eligible selected-module Oracle APEX 26.1 / APEXlang applications, self-contained
executive/technical HTML, CSV/JSON backlog and a hash-manifested modernization
package. Default reports omit source bodies/private notes but are not anonymous.
No invented executable database refactoring or labor estimate is emitted.

FormsLang 2.0 supports one independent module application per generation
run, not full-estate merging. Offline SQLcl validation does not establish runtime
parity or Oracle endorsement. See [user guide](user-guide/README.md),
[APEX target](apex-26-modernization.md), [limitations](user-guide/15-limitations.md)
and [actual acceptance/release status](quality-acceptance.md).
