# Proving an export against a real APEX 26.1 instance

`apex validate`/`apex import` (SQLcl, wired in `apeximport.py` and reachable
from the workbench's Import screen) only prove the APEXlang package
*compiles*. A whole class of defect survives that check and only shows up
when App Builder actually renders a page — the `LABEL_COLUMN_SPAN_TOO_BIG`
bug fixed for 0.1.14 is the example that motivated this runbook: SQLcl said
the package was fine, and the page still broke the moment anyone opened it.

This is the procedure used to validate that fix and, for 1.1.0, the native
layout of the showcase module, written down so it is repeatable rather than
reconstructed from memory each time a render-time regression is suspected.
It needs a local APEX 26.1 workspace reachable over ORDS; it is not part of
CI. Nothing in it makes a page public: the page is fetched with a real
login, as a temporary end user that exists only for the check.

## 1. Export and inspect

An APEXlang ZIP comes from the workbench's *Export APEX 26.1* button
(`Workbench.export()`) or, for a scripted check, from the CLI twin of that
button — same exporter, same bytes:

```
formslang export <session.db> --app-id 19078
formslang export tests/fixtures/showcase/module.xml -o out/showcase --app-id 190 --alias showcase-layout --json
```

Both remember the choices on the session, so a second run with no flags
rebuilds the same application; the export is deterministic (fixed ZIP
timestamps, one checksum salt per session), which is what makes two ZIPs
comparable at all.

Read the generated `.apex.zip`'s page file(s) directly before importing
anything — most render-time properties (`labelColumnSpan`, template
references, template options, grid columns, Interactive Grid columns) are
visible as plain text in the `.apx` page definition, and a wrong value is
often obvious without ever touching APEX. The `apexlang-manifest.json`
written next to the ZIP, in `<alias>-review/`, carries the layout mapping report (`layout.mapping_report`):
for every visible Forms control, the component it became, where it sits on
the grid, which rule applied and what was approximated. Read the
`approximations` and `unsupported` lists first; they say what a rendered
page will *not* show as Forms did.

## 2. Import into a real workspace

Use the workbench's *Import to database* button (`import_export()` in
`workbench.py`, backed by `apeximport.run_import()`), the CLI
(`formslang apex import <alias>.apex.zip`, password from
`FORMSLANG_APEX_PASSWORD`, the credential store, or a prompt), or drive
SQLcl by hand:

```
sql -S -thin /nolog
connect <user>/<password>@<connect_string>
apex import -input <alias>.apex.zip
```

(Under Git Bash on Windows, prefix that with `MSYS_NO_PATHCONV=1` — MSYS
otherwise rewrites `/nolog` into a Windows path and SQLcl prints its usage.)

Import into a **dedicated development application id** (the showcase uses
190), never over an application someone is working on, and never into a
production workspace.

A clean `apex import` only means the package compiled. It does not mean any
page renders correctly — that is what the remaining steps check.

## 3. Read the APEX dictionary

Before rendering anything, ask APEX what it stored. The dictionary views
show the resolved component types, the grid properties and the template
options exactly as Page Designer will present them:

```sql
-- regions: type, template, template options, parent, grid placement
select region_name, source_type, template, region_template_options,
       parent_region_id, display_sequence, grid_column, grid_column_span
  from apex_application_page_regions
 where application_id = :app and page_id = :page
 order by parent_region_id nulls first, display_sequence;

-- page items: native type and grid spans. The second query must return no rows:
-- a label span equal to or larger than the item span is LABEL_COLUMN_SPAN_TOO_BIG.
select item_name, display_as, region, grid_new_row, grid_column,
       grid_column_span, grid_label_column_span, label_alignment, item_template_options
  from apex_application_page_items
 where application_id = :app and page_id = :page
 order by region, display_sequence;

select item_name, grid_column_span, grid_label_column_span
  from apex_application_page_items
 where application_id = :app and page_id = :page
   and grid_label_column_span >= nvl(grid_column_span, 12);

-- Interactive Grid columns: order, heading, type, primary key, visibility
select r.region_name, c.name, c.heading, c.item_type, c.display_sequence,
       c.is_visible, c.is_primary_key
  from apex_appl_page_ig_columns c
  join apex_application_page_regions r on r.region_id = c.region_id
 where c.application_id = :app and c.page_id = :page
 order by r.region_name, c.display_sequence;

-- buttons: region and position
select button_name, region, display_position, button_sequence
  from apex_application_page_buttons
 where application_id = :app and page_id = :page
 order by region, button_sequence;
```

Compare what comes back with the mapping report: the same regions, the
same item types (`Number Field`, `Date Picker`, `Textarea`, `Display Only`,
`Select List`, `Radio Group`, `Checkbox`, `Hidden`), the grid columns in
the order the report lists them, the template options as the CSS classes
the page file named.

## 4. Render the page as a temporary end user

FormsLang's application template sets `authentication { scheme:
@oracle-apex-accounts }` (see `templates/apexlang26/application.apx`), so a
plain HTTP GET is redirected to the login page instead of rendering the
page under test. Do **not** make the page public for the check. Log in
instead, as a user that exists only for the check:

```
python examples/verify/apex_render_check.py out/render <app_id>:<page> [<app_id>:<page> ...]
```

The script uses the saved FormsLang connection (SQLcl path, connect string,
user name, and the password from the credential store or
`FORMSLANG_APEX_PASSWORD`; never a command-line argument) and does, in
order:

1. `apex_util.create_user` in the workspace: an end user with no developer
   privileges, a random password that never leaves the process, and
   `p_change_password_on_first_use => 'N'`;
2. a GET of the login page (`f?p=<app>:9999`), the hidden fields of the
   login form (`pInstance`, `pSalt`, `pPageSubmissionId`,
   `pPageItemsProtected`, `pPageItemsRowVersion` — HTML-unescaped, APEX
   escapes the `/` in them), and a POST to `wwv_flow.accept` with
   `p_request=LOGIN` and the username and password as page items, the way
   the browser submits them;
3. a GET of `f?p=<app>:<page>:<session>` with the session cookie, saved as
   `render<app>_p<page>.html`;
4. `apex_util.remove_user`, in a `finally`, so the user is gone even when a
   fetch fails.

It prints, per page, an inspection of the HTML: region templates,
Interactive Grids with their headings, form
fields, date pickers, number fields, textareas (rows and columns), tab
labels, buttons, and the failure signs below.

To do the same by hand, run the two PL/SQL blocks the script contains in
SQLcl, log in with a browser as that user, save the page from the browser,
and remove the user afterwards.

## 5. Read the actual HTML

Check the saved `render<app>_p<page>.html` for:

- No APEX error region — the `LABEL_COLUMN_SPAN` class of bug appears as an
  APEX-rendered error banner (`t-Alert--danger`) in the page body, not as a
  non-200 status or an exception in the ORDS log. A `200 OK` alone proves
  nothing. The script reports `error_banner`, `label_column_span_error` and
  `ora_errors`.
- The item(s) under test are present (`grep P1_ITEM_NAME rendered.html`)
  with the expected markup: a Date Picker renders as `<a-date-picker
  format="…">`, a Number Field carries `data-format` and `inputmode="decimal"`,
  a textarea its `rows` and `cols`, a required item the `required` attribute.
- Each Interactive Grid is initialised (`.interactiveGrid({…})`) with its
  headings in the order the mapping report lists the columns; a hidden
  column appears with `"hidden": true`.
- The specific property being verified is present with the expected value
  — e.g. a hidden item's label wrapper carries `col-0`, not `col-2`; a form
  region carries `t-Form--stretchInputs`.
- No `position: absolute`, no script that sets `top`/`left`/`position`, no
  style block of FormsLang's own: the layout is Universal Theme's grid and
  nothing else.

This is strictly more rigorous than `apex validate`/`apex import`, which
catch neither this nor any other render-time-only defect — both only ever
see the package before APEX's own grid-layout resolution runs at render
time. It still is not a visual comparison: for that, open the same page in
a browser at the viewport the mapping report names (1280 CSS px) and put
it next to the Forms runtime or the preview's Forms reconstruction.

## 6. Clean up

The temporary user is removed by the script. If the script was
interrupted before its `finally` ran, remove the user by hand:

```sql
begin
  apex_util.set_security_group_id(apex_util.find_security_group_id(p_workspace => 'FORMSLANG'));
  apex_util.remove_user(p_user_name => 'FL_VERIFY_TMP');
  commit;
end;
/
```

Drop the verification application from the workspace (App Builder →
Application → Utilities → Delete Application) once the check is done, so a
verification run does not linger as stray state in a shared workspace.
