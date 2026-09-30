# WP-10 portable-state schema draft

Status: **Draft for ADR-03 review**. This document is not a shipped format.
The executable spike currently proves only a smaller manifest with event and
object references.

## Root manifest candidate

```text
schema: formslang-checkpoint/1
repository_id: stable repository identity
origin_id: identity of the ledger that assigned local event sequence numbers
event_frontier: highest accepted event sequence in that origin
source_set: immutable object ID or explicit unavailable marker
analysis: immutable object ID, engine identity and capability schema
decision_frontier: accepted decision event ID and local sequence
policy: interpretation policy ID
objects: sorted referenced object IDs with kind, byte length and availability
publication: internal coordinator state; never a claim of Git synchronization
```

Each domain object references only earlier or independent immutable objects.
The root references the closure and is written last. It must never reference
its own digest. A report or validation run can reference the input checkpoint
that existed before it was produced; its publication belongs to a later
checkpoint. This avoids circular provenance.

Canonical encoding proposal: UTF-8 JSON with known field order, sorted
set-like references, preserved order for semantic arrays, no NaN/Infinity,
LF ending, bounded lengths and an explicit schema major version. Original
source objects preserve exact bytes; canonicalization applies only to
structured objects. IDs use a versioned kind-separated digest per ADR-02.

## Export profiles and closure

| Profile | Required closure | Claims it may make |
|---|---|---|
| Full authorized backup | All reachable accepted objects, decision history and permitted source bytes, plus verification metadata | Reopen the declared historical state after integrity and authorization checks |
| Review/redacted | Allowed facts, evidence locators or redacted excerpts, decision records permitted for review, explicit unavailable markers for omitted private/source objects | Inspect the declared subset; cannot reconstruct omitted bodies or trust imported approvals |

Import must verify repository/origin identity, object digests, schema versions,
closure, decision provenance and conflicts before an explicit apply. A Git
commit is a transport/review record, not authorization. Retention/deletion
must preserve a non-sensitive availability record where policy permits.

## Proof still required

Clean-workspace reopen; missing/corrupt object quarantine; divergent origins;
conflicting imported approvals; private proposal retention; Windows and Linux
canonical-byte equality; interrupted directory flush; artifact and validation
applicability; backward-compatible migration from 2.2. The WP-10 spike does
not supply those product proofs.
