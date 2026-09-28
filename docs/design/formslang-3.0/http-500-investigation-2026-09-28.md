# Windows project HTTP 500 investigation (28 September 2026)

This investigation stays on the WP-02 instrumentation line (Draft PR #23,
`b83ade2`) and does not change the parser PR stack or the 3.0 product gates.

## Historical evidence

| Source | Environment | Observation |
|---|---|---|
| [main CI 36135896101](https://github.com/B2DEV-TECH/FormsLang/actions/runs/36135896101/job/108073760585), `main@1d9cb47` | Windows / Python 3.11 | `test_overview_keeps_saved_metrics_and_reports_stale_source`: 1 failed, 1867 passed. `analyze_demo` received HTTP 500 while polling `GET /api/v2/projects/{id}/jobs/{id}`. The only application log was `Project request failed`; that commit did not record the exception type. |
| [M0 PR CI 36148128814](https://github.com/B2DEV-TECH/FormsLang/actions/runs/36148128814/job/108114306867), PR #21 | Windows / Python 3.13 | `test_system_map_and_search_http_endpoints`: 1 failed, 1872 passed. Its failure also occurred inside `analyze_demo` while polling the job endpoint, before the named endpoint was tested. |
| [WP-02 CI 36176591379](https://github.com/B2DEV-TECH/FormsLang/actions/runs/36176591379), `b83ade2` attempt 1 | Eight Python/OS test jobs plus five other checks | 13/13 passed. Windows/Python 3.11: 1871 passed. This does not establish that the intermittent 500 is fixed. |
| [WP-02 CI 36176591379, attempt 2](https://github.com/B2DEV-TECH/FormsLang/actions/runs/36176591379/job/108989729285), `b83ade2` | Windows / Python 3.11.9 | 1871 passed in 2510.09 s; no `Project request failed` marker in the job log. Two instrumented full CI attempts have passed without reproducing the 500. |

The separate [issue #20](https://github.com/B2DEV-TECH/FormsLang/issues/20)
concerns `ProjectBusy`/HTTP 409. The two HTTP 500 failures above have no
recorded exception type, so their cause cannot be equated with that issue.

## Reproduction attempts in this session

The checkout was the exact `b83ade2` commit from PR #23. Local Windows was
`NT 10.0.26200.0`; installed Python versions were 3.12.10 and 3.13.15.

| Attempt | Result |
|---|---|
| Targeted historical test, 11 separate pytest processes on Python 3.12.10 | 11 passed, 0 HTTP 500 |
| Same targeted test, 11 separate processes on Python 3.13.15 | 11 passed, 0 HTTP 500 |
| Whole `tests/test_project_http.py` on Python 3.13.15 | 30 passed in 82.21 s |
| Full `py -3.13 -m pytest -q -x` | 1866 passed, 5 skipped in 846.99 s |
| Four tests of the sanitized 500 log on Python 3.13.15 | 4 passed |
| Windows/Python 3.11 rerun of WP-02 CI job | 1871 passed, 0 HTTP 500 in attempt 2 |

The WP-02 log boundary records the response correlation ID, method,
sanitized route, exception types, safe SQLite/OS codes where present, and
basename/line/function frames. It omits exception messages, source bodies,
request data and full paths. The historical failures predate this boundary,
so no causal frame can be reconstructed from them.

## Decision boundary

No root cause or red regression has been established. A corrective code
change must wait for a reproduced 500 with its sanitized exception chain.
If the rerun remains green, the next falsifiable check is to exercise the
job-status polling route during an active analysis in Windows/Python 3.11
while retaining the WP-02 log boundary, then compare a failed request's
frames and code against the asynchronous writer path. This is a hypothesis,
not a diagnosis.
