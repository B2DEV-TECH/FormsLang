# ADR-07 — Git exchange synchronization

Status: **Accepted (architecture contract, 2026-09-30)**. This selects the
pre-WP-20 reconciliation boundary; it is not a Git implementation, a tested
worktree integration, or a release-gate result.

## Context

ADR-01 keeps accepted state in the operational coordinator; ADR-03 publishes
explicit portable roots. Git can version permitted exchange files but cannot
atomically switch the live SQLite database and object store with a checkout.
The current product has no 3.0 checkpoint exchange, imported-frontier tracking,
or Git reconciliation service. `.formslang/` contains local operational
databases and must not be treated as a shared Git working-tree payload.

Checkout, reset, merge, file deletion and manual edits can all change exchange
bytes without a file watcher event or a useful branch-name change. Two Git
worktrees may contain the same portable files while their local accepted
histories diverge.

## Proposed decision

Git is an **external transport and review surface** for explicitly exported,
policy-permitted portable files. FormsLang does not clone, merge branches,
push, pull, reset or infer approval from a commit. Every Git worktree or other
exchange directory has a separate operational workspace binding and live
SQLite/object storage. Opening a second directory must not point it at the
first directory's live database, including through a redirected or aliased
operational path. Moving or relinking a binding requires an explicit identity
check; matching folder names are insufficient.

Record a per-workspace synchronization reference containing the selected
exchange location, last reconciled portable root/object IDs, declared profile
and imported frontier, and the corresponding local accepted checkpoint.
Store the binding outside the portable files. Branch name, HEAD SHA and file
timestamps may aid diagnostics but are not the synchronization authority.
Status recomputes the relevant manifest and decision-file content identities
from the current filesystem before any operation that assumes exchange
synchronization. A watcher can prompt an early refresh, but is never the only
check. Identical bytes after a branch switch remain synchronized; changed,
missing, malformed or inaccessible bytes have distinct states.

On a changed exchange root, show **external changes awaiting reconciliation**
with the last reconciled and observed identities. Local history remains
inspectable, but no external bytes become accepted merely because they are
present. Import preview uses ADR-04's staging/trust rules and compares the
incoming frontier with the recorded base and current local checkpoint.
Origin-local revision numbers and a shared Git commit are not domain ancestry.
A common accepted checkpoint/foreign-event frontier may support a semantic
three-way comparison; unrelated or unverifiable ancestry requires explicit
conflict review. Same-subject competing decisions, changed
source/analysis bindings, unsupported schemas, policy differences and
unavailable objects cannot be last-writer-wins. Disjoint changes may be
applied only by an explicit, authorized, revision-fenced domain operation
after all bindings and policy are rechecked.

Preview and apply each stage immutable copies of the selected exchange bytes.
Apply verifies that its staged identities still match the preview before the
local write transaction; a mismatch returns a conflict without accepted-state
changes. The local fence cannot lock Git files: they may change after this
check. Apply therefore uses only its verified staged bytes, records import
events through ADR-01 and publishes a local checkpoint through ADR-03. It
rescans the exchange files before advancing the synchronization reference. If
they changed meanwhile, the accepted import remains recorded for the staged
bytes, but status stays **external changes awaiting reconciliation** rather
than falsely reporting synchronization. A publication-pending local
checkpoint is likewise not reported as synchronized.
Export likewise uses an explicit preview/profile and writes canonical files
without running Git commands or copying live SQLite. An external Git merge
never substitutes for the semantic import preview.

## Alternatives and consequences

- Keeping live SQLite inside Git is rejected: Git checkout is not a database
  transaction, and two worktrees cannot safely share an active coordinator.
- Relying on branch/HEAD, mtimes, or a watcher is rejected: manual edits,
  identical content on different branches, missed events and resets break
  those signals.
- Automatic import on checkout is rejected: it could promote untrusted
  approvals or overwrite local decisions without a revision fence.

The local binding needs its own recovery path if a process stops after domain
apply but before updating the synchronization reference. Retrying compares
the accepted import event and exact content IDs, then repairs the reference
idempotently; it must not append a second import. Local policy controls which
filenames and source bodies may be exported.

## Acceptance work and implementation boundary

The binding identity, content fingerprint, state transition and interruption
contract were reviewed against ADR-01/03/04 as the accepted architecture.
Local SQLite remains authoritative; Git transports explicit exchange files
and cannot grant an approval or silently apply a checkout.
WP-20 must prove two Git worktrees with separate operational stores, checkout
and manual-edit detection without a watcher, identical bytes on another
branch, deleted/corrupt/restricted files, changed bytes between preview and
apply, common-base disjoint changes, same-subject conflict, unrelated
origins, interrupted reference update, and repeat reconciliation. Tests must
show that no Git commit grants approval and that local reads do not silently
import changed files. No such product proof is supplied by this draft.
