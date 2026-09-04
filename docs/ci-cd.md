# FormsLang in a pipeline: export, validate, import

FormsLang 1.0 ships the two commands a pipeline needs and the one
property that makes a pipeline trustworthy: **the same session always
exports the same bytes.** This page is the contract for that -- what to
commit, what each command promises, how the password travels, and what the
next phase (SQLcl `project`-based promotion) will build on.

```
  git                          runner                                 APEX
  ────                         ──────                                 ────
  ORDERS.fmb        ──┐
  ORDERS_fmb.xml      ├─▶  formslang export ORDERS.session.db  ──▶  orders.apex.zip
  ORDERS.session.db ──┘           │                                     │
                                  ▼                                     ▼
                         formslang apex validate  ──── SQLcl ────▶  workspace (checks, changes nothing)
                                  │
                                  ▼  main only
                         formslang apex import    ──── SQLcl ────▶  workspace (the application)
```

## 1. What to commit

| File | Commit it? | Why |
|---|---|---|
| `ORDERS.fmb` | yes | The source of truth Forms Builder edits. Binary; git stores it, cannot diff it. |
| `ORDERS_fmb.xml` (Forms2XML output) | yes | Text. Every trigger, item and property as a diffable line; `formslang diff` reads two of them. Lets a runner without Oracle Forms rebuild everything. |
| `ORDERS.session.db` | yes | The review: every proposal, every decision, who made it, the export's choices and its checksum salt. Small SQLite file. |
| `export/orders/` (the APEXlang tree) | optional | Text. Committing it turns every export into a reviewable diff of the *application* -- `pages/p00001-orders.apx` changes exactly where the review changed. |
| `export/orders.apex.zip` | no | A build artifact: rebuilt from the session on every run, byte-identical when nothing changed. Publish it from the pipeline instead. |
| `export/orders-review/` | no | `approved.sql`, `session.json`, `tests.md`, `compliance.md` -- audit output derived from the session; rebuilt on demand. |

Keep the XML beside the `.fmb` under the name Forms2XML gives it
(`<module>_fmb.xml`): `formslang export` on a session whose source is a
`.fmb` first looks for that cached XML under `<work>/xml/` and only calls
Oracle's toolchain when it is missing. A runner that has the XML needs
**no Oracle Forms installation at all**.

## 2. The commands

### `formslang export <session.db>`

Builds the APEXlang 26.1 project and the import ZIP from a session's
approved work -- the same function the workbench's *Export APEX 26.1*
button calls, nothing else.

- **Choices are remembered on the session.** `--app-id`, `--alias`,
  `--name`, `--workspace`, `--schema` and `--page` are written into the
  session when given, and read back when omitted, so a bare
  `formslang export ORDERS.session.db` rebuilds the last export. A flag
  overrides only what it names.
- **Output lands beside the session** (`<session dir>/export/`), or under
  `--out`. The ZIP is `<alias>.apex.zip`; the expanded tree is `<alias>/`.
- **`--json`** prints the paths and the approved-component count for the
  next step to read.
- Also accepts a `.fmb`/`.xml`: creates the session beside it, exports
  with no approved work. Useful for "does this module still export" checks.

### `formslang apex validate <zip>` / `formslang apex import <zip>`

Drives your own SQLcl (`apex validate -input` / `apex import -input`)
against one ZIP. Nothing here invents a command SQLcl does not document.

| Setting | Flag | Environment | Fallback |
|---|---|---|---|
| target | `--connect host:port/service` | `FORMSLANG_APEX_CONNECT` | the workbench's Settings |
| user | `--user` | `FORMSLANG_APEX_USER` | the workbench's Settings |
| password | *(none, by design)* | `FORMSLANG_APEX_PASSWORD` | the connection saved from the workbench (OS credential store), then a hidden prompt if a person is at the terminal |
| SQLcl binary | `--sqlcl` | `FORMSLANG_SQLCL_PATH` | Settings, then `sql` on `PATH` |
| ceiling | `--timeout` seconds (default 120) | | |

**The password is never a command-line argument.** It travels to SQLcl on
stdin inside SQLcl's own `connect` line, is scrubbed from captured output,
and a runner that has neither the variable nor a terminal fails at once
with exit 2 instead of hanging on a prompt nobody will answer.

### Exit codes

| Code | Meaning | Typical cause |
|---|---|---|
| `0` | done | SQLcl succeeded; for `validate`, the package compiles against that workspace |
| `1` | SQLcl failed | connection refused, `ORA-01017`, or -- the one the exit code alone would hide -- SQLcl exited 0 but printed `APEXlang Compile Errors` and imported nothing |
| `2` | could not run | no SQLcl, no target, no password, no such ZIP |

`export` exits `0` or `2` (no session module, invalid alias, Oracle
toolchain missing when the XML is not cached).

## 3. Determinism, and what it buys

Two exports of an unchanged session are byte-identical, ZIP included:

- ZIP entries are written **in name order**, stamped **1980-01-01** and
  given one fixed permission mask, so nothing from the runner's clock or
  filesystem leaks into the archive.
- The application's **session-state checksum salt** -- the one value APEX
  needs to be unpredictable -- is drawn once per session from the OS
  CSPRNG and kept in the session file (`apex_checksum_salt`), instead of
  once per export.
- Everything else is a pure function of the parsed module and the
  approved decisions.

So a pipeline can: cache the ZIP by content hash; compare the artifact it
built against the one attached to a release; and treat a diff between two
committed `export/<alias>/` trees as a diff between two *reviews*.

## 4. GitHub Actions

The complete workflow is in
[`examples/ci/formslang-apex.yml`](../examples/ci/formslang-apex.yml). The
shape:

```yaml
- run: formslang export forms/ORDERS.session.db --json | tee export.json

- run: formslang apex validate forms/export/orders.apex.zip
  env:
    FORMSLANG_APEX_CONNECT:  ${{ secrets.APEX_CONNECT }}   # host:port/service
    FORMSLANG_APEX_USER:     ${{ secrets.APEX_USER }}
    FORMSLANG_APEX_PASSWORD: ${{ secrets.APEX_PASSWORD }}

- if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  run: formslang apex import forms/export/orders.apex.zip
  env: { …same three… }
```

Runner prerequisites: Python 3.10+, SQLcl (which needs a Java 17+
runtime; Oracle's public `sqlcl-latest.zip` needs no account), and a route
to the database. No Oracle Forms, as long as the Forms2XML `.xml` is
committed beside the `.fmb`.

The same example carries a second job for pull requests: `formslang diff`
between the base and head revisions of the module's XML, published as the
job's artifact -- the structural diff of the *form* (blocks, items,
triggers, program units, property changes, code hunks), next to git's
line diff of the same file.

## 5. Gotchas already paid for

- **`-thin`.** FormsLang starts SQLcl with `-thin` so a runner that also
  has an Oracle client on `PATH` never falls into the OCI driver
  (`no ocijdbc23 in java.library.path`).
- **Compile errors exit 0.** `apex import` prints `APEXlang Compile
  Errors` and exits 0 with nothing imported; FormsLang reads the output,
  not just the code, and reports `FAILED (SQLcl reported errors; nothing
  was imported)` with exit 1.
- **Git Bash on Windows rewrites `/nolog`.** If you drive SQLcl by hand
  from Git Bash, prefix with `MSYS_NO_PATHCONV=1`; FormsLang's own
  subprocess is not affected.
- **`validate` proves compilation, not rendering.** A grid-layout error
  (`LABEL_COLUMN_SPAN_TOO_BIG`) passes both `validate` and `import` and
  only appears when App Builder renders the page. The procedure for that
  last mile -- import, make the page public, `curl` it through ORDS, read
  the HTML -- is in
  [`apex-import-verification.md`](apex-import-verification.md).
- **The APEXlang vocabulary lives in the target database.** Item-type
  keywords (`textField`, `textarea`, `displayOnly`, …) come from each
  plugin's `apexlangName` on the APEX instance, not from SQLcl's jar; a
  keyword that is unknown there fails the import. FormsLang only emits
  keywords verified against a live 26.1, which is why `Date`/`Number`
  items still export as `textField`.

## 6. What comes next

1.0 leaves the ground level for the next phase, which is about promotion
rather than a single import:

- **SQLcl `project`** (`sql project init/export/stage/release/deploy`):
  export the application *back* from APEX after a Page Designer session,
  so the committed APEXlang tree round-trips and `formslang diff` can show
  what a developer changed by hand.
- **Environment promotion**: the same ZIP validated on DEV, imported on
  TEST, then PROD, with the workspace/schema resolved per deployment
  (`deployments/*.json`) rather than baked in.
- **Render-time verification in CI**: the ORDS `curl` check above as an
  optional job against a disposable APEX container.

Everything above builds on the two commands and the determinism promise
this page documents; none of it changes them.
