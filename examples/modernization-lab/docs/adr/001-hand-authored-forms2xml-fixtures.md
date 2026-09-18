# ADR-001: Hand-author Forms2XML fixtures instead of reverse-engineering .fmb

## Status
Accepted

## Context
This lab needs realistic Oracle Forms modules (CUSTOMERS, ORDERS, INVENTORY,
APPROVALS) to demonstrate modernization analysis against. FormsLang itself
parses Forms2XML exports, not the proprietary binary `.fmb` format, and the
project's own policy (documented at the FormsLang repo level, not specific
to this lab) is that the binary `.fmb`/`.fmd`/`.olb` formats are never
reverse-engineered or parsed — only Oracle's own documented Forms2XML
export format is read.

## Decision
Every form fixture in `forms/xml/*.xml` is hand-authored directly as
Forms2XML, matching the exact structure and escaping conventions
(`&amp;#10;` for a newline inside a `TriggerText` attribute, standard XML
attribute-escaping otherwise) that Oracle Forms Builder's own File > Export
> XML produces. No `.fmb` binary exists anywhere in this repository, and
none is ever produced, opened, or parsed as part of building or running
this lab.

## Consequences
- The fixtures are legally and technically safe to publish in a public,
  Apache-2.0 repository: nothing here depends on or embeds Oracle's binary
  format or any real customer's Forms modules.
- Hand-authoring means every structural element (block/item/trigger counts)
  is exactly and deliberately what `metrics/compute_metrics.py` reports —
  there is no ambiguity about what a "real" export would have contained,
  because there is no real export to diverge from.
- The XML comment restriction (`<!-- ... -->` cannot contain `--` anywhere,
  since `xml.etree.ElementTree` treats a bare `--` inside a comment as a
  parse error) had to be discovered and documented
  (`forms/source/README.md`) specifically because hand-authoring surfaces
  gotchas a real export tool would never trigger.
- Anyone wanting to regenerate these fixtures from an actual Forms Builder
  installation can do so and diff against these files, but that path is
  explicitly out of scope for this lab and not required to use it.
