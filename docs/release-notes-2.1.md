# FormsLang 2.1 — Estate Intelligence

FormsLang 2.1 makes the project workflow useful **before** a target technology
is chosen: understand what a Forms estate contains, find what deserves
architectural attention, and record decisions against saved evidence.
Everything in 2.0.0 is kept, and Oracle APEX 26.1 / APEXlang remains the only
implementation target.

> **Understand first. Modernize second.**

## Estate Intelligence

- **Hotspot candidates** derived from the saved Blueprint: *possible API
  bypass*, *duplicated business-rule candidate* and *global state coupling*.
  Each candidate lists its evidence, its severity rule and what that evidence
  cannot establish. Candidates are not verdicts.
- **Start Here** orders the items that deserve attention first and says why.
- Estate Intelligence is a projection over the saved assessment. It never
  re-analyzes source, and its identities are SHA-256 digests that are stable
  across runs and `PYTHONHASHSEED` values.

## System Map

- A module-level map of Forms, program units, packages, tables and views, with
  separate budgets for nodes, relationships and the focus selector, so a large
  estate stays readable.
- Same-named packages from different source roots stay separate nodes.
- **Project search** is bounded and covers the saved assessment only.

## Modernization Planning

- **Suggested investigation groups** collect related candidates for one
  architectural conversation.
- **Decision records** separate what a person recorded from what the engine
  PROPOSED. Engine recommendations stay proposed until a person decides.
- Not in this release: migration waves, dependency-ordered plans, and cost,
  schedule or ROI estimates. FormsLang does not invent them.

## Target Strategy

- **Analyze my Forms estate** creates a project with no implementation target
  (`UNSELECTED`) from the UI, HTTP API or CLI. Analysis, review, the System Map
  and reports all work without a target.
- A **target-neutral assessment package** ("Generic Modernization") is a
  non-code deliverable. It contains the assessment, not generated code.
- **Oracle APEX 26.1 / APEXlang** is the only code-generation target.
- The target choice is validated on the server and survives reopening the
  project. An unsupported target profile is rejected. Generation fails closed
  for an unselected target, and an unselected target never resolves to the
  target-neutral package.

## Delivery Integrity

- The target-neutral package and every report are built from **one reviewed,
  revision-fenced snapshot**. The output is deterministic, and an internal
  manifest hashes every member.
- A source or review change during an export rejects the "current" claim
  instead of mixing revisions.
- Executive and technical assessment reports carry the same findings, risks,
  review states and human decisions as Review. Source bodies, view SQL and
  private notes are excluded unless explicitly requested. When they are
  included, the file name says `-sensitive`.

## Reliability and Safety

- **Disclosure fix.** In 2.0.0, a finding named after a `HOST`, URL or
  `USER_EXIT` literal kept that literal in the exported reports and package.
  Such a literal can hold a connect string with a password. In 2.1, delivery
  packages and reports replace those names with a neutral label and a stable
  reference. The authorized local UI still shows the real name, which the
  user can already read in their own source.
- **Project lock contention fixed.** Opening a project briefly took its
  exclusive worker lock on every request, even when no interrupted job needed
  recovery. Concurrent requests could then fail with *Another project operation
  is active*. Recovery now takes the lock only when an interrupted job exists.
- A project job now reports a terminal status only after its worker has
  released the project, so the next operation does not collide with it.
- The Workbench conversion job persists its final run record before it stops
  reporting `running`.
- Experimental adapters fail closed. Missing inputs raise before anything is
  written, and an unavailable validator reports `NOT_VALIDATED`.

## Upgrade Notes

- Projects created by 2.0.0 open unchanged. Opening one with 2.1 rewrites no
  historical row and does not change the project descriptor. The only new row
  is the job record of any new operation you run.
- To move from a 2.0.0 installation, install the 2.1.0 Windows installer over
  it. Existing projects, reviews and artifacts are kept.
- Reports exported by 2.0.0 are historical files and are not changed. Export
  them again with 2.1 if they may contain integration literals. See
  *Reliability and Safety*.
- The modernization IR, architecture policy and target adapter registry are
  experimental library code with no product surface.

## Validation

Exact commands, run IDs, installer checksums and limitations are recorded in
[quality acceptance](quality-acceptance.md).
