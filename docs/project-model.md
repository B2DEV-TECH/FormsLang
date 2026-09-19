# Modernization project model (2.0 foundation)

Status: Phase A application-library foundation. This is not yet the 2.0 wizard,
project CLI, project HTTP API or generation workflow. Existing 1.x interfaces
continue to use their current contracts. See the approved
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
Missing source does not prevent reading a saved assessment, but Phase A does not
yet implement refresh or live source freshness checking.

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

## Revisions and review

Source IDs hash root ID plus normalized relative path, so equal module names in
different roots do not share history. Source revisions hash sorted manifest
entries and intake options, including raw-byte SHA-256 and missing/failed status.
File timestamp alone never establishes freshness. A hash is not parse support.

Analysis revision includes source revision, engine identity and options, including
the server-owned target. Engine identity includes rule versions and module-content
digests. The frozen distribution must retain the fingerprint resources before
project workflows are exposed there; absence fails explicitly rather than giving
an unverifiable revision. No benchmark baseline or legacy Blueprint protocol is
rewritten to achieve this stronger project contract.

`project-assessment/1` wraps the existing Blueprint with source manifest, target,
source/analysis revisions, engine identity, options, analysis timestamp and status.
Binding changes finding revision identities, not deterministic recommendations.
Architectural history remains in the existing append-only Blueprint review table.
A project-local trigger increments the review revision for each committed review;
rolled-back reviews do not advance it. Conversion approval remains separate.

Current means the published run was complete for its supplied manifest. Incomplete
retains explicit failed inputs. A changed engine projects Stale and removes
applicable approval overlays without deleting history. Until Phase B provides
live source checks, Current is not a claim that files were checked on every open.
Reanalysis against changed source conservatively invalidates project-wide review.

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
