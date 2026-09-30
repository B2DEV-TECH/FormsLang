# ADR-06 acceptance evidence plan

> Execute inline with `superpowers:executing-plans`; verify each change before claiming completion.

**Goal:** Decide the Oracle identity contract using an outside-product probe before changing WP-04 product keys.

**Architecture:** Keep typed symbols, source occurrences, analysis-bound IDs and reference resolution distinct. Add probe tests for the missing cases, then separate architecture acceptance from WP-04 product exit evidence in ADR-06. A later product branch must preserve historical snapshots and explicit reanalysis.

**Spec:** `docs/design/formslang-3.0/master-specification.md`, SRC-11/12/14, INV-01/02/06/07/08/10 and GRAPH-06; `adr/ADR-06-entity-identity.md`.

## Constraints

- No product identity changes before ADR acceptance; no merge, tag or release.
- Do not infer schemas, overload matches or decision approval.
- Use existing Case C and WP-08 inventories; preserve historical inventory bytes.
- Coordinate contract changes with the parent agent.

## Review focus

- Quoted mixed case and quoted dots survive conversion from declarations.
- Duplicate CREATE occurrences stay separate even when their symbols match.
- Missing owners, bodies and signatures cannot become confident resolution.
- Analysis/engine/root changes never transfer an approved binding.
- Product acceptance remains distinct from architecture acceptance.

## Tasks

1. [x] Add failing probe tests for occurrence identity, analysis-bound IDs, quoted declaration keys, qualified/ambiguous references, overloads and missing bodies.
2. [x] Extend only `examples/verify/entity_identity_contract.py` until those tests pass; run the focused identity and historical compatibility suites.
3. [x] Run repository Ruff, full pytest and diff checks with code files stable; record exact evidence. Repeated full suite after the final root-plus-key review correction.
4. [ ] Review the acceptance evidence and update ADR-06/index in a separate acceptance commit if sufficient. Keep WP-04/G-04 open.
5. [ ] Coordinate the separate product implementation branch and its test-first plan after acceptance.

## Review checkpoint

Independent review found that a changed key at the same source locator was
incorrectly classified as `REMOVED`. Two failing tests now prove the conservative
`NOT_COMPARABLE` result and prevent an unrelated same-file object from becoming
an inferred rename target. The coordinator requires ADR-06 to remain Draft
through publication of this probe evidence and final review. Acceptance requires
a separate authorized commit; no product implementation or gate change is part
of this evidence commit.

A further review case changes both root and key. It failed before the probe
withheld `REMOVED` for a populated scope lacking the original root. Related
tests and Ruff pass; the final full suite after this correction returned
1992 passed, 5 skipped, 3 xfailed in 847.99 s. ADR acceptance still awaits the
coordinator's independent review and separate authorization.
