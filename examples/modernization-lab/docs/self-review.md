# Self-review: five perspectives on this lab

Before calling this lab finished, it was read back through five different
lenses, each looking for a different kind of failure. This is a genuine
review pass -- one real defect was found and fixed while writing it (see
Persona 1), and two verified FormsLang parser/documentation gaps outside
this lab surfaced along the way (write-up: `HANDOFF.md`, section
"FormsLang improvements found").

## 1. The FormsLang maintainer -- "does this actually exercise my parser?"

Checked: does every structural element FormsLang's parser exposes
(`FormModule`, `Block`, `Item`, `Trigger`, `Lov`, `RecordGroup`,
`Relation`) appear at least once across the four fixtures, with a real,
non-trivial value?

- Yes -- `metrics/compute_metrics.py` calls `formslang.parser.parse_xml()`
  directly (not a hand-rolled re-count) and both it and
  `tests/test_fixtures.py` pass cleanly against the current fixtures (9/9
  tests, metrics exit 0).
- **Found and fixed**: `forms/source/README.md` claimed the newline
  escape sequence baked into every `TriggerText` attribute was the
  "literal five-character sequence `&#10;`" -- but a grep of the actual
  fixtures shows all four files use `&amp;#10;` exclusively (76/97/62/247
  occurrences respectively across APPROVALS/CUSTOMERS/INVENTORY/ORDERS;
  zero bare `&#10;` anywhere). The doc was describing the pre-XML-escape
  form, not what is actually on disk. Fixed in place.
- While chasing that discrepancy, cross-checked FormsLang's own
  `README.md` and `formslang/parser.py`'s module docstring for the same
  fact, and found both call `&#10;` a "seven-character string" -- it's
  five (`len("&#10;") == 5`, confirmed by direct evaluation). This is a
  FormsLang defect, not a lab defect, so it isn't fixed here -- it's
  reported in `HANDOFF.md`.
- Also confirmed, by reading `formslang/model.py` directly, that the
  `Item` dataclass captures `lov_name` but has no field at all for
  `ValidateFromList` -- an attribute both this lab's fixtures and
  FormsLang's own `tests/fixtures/showcase/module.xml` actually set to
  `"true"`. This is a real, silent parser gap, also reported in
  `HANDOFF.md` rather than patched here (patching FormsLang's parser is
  outside this lab's scope).

## 2. The migration architect -- "does this answer questions I'd actually ask?"

Checked: pick five real migration questions and see if the lab answers
them without contradiction.

- "Can I trust the order-status column to tell me what transitions are
  legal?" -- No, and the lab says so three times, consistently:
  `docs/business-rules.md` (`SEQUENCE_NO` is descriptive only),
  `expected/modernization-ground-truth.json` (LOM-MOD-002, `CRITICAL`),
  and `docs/adr/002-status-transitions-owned-by-plsql-matrix.md`. No
  contradiction found across the three.
- "If I port the Approve/Reject buttons as-is, what breaks?" -- Answered
  concretely and consistently in `docs/modernization-challenges.md`
  (Theme 3), the ground truth (LOM-MOD-041/042), and
  `blueprint/expected-apex-architecture.md`'s Approvals section, which
  explicitly says "do not do that" about a literal translation.
- "Which module is the highest-risk piece of this migration?" --
  `assessment/complexity-and-risk-rollup.md` answers this quantitatively
  (3 of 4 CRITICAL cases converge on `APPROVALS.fmb` and the status
  matrix it calls into) rather than just asserting it qualitatively.
- "Is there a case where duplicating logic between Forms and PL/SQL is
  actually low-risk and fine to leave?" -- Yes: LOM-MOD-010 is `LOW` risk,
  called out explicitly in `docs/modernization-challenges.md` Theme 1 as
  a harmless instance of the same pattern, alongside the high-risk ones.
  The lab does not flatten every instance of a pattern to the same risk
  level, which would have been a cheaper but less honest way to write it.
- "Where do I still have to make a judgment call the lab can't make for
  me?" -- The 10 `MANUAL_REVIEW` cases, and ADR-005's explicit statement
  that the three navigation flows get three different answers, not one
  reusable pattern.

No contradiction found between the narrative docs, the ADRs, the
blueprint, and the registry on any of the five questions.

## 3. The new contributor -- "can I get oriented in ten minutes?"

Checked: follow `README.md`'s numbered reading order from a cold start,
verifying every link target actually exists and every forward reference
(e.g. "see ADR-002", "see the FormsLang-improvements handoff document")
resolves to a real file.

- All six items in the "start here" list resolve to files that exist.
- All five ADRs are cross-referenced correctly from
  `assessment/complexity-and-risk-rollup.md` (relative paths
  `../docs/adr/00N-*.md`, confirmed to resolve from that file's own
  directory).
- `forms/source/README.md` promises "see the FormsLang-improvements
  handoff document at the root of this lab" -- confirmed that document
  now exists at `HANDOFF.md`.
- The top-level `README.md`'s "Running the lab" section gives commands
  that were actually run during this build (`compute_metrics.py`,
  `unittest`), not aspirational ones -- both re-confirmed passing
  immediately before this review was written.

## 4. The legal/provenance reviewer -- "is this safe to publish?"

Checked against FormsLang's own `CONTRIBUTING.md` rule: "Never commit
third-party material. No `.fmb`, no Forms2XML `.xml` extracted from any
real system, no proprietary PL/SQL, no production data. Test fixtures
must be synthetic."

- No `.fmb`/`.fmd`/`.olb` file exists anywhere under
  `examples/modernization-lab/` -- confirmed by directory listing.
- Every `.xml` fixture is hand-authored (ADR-001, `forms/source/README.md`);
  none was produced by exporting a real Forms module.
- Every table/package/business rule is invented for this scenario; no
  identifiers, comments, or data resemble a real company's schema.
- No stray build artifacts were left behind that don't belong in a public
  repo: found and removed a `tests/__pycache__/` directory that had
  accumulated from running the test suite locally.
- No real credentials appear in any script: `scripts/install.sql`,
  `seed.sql`, `reset.sql`, and `verify.sql` all connect interactively
  (`sqlplus <user>/<password>@...`), never embedding one.

## 5. The skeptical auditor -- "does the lab's own tooling actually catch problems, or does it rubber-stamp?"

Checked: rather than trusting that `metrics/compute_metrics.py` and
`tests/test_fixtures.py` are doing real work, verify they can fail.

- Both scripts already proved themselves once earlier in this lab's
  construction: they caught two real fixture/documentation mismatches
  (the `INVENTORY.fmb` `BT_ADJUST` gap and the far more serious
  `APPROVALS.fmb` `BT_APPROVE`/`BT_REJECT` gap, where the ground truth,
  the package header comment, and the module's own XML header comment all
  asserted buttons existed that the fixture never actually contained).
  That these were caught by the tooling built for this lab, rather than
  missed until a reader noticed, is itself evidence the tests are load-
  bearing rather than decorative.
- Re-ran both after every subsequent fixture edit (not just once at the
  end) -- both still pass (9/9 tests, metrics exit 0) as of this review.
- Spot-checked one narrative claim against source directly rather than
  trusting the ground-truth JSON's own prose: `docs/business-rules.md`
  states the approval-rejection comment requirement is "enforced in
  PL/SQL, not by any `NOT NULL`/`CHECK` constraint" -- confirmed by
  grepping `database/ddl/lom_approvals.sql` (`COMMENTS` column has no
  `NOT NULL`) and `database/packages/lom_approval_api.pkb` (the check is
  an explicit `IF p_comments IS NULL THEN raise_application_error`).
- One limitation this review does not close: the SQL scripts
  (`install.sql`/`seed.sql`/`verify.sql`/`reset.sql`) were validated by
  static review (names and FK order cross-checked against the actual DDL)
  but never executed against a live Oracle instance in this session, for
  lack of any stored credential in this environment. This is stated
  plainly in `README.md`'s "Running the lab" section rather than glossed
  over, and is the one honest gap in this lab's own verification of
  itself.
