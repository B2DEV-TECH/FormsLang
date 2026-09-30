# ADR-04 — Trust of imported history and approvals

Status: **Draft**. This selects a pre-WP-20 trust boundary for review; it does
not authorize a product import route, accept an ADR, or satisfy a release gate.

## Context

ADR-01 makes the local coordinator authoritative for accepted events, and
ADR-03 gives portable packages a declared object and history closure. A digest
can verify package bytes but cannot authenticate an actor or an approval. The
current `project_migration.import_legacy_session` copies a legacy SQLite
snapshot and retains its `decision` and `blueprint_review` rows. Its tests
prove preservation and idempotent re-import of that legacy snapshot, not a
3.0 decision trust policy or clean-workspace exchange import.

The same bytes may arrive as a locally catalogued disaster backup, a review
package from a colleague, or a Git checkout. Repository ID, origin ID, event
sequence, reviewer string, Git author, and `approved` text are claims inside
the package. The receiving workspace needs to inspect them without granting
those claims local authority.

## Proposed decision

Keep **integrity**, **origin trust**, **decision applicability**, and **current
authorization** as separate determinations:

| Determination | Meaning |
|---|---|
| Integrity | Supported schema, bounded archive paths/sizes, object digests, event references and declared closure verify, or the package is rejected/quarantined. |
| Origin trust | `UNVERIFIED_EXCHANGE` by default. `TRUSTED_RESTORE` requires an explicit restore workflow and a trusted, independently retained anchor for the exact backup root (or a future verified signature under accepted key policy). A package's own hash or claimed repository/origin ID is not that anchor. |
| Applicability | Each decision binds its original analysis, subject, evidence, policy and target. Changed or unavailable bindings remain historical or need revalidation even if origin is trusted. |
| Authorization | The receiving actor and current workspace policy control preview, apply, disclosure and any new approval. Imported policy cannot weaken them. |

Import preview parses and verifies in isolated staging, then reports repository
identity, ancestry, included/omitted objects, source availability, trust
classification, actor claims, decision kinds, applicability and semantic
conflicts against a selected local base. Preview does not modify accepted
history. An explicit apply with a current revision fence and authorization
registers verified foreign objects and imported events through ADR-01's
transaction/publication protocol. It records the import source and chosen
trust classification without rewriting foreign event authorship.

Foreign event identity is `(repository_id, origin_id, event_id)` plus a
canonical payload digest. Reapplying the same package and payload is
idempotent; the same foreign identity with different bytes is an integrity
conflict. Equal local revision numbers from different origins prove nothing.
An omitted source body, private note or event frontier stays visibly
unavailable; import never regenerates it with the current engine.

For `UNVERIFIED_EXCHANGE`, an imported approval remains inspectable historical
data and cannot authorize generation. A local reviewer can explicitly make a
new decision after current preview, subject/evidence binding, applicability,
permission and confirmation checks. That new event names the receiving actor
and references the imported claim; it never edits the foreign event. For
`TRUSTED_RESTORE`, previously accepted decisions may resume only within the
verified restored origin, original binding and receiving policy. A stale
decision or a distinct receiving workspace still needs explicit revalidation.
Architectural review and conversion approval remain distinct throughout.

## Alternatives and consequences

- Trusting Git authors, a manifest digest, reviewer text, or matching repository
  ID alone is rejected: none authenticates a local approval.
- Treating every recovered backup as foreign and permanently inert is safer
  than silent promotion, but prevents a verified disaster restore from
  recovering its accepted state. The anchored restore path is deliberately
  narrower than ordinary exchange import.
- Automatically translating foreign approvals into new local events is
  rejected. It would invent consent and can silently change applicability.

The receiving workspace must retain enough provenance to explain why an
imported event is visible but inactive. A future signature/key scheme requires
its own accepted trust policy; this ADR does not claim signatures exist.

## Acceptance work and implementation boundary

Before accepting this architecture, review the anchor custody/recovery
procedure and a table of trusted-restore versus untrusted-exchange outcomes.
WP-20 must then test forged actor/approved fields, identical bytes supplied
through both paths, wrong or missing trusted anchor, duplicate foreign ID with
different payload, repeat apply, restricted-profile omissions, weaker imported
policy, changed analysis binding, and preview without accepted-state writes.
It must prove the receiving actor and permission checks at apply time. WP-22
must separately prove lossless legacy preservation without promoting old
review rows to new authenticated approvals. No such product tests are supplied
by this draft.
