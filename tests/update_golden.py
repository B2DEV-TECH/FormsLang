"""Regenerate golden-corpus files -- manual invocation only.

This script is never imported by a test and never called by anything that
runs unattended. The whole point of a golden file is that it changes only
when a human looked at the diff and decided the new behaviour is correct;
wiring this into CI or a test would defeat that on the first commit that
introduced a regression, since the "check" would just rewrite itself to
match. (CI runs the golden-corpus *tests* on every push -- see
.github/workflows/ci.yml -- but never this script; regeneration stays a
human decision made by hand on a developer's machine.)

Usage:
    py tests/update_golden.py --tier medium
    py tests/update_golden.py --all
    py tests/update_golden.py --all --yes    # skip the confirmation prompt
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import golden


def _diff(tier: str, old_text: str, new_text: str) -> str | None:
    if old_text == new_text:
        return None
    return "\n".join(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=f"{tier}.json (current)",
            tofile=f"{tier}.json (new)",
            lineterm="",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tier", choices=golden.TIERS, action="append", help="tier to update (repeatable); default: all")
    parser.add_argument("--all", action="store_true", help="update every tier")
    parser.add_argument("--yes", action="store_true", help="write without an interactive confirmation")
    args = parser.parse_args()

    tiers = args.tier if args.tier else list(golden.TIERS)

    changed: list[tuple[str, Path, str]] = []
    for tier in tiers:
        new_text = golden.dumps(golden.build_golden(tier))
        path = golden.golden_path(tier)
        old_text = path.read_text(encoding="utf-8") if path.exists() else ""
        diff = _diff(tier, old_text, new_text)
        if diff is None:
            print(f"{tier}: unchanged")
            continue
        print(f"{tier}: CHANGED")
        print(diff)
        changed.append((tier, path, new_text))

    if not changed:
        print("\nnothing to update")
        return 0

    if not args.yes:
        answer = input(f"\nWrite {len(changed)} golden file(s) shown above? [y/N] ").strip().lower()
        if answer != "y":
            print("aborted -- no file written")
            return 1

    for tier, path, new_text in changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text, encoding="utf-8")
        print(f"{tier}: wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
