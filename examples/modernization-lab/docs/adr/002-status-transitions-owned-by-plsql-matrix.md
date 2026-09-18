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
  every one of the ten legal transitions does increase `SEQUENCE_NO` --
  including `PENDING_APPROVAL` (30) -> `REJECTED` (35)) would keep every
  legal transition and silently admit illegal ones the matrix forbids:
  `DRAFT` -> `SHIPPED`, `REJECTED` -> `APPROVED`, `APPROVED` ->
  `CANCELLED`, `RELEASED` -> `CANCELLED`. Nothing in the seed data or the
  happy path would reveal the difference; `tests/test_fixtures.py` checks
  it statically (the legal set from `is_valid_transition`, the sequence
  numbers from `database/seed/01_lookup_data.sql`).
- The APEX target architecture (`blueprint/expected-apex-architecture.md`)
  routes every status change through a single call to
  `LOM_ORDER_API.transition_status`, never through direct `UPDATE ...
  SET status = :P1_STATUS`, for exactly this reason.
- This decision generalizes the lesson from LOM-MOD-041/042 (the
  APPROVALS.fmb bypass): centralizing a transition rule in PL/SQL only
  protects the system if every caller actually goes through it.
