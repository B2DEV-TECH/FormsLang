# Forms source note

There is no `.fmb` (binary Oracle Forms module) anywhere in this lab, and
there never will be — see [FormsLang: sem reverse-engineering de .fmb] in
this project's own contribution policy: FormsLang only ever reads Oracle's
**Forms2XML** export format, never the proprietary compiled binary.

What lives in `forms/xml/*.xml` is **hand-authored Forms2XML**, written
directly to look like what `frmf2xml` (or Forms Builder's own XML export)
would produce for a real `CUSTOMERS.fmb` / `ORDERS.fmb` / `INVENTORY.fmb` /
`APPROVALS.fmb`. Every module, block, item, trigger, LOV, alert and relation
in those four files is a **FIXTURE**: invented for this lab, not extracted
from any real Forms application, and grounded only in the DDL/PL&#8203;SQL
under `database/` that this lab also invents.

## Why hand-authored XML instead of a real `.fmb` export

1. This repository is public (Apache 2.0) and used in the author's Oracle
   ACE application — it must never contain a real customer's Forms
   artifacts, and must never rely on parsing Oracle's proprietary binary
   format.
2. FormsLang's parser (`formslang/parser.py`) consumes Forms2XML, so a
   hand-written fixture in that exact format exercises the real parser
   end-to-end, the same way a real export would.
3. Hand-authoring makes every fact in this lab traceable: every trigger's
   business logic is something a human wrote and can cite a line number
   for, rather than something extracted from a black box.

## How the fixtures were generated

The four XML files are produced by a small script
(`gen_lom_forms.py`, not committed — it lived in a scratch directory during
authoring) that renders four f-string templates and writes them to
`forms/xml/*.xml`. Regenerating by hand is straightforward: each module is
one `<Module><FormModule>...</FormModule></Module>` document following the
shapes already in this directory. If you add or change a trigger, prefer
editing the XML directly (it is the actual fixture FormsLang parses) and
keep any generator script you use in sync, not the other way around.

## Gotcha: Forms2XML encoding rules, and one restriction that isn't Forms' own

The encoding used throughout `forms/xml/*.xml` follows Forms2XML exactly:

- A literal newline inside `TriggerText` (or any other multi-line attribute)
  is first written by Forms2XML as the character reference `&#10;` — **not**
  an actual line break in the file. That reference itself contains an `&`,
  and the whole value sits inside an XML attribute, so ordinary XML
  attribute-escaping still applies on top of it: `&` becomes `&amp;`, `<`
  becomes `&lt;`, `>` becomes `&gt;`, and `"` becomes `&quot;`. The net
  effect is that every newline in these fixtures appears on disk as the
  literal nine-character sequence `&amp;#10;`, not the bare `&#10;` you'd
  get from only one escaping pass. Every file in `forms/xml/*.xml` uses
  `&amp;#10;` exclusively — grep for a bare `&#10;` (no `amp;` before it)
  as a quick sanity check; it should never match.

One restriction is **not** part of the Forms2XML format itself, but a
consequence of using Python's standard-library `xml.etree.ElementTree` to
validate these fixtures (which is what FormsLang's own parser uses): a
literal `<!-- ... -->` XML comment must not contain the two-character
sequence `--` anywhere inside it, or `ElementTree.parse()` raises
`xml.etree.ElementTree.ParseError`. This does **not** apply inside
attribute values (a `TriggerText` attribute can and does contain `--` for
inline PL/SQL comments freely, escaped as ordinary attribute text) — it
only bites the hand-written file-header `<!-- ... -->` comments at the top
of each module. Every header comment in `forms/xml/*.xml` was written with
this in mind (using `--` only inside PL/SQL, never inside an XML comment
body). If you add a new file-header comment and it fails to parse, this is
almost certainly why — see the FormsLang-improvements handoff document at
the root of this lab for a proposal to make this failure mode easier to
diagnose.

## What is intentionally NOT built

- `forms/libraries/OM_SHARED.pll` is documented (see `OM_SHARED.md` in
  that directory) but not built as a fixture — FormsLang does not parse
  `.pll` library files, so there is nothing for a fixture to exercise. The
  four modules' `<AttachedLibrary Name="OM_SHARED"/>` references and their
  trigger bodies' calls into `om_shared.*` are enough to document the
  contract without needing a fifth XML file whose only content would be a
  handful of function signatures.
- `forms/menus/LOM_MAIN.md` documents the one custom menu module
  (`LOM_MAIN`) referenced by every form's `MenuModule="LOM_MAIN"` attribute,
  for the same reason: it carries no business logic worth a parseable
  fixture, only a menu structure.
