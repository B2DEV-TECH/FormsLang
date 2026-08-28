# How FormsLang prices a migration

This document exists so the numbers in a FormsLang report can be argued
with. Every weight below is a decision, and a decision you disagree with is
one you can change — the point is that none of it is hidden.

## 1. What is counted

FormsLang converts each module through Oracle's own `Forms2XML`, parses the
result, and counts only what survives a migration:

- **Structure** — blocks, items, LOVs, record groups, relations, canvases,
  windows, tab pages, report objects
- **Code** — every trigger and program unit, with its body
- **Behaviour** — every Forms built-in called, every `:GLOBAL`, every system
  variable, every SQL statement

Layout properties (font, colour, pixel position) are deliberately **not**
parsed. They do not survive a migration to APEX and would only add noise.

## 2. The verdict, and why it is economic

Each trigger and built-in is classified against the catalog in `rules.py`:

| Verdict | Weight | Meaning |
|---|---|---|
| `AUTO` | 1.0 | Direct APEX equivalent. Converted by machine, reviewed by a human. Not zero: review is real work. |
| `DROP` | 0.2 | Solves a problem APEX does not have. Disappears, but someone must confirm it can. |
| `ASSISTED` | 4.0 | Intent translates, form does not. AI proposal plus human approval. |
| `UNKNOWN` | 6.0 | Outside the catalog. Priced above `ASSISTED` on purpose. |
| `MANUAL` | 12.0 | No equivalent. Redesign, architecture decision, or integration. |

`UNKNOWN` costing more than `ASSISTED` is the central honesty rule. An
unknown symbol is a thing nobody has looked at yet; the cheapest possible
assumption about it is the one most likely to be wrong. Every unknown is
also named in the report, under *catalog debt*, so the list shrinks with
evidence rather than with optimism.

## 3. Cost of one code body

Each trigger and program unit is priced on its own:

```
unit_points = verdict_weight
            + lines × 0.06
            + Σ over distinct built-ins:  weight × (1 + log2(occurrences))
```

Three deliberate choices:

- **`lines × 0.06`** — reading and re-testing a line of PL/SQL costs time
  even when everything in it is portable.
- **`log2(occurrences)`** — the first `SET_ITEM_PROPERTY` in a body costs a
  decision; the tenth is the same pattern repeated. Repetition is charged,
  but not charged ten times.
- **Per body, not per module** — this is what makes portfolio deduplication
  possible in step 5.

## 4. Cost of structure

```
structure = database_blocks × 3.0
          + other_blocks    × 1.5
          + database_items  × 0.15
          + other_items     × 0.4
          + lovs            × 1.0
          + record_groups   × 1.5
          + relations       × 3.0
          + extra_canvases  × 2.0
          + extra_windows   × 2.0
          + tab_pages       × 1.0
          + report_objects  × 8.0
```

A database item is cheap because APEX generates it. A non-database item is
more expensive because someone has to decide what it becomes. Canvases and
windows are counted from the second one onward: the first is the page, the
rest are layout decisions. Report objects are the most expensive single item
in the table because Oracle Reports has no APEX equivalent — it is a target
choice (BI Publisher, APEX printing, ORDS), not a conversion.

## 5. Portfolio deduplication

Legacy Forms systems are built by cloning a template form. The same
error-handling procedure, the same menu-security block, the same WebUtil
event handler exist in hundreds of modules — byte for byte.

FormsLang fingerprints every code body (comments and formatting normalised,
string literals and identifiers preserved, so only literal copy-paste
collides). A fingerprint present in two or more modules is **solved once**:

```
portfolio_total = Σ modules (structure + unique bodies + shared bodies × 0.15)
                + Σ distinct shared blocks (one full price each)
```

The `0.15` is the review share: someone still has to confirm each copy really
is identical and wire it into its module. Like the hours factor, it is an
**assumption**, and the report says so.

Both totals — raw and deduplicated — appear in the report. The correction is
visible, never silent.

## 6. Points are not hours

A point is a derived measure of counted work. Turning it into hours needs a
calibration factor from conversions you have actually performed and timed.
The default (`0.25 h/point`) is a starting assumption, labelled as such in
every report, and overridable with `--hours-per-point`.

The intended workflow: convert a handful of modules for real, measure them,
compute your own factor, and re-run. From then on the estimate is calibrated
against your team, your codebase and your definition of done.

## 7. Complexity tiers

Tiers are bands over the deduplicated per-module points:

| Tier | Points | Reading |
|---|---|---|
| `SIMPLE` | < 120 | Straight CRUD: table block, few rules of its own |
| `MODERATE` | 120–300 | CRUD with validation and LOVs; assisted conversion |
| `COMPLEX` | 300–700 | Heavy business logic in the screen; review case by case |
| `REWRITE` | > 700 | Converting costs about as much as rewriting |

The boundaries are a starting heuristic over the point model, not a law. A
portfolio with a different profile may well deserve different bands: calibrate
them against conversions you have measured yourself, and move them — it is a
one-line change in `assess.py`.

## 8. What FormsLang does not claim

- It does not claim a percentage of screens will convert automatically.
  *Automation-friendly* is the share of classified symbols that are `AUTO` or
  `DROP` — a theoretical ceiling on what a machine can reach, not a delivery
  promise.
- It does not evaluate the quality of the resulting APEX application.
- It does not read the database schema. Calls into external packages are
  reported as dependencies to inventory, not as work already understood.
