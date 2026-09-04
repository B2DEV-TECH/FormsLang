# Proving an export against a real APEX 26.1 instance

`apex validate`/`apex import` (SQLcl, wired in `apeximport.py` and reachable
from the workbench's Import screen) only prove the APEXlang package
*compiles*. A whole class of defect survives that check and only shows up
when App Builder actually renders a page — the `LABEL_COLUMN_SPAN_TOO_BIG`
bug fixed for 0.1.14 is the example that motivated this runbook: SQLcl said
the package was fine, and the page still broke the moment anyone opened it.

This is the manual procedure actually used to validate that fix, written
down so it is repeatable rather than reconstructed from memory each time a
render-time regression is suspected. It needs a local APEX 26.1 workspace
reachable over ORDS; it is not part of CI, and it is not automated.

## 1. Export and inspect

An APEXlang ZIP comes from the workbench's *Export APEX 26.1* button
(`Workbench.export()`) or, for a scripted check, from the CLI twin of that
button — same exporter, same bytes:

```
formslang export <session.db> --app-id 19078
```

Both remember the choices on the session, so a second run with no flags
rebuilds the same application; the export is deterministic (fixed ZIP
timestamps, one checksum salt per session), which is what makes two ZIPs
comparable at all.

Read the generated `.apex.zip`'s page file(s) directly before importing
anything — most render-time properties (`labelColumnSpan`, template
references, grid columns) are visible as plain text in the `.apx` page
definition, and a wrong value is often obvious without ever touching APEX.

## 2. Import into a real workspace

Use the workbench's *Import to database* button (`import_export()` in
`workbench.py`, backed by `apeximport.run_import()`), the CLI
(`formslang apex import <alias>.apex.zip`, password from
`FORMSLANG_APEX_PASSWORD` or a prompt), or drive SQLcl by hand:

```
sql -S -thin /nolog
connect <user>/<password>@<connect_string>
apex import -input <alias>.apex.zip
```

(Under Git Bash on Windows, prefix that with `MSYS_NO_PATHCONV=1` — MSYS
otherwise rewrites `/nolog` into a Windows path and SQLcl prints its usage.)

A clean `apex import` only means the package compiled. It does not mean any
page renders correctly — that is what the remaining steps check.

## 3. Make the page reachable without a login

FormsLang's application template sets `authentication { scheme:
@oracle-apex-accounts }` (see `templates/apexlang26/application.apx`), so a
plain HTTP GET is redirected to the login page instead of rendering the
page under test. For a one-off verification, add a `security` block to the
page(s) being checked before importing:

```
page 1 (
    ...
    security {
        authentication: public
    }
)
```

(`templates/apexlang26/pages/p09999-login.apx` uses the same
`authentication: public` key — it is a normal, supported page property, not
a hack.) Re-import after the edit. Revert it, or re-export cleanly, once
the check is done — this is only for reaching the page anonymously during
verification, not a setting to ship.

## 4. Render the page and read the actual HTML

```
curl -s "http://localhost:8080/ords/f?p=<app_id>:<page_number>" -o rendered.html
```

Then check `rendered.html` for:

- The item(s) under test are present (`grep P1_ITEM_NAME rendered.html`).
- No APEX error region — the `LABEL_COLUMN_SPAN` class of bug appears as an
  APEX-rendered error banner in the page body, not as a non-200 status or an
  exception in the ORDS log. A `200 OK` alone proves nothing.
- The specific property being verified is present with the expected value
  — e.g. a hidden item's label wrapper carries `col-0`, not `col-2`.

This is strictly more rigorous than `apex validate`/`apex import`, which
catch neither this nor any other render-time-only defect — both only ever
see the package before APEX's own grid-layout resolution runs at render
time.

## 5. Clean up

Drop the application from the workspace (App Builder → Application →
Utilities → Delete Application) once the check is done, so a verification
run does not linger as stray state in a shared workspace.
