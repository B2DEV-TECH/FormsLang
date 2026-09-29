# ADR-01 — Repository authority and transaction boundary

Status: **Draft**. Owner acceptance and product migration are pending.

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
are required before acceptance and WP-20.

## Alternatives retained for comparison

- File-authoritative operation needs an independent atomicity, conflict and
  migration proof; the current specification selects SQLite authority.
- Publishing the manifest before SQLite commit permits an unaccepted state to
  appear current. Publishing after commit without a durable intent loses the
  ability to recover an accepted state deterministically.

## Acceptance work

Failure injection across real project migration; Windows/Linux reader and
writer matrix; explicit no-write read tests; idempotency and authorization;
recoverable mirror/checkpoint publication; backup and restore proof. The
intermittent HTTP 500 has no established cause and is not assigned to this ADR.
