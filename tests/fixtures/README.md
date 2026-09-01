# Golden corpus

Synthetic Oracle Forms XML fixtures used by `tests/test_golden_corpus.py`.
Every fixture is 100% invented -- no client data, no real Form, ever.

## Tiers

| Tier | `corpus/<tier>/module.xml` | Built by | Proves |
|---|---|---|---|
| `tiny` | one form trigger, no blocks | hand-authored | minimum input that still yields exactly one task |
| `small` | ~10 objects, two triggers (one below `MIN_SOURCE_CHARS` and silently dropped), a validated item, a program unit, LOV/record group | hand-authored | a realistic small module end to end |
| `medium` | 33 blocks, one per common Forms trigger family + an unrecognized trigger name | `tests/fixtures/generate_corpus.py` | breadth across `rules.py`'s verdict/category catalog |
| `large` | 60 blocks: a hub that `GO_BLOCK`s to all 59 others, plus a `B_i -> B_i+1` chain | `tests/fixtures/generate_corpus.py` | `depgraph.py`'s `MAX_DEPTH=4` / `MAX_RESULTS=250` are genuinely hit (confirmed: 362 nodes / 480 edges, a walk from the hub returns exactly 250 results at both depth 4 and depth 6) |
| `pathological` | circular `BLOCK_A <-> BLOCK_B`, a dynamic `GO_BLOCK(v_dynamic_target)` (unresolvable), cp1252-mojibake in a `Prompt` attribute, a 200+ line `ProgramUnit` | hand-authored | the parser/depgraph edge cases a straight-line fixture never touches |

`tiny`, `small` and `pathological` stay hand-authored because each one
demonstrates something specific that a generator loop would obscure.
`medium` and `large` are generated because hand-typing 50-200+ repetitive
XML objects is how a fixture silently drifts from what it claims to cover.

Regenerate `medium`/`large` (only needed if their shape changes):

```
py tests/fixtures/generate_corpus.py
```

## Golden files

`tests/golden.py` runs each tier through the real pipeline (parse -> task
queue -> dependency graph -> offline `EchoProvider` proposal -> export) and
reduces the result to deterministic JSON in `fixtures/golden/<tier>.json`.
Two non-deterministic fields (the `-- exported: <timestamp>` line and the
session's `created_at`) are normalized before hashing; everything else in
a fresh, undecided session is already deterministic.

- `tests/test_golden_corpus.py` checks the committed golden still matches
  what the pipeline produces today, with a readable diff on mismatch, and
  separately proves the pipeline is deterministic (two runs, same tier,
  byte-identical output).
- `tests/update_golden.py` is the *only* sanctioned way to change a golden
  file. It is manual-only: never imported by a test, never called by CI
  (no CI configuration exists in this repository), always prints a diff,
  and always requires an interactive `y` confirmation unless `--yes` is
  passed explicitly on the command line.

```
py tests/update_golden.py --tier medium     # review the diff, then confirm
py tests/update_golden.py --all --yes       # regenerate everything, no prompt
```

If `test_golden_corpus.py` fails, that is the point: something --
usually a `rules.py` verdict, a `depgraph.py` bound, or an `ai.py`
proposal shape -- moved. Read the diff, decide whether the new behaviour
is correct, and only then run `update_golden.py`.
