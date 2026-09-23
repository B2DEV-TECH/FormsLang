# FormsLang: Modernization Intelligence Platform Vision

> **Status:** long-term vision, not a product description. Released: 2.0.0. In development: 2.1 Estate Intelligence. Everything beyond 2.1 is future work.

**Repository:** `B2DEV-TECH/FormsLang`\
**Current Baseline:** `FormsLang 2.0.0`\
**Horizon:** `FormsLang 2.1 → 3.0`\
**Authoritative Reference:** [docs/superpowers/specs/2026-09-21-formslang-modernization-intelligence-platform-spec.md](2026-09-21-formslang-modernization-intelligence-platform-spec.md)

---

## 1. Executive Summary & Strategic Problem

### 1.1 The Legacy Migration Trap
For decades, enterprise Oracle Forms modernization projects have followed a high-risk pattern:
1. An organization decides to migrate a massive Forms estate (hundreds or thousands of `.fmb` files).
2. A target technology is chosen prematurely (e.g., "we are rewriting everything in Java", "we are rewriting in React", or "we are converting to APEX").
3. Teams attempt mechanical 1:1 code transpilation or ad-hoc manual rewrites without understanding the actual architecture of the legacy estate.
4. Hidden dependencies, API bypasses (UI triggers directly executing DML against tables guarded by database packages), duplicated business logic spread across triggers, and unowned global state emerge during development, causing massive budget overruns, architecture collapse, and project failure.

### 1.2 The Strategic Solution
FormsLang transforms from a dedicated **Oracle Forms → Oracle APEX Modernization Workbench** into an **Oracle Forms Modernization Intelligence Platform**.

The strategic objective:
> **"Before a team rewrites a single Oracle Form, FormsLang should be the first tool they run."**

FormsLang provides immense, standalone value during discovery, assessment, and architectural review—**even when the eventual target is not Oracle APEX**.

Core positioning statement:
> **"Understand first. Modernize second."**

```
                  +----------------------------------------------+
                  |               LEGACY SYSTEM                  |
                  |  Oracle Forms (.fmb/.xml) + Database (DDL/PLSQL)
                  +----------------------------------------------+
                                         |
                                         v
                  +----------------------------------------------+
                  |         FORMSLANG INTELLIGENCE CORE          |
                  |  - Discover: Static extraction & cataloging  |
                  |  - Understand: Cross-layer dependency graph  |
                  |  - Assess: Hotspots, rule clusters & risk   |
                  |  - Decide: Human-in-the-loop review queue   |
                  |  - Plan: Dependency-aware wave sequencing    |
                  +----------------------------------------------+
                                         |
                       Target Selection (Decoupled & Late)
                                         |
         +-------------------------------+-------------------------------+
         |                               |                               |
         v                               v                               v
+------------------+           +-------------------+           +------------------+
|  Oracle APEX     |           | Generic Modernize |           | Future Adapters  |
|  Adapter         |           | (Neutral Backlog, |           | (Java / Spring,  |
|  (APEXlang, 26.1,|           |  Decisions, Waves,|           |  .NET, Custom)   |
|   SQLcl valid.)  |           |  Deliverables)    |           |                  |
+------------------+           +-------------------+           +------------------+
```

---

## 2. Primary Users & Jobs-To-Be-Done (JTBD)

FormsLang serves the broader enterprise modernization ecosystem beyond individual converter developers:

| Persona | Core Job to be Done (JTBD) | Value Delivered by FormsLang |
| :--- | :--- | :--- |
| **Enterprise Enterprise Architect** | *"I need to understand the true coupling and state of our 600 legacy Forms before committing to a technology roadmap."* | Cross-layer system map, API bypass detection, global state hotspots, and target-neutral architectural backlog. |
| **Modernization Practice / Consultant** | *"I need to conduct a rapid discovery assessment for a client in 3 days without installing complex servers or requesting production DB credentials."* | Zero-config, local-first discovery generating executive assessments, technical audits, and modernization backlog in CSV/JSON. |
| **Oracle Forms Technical Lead** | *"I need to know which business rules can be preserved in our existing PL/SQL packages versus what needs redesign."* | Business-rule candidate detection, layer ownership classification (`DATABASE_API` vs `FORM` vs `MULTIPLE`), and conflict detection. |
| **Oracle APEX Specialist** | *"I need a proven path to migrate eligible Forms into idiomatic APEX 26.1 applications without hallucinated runtime parity."* | Deterministic APEXlang generator, APEX layout fidelity mapping, item bindings, and offline SQLcl syntax gate. |

---

## 3. Product Doctrine (System Laws)

These eight doctrines are invariant architectural laws. Any design or implementation conflicting with them requires formal escalation and rejection.

### 2.1 Understand before generating
The modernization lifecycle has a strict, monotonic order:
$$\text{Discover} \longrightarrow \text{Understand} \longrightarrow \text{Assess} \longrightarrow \text{Decide} \longrightarrow \text{Plan} \longrightarrow \text{Generate} \longrightarrow \text{Validate} \longrightarrow \text{Deliver}$$
Generation is downstream. It must never become the entry point or an implicit default.

### 2.2 Facts and recommendations are strictly decoupled
The engine explicitly separates:
$$\text{Observed Facts} \longrightarrow \text{Structural Interpretation} \longrightarrow \text{Modernization Intent} \longrightarrow \text{Target Recommendation} \longrightarrow \text{Human Decision} \longrightarrow \text{Eligibility}$$
Never collapse facts, inferences, and suggestions into a single opaque object.

### 2.3 Engine recommendation is not human approval
The engine proposes; humans decide. An engine verdict (`AUTO`, `ASSISTED`, `MANUAL`) never implies human acceptance. Human decisions never imply code approval, which never implies generation authorization, which never implies runtime verification or UAT.

### 2.4 Evidence is mandatory
Every architectural finding, risk score, and recommendation must be anchored to verifiable evidence (source module, line/trigger, database object, structural relationship). When evidence is insufficient, state must degrade to `UNKNOWN` or `MANUAL REVIEW`—never fabricated confidence.

### 2.5 No black-box modernization decisions
Every state transition must answer: *What did FormsLang observe? Where did it observe it? What structural relationship was inferred? What rule fired? What did the human decide?*

### 2.6 Human review is architecture
Human-in-the-loop is not a disclaimer; it is a product boundary. FormsLang assists mechanical and structural verification, leaving business and architectural judgment to human owners.

### 2.7 Unknown is a valid state
Incomplete knowledge is presented honestly as `UNKNOWN`, not coerced into `LOW` risk or automatic preservation.

### 2.8 Local-first remains mandatory
Deterministic discovery, assessment, and review run 100% locally on the Python standard library without requiring external AI keys, cloud telemetry, or live database connections.

---

## 4. Target-Neutral Strategy

### 4.1 Target Selection is Optional During Assessment
A project initialized with Forms XML and database sources must be fully functional with:
```text
target_strategy = UNSELECTED
```
In this state, the entire Modernization Intelligence suite remains active:
* **Estate Discovery & Inventory**
* **Cross-Layer Dependencies & System Map**
* **Hotspot Detection & Business-Rule Ownership**
* **Human Architectural Review of Modernization Intents**
* **Executive & Technical Assessment Reports**
* **Modernization Wave Planning & CSV/JSON Backlogs**

Target-specific planning, code generation, and SQLcl validation become enabled **only** when a concrete target adapter (such as `ORACLE_APEX_26_1`) is explicitly configured.

### 4.2 Initial Supported Target Strategies
1. `UNSELECTED`: Target-neutral mode. Pure modernization intelligence and architectural planning.
2. `GENERIC_MODERNIZATION`: Non-generating target producing formal architecture decision packages, modernization backlogs, and wave roadmaps.
3. `ORACLE_APEX_26_1`: Native APEXlang 26.1 export, Universal Theme mapping, component binding, and offline SQLcl validation gate.

---

## 5. Non-Goals Through FormsLang 3.0

To preserve focus and engineering integrity, the following are explicit non-goals:
* ❌ **Automatic Java / Spring code generation.**
* ❌ **Automatic .NET application generation.**
* ❌ **Automatic React / frontend transpilation.**
* ❌ **Autonomous architecture decisions without human sign-off.**
* ❌ **Replacing User Acceptance Testing (UAT) or claiming runtime equivalence.**
* ❌ **Cloud SaaS migration or rewrites into external multi-tenant hosted services.**
* ❌ **Frontend framework rewrites (no React/Vue/Angular migration for the desktop workbench).**
* ❌ **LLM-based risk scoring or opaque AI architecture authority.**
* ❌ **Invented project duration or cost estimations without calibrated enterprise input.**

---

## 6. Phased Platform Roadmap (2.1 → 3.0)

```
2.0.0 (Released) ──> 2.1 (Estate Intelligence) ──> 2.2 (Modernization Model)
                                                          │
3.0 (Intelligence Platform) <── 2.5 (Target Adapters) <── 2.3 & 2.4 (Architecture & Policy)
```

* **FormsLang 2.1 — Estate Intelligence:**
  * Phase 0 UX & Design Tokens foundation.
  * Target-unselected project descriptor support.
  * Modernization Cockpit Overview with "Start Here" deterministic ranking.
  * Grouped Estate workspace (Inventory, Dependencies, Rules, Ownership, Hotspots).
  * Scalable dependency navigation and server-side global search foundations.
* **FormsLang 2.2 — Modernization Model (IR):**
  * Decoupling observed facts from structural signals and target-neutral modernization intents.
  * Compatibility mapping for existing 2.0 recommendations; unmapped values (for example `WRAP_AS_API`) stay `UNKNOWN` with their raw legacy value.
  * Invalidation matrix and multi-revision fencing.
* **FormsLang 2.3 — Architecture & Planning:**
  * Bounded interactive System Map (neighborhood expansion, edge filtering).
  * First-class Modernization Plan (wave sequencing, coupling-aware ordering).
  * Expanded Technical Assessment reports.
* **FormsLang 2.4 — Architecture Policy:**
  * Layered policy hierarchy (Default → Organization → Project).
  * Deterministic policy evaluation without fact rewriting.
  * Policy provenance in recommendation explanations.
* **FormsLang 2.5 — Target Adapter Foundation:**
  * Formal `TargetAdapter` interface and capability model.
  * Extraction of APEX 26.1 exporter behind the adapter contract.
  * Native `Generic Modernization Target`.
* **FormsLang 2.6 — Extension Model:**
  * Target SDK contract and sandboxed capability boundaries.
  * Developer documentation for third-party target adapters.
* **FormsLang 3.0 — The Oracle Forms Modernization Intelligence Platform:**
  * Complete target-neutral intelligence platform delivering validated modernization discovery and governance across enterprise Forms portfolios.
