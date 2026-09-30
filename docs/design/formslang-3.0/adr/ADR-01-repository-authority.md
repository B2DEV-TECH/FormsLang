# ADR-01 — Repository authority and transaction boundary

Status: **Accepted (architecture contract, 2026-09-30)**. This selects the
transaction ordering for WP-20. Product migration and durability still require
their own tests; this acceptance does not validate a product repository or close
a release gate.

## Context

The 2.2 project database is operationally authoritative, but ordinary opens
may run migrations or repair `project.json`; freshness reads create durable job
rows. [WP-06](../wp06-read-write-inventory.md) lists those paths. A future
checkpoint spans SQLite and files, so SQLite commit alone cannot make an
unrelated file replacement atomic.

## Proposed decision

Keep SQLite as the coordinator for accepted events, revision fences, object
references and publication intent. Promote verified immutable object bytes
before a short SQLite write transaction. Inside that transaction, recheck the
expected revision and register one accepted event plus the exact checkpoint
bytes as `PENDING`. Publish the checkpoint root manifest last from the
committed bytes, then mark it `PUBLISHED` in a second short transaction.
Failure after commit reports accepted state with pending publication; recovery
replays the committed bytes. A failed or missing object blocks publication.
Never infer approval from a file edit or Git commit.

An ordinary query needs a no-mutation path. Schema upgrade, mirror repair,
job recovery and a fresh source scan each need an explicit operation contract.
Keep the current rollback-journal mode unless a separate Windows and
supported-filesystem experiment proves a different mode safer; this ADR does
not adopt WAL.

## Evidence and limits

`examples/verify/repository_spike.py` is outside the product import path. Its
tests inject a pre-commit failure, post-commit crash, missing newly referenced
or inherited accepted object, flush interruption and concurrent revision
conflict. The inherited-object test first exposed an incorrectly accepted new
event; verification before the revision transaction repaired it. The spike demonstrates
the proposed order but does **not** prove power-loss durability of directory
entries, product migration, idempotency keys, permission checks, safe exports,
network filesystem support or recovery under real process termination. Those
are required for WP-20 and later release gates; this ADR's contract review
must record them as unproven rather than treating the spike as product proof.

## Alternatives retained for comparison

- File-authoritative operation needs an independent atomicity, conflict and
  migration proof; the current specification selects SQLite authority.
- Publishing the manifest before SQLite commit permits an unaccepted state to
  appear current. Publishing after commit without a durable intent loses the
  ability to recover an accepted state deterministically.

## Acceptance work

The WP-06 read/write inventory and WP-10 spike were reviewed together. The
spike's pre-commit, post-commit, inherited-object, flush-interruption and
concurrent-publisher tests establish the proposed ordering and expose the
verification-before-publication requirement. The accepted decision is the
coordinator/verified-object/revision-fence/recovery contract above, not a claim
that the spike is the product implementation. WP-20 must prove failure
injection across real project migration, a Windows/Linux reader and writer
matrix, explicit no-write reads, idempotency and authorization, recoverable
mirror/checkpoint publication, and backup/restore. The intermittent HTTP 500
has no established cause and is not assigned to this ADR.
