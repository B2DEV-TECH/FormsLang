# ADR-005: Each cross-module navigation flow gets its own pattern decision

## Status
Accepted

## Context
Oracle Forms' `CALL_FORM` (modal, stacks on the calling form) and
`OPEN_FORM` (non-modal, both forms stay open concurrently) have no single
equivalent in Oracle APEX, which is stateless and page-based. `ORDERS.fmb`
uses both: `CALL_FORM` into `APPROVALS` (LOM-MOD-020), `OPEN_FORM` into
`INVENTORY` (LOM-MOD-022), and `CALL_FORM` into `CUSTOMERS` for a
query-only lookup (LOM-MOD-023). `OM_SHARED.open_form_with_context`
(LOM-MOD-007) wraps all three calls with shared window-positioning logic.

## Decision
There is no single APEX replacement pattern applied uniformly to all three
flows. Each is evaluated independently against what it actually needs:
- LOM-MOD-020 (modal, blocking, needs the calling page's context) ->
  modal dialog page passing the order ID via page item, in the target
  architecture.
- LOM-MOD-022 (non-modal, both stay open, minimal shared state) -> a
  plain link opening `INVENTORY`'s page in a new browser tab; no in-memory
  `PARAMLIST` state survives a page navigation either way, so whatever
  context is needed travels as a URL parameter, not as shared session
  state.
- LOM-MOD-023 (query-only lookup) -> the simplest option, a plain link;
  no modal or new-tab behavior is needed since nothing is edited.
`OM_SHARED.open_form_with_context` itself (LOM-MOD-007) is dropped
wholesale, not translated: the window-positioning coordinates it computes
mean nothing in a responsive browser layout.

## Consequences
- This is deliberately not a "one navigation helper to rule them all"
  design. Treating all `CALL_FORM`/`OPEN_FORM` sites the same way (e.g.
  always-modal) would misrepresent flows that were never modal in the
  legacy system (LOM-MOD-022) and would lose the blocking guarantee the
  legacy system did rely on for others (LOM-MOD-020).
- Each of the three cases is marked `MANUAL_REVIEW` or `REPLACE_WITH_APEX_NATIVE`
  in the ground-truth registry rather than `CONVERT`, precisely because the
  right answer depends on human judgment about the calling context, not on
  a mechanical rule.
