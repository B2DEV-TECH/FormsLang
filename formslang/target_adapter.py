"""Target adapter protocol and static registry -- EXPERIMENTAL foundation.

Status in FormsLang 2.1: production APEX generation does not run through this
registry (see ``adapters.apex``); the target-neutral assessment package calls
its adapter directly from ``ProjectGenerationService``. Resolution requires a
complete supported profile. There is no external or dynamic adapter loading.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .project_model import ProjectError, TargetProfile


@runtime_checkable
class TargetAdapter(Protocol):
    """Authoritative contract for FormsLang modernization target adapters (§106, §2)."""

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

    @property
    def target_profile(self) -> TargetProfile:
        """TargetProfile instance associated with this adapter."""
        ...

    def capabilities(self) -> dict[str, bool]:
        """Declared adapter capabilities.

        Keys:
            - supports_code_generation: bool
            - supports_offline_validation: bool
            - supports_layout_fidelity: bool
            - supports_wave_planning: bool
            - supports_backlog_export: bool
        """
        ...

    def interpret_intent(
        self, intent: str, context: dict[str, Any] | None = None
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
        self, package_path: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Performs target-specific syntax or schema validation.

        Returns:
            - valid: bool
            - engine_name: name of validator (e.g. 'Oracle SQLcl APEXlang Compiler')
            - diagnostics: list of compiler error strings or warnings
        """
        ...


# ---------------------------------------------------------------------------
# Static Adapter Registry (§5)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, TargetAdapter] = {}
_PROFILES: dict[TargetProfile, TargetAdapter] = {}
# Aliases name one documented complete profile each; nothing else is inferred.
_ALIASES = {
    "apex": TargetProfile("Oracle APEX", "26.1", "APEXlang"),
    "oracle_apex": TargetProfile("Oracle APEX", "26.1", "APEXlang"),
    "generic": TargetProfile("Generic Modernization", "1.0", "Neutral Backlog"),
}


def register_adapter(adapter: TargetAdapter) -> None:
    """Register a built-in target adapter under its complete profile."""
    _REGISTRY[adapter.id] = adapter
    _PROFILES[adapter.target_profile] = adapter


def get_target_adapter(target: TargetProfile | str) -> TargetAdapter:
    """Resolve an adapter by complete profile, registered id or documented alias."""
    _ensure_builtin_adapters_registered()
    if isinstance(target, TargetProfile):
        profile = target
    elif isinstance(target, str) and target in _REGISTRY:
        return _REGISTRY[target]
    elif isinstance(target, str) and target.strip().lower() in _ALIASES:
        profile = _ALIASES[target.strip().lower()]
    else:
        raise ProjectError(f"Unknown target adapter identifier: {target}")
    if profile.platform == "UNSELECTED":
        raise ProjectError("No implementation target is selected; no target adapter applies.")
    adapter = _PROFILES.get(profile)
    if adapter is None:
        raise ProjectError("Unsupported target profile: "
                           f"{profile.platform} {profile.version} / {profile.representation}")
    return adapter


def list_target_adapters() -> list[TargetAdapter]:
    """Return all registered target adapters."""
    _ensure_builtin_adapters_registered()
    return list(_REGISTRY.values())


def _ensure_builtin_adapters_registered() -> None:
    if not _REGISTRY:
        from .adapters import register_builtin_adapters
        register_builtin_adapters()
