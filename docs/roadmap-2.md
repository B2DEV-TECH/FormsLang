# Roadmap after FormsLang 2.0

**Released:** FormsLang 2.0.0 — the corporate project workflow with reviewed
Oracle APEX 26.1 / APEXlang generation.
**In development:** FormsLang 2.1 — Estate Intelligence (not released; no
installer contains it).
**Motto:** *Understand first. Modernize second.*

Planned does not mean implemented. Only a published release, recorded in
[quality acceptance](quality-acceptance.md), establishes what an installer
contains.

## 2.1 Estate Intelligence — in development

Goal: before a team modernizes Oracle Forms, FormsLang is the first tool they
run, and it is useful before the target technology is chosen.

In scope, built on the existing persisted assessment (Blueprint + review
ledger), with no second analysis engine or project store:

- Target-neutral project creation (*Analyze my Forms estate*, target not
  selected) from the UI, HTTP and CLI; APEX remains the first supported
  implementation path.
- Overview with estate size, coverage, freshness, hotspot candidates and an
  explained *Start Here* list.
- Hotspot candidates derived from saved evidence: possible API bypass,
  duplicated business-rule candidate, global state coupling. Each carries an
  evidence contract, a severity rule and an uncertainty statement.
- Module-level System Map with bounded nodes, relationships and selectors.
- Bounded project search.
- Review presentation that separates observed evidence, structural
  interpretation, the proposed engine recommendation and the human decision.
- Executive and technical assessment reports, suggested investigation groups
  (not a migration schedule), decision records and a target-neutral assessment
  package that preserve human decisions and exclude source bodies by default.

## Future — ideas, not commitments

These appeared in the long-term specification. None is implemented as product
behavior; some have experimental library code that the product does not use.

- An authoritative target-neutral modernization model (IR) with selective
  invalidation. Experimental code: `formslang/modernization_model.py`.
- Enforced architecture policy with provenance (Default → Organization →
  Project). Experimental code: `formslang/architecture_policy.py`; no UI, HTTP
  or CLI surface in 2.1.
- Dependency-aware modernization planning (sequencing, cycles, hold groups).
- Extracting APEX generation behind the target adapter protocol without
  regression. Experimental code: `formslang/target_adapter.py`,
  `formslang/adapters/`.
- Further implementation targets and any extension model. FormsLang does not
  generate Java, .NET or React code.

Design notes for this direction live under `docs/superpowers/specs/`. The
[long-term specification](superpowers/specs/2026-09-21-formslang-modernization-intelligence-platform-spec.md)
is a vision document, not a description of the current product.

Core analysis, review, generation, reports and CLI remain open source.
Correctness, local operation, zero runtime dependencies and generation safety
remain release gates.
