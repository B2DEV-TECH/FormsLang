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

### Anchor custody and clean-workspace restore

At backup creation, the accepted local coordinator must produce a receipt for
the exact published backup root. The receipt identifies the digest algorithm
and schema, repository and origin IDs, event frontier, export profile, root
digest and closure-manifest digest. The custodian retains that receipt
**outside the package and its Git branch** in an independently controlled
backup inventory or offline record. A duplicate receipt carried in the archive, placed beside
it by the sender, or calculated from the archive during restore is package
data, not a trust anchor.

For restore, an authorized local custodian selects the independently retained
receipt and records its custody source and the restore actor. The application
verifies the package schema and closure, recomputes the root digest, and
compares every receipt field above before assigning `TRUSTED_RESTORE`. The
receiving policy must allow restoration of that repository/origin into this
destination. This procedure also works in a clean workspace when the
original local catalog is gone **if** the independent receipt survived and
its custody can be established through a configured independent inventory or
a policy-approved local custodian's recorded offline-record attestation. A
typed digest alone does not establish custody. This supports local disaster
recovery; it does not cryptographically authenticate a named historical
reviewer. An authenticated/team-mode trust source needs its own accepted
policy under ADR-11 before it may activate imported approvals.

If the receipt or independent custody is unavailable, the package can only
enter the ordinary `UNVERIFIED_EXCHANGE` path after integrity checks. A
digest printed by the package itself, matching repository ID, owner
attestation without an independent receipt, or a Git commit cannot upgrade
it. A mismatched receipt stops the trusted-restore attempt; any later
unverified inspection must be a separately chosen operation, not a silent
fallback.

| Input and destination | Classification after integrity checks | Approval consequence |
|---|---|---|
| Complete backup, matching independently held receipt, permitted clean restore of the same origin; original catalog unavailable | `TRUSTED_RESTORE` | Original accepted decisions may resume only at their original applicable binding and under receiving policy. |
| Same bytes with only an embedded/adjacent receipt or self-calculated hash | `UNVERIFIED_EXCHANGE` | Claimed approvals are historical and inactive. |
| No independent receipt or no established custody, even if repository/origin IDs match | `UNVERIFIED_EXCHANGE` | Claimed approvals are historical; a current actor must make a new local decision. |
| Independent receipt disagrees with root, profile, frontier or closure | Trusted restore rejected | No approval activation; no automatic downgrade to exchange. |
| Missing/corrupt object or invalid declared closure | Import rejected/quarantined | No accepted import or approval activation. |
| Matching trusted receipt, but changed analysis/evidence binding or stricter receiving policy | Trusted history, inapplicable decision | Preserve the old decision; require explicit revalidation or new approval. |
| Valid review/Git package or backup applied into a distinct existing workspace | `UNVERIFIED_EXCHANGE` | Preserve foreign provenance; no local approval promotion. |

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

Before accepting this architecture, ratify the custody source and recovery
procedure above, including how an independent receipt survives loss of the
original local catalog and how its custodian establishes control. Review the
outcome table as the expected trust contract.
WP-20 must then test forged actor/approved fields, identical bytes supplied
through both paths, a clean restore with no original catalog but a retained
independent receipt, a package-supplied receipt, wrong or missing trusted
anchor, duplicate foreign ID with different payload, repeat apply,
restricted-profile omissions, weaker imported policy, changed analysis
binding, and preview without accepted-state writes.
It must prove the receiving actor and permission checks at apply time. WP-22
must separately prove lossless legacy preservation without promoting old
review rows to new authenticated approvals. No such product tests are supplied
by this draft.
