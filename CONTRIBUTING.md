# Contributing to FormsLang

Thank you for considering a contribution. FormsLang is a small, focused
codebase — standard-library-only Python plus a thin Tauri shell — and it
tries hard to stay that way. Contributions that respect that shape are the
easiest to merge.

## Ground rules

- **No new runtime dependencies.** The Python engine is stdlib-only by
  design. A PR that adds a package to `pyproject.toml` dependencies needs a
  very strong reason.
- **Every behavior change comes with a test.** The suite in `tests/` pins
  the promises made in `docs/SPEC.md`; if you change a promise, change the
  spec and the test in the same PR.
- **English everywhere.** Code, comments, docs, commit messages and AI
  prompt text are all in English.
- **Never commit third-party material.** No `.fmb`, no Forms2XML `.xml`
  extracted from any real system, no proprietary PL/SQL, no production data.
  Test fixtures must be synthetic.

## Getting started

```bash
git clone https://github.com/B2DEV-TECH/FormsLang.git
cd FormsLang
python -m pytest tests/ -q        # Python 3.11+
python -m formslang serve         # run the workbench locally
```

The desktop shell lives in `desktop/` (Tauri 2.x); see `packaging/` for how
the engine is frozen into the sidecar binary.

## Workflow

1. **Fork** the repository and create a topic branch from `main`
   (`feat/…`, `fix/…`, `docs/…`).
2. **Develop** — keep the change as small as it can honestly be.
3. **Test** — `python -m pytest tests/ -q` must pass on your branch.
4. **Open a pull request** describing what changed and why. Reference the
   issue it addresses, if one exists.

## Reporting bugs

Open a GitHub issue with the FormsLang version, your OS, what you did,
what you expected and what happened instead. Never attach third-party Forms
modules or proprietary code — reproduce with a synthetic module (the
`tests/` fixtures show the shape).

## Proposing features

Open an issue first and describe the problem before the solution. FormsLang
deliberately keeps its surface small; a conversation before the code saves
everyone time.

## Security issues

Do **not** open a public issue — see [SECURITY.md](SECURITY.md).

## License of contributions

By submitting a pull request you agree that your contribution is licensed
under the [Apache License 2.0](LICENSE), the same license that covers the
project.
