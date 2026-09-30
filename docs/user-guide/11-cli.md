# 11. CLI and automation

CLI, local API and UI use the same ProjectService. Existing 1.x commands remain available.

```console
formslang project create ./assessment --name "Orders" --forms ./forms --database ./database
formslang project discover ./assessment --json
formslang project analyze ./assessment --json
formslang project status ./assessment --json
formslang project freshness ./assessment --json
formslang project analysis-history ./assessment --limit 50 --offset 0 --json
formslang project summary ./assessment --json
formslang project inventory ./assessment --category findings --risk HIGH --json
formslang project review list ./assessment --json
formslang project generation status ./assessment --json
formslang project report ./assessment --format executive --output executive.html
formslang project report ./assessment --format package --include-artifacts --output delivery.zip
```

Use `project review show --finding ID` to obtain the exact binding before `decide` or `annotate`. Generation commands use JSON request files with returned revision bindings. Do not fabricate revision tokens or auto-replay a conflicted approval.

`--json` gives machine-readable output; analysis progress goes to stderr. Downloads refuse existing output paths. Use each command's `--help` for exact parameters.

`status` shows the last saved source-freshness check; it does not scan current
source files. Run `freshness` explicitly to record a new check. The read-only
`analysis-history` command lists saved analysis and source revision identities
only. It is not the whole-project `log`, a checkpoint, or a portable history.

Authenticated deployments use the authorized HTTP API; local CLI is not an authorization bypass. Versioned project routes are under `/api/v2/projects`, separate from legacy project routes.
