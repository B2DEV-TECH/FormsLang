# Modernization project model (2.0 foundation)

Status: released in FormsLang 2.0.0. The project wizard, local CLI and versioned HTTP
API share this model, including persisted assessment, review and gated generation.
Existing 1.x interfaces retain their contracts. See the approved
[product architecture](formsLang-2-product-architecture.md).

## Storage and portability

```text
<project>/
  .formslang/
    project.json
    project.session.db
    modules/<source-id>/<revision>.session.db
    backups/<snapshot-sha256>.session.db
```

`project.json` uses `formslang-project/1`. It contains ID, name, optional
description/client label, source roots, `target_platform`, `target_version`,
`target_representation`, fixed store basename and mirrored analysis/engine revision.
The default supported target is Oracle APEX / 26.1 / APEXlang. Unsupported target
or format values fail explicitly. Secrets and source bodies have no descriptor
fields. Unknown fields are rejected, not passed to another configuration layer.

Source paths are relative to the project directory, not `.formslang`. External
paths can be explicitly authorized; moving such a project may require relinking.
Metadata is not filesystem authority. The caller supplies host-approved roots.
Missing source does not prevent reading a saved assessment. Reopen loads saved
evidence first, then hashes current source through a local freshness job. It does
not rerun the reasoning engine or contact an external provider.

SQLite is authoritative. A stale, missing or syntactically broken descriptor is
repaired from the valid database on open. A descriptor that names another project,
store or unsupported format is rejected. A read-only descriptor repair failure
reports that SQLite state is preserved. Project creation reserves a new
`.formslang` directory and publishes a complete staged DB with a hardlink; it
never overwrites an existing project. The filesystem must support hardlinks.
A failure before DB publication may leave an empty reserved directory requiring
inspection; no successful creation is reported in that case.

The project database adds `modernization_project`, `project_assessment`, and
`project_module_session` alongside the existing Store schema. Assessments are
retained by revision. Publishing the current pointer, assessment and Blueprint
snapshot is one `BEGIN IMMEDIATE` transaction with an expected-revision check.
Another writer with an outdated expected revision receives `RevisionConflict`.
Contention is bounded and returns `ProjectBusy`.

Phase B adds configuration revisions, discovery runs/entries/diagnostics, durable
jobs, run metadata and explicitly selected derived XML through additive schema
migrations. The descriptor is not a job database. Recent-project metadata stores
locators and host-local source capabilities, never a second assessment copy.
Assessment publication and the successful job transition share one transaction.
Cancellation, lost authority or changed source leaves the previous pointer intact.
Repeated identical input retains the original assessment timestamp.

Both managed and local creation reserve locator metadata and an initialization
owner marker before publication. Retry must match actor/request/descriptor; it can
repair a committed DB's mirror without adopting an unrelated directory. Explicit
same-user relocation can replace a missing local locator, never a live clone, and
does not inherit source capabilities from the relocated descriptor.

## Revisions and review

Source IDs hash root ID plus normalized relative path, so equal module names in
different roots do not share history. Source revisions hash sorted manifest
entries and intake options, including raw-byte SHA-256 and missing/failed status.
File timestamp alone never establishes freshness. A hash is not parse support.

Analysis revision includes source revision, engine identity and options, including
the server-owned target. Engine identity includes rule versions and module-content
digests. The frozen distribution includes Python fingerprint resources and the
synthetic demo; absence fails explicitly rather than giving an unverifiable revision.
No benchmark baseline or legacy Blueprint protocol is
rewritten to achieve this stronger project contract.

`project-assessment/1` wraps the existing Blueprint with source manifest, target,
source/analysis revisions, engine identity, options, analysis timestamp and status.
Binding changes finding revision identities, not deterministic recommendations.
Architectural history remains in the existing append-only Blueprint review table.
A finding retains its original engine revision; publication verifies the derived
project finding revision against the current analysis revision before writing.
A project-local trigger increments the review revision for each committed review;
rolled-back reviews do not advance it. Conversion approval remains separate.

Assessment completion is `COMPLETE`, `COMPLETE_WITH_WARNINGS` or `INCOMPLETE`.
Freshness is separate: `CURRENT`, `STALE`, `MISSING_SOURCE`, `INCOMPLETE` or
`UNVERIFIED` before a check. Current is evidence as of the last hash check, not a
filesystem watch. Failed material inputs remain explicit. Changed source/engine
suppresses applicable review overlays without deleting history. Reanalysis against
changed source conservatively invalidates project-wide review.

Relink preserves the logical root ID and validates content, not the directory
name. Same-content relocation can retain a current assessment; different content
requires refresh. Raw bytes are staged and hashed before parsing, then checked
again before publication; source-change failures never publish mixed evidence as
Current. Matching FMB/XML names do not prove XML freshness.

## Importing 1.x sessions

`import_legacy_session(project, source, source_key=...)` inspects recognized schema
read-only, rejects unknown tables/triggers/views and performs SQLite backup rather
than copying a potentially stale main file. Committed WAL state is included.
The original is never opened as a writable Store or migrated in place.

An immutable pre-migration backup is retained. A second staged copy receives
additive Store migrations with job reconciliation disabled. Original columns and
rows are compared before publication. Provenance records original location,
migration version and snapshot hash in the local database. Logical snapshot
digests make repeated import idempotent; changed snapshots get new revisions.
An interrupted import can leave a published but unlinked module copy. Retry only
reuses identical content and does not overwrite a divergent existing copy.

Original tasks, proposals, all decisions, Blueprint reviews, settings, key
confirmations, test records and export salt survive. A source-less legacy session
remains inspectable under its legacy contract; import does not manufacture a
current project assessment or new generation approval.

## Local application-library example

```python
from pathlib import Path
from formslang.projects import local_project_access
from formslang.project_service import ProjectService
from formslang.project_model import SourceRoot

root = Path("modernization-project").resolve()
sources = Path("legacy-exports").resolve()
access = local_project_access(root, approved_roots=(sources,))
service = ProjectService(access)
try:
    project = service.create("Order Management", roots=(
        SourceRoot("forms", "forms", str(sources)),
    ))
finally:
    service.close()

service = ProjectService(access)
try:
    reopened = service.open()
    saved_assessment = service.assessment()  # None until an assessment is published
finally:
    service.close()
```

Creation needs no provider, Oracle connection or account in local mode.
Authenticated mode rejects local shortcuts. Server adapters must obtain a fresh
authorized project context on every request, honoring membership and RBAC; the
in-process context is not a credential that can be submitted by a browser.
Registered paths are checked before canonicalization so an adopted project cannot
hide a junction into another organization's project under the same data directory.
