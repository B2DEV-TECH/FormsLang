# FormsLang

**Oracle Forms analysis and AI-assisted conversion to Oracle APEX.**
A product of [B2DEV TECH](https://b2dev.tech).

FormsLang reads your `.fmb` modules, classifies every trigger and built-in
against a Forms→APEX catalog, and tells you what the migration actually
costs — measured from your own code, not estimated from a spreadsheet.

> **Status: alpha, in development.** The assessment engine is working and has
> been run end to end on a real production portfolio. The AI-assisted
> conversion workbench is next.

---

## Why this exists

Every Oracle Forms migration starts with the same question — *how big is
this, really?* — and the same three bad answers: a guess, a per-screen
average, or a vendor's optimistic demo on the simplest form in the system.

FormsLang answers it by counting. It converts each module through Oracle's
own XML toolchain, parses the result, and prices every trigger, built-in and
program unit against a catalog of what happens to it in APEX.

## What makes the numbers defensible

**1. Effort is reported in points, not hours.**
A point is derived from what was counted in the XML. Converting points to
hours needs a calibration factor that can only come from real conversions you
have measured. The report labels that factor an assumption, every time.

**2. Unknown is never treated as easy.**
Anything outside the catalog is weighted as expensive and named in the report
as *catalog debt*. The catalog grows against reality, not imagination.

**3. Copy-paste is charged once.**
Legacy Forms systems are built by cloning a template. FormsLang fingerprints
every code body; blocks that appear in more than one module are solved once
at portfolio level and only reviewed in the copies. Both totals are shown —
raw and deduplicated — so the correction is visible, not hidden.

**4. Nothing leaves your machine.**
The analysis runs locally against a local Oracle Forms install. The HTML
report is a single self-contained file: no CDN, no remote fonts, no
telemetry.

## The verdict taxonomy

Every trigger and built-in gets one of five verdicts. The difference between
them is economic, not technical.

| Verdict | Meaning |
|---|---|
| `AUTO` | Direct, deterministic APEX equivalent. The machine converts; a human reviews. |
| `ASSISTED` | The intent translates, the form does not. AI proposal, human approval per hunk. |
| `MANUAL` | No APEX equivalent. Needs redesign, an architecture decision, or an integration. |
| `DROP` | Solves a problem APEX does not have. It disappears — and that is a gain. |
| `UNKNOWN` | Catalog debt. Weighted expensive, named in the report, never silently cheap. |

## Install

```bash
git clone <this repo>
cd formslang
pip install -e .
```

The analysis core has **zero third-party dependencies** — standard library
only, so it runs on a locked-down machine inside a customer network.

### Oracle Forms toolchain

Converting `.fmb` to XML requires an Oracle Forms installation **you have
licensed and installed yourself**. FormsLang redistributes no Oracle
software; it locates your `ORACLE_HOME` and invokes your own tools.

FormsLang looks for the toolchain in this order:
explicit `--oracle-home` → the `ORACLE_HOME` environment variable → common
install paths. It validates `java.exe` plus `frmxmltools.jar`,
`frmjdapi.jar` and `xmlparserv2.jar`, and names the exact missing file when
something is wrong.

**No Oracle install?** Feed FormsLang the XML directly. If someone else has
already run `frmf2xml`, point the CLI at the `.xml` files and Oracle is out
of the pipeline entirely.

## Use

```bash
# Assess a whole portfolio: convert, analyze, write the report
formslang assess "D:\legacy\forms" -o out -j 8 --title "ERP portfolio"

# One module, in the terminal
formslang inspect "D:\legacy\forms\ORDERS.fmb"

# What the catalog currently covers
formslang catalog
```

`assess` writes two files into `-o`:

- `assessment.html` — the report you send to a decision maker
- `assessment.json` — the same data, for your own tooling

Useful flags: `--limit N` (dry run on a sample), `--no-recursive`,
`--overwrite` (reconvert cached XML), `--hours-per-point` (your own measured
calibration), `--oracle-home`.

**Your source tree is never written to.** Oracle's `Forms2XML` emits the XML
next to the `.fmb`, so FormsLang copies each module into a temporary
directory, converts it there, and moves only the result into your output
folder.

## Measured on real code

The engine has been run end to end against a production ERP portfolio of
**541 Forms modules** (a customer system; the modules themselves are not
distributed and are not part of this repository).

- 541 / 541 modules converted and parsed, **zero failures**
- 2,492 blocks · 34,844 items · 21,186 triggers · 6,372 program units
- 746,718 lines of PL/SQL
- **59% of all code bodies in the system are literal copies of just 700
  distinct blocks** — the signature of a system built by cloning a template
  form, and the single largest lever in its migration budget

That last number is the reason deduplication exists in the scoring. Counting
each copy in full would have inflated the estimate by more than half.

## Architecture

```
formslang/
├── oracle.py    # the ONLY module that touches Oracle binaries
├── parser.py    # Forms2XML output -> domain model
├── model.py     # what a Forms module is, minus the layout noise
├── rules.py     # the catalog: Forms -> APEX. The core asset.
├── plsql.py     # lexical analysis + code fingerprinting
├── assess.py    # scoring, tiers, portfolio deduplication
├── report.py    # self-contained HTML + JSON
└── cli.py       # assess / inspect / catalog
```

Two parser details that break naive readers, both handled:

1. **Double-escaped newlines.** Forms2XML stores code in an XML *attribute*,
   escaping newlines as the literal string `&#10;`. After the normal XML
   unescape the text still contains those seven characters. Without a second
   decoding pass, every trigger collapses to a single line.
2. **Accent mojibake.** The `.fmb` stores cp1252; Forms2XML declares UTF-8
   but emits the original bytes, so `Conexão` arrives as `ConexÃ£o`. The
   repair is applied only when it produces valid text.

## Tests

```bash
pytest
```

The fixtures are synthetic: they reproduce the exact shape Forms2XML emits —
namespace, attribute-held code, double-escaped newlines, mojibake — without
carrying a single line of customer code.

## Roadmap

- [x] Oracle toolchain bridge and XML parser
- [x] Forms→APEX classification catalog
- [x] Portfolio assessment with copy-paste deduplication
- [x] Self-contained HTML / JSON report
- [ ] AI-assisted conversion workbench (proposal + approval per hunk)
- [ ] APEX artifact generation
- [ ] Semantic diff and merge across module versions

## Legal

Proprietary software. See [LICENSE](LICENSE). Not open source.

Oracle, Oracle Forms and Oracle APEX are trademarks of Oracle Corporation.
FormsLang is neither affiliated with nor endorsed by Oracle Corporation and
redistributes no Oracle software.
