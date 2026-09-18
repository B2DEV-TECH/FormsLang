# OM_SHARED.pll — documented, not built as a fixture

`OM_SHARED` is the one shared Forms library attached by all four modules
(`<AttachedLibrary Name="OM_SHARED"/>` in `CUSTOMERS.xml`, `ORDERS.xml`,
`INVENTORY.xml`, `APPROVALS.xml`). FormsLang has no `.pll` parser and a
library carries no block/item/trigger structure of its own to exercise, so
there is no `OM_SHARED.xml` fixture — this file documents the contract
every module relies on, sourced entirely from how each function is called
in `forms/xml/*.xml` (grep for `om_shared\.` to see every call site).

## Functions

### `format_currency(p_amount IN NUMBER) RETURN VARCHAR2`
Wraps `TO_CHAR(p_amount, 'FM999G999G990D00')`-style formatting for on-screen
display. Pure presentation, no business logic.
**LOM-MOD-006**: replaced outright by an APEX number format mask; nothing
to port.

### `show_message(p_text IN VARCHAR2)`
Wraps `MESSAGE(p_text)` / a simple alert popup. Pure presentation.
**LOM-MOD-006**: replaced outright by an APEX Error/Success region or a
Confirm dynamic action; nothing to port.

### `check_user_permission(p_action IN VARCHAR2) RETURN BOOLEAN`
Wraps a lookup against the connected user's role for a coarse allow/deny
per action name (e.g. `'APPROVE_ORDER'`, `'ADJUST_INVENTORY'`).
**LOM-MOD-006**: replaced outright by APEX Access Control / Authorization
Schemes; nothing to port.

### `open_form_with_context(p_form IN VARCHAR2, p_params IN PARAMLIST)`
Wraps `CALL_FORM` / `OPEN_FORM` plus hardcoded window-positioning
coordinates for the target module's window (a Forms-MDI-specific concept:
child window X/Y/width/height relative to the calling form).
**LOM-MOD-007**: dropped entirely — APEX has no window-positioning
equivalent, and each of this helper's three call sites
(`BT_VIEW_APPROVALS`, `BT_VIEW_INVENTORY`, `BT_VIEW_CUSTOMER` in
`ORDERS.xml`) needs its own navigation-pattern decision instead (see
LOM-MOD-020, LOM-MOD-022, LOM-MOD-023).

### `log_action(p_entity IN VARCHAR2, p_entity_id IN VARCHAR2, p_action IN VARCHAR2, p_old IN VARCHAR2, p_new IN VARCHAR2)`
Inserts directly into `LOM_AUDIT_LOG`, bypassing `LOM_AUDIT_API.log_event`
— the same function every business package (`lom_order_api`,
`lom_customer_api`, `lom_inventory_api`, `lom_approval_api`) already calls
correctly for the exact same purpose.
**LOM-MOD-039** (`MOVE_TO_PLSQL_API`, risk `MEDIUM`): a second, independent
write path into the audit table is exactly the kind of divergence this lab
exists to surface. Since `OM_SHARED` itself has no APEX equivalent and is
dropped wholesale, the fix is simple: every Forms trigger currently calling
`om_shared.log_action` should be calling `lom_audit_api.log_event` instead,
even before any APEX work starts — there is no reason for this bypass to
exist even in the legacy Forms application.

### `get_global_user RETURN VARCHAR2`
Thin wrapper some triggers use instead of reading `:GLOBAL.G_USER`
directly; returns the same value.
**LOM-MOD-008**: replaced by `:APP_USER`, alongside every direct
`:GLOBAL.G_USER` reference — see that case for the one thing to verify
before treating this as purely mechanical (whether any call site actually
needs the OS/DB username rather than the application-level identity APEX
exposes).

## What this library deliberately does NOT contain

No function in `OM_SHARED` implements a business rule (a validation, a
calculation, a state transition). Every business rule in this lab lives
either in a `LOM_*_API` package (the correct place) or, where duplicated or
missing, directly in a Forms trigger (documented as its own
`LOM-MOD-###` case). `OM_SHARED` is presentation glue and navigation glue
only — which is exactly why it can be dropped wholesale in the APEX build
rather than migrated function-by-function.
