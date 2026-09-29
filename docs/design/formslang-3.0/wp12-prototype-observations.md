# WP-12: one read-only Form journey

This is a task prototype on the existing Workbench and the bundled **Synthetic dispatch desk**. It reads the saved assessment, System Map relationship, source evidence and generation checks. It creates no decision, generation artifact or new persistence record. These are scripted browser observations, not observations from five participants.

## Product review task script

1. Run `formslang workbench`, then choose **Explore Demo Project**. Wait for the saved assessment to finish.
2. Open **Explore a Form** in the project navigation. Open **CUSTOMERS**.
3. Select **Opens Form → SHIPMENTS**. Identify the saved evidence ID, the structural `OPEN_FORM` excerpt, and what the excerpt cannot establish.
4. Select **References → CUSTOMERS**. Check whether the destination is confirmed or unresolved.
5. Return to **Opens Form → SHIPMENTS**, then choose **Open related Form: SHIPMENTS**.
6. Read the current generation blocker categories for `forms/shipments.xml`. State whether this Form is ready to generate.

The journey can be run against another analyzed project. The bundled demo keeps this review repeatable and free of private source material.

## Recorded observations

The Edge acceptance script uses the real local server and bundled synthetic project. It found two Forms. **CUSTOMERS** exposes an observed `OPENS_FORM` relationship to **SHIPMENTS** and an observed `REFERENCES` relationship whose destination remains **UNRESOLVED**. The selected `OPENS_FORM` evidence ID matches the ID attached to that exact saved edge. Its excerpt retains `OPEN_FORM` while omitting the `'SHIPMENTS'` literal. The interface labels the excerpt as bounded, names the relationship as a structural observation, and says runtime behavior is unverified.

Following the resolved edge opens the **SHIPMENTS** Form in the same journey. The generation service reports it blocked, including `MODULE_NOT_PREPARED`; the page groups all current blocker records by code and shows counts. The journey has no controls for accepting decisions, preparing code or generating output. The browser check compares analysis, review and source revisions before and after this sequence.

Captured synthetic screens: [relationship evidence and limits](assets/wp12-customers-evidence.png) and [blockers after following the Form](assets/wp12-followed-form.png).

The navigation stays connected across the four steps, but the evidence and blocker sections are below the initial viewport at 1360 × 800. The reviewer must scroll. Repeated finding-level blockers are grouped for readability; this is a summary of the existing checks, not a replacement for the full generation detail.

## Evidence boundaries and known gaps

- The System Map and Module 360 are bounded projections. The UI reports when the Form selector or relationship list is truncated; relationship evidence contains at most the existing five sampled component edges.
- Source excerpts omit literals, comments and sensitive contexts; an authorized reviewer must inspect the local source for exact values. A structural `OPEN_FORM` call does not prove runtime behavior or migration parity.
- Unresolved targets stay unresolved and cannot be followed as confirmed Forms. Absence of a shown relationship does not prove absence in the estate.
- This prototype does not link blockers back to a decision workflow, assess keyboard and screen-reader use, or validate a large estate. UX-02 and UX-03 remain open for WP-41 and formal acceptance.
- No 3.0 release gate is closed by this prototype. It is not the five-person usability study.

The separate post-merge `main` CI run [36511441846](https://github.com/B2DEV-TECH/FormsLang/actions/runs/36511441846) had one Windows/Python 3.13 failure: `tests/test_project_http.py::test_cli_summary_and_inventory_reconcile_with_http` received HTTP 500 while reading a project job status. The response carried correlation ID `5ff98d6503524d0e9e636b059664e777`; 1 test failed, 1973 passed and 3 xfailed in that job. The cause remains unknown. PR #23 remains separate observability work.
