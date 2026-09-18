# ADR-004: Approval/audit attribution must explicitly pass v('APP_USER') in APEX

## Status
Accepted

## Context
`LOM_APPROVAL_API.create_approval_request`, `.approve`, and `.reject` all
default their identity parameter (`p_requested_by`/`p_approver`) to the
PL/SQL `USER` pseudo-column when the caller omits it (LOM-MOD-008,
LOM-MOD-031). In Oracle Forms, `USER` genuinely resolves to the connected
end user's own database session identity, so relying on the default was
harmless there. In an Oracle APEX application, every request runs under
the workspace's parsing schema, not under a per-end-user database session
— `USER` inside any procedure called from an APEX page resolves to the
schema owner, not to the logged-in APEX user.

## Decision
Every APEX page process or Dynamic Action that calls
`create_approval_request`, `approve`, or `reject` must explicitly pass
`v('APP_USER')` as the identity argument. Relying on the PL/SQL default is
treated as a defect, not a stylistic choice, anywhere in the target
architecture (`blueprint/expected-apex-architecture.md`).

## Consequences
- Skipping this is invisible in code review unless the reviewer already
  knows to look for it: the call compiles, runs, and returns success:
  every approval is just silently attributed to the schema owner instead
  of the real approver, which is a compliance/audit defect, not a
  functional bug a QA pass would typically catch.
- The same reasoning applies to any other PL/SQL API in this codebase that
  defaults an identity parameter to `USER` — this ADR's rule generalizes
  beyond the two approval procedures it was discovered on.
- This decision doesn't require changing the PL/SQL API itself (the
  default remains useful for non-APEX callers, e.g. batch jobs running
  under a service account) — the fix is entirely at the APEX call site.
