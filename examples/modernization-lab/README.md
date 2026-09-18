# Legacy Order Management (LOM) modernization lab

A complete, fictional Oracle Forms application -- schema, PL/SQL API
layer, and four Forms modules -- built specifically to exercise
FormsLang's Forms-to-APEX modernization analysis against something more
realistic than a single toy form. Nothing in this lab is a real customer
system: every table, package, and trigger is invented for this exercise,
though every business rule and every defect is grounded concretely in the
fixtures under `database/` and `forms/` -- nothing in the analysis
documents below is speculative.

## Start here, in this order

1. **`docs/business-rules.md`** -- what the LOM system actually does,
   independent of migration concerns. Read this first if you don't yet
   know the domain.
2. **`docs/modernization-challenges.md`** -- why migrating LOM to APEX is
   harder than a literal Forms-to-page port, organized by recurring
   theme and cross-referenced to specific cases.
3. **`expected/modernization-ground-truth.json`** -- the full registry of
   41 modernization cases (`LOM-MOD-001`..`LOM-MOD-042`, with three IDs
   deliberately reserved/unfilled), each classified against the taxonomy
   defined in the same file (`classification`, `risk`, `category`).
4. **`assessment/complexity-and-risk-rollup.md`** -- the same registry,
   summarized: counts by classification/risk/category/module, and which 8
   cases carry HIGH or CRITICAL risk.
5. **`docs/adr/`** -- five Architecture Decision Records capturing the
   non-obvious calls a migration has to make (fixture strategy, status
   transitions, where business logic lives, approval attribution,
   navigation patterns).
6. **`blueprint/expected-apex-architecture.md`** -- the target APEX page
   map this analysis points toward, module by module.

## Layout

```
database/     11 tables (DDL), 2 views, 5 PL/SQL API packages (spec+body),
              7 seed scripts, in FK-safe dependency order
forms/        4 Oracle Forms modules as hand-authored Forms2XML fixtures
              (CUSTOMERS, ORDERS, INVENTORY, APPROVALS) -- see
              forms/source/README.md for why there is no .fmb binary
              anywhere in this lab; forms/libraries and forms/menus
              document (not build) OM_SHARED.pll and the LOM_MAIN menu
expected/     the ground-truth case registry FormsLang's own analysis
              should be checked against
metrics/      compute_metrics.py -- stdlib-only script that measures
              every fixture's structure and cross-checks every
              LOM-MOD-### id referenced in forms/database against the
              ground-truth registry
tests/        stdlib unittest suite over the fixtures and metrics
scripts/      install.sql / seed.sql / verify.sql / reset.sql -- run
              against a real Oracle schema in that order
docs/         business-rules.md, modernization-challenges.md, adr/
assessment/   complexity-and-risk-rollup.md
blueprint/    expected-apex-architecture.md
```

## Running the lab

```bash
# Structural checks -- no database required
python metrics/compute_metrics.py
python -m unittest tests/test_fixtures.py -v

# Against a real Oracle schema (you provide the connection and password --
# scripts never contain one)
sqlplus <user>/<password>@<connect_string> @scripts/install.sql
sqlplus <user>/<password>@<connect_string> @scripts/seed.sql
sqlplus <user>/<password>@<connect_string> @scripts/verify.sql
# scripts/reset.sql tears everything back down (destructive, see its header)
```

`compute_metrics.py` and `tests/test_fixtures.py` were run and passed as
part of building this lab. The SQL scripts were validated by static review
against the actual DDL/package/view names (dependency order confirmed by
grepping every `references` clause) but **not executed against a live
database** in this session -- no stored credentials for any Oracle
instance were found in this environment, and inventing one was out of the
question given the "never hardcode a real password" rule the scripts
themselves state. Run them yourself against a disposable schema before
trusting them in anything more permanent.

## What this lab is not

- Not a real customer system, and not reverse-engineered from one.
- Not a working Oracle Forms application -- no `.fmb`/`.fmd`/`.olb`
  binary exists or is ever produced; see ADR-001 and
  `forms/source/README.md`.
- Not a working Oracle APEX application -- `blueprint/expected-apex-architecture.md`
  is a design target, not an APEX export.
- Not a sizing or estimation tool -- `assessment/complexity-and-risk-rollup.md`
  counts and classifies cases; it does not estimate hours or cost.

## Provenance

Built as a single, self-contained scenario for FormsLang's own examples
directory. The single largest and most load-bearing artifact is
`expected/modernization-ground-truth.json`; everything else (fixtures,
scripts, docs) either produces the evidence that registry cites, or
explains and summarizes it.
