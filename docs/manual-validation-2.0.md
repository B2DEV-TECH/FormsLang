# FormsLang 2.0 manual validation

Use synthetic/public-safe sources and a disposable Windows VM for installer changes.
Record candidate SHA/version, installer SHA-256, OS, result and screenshots. Do not
substitute these steps for the automated release gates in quality-acceptance.md.

| Step | Action | Expected result |
|---|---|---|
| Install | Install the accepted EXE or MSI | Correct version; no Python setup required |
| Launch | Start desktop; also try local browser mode | Local use requires no account/provider/database credentials |
| Demo | Explore Demo Project | A real persistent project is analyzed; no fake dashboard |
| Create | New Project; name, source folders, target, Analyze | Four conceptual steps; APEX 26.1/APEXlang default |
| Sources | Include valid XML/SQL, one malformed XML and an FMB without XML | Inventory/disclosures/remediation; no claim binary parsing succeeded |
| Analyze | Observe phases; cancel a separate refresh run | Real progress; cancelled run preserves previous committed assessment |
| Overview | Inspect scope, risk, direction, intervention, warnings | Real counts; Unknown visible; AUTO is not generation-ready |
| Inventory | Search package, filter risk, page, open/close details | Counts reconcile; filters/focus retained; no unrelated project rows |
| Review | Start Priority Review; inspect Forms/database evidence | Engine fact/inference and human overlay are distinguishable |
| Accept | Accept one safe item, reopen history | Decision/reviewer/rationale/revisions persist; engine unchanged |
| Change | Change another direction with rationale | Human decision separate; no implicit code approval |
| Critical | Try change without confirmation, then with rationale/confirmation | First rejected; deliberate expert override recorded |
| Bulk | Select mixed low/critical/manual items and preview | Unsafe exclusions explained; only exact eligible set may commit |
| Conflict | Open same finding in two clients; review one then submit other | Stale submission conflicts and reloads evidence |
| Generate | Select eligible module; prepare; review architecture; save prerequisite plan; approve code | Separate gates visible; unsupported behavior stays blocked |
| Artifact | Generate/download twice | Versioned artifacts; unchanged eligible content deterministic |
| Edited copy | Edit a downloaded copy, not managed files | Original retained; no silent overwrite or inherited validation |
| Validate | Explicit offline SQLcl validation | Hash/tool/mode recorded; missing tool never says Validated |
| Reports | Executive/technical/backlog/decision downloads | Standalone readable output; no source/private notes by default |
| Package | Explicit artifact opt-in; inspect manifest/files | Hashes match; exclusions and syntax-vs-runtime limits visible |
| Reopen | Close/relaunch and open Recent Project | Assessment, decisions/history and artifacts retained without analysis |
| Stale | Modify one synthetic source and reopen | Stale visible; old evidence retained; approval not silently reused |
| Relink | Move source, relink same then different contents | Missing Source remediation; different contents not called equivalent |
| CLI | Run project summary/inventory/review list/report | Same revisions/counts as UI; no competing persistence |
| Privacy | No provider configured; inspect network and report contents | Project workflow remains local; exports are labelled not anonymous |
| Upgrade | In disposable VM install 1.6.0, save session/settings/review/key, upgrade accepted candidate | State/export contract preserved; original session not destroyed |
| Uninstall/reinstall | Remove only application in disposable VM, reinstall | User source/project data preserved and reopenable |

For generation controls use `tests/fixtures/project-generation/notice.xml`; its
validation still needs explicit reviewed code. The dispatch demo intentionally
includes architectural blockers: do not force it to generate merely to finish a checklist.

Manually check keyboard-only navigation, visible focus, dialog focus containment,
tablet layout, zoom and a screen reader. Automated browser checks do not replace
that audit. Any live APEX import/runtime testing requires a separately approved
disposable target. Never use production/customer schemas.

Record defects with safe reproduction steps. Do not mark runtime parity, analyst
productivity or Oracle endorsement as validated by this checklist.
