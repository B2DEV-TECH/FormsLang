# ADR-06 — Oracle entity identity and cross-revision correspondence

Status: **Draft**. Architecture acceptance requires the probe evidence below;
WP-04 product exit evidence is a separate gate. WP-04 must not change product
identity keys until this ADR is accepted.

## Context

The 2.2 database maps use a bare object name as a key. WP-08 preserves package
CREATE occurrences and withholds ambiguous bare-name projections, but cannot
publish two same-named schemas as separate database entities. `Blueprint`
entity IDs also derive from displayed names. A source locator, an Oracle symbol,
an occurrence in an export, and a decision's binding are different identities.
Treating any of them as a universal name would silently join unrelated evidence.

## Alternatives

1. Keep the bare-name maps and infer an owner from the filename or nearby
   declaration. This loses Case C and invents a schema context.
2. Use one printable dotted string as the key. Quoted names containing dots,
   quoted case, missing owners, and overloads make this ambiguous.
3. Use a typed canonical key within a pinned analysis, keep source occurrences
   separately, and represent cross-revision correspondence explicitly.

The proposed decision is **3**.

The typed key preserves Oracle equivalence without depending on a printable
label. Separate occurrences prevent a repeated export or redeclaration from
becoming an arbitrary winner. Analysis-bound entity IDs prevent a stable
symbol name from acting as permission to reuse a prior decision. The cost is
more explicit unresolved results and a new engine version for product facts;
those costs are preferable to attaching evidence or approval to the wrong object.

## Proposed contract

- An Oracle database symbol key is a typed tuple: object kind, optional schema
  identifier, object identifier, optional package membership, and an overload
  discriminator where the parser has enough signature evidence. Each identifier
  is a separate length-safe component. The absence of a schema is its own value;
  it is never silently substituted with a filename, directory or default owner.
- Oracle unquoted identifiers fold to uppercase. Quoted identifiers retain
  exact case and their decoded content; the raw spelling remains in source
  evidence. A quoted `"FOO"` and unquoted `FOO` denote the same Oracle identifier,
  while `"Foo"`, `FOO`, and `"A.B"` remain distinct as Oracle requires. A dot inside
  quotes never becomes a key separator.
- WP-08's `owner` and `name` display fields do not say whether an original
  mixed-case token was quoted. WP-04 must derive its key from the lexical header
  tokens or add explicit raw identifier components; it must never uppercase an
  already-decoded quoted name a second time. Oracle does not permit an
  embedded double quote or NUL in an object identifier; the probe rejects
  that invalid syntax.
- The identifier equivalence above follows Oracle's documented
  [database object naming rules](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Database-Object-Names-and-Qualifiers.html).
- Source occurrence identity includes the logical source root, relative source
  locator, physical line and ordinal. Two CREATE statements for one symbol stay
  as two occurrences. They are not silently reduced to the last statement or
  treated as proof of deployment order. Colliding or incomplete signatures
  remain ambiguous and retain their evidence.
- Within one source namespace, logical paths normalize separators to `/`,
  reject absolute paths and traversal, and preserve spelling and case. The
  occurrence ordinal distinguishes repeated declarations on the same physical
  line. A case-insensitive filesystem must detect source-path collisions at
  intake; it must not case-fold Oracle symbols or merge occurrences.
- A database entity ID is deterministic only inside an exact immutable analysis
  identity and its declared entity schema. A new analysis does not inherit a
  decision binding because a display name or local revision counter matches.
  A locator match or same bytes may produce a reviewable correspondence
  candidate, never an automatic approved rebind. A changed logical source root
  is `NOT_COMPARABLE`, not proof of removal. Duplicate candidate rows are
  deduplicated, and ambiguous candidates have a stable exact-locator-first
  order so filesystem enumeration cannot change the review result.
- Qualified references may resolve only to a unique compatible symbol under a
  pinned analysis. A bare reference with several valid candidates is
  `AMBIGUOUS`; a bare reference without proven schema context remains symbolic.
  Missing bodies, synonyms, dynamic SQL, and incomplete overload data remain
  explicit limits. A static match is not runtime call proof.
- A routine signature is structural evidence: routine kind, ordered parameter
  modes and declared types, and return type when present. It is not argument
  type inference. Exact supplied signatures may narrow candidates; an unknown
  signature cannot be used to eliminate a potential overload. Multiple CREATE
  occurrences remain ambiguous even when their signatures match. A missing
  body does not prevent a unique specification from being identified, but it
  cannot become an `IMPLEMENTS` edge or proof of behavior.
- Older `blueprint-analysis` snapshots retain their saved meanings. New
  schema-aware facts require an engine/capability version bump and explicit
  reanalysis. Existing 2.2 `LEGACY_RESOLVED` presentation is never silently
  upgraded by the UI.

## Implementation boundary

WP-04 may add typed identity and owner-aware projections for package specs,
bodies, tables, views and sequences, plus unique qualified reference resolution.
It must reuse the WP-08 occurrence and coverage inventory and preserve historical
`inventory-2.2.json`. It must not add a general correspondence service, change
decision applicability, infer default schemas, or rewrite the Oracle parser.
WP-11 and WP-31 consume the later correspondence contract.

## Architecture acceptance evidence

Acceptance of this contract is not acceptance of product WP-04 or gate G-04.
The former wording required schema-aware product behavior before allowing the
identity change that produces it. The coordinator approved separating those
two gates on 29 September 2026; product criteria below remain mandatory.

The probe remains in `examples/verify/entity_identity_contract.py`, outside
`formslang/`, with no product caller. It proves the proposed key and selection
rules using source fixtures and explicit candidate records. It does not prove
Oracle execution, general expression typing, an entity migration or approval
transfer.

- **Symbols and occurrences:** typed kind/owner/name/member/signature keys;
  raw quoted header decoding once; quoted case and dots; logical root/path,
  physical line and ordinal; deterministic analysis-bound IDs; duplicate CREATE
  ambiguity and duplicate candidate-row deduplication.
- **Resolution:** real Case C members select their qualified owner; bare
  references remain ambiguous or unresolved without schema context. Table,
  view and sequence candidate keys stay distinct. Overloads require enough
  signature evidence, and an absent body stays unresolved.
- **Correspondence:** rename/schema/signature changes are not silent matches;
  root/engine/byte changes are not comparable; move and exact candidates remain
  review candidates. The existing `classify` probe assumes a complete supplied
  candidate scope; it is not a general cross-revision search service. If a key
  changes while the same source locator remains, the result is `NOT_COMPARABLE`
  with no inferred target. An unrelated object in the same export is never
  guessed to be a rename. `REMOVED` requires no matching key or same source
  locator within the complete comparable candidate scope.
- **Fresh local verification:** 22 focused contract cases; 13 new cases failed
  before their probe implementation, and an additional case exposed a false
  resolution of a lone incomplete signature before its fix. Independent review
  exposed false `REMOVED` results for changed keys at the same source locator;
  two further tests failed first, then passed after the conservative
  `NOT_COMPARABLE` correction. The combined
  identity, WP-08, Case C, project-source and assessment suites returned
  **121 passed, 1 xfailed** in 6.65 s on Windows 11 / Python 3.13.15. The final
  22 contract tests also passed on Python 3.12.10 in 0.34 s. Repository
  Ruff and `git diff --check` passed. The complete suite, with code files held
  stable, returned **1991 passed, 5 skipped, 3 xfailed** in 903.85 s on
  Python 3.13.15 (`py -3.13 -m pytest -q -p no:cacheprovider`). An earlier run
  was interrupted before applying the review correction and is discarded.
  The WP-08 inventory generator check passed; product code and historical
  `inventory-2.2.json` remain unchanged from `360ab80`. The coordinator's final
  review and a separate acceptance commit are required before Accepted status.
- **Existing CI:** Draft PR #32 head `360ab8081d9855310e5029d1e070dc2399c04d78`,
  run `36633010065`, passed 13/13 checks. This evidence predates the new probe
  cases and is not represented as CI for their future commit.

### Earlier probe evidence

- At head `360ab80`, the outside-product probe
  `examples/verify/entity_identity_contract.py` and
  `tests/test_entity_identity_contract.py` passed **6** fixture tests on
  Windows / Python 3.12.10. They cover Case C owner keys, quoted source spelling
  retained by WP-08, Oracle identifier rules, and correspondence for move,
  rename, schema, overload, root, engine and changed bytes. Two new red tests
  exposed false `REMOVED` classification after a root change and false
  `AMBIGUOUS` classification for duplicate candidate rows; the probe now
  returns `NOT_COMPARABLE` and deduplicates with stable ordering. This validates
  a candidate contract, not product implementation or approval transfer.
  Before these two tests, the complete local suite returned **1973 passed,
  5 skipped, 3 xfailed** in 848.07 s on Python 3.13.15. The final local suite on
  Python 3.12.10 returned **1975 passed, 5 skipped, 3 xfailed** in 916.64 s.

## Product exit evidence required for WP-04 / G-04

These are implementation acceptance criteria, not prerequisites for selecting
the architecture. They must be proved on the separate product implementation
branch after ADR acceptance; they are not satisfied by the probe.

- Case C: both `ORDER_API` owners retain separate spec/body/member identities;
  each qualified call selects its owner and the bare call is ambiguous.
- Fixtures for quoted/unquoted equivalence, quoted case and dots, duplicate
  CREATEs, missing owner, table/view/sequence collisions, package overloads and
  missing bodies. Every withheld projection remains visible in coverage.
- Rename, move, schema change, overload change, logical-root change and engine
  change across revisions produce the appropriate explicit correspondence
  candidate or `NOT_COMPARABLE`, never a silent binding.
- Direct Blueprint and project pipeline agree; deterministic repeated builds,
  stable source revisions, legacy snapshot readability and the full CI matrix.

## Consequences and compatibility

The new analysis schema will contain more distinct entities than 2.2 and some
previously resolved references will become ambiguous. Consumers must use the
new typed identity and explicit resolution state. Historical analyses remain
readable under their original engine identity; migration does not edit them.
