# FormsLang 2.2 — Visual Modernization Intelligence

FormsLang 2.2 lets a team **see** the architecture of an Oracle Forms estate
from the evidence the engine already saved: where the modules sit, what they
reach, which candidates deserve attention and what a person has decided.
It adds views, not analysis claims. There is no new detection rule, no AI
dependency, no Python runtime dependency and no Node build chain. Everything in
2.1.0 is kept, and Oracle APEX 26.1 / APEXlang remains the only implementation
target.

> **Understand first. Modernize second.**

## Executive and Technical views

- A toggle switches the presentation between Executive and Technical. Only the
  labels change: "Shared PL/SQL service" or "PL/SQL package", "Changes data" or
  `WRITES`. Identities, counts and evidence are the same in both.
- In Executive mode, hotspot evidence and Module 360 composition are worded in
  plain language. For example, `DIRECT_DML_BYPASSES_API` reads "Direct table
  access bypasses a related shared service", and the code stays in the tooltip.
  Technical mode shows the exact Oracle terms and engine signal codes.
- The choice is remembered for the browser session and is never stored in the
  project.

## Overview

- **Estate at a Glance** groups the estate by architectural lane.
- An investigation board, source coverage and a journey panel sit beside it.
  Every number comes from the saved assessment.
- **Start Here** still orders what to review first and says why on each line.

## Hotspot Explorer

- Filters by hotspot type, severity and module, and a modules × hotspot-type
  matrix.
- Each candidate (possible API bypass, duplicated business-rule candidate,
  global state coupling) shows **Why FormsLang noticed this** and **What this
  does NOT prove**. Candidates are not verdicts.
- **Show on map**, **Open Module 360** and **Review the linked finding** keep
  the context, and **Back** returns to the filtered list.

## System Map

- The estate view is laid out by lane on the server, deterministically and
  without a force simulation. It is bounded and states what it left out.
- The focus view draws what reaches the node on the left and what it reaches on
  the right, flags cycles and opens centred on the focus.
- Lenses, pan and zoom, a minimap, keyboard navigation and an inspector. A
  relationship table is the accessible alternative to the drawing.

## Module 360

- One module as a whole: composition, neighbours, hotspot candidates, findings
  and review state. A decision recorded in Review is counted there at once.
- Module 360 is a view of the saved evidence. It is not a migration plan, an
  effort estimate or a readiness verdict.

## Review and reports

- Review shows where the finding's module sits and its decided and deferred
  counts. A deferred finding is not a decided one.
- The executive and technical reports carry two static SVG figures: the estate
  by lane and the attention matrix. They are built from the same redacted
  snapshot as the rest of the report, contain no script, link or
  `foreignObject`, and are byte-stable when the project is reopened.

## Safety and accessibility

- Every HTML and SVG output escapes untrusted text.
- Exported figures and packages never carry HOST, URL or connect-string
  literals. The authorized local map may show them, as in 2.1.
- Map controls have names, a node's risk is stated in its label and not only
  by colour, and the 2.2 views fit 1920×1080 down to 390×844 without horizontal
  page scroll.
- FormsLang still produces no health score, migration percentage, effort,
  schedule or ROI.

## Upgrade Notes

- Install the 2.2.0 Windows installer over 2.1.0. Existing projects, reviews
  and artifacts are kept.
- Projects analysed by 2.1.0 open as CURRENT with the same analysis revision.
  They are not reanalysed, and the 2.1 HTTP API fields are kept.
- Reports exported by earlier versions are not changed. Export them again with
  2.2 to get the figures.

## Walkthrough

The [modernization lab walkthrough](modernization-lab-walkthrough.md) follows
the fictional Legacy Order Management lab from the estate to a recorded human
decision and the reports.

## Validation

Exact commands, run IDs, installer checksums and limitations are recorded in
[quality acceptance](quality-acceptance.md).
