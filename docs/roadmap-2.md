# Roadmap: FormsLang 2.1 → 3.0

**Platform Vision:** Oracle Forms Modernization Intelligence Platform
**Current Stable Baseline:** `FormsLang 2.0.0` (2026-09-21)
**Authoritative Specification:** [docs/superpowers/specs/2026-09-21-formslang-modernization-intelligence-platform-spec.md](superpowers/specs/2026-09-21-formslang-modernization-intelligence-platform-spec.md)
**Core Motto:** *"Understand first. Modernize second."*

---

## Architectural Design Package

Before modifying core code, the platform architecture has been formally specified across five foundational design documents:

1. **Platform Vision & Positioning:** [docs/superpowers/specs/formslang-modernization-intelligence-vision.md](superpowers/specs/formslang-modernization-intelligence-vision.md)
   *The strategic mission, primary personas (enterprise architects, consultancies, tech leads), product doctrine, and non-goals through 3.0.*
2. **UX & Information Architecture:** [docs/superpowers/specs/formslang-21-ux-information-architecture.md](superpowers/specs/formslang-21-ux-information-architecture.md)
   *The 5-stage modernization journey (Understand → Assess → Decide → Plan → Deliver), Phase 0 design tokens, terminology normalization, and ASCII wireframes.*
3. **Modernization Model (IR):** [docs/superpowers/specs/formslang-modernization-model-design.md](superpowers/specs/formslang-modernization-model-design.md)
   *The 6-level taxonomy (Observed Facts → Structural Signals → Modernization Intent → Target Recommendation → Human Decision → Eligibility), lossless 2.0 mapping, and multi-revision invalidation matrix.*
4. **Target Adapter Architecture:** [docs/superpowers/specs/formslang-target-adapter-design.md](superpowers/specs/formslang-target-adapter-design.md)
   *Decoupling core intelligence from target generation via `TargetAdapter`, preserving native APEX 26.1 capabilities, and introducing the non-generating Generic Modernization Target.*
5. **Estate Intelligence Design:** [docs/superpowers/specs/formslang-21-estate-intelligence-design.md](superpowers/specs/formslang-21-estate-intelligence-design.md)
   *The Modernization Cockpit Overview, deterministic hotspot engine contracts (API Bypass, Duplicated Rules, Global State), "Start Here" explainable ranking, and scale performance budgets.*

---

## Release Progression

The evolution from FormsLang 2.0 to 3.0 proceeds in disciplined, incremental phases:

* **FormsLang 2.1 — Estate Intelligence:**
  * Phase 0 UX Foundation and design tokens.
  * Target-unselected project descriptor support.
  * Modernization Cockpit Overview with explainable "Start Here" priority ranking.
  * Grouped Estate workspace (Inventory, Dependencies, Business Rules, Ownership, Hotspots).
  * Global search foundations and bounded graph navigation.
* **FormsLang 2.2 — Modernization Model (IR):**
  * Decoupling observed facts from structural signals and target-neutral modernization intents.
  * Lossless bidirectional compatibility mapping for all existing 2.0 recommendations.
  * Append-only event store compatibility and multi-revision fencing.
* **FormsLang 2.3 — Architecture & Planning:**
  * Bounded interactive System Map (neighborhood expansion, edge filtering).
  * Modernization Plan workspace (dependency-aware wave sequencing without fabricated duration estimates).
  * Expanded Technical Modernization Assessment reports.
* **FormsLang 2.4 — Architecture Policy:**
  * Layered policy hierarchy (FormsLang Default → Organization Policy → Project Policy).
  * Policy provenance in recommendation explanations.
* **FormsLang 2.5 — Target Adapter Foundation:**
  * Formal `TargetAdapter` protocol implementation.
  * Extraction of APEX 26.1 exporter behind adapter contract without regression.
  * Delivery of the native Generic Modernization Target (backlog, decision packages, wave roadmaps).
* **FormsLang 2.6 — Extension Model:**
  * Sandboxed Target SDK contract and developer documentation for future community adapters.
* **FormsLang 3.0 — The Oracle Forms Modernization Intelligence Platform:**
  * Full target-neutral modernization intelligence across enterprise Forms estates.

---

> [!NOTE]
> Do not infer planned features are implemented until explicitly released. Core analysis, review, generation, reports, and CLI remain open source. Correctness, local trust, zero runtime dependencies, and generation safety remain uncompromising release gates.
