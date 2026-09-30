# WP-05 disclosure probe (synthetic data)

Scope: the local System Map JSON and `convert.build_prompt`, as listed in the
implementation plan. The probe used only synthetic Forms XML, a synthetic host
path and a synthetic credential. It made no provider call and changed no
production behavior.

## Observations

| Path | Observed result | Limit |
|---|---|---|
| `ProjectService.system_map(focus="SCREENS")` | A symbolic `CALL_FORM` target containing `C:\Users\ProbeOwner\Private\SECRET_FORM` appeared as a target named `SECRET_FORM`; the serialized map did not contain the full path, `ProbeOwner` or `Private`. | This probes one real parser/project path. It does not prove that every possible literal, identifier or System Map field is safe. The symbolic target name is still visible as an unresolved reference. |
| `convert.build_prompt(task)` | The prompt included the selected unit's exact source body, including `synthetic_password_do_not_disclose_8472` and the synthetic host path. | This is the existing conversion contract, not a provider call. The enterprise egress policy can block cloud providers, but the prompt builder itself offers no per-call context preview or consent. Blindly changing the source body would change conversion input. |

The second probe is pinned as a strict `xfail` in
`tests/test_wp05_disclosure_probe.py`; the first is a passing characterization.
The source-body disclosure and consent boundary belong to SEC-05/SEC-06 and
AI-01..03, with a contract and separate tested correction in WP-47. Do not
describe the current egress policy as prompt sanitization or as proof that a
private endpoint cannot forward traffic elsewhere.

This probe closes no 3.0 release gate and makes no claim about real customer
sources, Oracle runtime behavior or the separate HTTP 500 investigation.

Local verification: Windows 11, Python 3.13.15. The targeted probe, policy and
conversion tests returned **39 passed, 1 xfailed**. The full suite returned
**1970 passed, 5 skipped, 4 xfailed** in 846.41 seconds. Ruff and
`git diff --check` passed. The three earlier strict xfails are unchanged.
