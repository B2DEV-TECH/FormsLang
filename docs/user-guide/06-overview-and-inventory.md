# 6. Overview and Inventory

Overview answers scope, risk, recommended direction and priority using saved evidence. Counts are not estimates of labor, cost or migration completion.

- Risk: Critical, High, Medium, Low and Unknown. Unknown is never Low.
- Direction: Preserve, Convert, Refactor, Move to PL/SQL API, Use Native APEX, Human Review, Drop or Unresolved.
- Intervention: AUTO, Assisted, Manual or Unknown. AUTO is not generation authorization.
- Coverage: analyzed/discovered/failed representations, with explicit denominators. No invented database-completeness percentage.

Click a distribution to inspect matching findings. Inventory supports Forms, Libraries, Packages, Routines, Views, Tables, Dependencies, Business Rules and Findings. Search and filters compose; pages default to 50, maximum 200. Details preserve context when returning to the list.

A modernization finding is an engine recommendation, not every graph node. Package specs/bodies and unique packages have different counts. Business-rule candidates are not verified business intent. The **Dependencies** tab stays in the current project; detailed legacy Blueprint graph exploration remains available in the existing-session workflow.

Current, Stale, Incomplete, Missing Source and Unverified states remain visible. See [count semantics](../project-overview.md).

## Visual views (2.2)

- **Executive / Technical** changes labels only. Technical keeps the exact Oracle terms and engine signal codes; Executive words them plainly and keeps the code in the tooltip. Identities, counts and evidence are the same.
- **Overview** groups the estate by architectural lane (Estate at a Glance) beside source coverage and an investigation board. **Start Here** says why each item is first.
- **Hotspot Explorer** lists the engine's candidates (possible API bypass, duplicated business-rule candidate, global state coupling) with filters and a module × type matrix. Each card states *Why FormsLang noticed this* and *What this does NOT prove*.
- **System Map** shows the estate by lane, bounded and with its truncation stated. The focus view puts what reaches a node on the left and what it reaches on the right. A relationship table offers the same edges by keyboard.
- **Module 360** shows one module's composition, neighbours, candidates, findings and review state. It is not a migration plan or a readiness verdict.

These views read the saved assessment; none re-analyzes source or produces a score, percentage, effort or schedule. The [modernization lab walkthrough](../modernization-lab-walkthrough.md) follows them end to end.
