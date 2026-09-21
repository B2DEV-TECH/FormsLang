# Reviewed project APEXlang generation — Phase E development

Unreleased development, still version 1.6.0. Generation is local and deterministic;
it needs neither AI nor Oracle database credentials. The default target profile is
Oracle APEX 26.1 / APEXlang. SQLcl is optional for **offline syntax validation**.

## Workflow

1. Open an analyzed project and choose **Generate**.
2. Select a module. Inspect the actual blockers, not just its intervention badge.
3. **Prepare code review** creates a source-bound session using the existing conversion Store.
4. Review architecture findings in **Review**. Accepted/Changed must remain applicable.
5. Confirm the observed target mapping, security and database prerequisites with a
   rationale. Confirm row keys explicitly where supported. Checkboxes do not implement
   missing business or security behavior.
6. Review each executable unit separately. Save the target plan before approving code;
   later review/target changes require code revalidation. Drafts do not authorize generation.
7. Generate the eligible module. Download its immutable APEXlang ZIP, then explicitly
   choose **Validate offline with SQLcl**. Generation never imports or deploys.

One run selects one independent module application. Other modules remain excluded,
with their source IDs in artifact metadata; this is not a merged estate application.
Empty skeletons, arbitrary page selection and multi-module merging are not implemented.

## Eligibility and safety

The server checks current source/analysis/review/target/code revisions. It requires
applicable human decisions, supported mappings, reviewed prerequisite rationale and
explicit code approval. `AUTO` alone is never sufficient. Unknown, stale, unresolved
architecture, unsupported Forms code and unobserved database identity block generation.

Only implemented layout mappings and enabled validation mappings are accepted.
Executable mappings that the exporter would disable block the whole module, rather
than leave a save operation without its business control. Unsupported item/block
write restrictions, query predicates, hidden validation/default behavior, range rules,
dynamic initial values and subclassed controls fail closed. Database-bound forms
require observed exact table/column identities and confirmed supported row keys.
Quoted, remote and ambiguous database names are not silently normalized into targets.

Item/LOV collisions and incompatible mappings block publication. The original source,
deterministic engine recommendation and architectural history are never replaced.
Approved code records explicit reviewer identity and evidence binding in existing
decision history. A legacy reapproval without that binding is not current approval.

## Artifacts and validation

Every run gets an opaque ID under the project's managed `.formslang/artifacts` area.
The expanded `.apx` application and ZIP have hashes; earlier files are never overwritten.
Downloads verify the exact file set and hashes. Edit a copy in your own version-control
workspace: editing the managed artifact invalidates validation/download eligibility.

Metadata records source/analysis/review/target/code revisions, target, policy, timestamp,
exclusions and hashes. Generation state is `Generated`; validation is `Not Validated`,
`Validated` or `Validation Failed`. Unavailable/broken SQLcl never means success.
Validation must report actual success, not merely exit code zero. The tool operates on
a private snapshot and the managed artifact is rechecked before recording the result.

Syntax validation does not verify runtime behavior, security configuration, database
dependencies or functional equivalence. Developers and application owners still review,
test and perform UAT. No executable database refactoring is invented.

## API and CLI

All routes below are under `/api/v2/projects/:id` and reauthorize project access.

| Route | Action |
|---|---|
| `GET generation` | Modules and latest 50 versioned artifacts |
| `GET generation/modules/:source` | Current blockers, target plan, code/key revisions |
| `POST generation/modules/:source/prepare` | Prepare existing conversion session |
| `POST generation/modules/:source/plan` | Explicit reviewed prerequisites/key plan |
| `GET/POST generation/modules/:source/code/:task` | Bounded evidence/history / code decision |
| `POST generation` | Generate exact selected source/target/code scope |
| `GET artifacts/:artifact/download` | Export-authorized, verified ZIP |
| `POST artifacts/:artifact/validate` | Explicit export-authorized offline validation |

Mutations carry the returned project/source/analysis/review binding plus target/code
revisions where relevant. Stale requests return 409 and must reload, never auto-replay.
Code writes use approval permission; generation/download/validation use export permission.
Viewer export grants are project-specific and do not grant code or target-plan writes.

`formslang project generation` offers `status`, `module`, `prepare`, `plan`, `task`,
`code`, `generate`, `validate` and `download`. Use `--help` for exact parameters.
Commands use the same service. JSON request files contain revision-bound commands;
downloads refuse to replace an existing file. Authenticated mode uses the authorized
API rather than local CLI bypass. Source/code excerpts are limited; default lists
do not expose host paths or full source bodies.

## Operational limits

Generation is synchronous, not a durable background job; no continuation after app
exit is promised. An interrupted preparation may leave unregistered source/session
files: preparation refuses to overwrite them. Preserve them and inspect the project
before recovery; there is no automatic cleanup/retry masking this condition.
Cross-database target/key updates are fail-closed, not globally atomic. Reanalysis
or target/review changes can require fresh code approval. This conservative first
scope favors reviewability over converting unsupported behavior.
