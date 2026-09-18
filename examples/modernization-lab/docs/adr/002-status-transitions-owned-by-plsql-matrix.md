# ADR-002: Order status transitions are owned exclusively by a PL/SQL matrix

## Status
Accepted

## Context
`LOM_ORDER_STATUS` carries a `SEQUENCE_NO` column that looks, at a glance,
like it could drive transition logic (e.g. "status can only move to a
higher SEQUENCE_NO"). It does not: `LOM_ORDER_API.transition_status`
contains a hardcoded matrix of valid `(from_status, to_status)` pairs,
independent of `SEQUENCE_NO`'s numeric ordering. `SEQUENCE_NO` exists only
to drive **display order** in Forms LOVs and (in the target state) an APEX
select list.

## Decision
`SEQUENCE_NO` is documented and treated everywhere in this lab as
presentation-only metadata. The single source of truth for "can an order
move from status A to status B" is, and remains, the explicit matrix
inside `LOM_ORDER_API.transition_status`. No code — Forms trigger, PL/SQL
package, or (in the target APEX app) page process — may infer a valid
transition by comparing `SEQUENCE_NO` values.

## Consequences
- A migration that "simplifies" the transition check into
  `new.sequence_no > old.sequence_no` (an intuitive-looking shortcut, since
  the sequence numbers do happen to increase along the common path) would
  silently allow illegal transitions the matrix forbids (for example,
  jumping straight from `DRAFT` to `SHIPPED`) and silently forbid a
  legal one the matrix allows (`PENDING_APPROVAL` -> `REJECTED` has a
  `SEQUENCE_NO` that is not monotonically related to the surrounding
  happy-path states). This is exactly the kind of defect a demo would not
  surface, because demo data rarely exercises rejection or cancellation.
- The APEX target architecture (`blueprint/expected-apex-architecture.md`)
  routes every status change through a single call to
  `LOM_ORDER_API.transition_status`, never through direct `UPDATE ...
  SET status = :P1_STATUS`, for exactly this reason.
- This decision generalizes the lesson from LOM-MOD-041/042 (the
  APPROVALS.fmb bypass): centralizing a transition rule in PL/SQL only
  protects the system if every caller actually goes through it.
