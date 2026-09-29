# ADR-06 — Oracle entity identity and cross-revision correspondence

Status: **Draft**. WP-04 must not change product identity keys until the fixture
and compatibility evidence below has been reviewed and this ADR is accepted.

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

## Evidence required before acceptance

- The outside-product probe `examples/verify/entity_identity_contract.py` and
  `tests/test_entity_identity_contract.py` currently pass **6** fixture tests on
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
