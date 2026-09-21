# Oracle APEX 26.1 and APEXlang modernization

FormsLang's default project target is the shared Oracle APEX / 26.1 / APEXlang
profile. This is a supported generation target, not Oracle endorsement or a claim
that every Forms behavior can be converted.

APEXlang provides human-readable `.apx` files suitable for inspection, diff and
version control. FormsLang reuses its existing layout/exporter rather than a
second generator. Generated files are versioned, deterministically ordered where
supported, and accompanied by hashes, provenance, exclusions and review bindings.

The current project scope is one independent module application per run.
Supported structural/native/validation mappings are described in
[generation boundaries](project-generation.md). Unimplemented execution semantics,
unresolved controls and unsupported mappings block the module. A partial estate
can therefore produce one reviewed application artifact while other modules remain excluded.

Architecture acceptance, executable code approval and generation authorization
are separate. Confirm observed database keys and security prerequisites; a
confirmation does not create missing policies or packages. Database refactoring
candidates remain non-executable descriptions unless an actual supported
generator exists.

Offline SQLcl validation records the exact artifact hash, tool version and mode.
It establishes only the supported syntax/structural checks, not database/runtime
equivalence. Import/deploy is a separate, explicit authorized operation. Review
source behavior, security, navigation, transaction semantics and UAT in a disposable
target before any production rollout.

See [user workflow](user-guide/08-apexlang-generation.md),
[validation](user-guide/09-validation.md) and [acceptance evidence](quality-acceptance.md).
