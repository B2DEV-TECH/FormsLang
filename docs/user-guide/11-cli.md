# 11. CLI and automation

CLI, local API and UI use the same ProjectService. Existing 1.x commands remain available.

```console
formslang project create ./assessment --name "Orders" --forms ./forms --database ./database
formslang project discover ./assessment --json
formslang project analyze ./assessment --json
formslang project summary ./assessment --json
formslang project inventory ./assessment --category findings --risk HIGH --json
formslang project review list ./assessment --json
formslang project generation status ./assessment --json
formslang project report ./assessment --format executive --output executive.html
formslang project report ./assessment --format package --include-artifacts --output delivery.zip
```

Use `project review show --finding ID` to obtain the exact binding before `decide` or `annotate`. Generation commands use JSON request files with returned revision bindings. Do not fabricate revision tokens or auto-replay a conflicted approval.

`--json` gives machine-readable output; analysis progress goes to stderr. Downloads refuse existing output paths. Use each command's `--help` for exact parameters.

Authenticated deployments use the authorized HTTP API; local CLI is not an authorization bypass. Versioned project routes are under `/api/v2/projects`, separate from legacy project routes.
