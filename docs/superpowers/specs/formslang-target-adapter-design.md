# FormsLang Target Adapter Architecture Specification

> **Status:** future design (experimental code only). Production APEX generation in 2.1 does not run through `TargetAdapter`; the target-neutral assessment package is built from the delivery snapshot. No Java, .NET, React or external adapter exists.

**Repository:** `B2DEV-TECH/FormsLang`\
**Horizon:** `FormsLang 2.5 → 2.6`\
**Authoritative Reference:** [docs/superpowers/specs/2026-09-21-formslang-modernization-intelligence-platform-spec.md](2026-09-21-formslang-modernization-intelligence-platform-spec.md) §23–§28, §61–§63

---

## 1. Executive Summary & Adapter Doctrine

In FormsLang 2.0, the core modernization service directly invoked APEX generation routines (`ProjectGenerationService` importing `apexlang.py`). While effective for APEX 26.1 delivery, this tightly coupled architecture prevents supporting other modernization targets (e.g. Java/Spring, .NET, microservices, or target-neutral modernization planning).

FormsLang 2.5 introduces the **Target Adapter Boundary**:
1. **The Modernization Core is Target-Neutral:** Core analysis, dependency extraction, business-rule clustering, risk assessment, and human decision recording never call target-specific code directly.
2. **Target Knowledge Lives in Adapters:** Only the adapter knows how a target-neutral intent (`CENTRALIZE_EXISTING_OWNER` or `REPLACE_MECHANICAL_BEHAVIOR`) maps into target-native components (e.g. APEX `validation` with `plsqlError` vs a Spring `@Service` bean).
3. **No Loss of APEX Excellence:** The APEX adapter retains 100% of its native capabilities, including Universal Theme layout fidelity, item bindings, and offline SQLcl syntax validation.
4. **The Generic Modernization Target:** A fully supported, non-generating target providing architectural deliverables (backlogs, wave roadmaps, decision packages) without requiring any target code generator.

```
+--------------------------------------------------------------------------+
|                     FORMSLANG INTELLIGENCE CORE                          |
|  (ProjectService, ProjectAssessment, Modernization IR, Store, Review)   |
+--------------------------------------------------------------------------+
                                    │
                         Target Adapter Interface
                                    │
         +--------------------------+--------------------------+
         │                                                     │
         ▼                                                     ▼
+------------------------------------+   +------------------------------------+
| ORACLE APEX 26.1 ADAPTER           |   | GENERIC MODERNIZATION TARGET       |
| - Target ID: `oracle_apex_26_1`    |   | - Target ID: `generic_modernize`   |
| - Maps intents to APEX components  |   | - Maps intents to generic backlogs |
| - APEXlayout & Universal Theme     |   | - Generates no executable code     |
| - APEXlang 26.1 YAML/APX export    |   | - Exports CSV/JSON backlog,        |
| - Offline SQLcl compiler gate      |   |   decision packages, wave roadmaps |
+------------------------------------+   +------------------------------------+
```

---

## 2. TargetAdapter Contract Specification

All target adapters adhere to a pure Python standard library contract. No external plugin runner or dynamic evaluation is required in core.

```python
from typing import Any, Protocol

class TargetAdapter(Protocol):
    """Authoritative contract for FormsLang modernization target adapters."""

    @property
    def id(self) -> str:
        """Unique machine-readable adapter identifier (e.g. 'oracle_apex_26_1')."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable adapter name."""
        ...

    @property
    def target_version(self) -> str:
        """Target platform version supported (e.g. '26.1')."""
        ...

    def capabilities(self) -> dict[str, bool]:
        """Declared adapter capabilities.

        Examples:
            - supports_code_generation: bool
            - supports_offline_validation: bool
            - supports_layout_fidelity: bool
            - supports_wave_planning: bool
        """
        ...

    def interpret_intent(
        self, intent: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Maps a target-neutral Modernization Intent to a target-specific recommendation.

        Returns:
            - recommendation: target-specific action code (e.g. 'MOVE_TO_PLSQL_API')
            - target_component_kind: suggested target construct (e.g. 'validation')
            - rationale: plain language architectural justification
            - native_opportunity: whether the target platform replaces this natively
        """
        ...

    def evaluate_eligibility(
        self, module_id: str, project_state: dict[str, Any]
    ) -> dict[str, Any]:
        """Evaluates whether a module satisfies all target-specific delivery gates.

        Returns:
            - eligible: bool
            - blockers: list of unresolved architectural blockers
            - warnings: list of non-blocking warnings
        """
        ...

    def generate_deliverables(
        self, module_id: str, reviewed_scope: dict[str, Any], output_path: str
    ) -> dict[str, Any]:
        """Generates target-specific delivery artifacts.

        Returns:
            - manifest: dictionary of generated files with SHA-256 member hashes
            - package_path: absolute path to delivered archive or document bundle
        """
        ...

    def validate_deliverables(
        self, package_path: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Performs target-specific syntax or schema validation.

        Returns:
            - valid: bool
            - engine_name: name of validator (e.g. 'Oracle SQLcl APEXlang Compiler')
            - diagnostics: list of compiler error strings or warnings
        """
        ...
```

---

## 3. Code Partitioning & Refactoring Plan

To cleanly decouple the codebase without risking regressions to existing 2.0 projects:

### 3.1 Components Remaining in Core (`formslang/`)
* **Source Discovery & Ingestion:** `project_discovery.py`, `project_sources.py`, `project_intake.py`.
* **Parsing & Semantic AST:** `parser.py`, `model.py`, `plsql.py`, `plsql_evidence.py`.
* **Cross-Layer Analysis:** `depgraph.py`, `analysis.py`, `rules.py`, `project_analysis.py`.
* **Modernization Model & Hotspots:** `project_assessment.py`, `project_model.py`.
* **Review Service & Event Store:** `project_review.py`, `project_store.py`, `store.py`.
* **HTTP API & Workbench Server:** `project_http.py`, `workbench.py`.

### 3.2 Components Moving Behind the APEX Adapter (`formslang/adapters/apex/`)
* **Layout Geometry:** `apexlayout.py`, `test_apexlayout_geometry.py`.
* **APEXlang Generation:** `apexlang.py`, `templates/apexlang26/`.
* **SQLcl Validation Gate:** `apeximport.py`.
* **APEX Delivery Adapter Implementation:** `Apex26TargetAdapter` implementing `TargetAdapter`.

### 3.3 Components in the Generic Target Adapter (`formslang/adapters/generic/`)
* **Generic Recommendation Mapping:** `GenericTargetAdapter`.
* **Modernization Backlog Exporter:** CSV, JSON, and Markdown architectural report generator.
* **Modernization Wave Deliverables:** Structured sequencing plans.

---

## 4. The Generic Modernization Target Specification

The **Generic Modernization Target** (`generic_modernize`) proves target neutrality. It produces high-value architectural deliverables for teams migrating to non-APEX stacks (Java/Spring, .NET, microservices):

* **Capability Profile:**
  * `supports_code_generation = False` (Never claims to emit executable Java or .NET).
  * `supports_offline_validation = True` (Validates backlog schema and referential integrity).
  * `supports_wave_planning = True`.
* **Deliverables Package:**
  1. `modernization_backlog.csv`: Structured, issue-tracker ready backlog with rule ownership, risks, and recommended actions.
  2. `architectural_decisions.json`: Immutable audit trail of all human review decisions signed by reviewers.
  3. `modernization_waves.md`: Sequenced wave plan grouped by dependency coupling.
  4. `cross_layer_evidence.json`: Structural graph connecting UI triggers directly to DB packages and tables.

---

## 5. Security & Sandbox Boundary

In accordance with §28 of the master specification:
* Target adapters are registered statically in core code during initial phases. Dynamic third-party plugin loading is strictly deferred to Phase 2.6.
* Adapters receive bounded inputs (`reviewed_scope`, `project_metadata`) and write strictly to designated sandbox artifact output directories.
* Adapters have **zero access** to OS secret stores, network connections, or raw database connection strings.
