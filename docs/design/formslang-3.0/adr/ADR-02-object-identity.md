# ADR-02 — Immutable object identity and canonical bytes

Status: **Draft**. The example scheme is a spike, not a shipped object format.

## Context

A local revision counter is not a content identity. Sources need exact-byte
identity, while structured durable outputs need deterministic serialization.
Direct Blueprint `source_revision` still has a pinned gap for changed SQL bytes
at the same path; the project manifest path already hashes supplied bytes.

## Proposed decision

Use a versioned, kind-separated SHA-256 identity. The spike computes
`sha256(b"formslang-object/1\0" + kind + b"\0" + body)` and encodes the
kind and digest in the ID. Source bodies use their exact original bytes;
structured objects use a declared canonical UTF-8 encoding. A digest means
identity/integrity, never authorship, approval or semantic equivalence.

The object ID is distinct from a source locator, entity ID, event sequence,
job ID, and display label. Two workspace origins can have the same local
revision number and different accepted state. Do not rebind a decision by
matching labels or counters.

## Evidence and limits

The spike tests CRLF versus LF, identical bytes, domain separation and
content verification. Golden checkpoint bytes are pinned in its tests, with
the same UTF-8 Unicode output for different mapping and set input orders.
The scheme still needs source metadata, directory durability, hash-collision
response, cross-platform filename and source-set closure tests. The direct
Blueprint strict xfail remains unchanged. No product source identity was
changed in this WP.
