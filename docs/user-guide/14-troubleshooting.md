# 14. Troubleshooting

| Symptom | Action |
|---|---|
| FMB requires XML | Supply Forms2XML exports or explicitly configure installed Oracle conversion tooling |
| Unsupported PLL/menu/library | Supply a supported semantic representation; do not treat discovery as successful parsing |
| Source Stale | Inspect changed sources, then Refresh Analysis; keep prior evidence/history |
| Missing Source | Relink the authorized source root; different contents invalidate applicability |
| Project busy | Inspect the running local operation; do not submit repeated competing writes |
| Process interrupted | Reopen, inspect the failed job and run a deliberate new analysis |
| Revision conflict | Reload evidence and consciously resubmit; never replay an old approval blindly |
| Generation blocked | Read each blocker; architectural acceptance does not approve code |
| Prepared session missing/corrupt | Preserve files, restore the complete source-bound review session; do not replace it with an empty DB |
| Artifact edited | Keep your edited copy; generate a new eligible managed artifact |
| SQLcl unavailable/failed | Check supported installation/path and diagnostics; leave Not Validated/Failed honestly |
| Reports conflict | Finish the current operation and reopen Reports for a fresh snapshot |

For support, include version, platform, safe error code and reproduction using synthetic data. Do not attach customer sources, credentials, private notes or full project databases without explicit organizational approval.
