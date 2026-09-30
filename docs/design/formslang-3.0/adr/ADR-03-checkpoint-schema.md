# ADR-03 — Whole-project checkpoint and portable history

Status: **Draft**. The schema below is a spike fixture, not an accepted 3.0
exchange format. Acceptance of the architecture does not approve the example
as a product format or satisfy portability gates.

## Context

The current `blueprint_snapshot` is one overwritten row. Older project
assessments remain in SQLite without a complete public history API. A 3.0
checkpoint must bind sources, analyses, evidence, decisions, plans, artifacts,
validations and their availability without circular references or false
reconstruction claims.

## Proposed decision

An accepted SQLite event records the exact canonical checkpoint bytes and
their publication state. The root manifest is written last; object references
must be verified before it appears. Recovery republishes the committed bytes
without rerunning a parser or model. The root carries repository/origin,
schema, event frontier, source set, analysis, decision frontier, policy,
object references and declared availability/omissions. An export profile states
which referenced objects and private records it includes. Redacted exports
cannot claim to restore omitted sources or approvals.

Spike example (only):

```json
{"events":[{"action":"analyze"}],"objects":["sha256:source:..."],"revision":1,"schema":"formslang-spike-checkpoint/1"}
```

The product schema must replace this example with typed references, versioned
canonical bytes and a closure algorithm. Historical revisions remain
inspectable where objects are available; missing objects surface an integrity
error or availability record rather than being regenerated with a newer engine.

## Evidence and limits

The spike pins exact bytes, crash recovery and an idempotent replay. Before
owner acceptance, review its canonical-byte contract, root-last publication,
verified-object closure rule and declared-omission rule. It has not proven
full/review export closure, import trust, divergent origins, private proposal
retention, artifact/validation linkage or a clean-workspace reopen. WP-20 and
ADR-04/07 must produce those product tests before claiming completion or a
release gate; they cannot be prerequisites for accepting the contract that
WP-20 depends on. The versioned product schema and its golden bytes must be
reviewed and tested before WP-20 publishes a product checkpoint.
