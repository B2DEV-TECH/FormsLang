# FormsLang WP-08 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract every supported package declaration in multi-CREATE scripts, accept documented package header clauses, and split SQLcl slash-delimited statements without hiding unsupported input.

**Architecture:** Keep source-order package occurrences separate from the legacy bare-name maps. Only project unambiguous occurrences into those maps while ADR-06 remains open. Use lexical tokens to locate CREATE boundaries and slash delimiters; use bounded declaration text for the existing spec/body parsers. Coverage compares occurrences rather than deduplicated map keys.

**Tech Stack:** Python 3.10+, standard library parser, pytest and ruff.

**Spec:** `C:/Users/geefa/Downloads/FormsLang-3.0-Spec-Completa-Handoff-Agente-2026-09-28.md`, section “Próxima execução combinada: WP-08A → WP-08B → WP-08C”.

## Global Constraints

- Preserve source revision behavior and historical snapshots; do not implement ADR-06 identity changes in this slice.
- Every supported CREATE must appear in extracted inventory or explicit not-extracted coverage with source line and reason.
- Keep separate parser and HTTP 500 diagnosis lines; do not merge, tag, or release.
- Run focused tests per slice and the project quality gates; report exact Python/OS and results.

## Review Focus

- A CREATE token inside comments, quoted strings or q-quoted strings must not become a package declaration.
- Repeated same-name packages from distinct owners must remain visible and must not produce an arbitrary Blueprint link.
- A package body procedure must not consume the next package's subprograms.
- Header clauses containing parentheses or quoted identifiers must not advance into the next declaration.
- Slash embedded in strings, comments or package code must not split a statement.

---

### Task 1: WP-08A, ordered package occurrences

**Files:** Modify `formslang/database.py`; add `tests/test_database_wp08.py`; update the pinned collision test if its expected boundary changes.

**Interfaces:** Produce `DatabaseProject.package_declarations` as an ordered, serializable occurrence inventory with kind, owner, name, qualified name, source, line, order, and parsed object. `SourceCoverage.objects` counts extracted occurrences; ambiguous bare-name projections are excluded from the legacy maps.

- [ ] Write tests for two specs plus bodies in one file, owner homonyms, repeated identity, exact order and lines, comment/string false positives, coverage counts, and Blueprint ambiguity.
- [ ] Run `py -3.13 -m pytest -q tests/test_database_wp08.py` and confirm feature failures.
- [ ] Implement source-bounded declaration parsing, occurrence inventory, deterministic merging and coverage accounting.
- [ ] Run the focused tests and relevant existing database/Blueprint tests; confirm output.
- [ ] Commit `fix(database): inventory every package declaration in source order`.

### Task 2: WP-08B, package header clauses

**Files:** Modify `formslang/database.py`; extend `tests/test_database_wp08.py`.

**Interfaces:** Consume Task 1 occurrence boundaries. Produce parsed `AUTHID`, `ACCESSIBLE BY`, `DEFAULT COLLATION`, and `SHARING` header text and provenance without claiming semantic resolution.

- [ ] Write tests for individual and combined real clause forms, both spec/body, malformed and cross-declaration negatives.
- [ ] Run focused tests and confirm expected failures.
- [ ] Extend header recognition and bounded metadata capture without changing downstream identity semantics.
- [ ] Run focused and database/Blueprint tests; confirm output.
- [ ] Commit `fix(database): recognize package header clauses with provenance`.

### Task 3: WP-08C, SQLcl slash delimiter

**Files:** Modify `formslang/database.py`; extend `tests/test_database_wp08.py`.

**Interfaces:** Consume Task 1 occurrence inventory. Produce correctly bounded statements for isolated slash lines with whitespace and adjacent CREATEs, without splitting lexical strings or comments.

- [ ] Write tests for bare/indented/blank-line slash, table and view after slash, slash in strings/comments/bodies, and combined A+B+C fixture.
- [ ] Run focused tests and confirm expected failures.
- [ ] Update the statement splitter using token positions and physical-line delimiter checks.
- [ ] Run focused and full project tests plus ruff; record exact results.
- [ ] Commit `fix(database): split SQLcl slash-delimited scripts safely`.
