"""FormsLang command line.

    formslang assess <dir|file>...   -> convert, analyze and write the report
    formslang inspect <file.fmb>     -> detail of a single module, in the terminal
    formslang catalog                -> catalog size and coverage

Conversion runs in parallel because each module is an independent Java
process: the bottleneck is process I/O, not Python CPU.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import sys
from pathlib import Path

from . import __version__, rules
from .assess import (
    HOURS_PER_POINT_DEFAULT,
    TIERS,
    PortfolioAssessment,
    assess_module,
)
from .oracle import (
    OracleToolchainError,
    Toolchain,
    convert_module,
    detect_toolchain,
    expected_xml_name,
)
from .parser import parse_xml
from .report import write_reports

MODULE_EXT = {".fmb", ".mmb"}
SCAN_EXT = MODULE_EXT | {".xml"}


def _collect(paths: list[str], recursive: bool) -> list[Path]:
    """Expand directories into Forms modules, without duplicates.

    Already-converted XML is accepted too, so a portfolio can be assessed on
    a machine with no Oracle install. When a directory holds both a module
    and the XML produced from it, the module wins and the XML is skipped --
    otherwise the same form would be counted twice.
    """
    found: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            found.extend(f for f in it if f.suffix.lower() in SCAN_EXT)
        elif p.suffix.lower() in SCAN_EXT:
            found.append(p)

    found = sorted(dict.fromkeys(found))
    modules = [f for f in found if f.suffix.lower() in MODULE_EXT]
    already = {expected_xml_name(m).lower() for m in modules}
    return modules + [
        f
        for f in found
        if f.suffix.lower() == ".xml" and f.name.lower() not in already
    ]


def _prepare(
    module: Path, xml_dir: Path, tc: Toolchain | None, overwrite: bool
) -> tuple[Path, Path, str]:
    """Return (original_module, xml, conversion_log)."""
    if module.suffix.lower() == ".xml":
        return module, module, ""
    assert tc is not None
    xml, log = convert_module(module, xml_dir, tc, overwrite=overwrite)
    return module, xml, log


def cmd_assess(args: argparse.Namespace) -> int:
    modules = _collect(args.paths, recursive=not args.no_recursive)
    if args.limit:
        modules = modules[: args.limit]
    if not modules:
        print("No .fmb/.mmb/.xml module found in the given paths.")
        return 1

    out_dir = Path(args.out)
    xml_dir = out_dir / "xml"
    needs_oracle = any(m.suffix.lower() != ".xml" for m in modules)

    tc: Toolchain | None = None
    if needs_oracle:
        try:
            tc = detect_toolchain(args.oracle_home)
        except OracleToolchainError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        print(f"ORACLE_HOME : {tc.oracle_home}")

    print(f"Modules     : {len(modules)}")
    print(f"Output      : {out_dir}")
    print(f"Parallelism : {args.jobs}\n")

    pf = PortfolioAssessment(hours_per_point=args.hours_per_point)
    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(_prepare, m, xml_dir, tc, args.overwrite): m for m in modules
        }
        for fut in cf.as_completed(futures):
            source = futures[fut]
            done += 1
            try:
                _mod, xml, log = fut.result()
                fm = parse_xml(xml, convert_log=log)
                fm.source_path = str(source)
                pf.modules.append(assess_module(fm))
                mark = "ok "
            except Exception as e:  # one bad module must not kill the batch
                pf.failures.append((source.name, f"{type(e).__name__}: {e}"))
                mark = "FAIL"
            if done % 10 == 0 or done == len(modules) or mark == "FAIL":
                print(f"[{done:>4}/{len(modules)}] {mark:5} {source.name}")

    # Second pass: charge copy-paste once for the whole portfolio.
    pf.finalize()
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    html_path, json_path = write_reports(
        pf, out_dir, title=args.title, generated_at=generated_at
    )

    tv = pf.aggregate_trigger_verdicts()
    bv = pf.aggregate_builtin_verdicts()
    tiers = pf.by_tier()
    print("\n" + "=" * 64)
    print(f"Analyzed        : {len(pf.modules)}   Failures: {len(pf.failures)}")
    print(f"Blocks/Items    : {sum(m.blocks for m in pf.modules):,} / "
          f"{sum(m.items for m in pf.modules):,}")
    print(f"Triggers        : {sum(m.triggers for m in pf.modules):,}")
    print(f"Program units   : {sum(m.program_units for m in pf.modules):,}")
    print(f"PL/SQL lines    : {sum(m.plsql_lines for m in pf.modules):,}")
    print(f"Shared blocks   : {len(pf.shared_blocks):,} distinct, "
          f"{pf.shared_instances:,} copies across modules")
    print(f"Effort points   : {pf.total_points:,.0f} "
          f"(raw {pf.raw_points:,.0f}, -{pf.duplication_savings:,.0f} deduplicated)")
    print(f"Automation-ok   : {pf.automatable_pct():.1f}%")
    print("Tiers           : " + "  ".join(
        f"{k}={tiers.get(k, 0)}" for _l, _h, k, _n in TIERS))
    print("Triggers        : " + "  ".join(
        f"{v}={tv.get(v, 0)}" for v in rules.VERDICT_ORDER if tv.get(v)))
    print("Built-ins       : " + "  ".join(
        f"{v}={bv.get(v, 0)}" for v in rules.VERDICT_ORDER if bv.get(v)))
    print("=" * 64)
    print(f"HTML : {html_path}")
    print(f"JSON : {json_path}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    target = Path(args.path)
    out_dir = Path(args.out)
    if target.suffix.lower() == ".xml":
        xml, log = target, ""
    else:
        try:
            tc = detect_toolchain(args.oracle_home)
        except OracleToolchainError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        xml, log = convert_module(target, out_dir / "xml", tc, overwrite=True)

    fm = parse_xml(xml, convert_log=log)
    a = assess_module(fm)

    print(f"\n{fm.name}  [{a.tier}]  {a.points:,.0f} points  "
          f"({a.automatable_pct:.0f}% automation-friendly)")
    print(f"  {a.tier_note}")
    print(f"\nStructure: {a.blocks} blocks ({a.database_blocks} database), "
          f"{a.items} items, {a.triggers} triggers, {a.program_units} program units")
    print(f"           {a.lovs} LOVs, {a.record_groups} record groups, "
          f"{a.relations} relations, {a.plsql_lines:,} PL/SQL lines")
    if a.attached_libraries:
        print(f"           libraries: {', '.join(a.attached_libraries)}")

    print("\nTriggers by verdict:")
    for v in rules.VERDICT_ORDER:
        if a.trigger_verdicts.get(v):
            print(f"   {v:<9} {a.trigger_verdicts[v]:>4}")

    if a.blockers:
        print("\nBlockers (built-ins with no APEX equivalent):")
        for name, reason, n in a.blockers[:15]:
            print(f"   {name:<28} x{n:<4} {reason}")

    if a.manual_triggers:
        print("\nTriggers that require a redesign:")
        for name, reason in a.manual_triggers[:15]:
            print(f"   {name:<28} {reason}")

    if a.code.builtins:
        print("\nMost used built-ins:")
        for name, n in a.code.builtins.most_common(12):
            v, apex_target = rules.classify_builtin(name)
            print(f"   {name:<28} x{n:<4} [{v}] {apex_target}")

    if a.warnings:
        print("\nWarnings:")
        for w in a.warnings:
            print(f"   - {w}")
    print()
    return 0


def cmd_catalog(_args: argparse.Namespace) -> int:
    c = rules.catalog_size()
    print(f"FormsLang {__version__} -- conversion catalog")
    for k, v in c.items():
        print(f"  {k:<18} {v}")
    print("\nVerdicts:")
    for v in rules.VERDICT_ORDER:
        n_b = sum(1 for x in rules.BUILTINS.values() if x[0] == v)
        n_t = sum(1 for x in rules.TRIGGERS.values() if x[0] == v)
        if n_b or n_t:
            print(f"  {v:<9} built-ins={n_b:<4} triggers={n_t}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="formslang",
        description="Oracle Forms analysis and conversion to Oracle APEX.",
    )
    p.add_argument("--version", action="version", version=f"FormsLang {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("assess", help="assess a portfolio of modules")
    a.add_argument("paths", nargs="+", help=".fmb/.mmb/.xml files or directories")
    a.add_argument("-o", "--out", default="formslang-out", help="output directory")
    a.add_argument("-j", "--jobs", type=int, default=6, help="parallel conversions")
    a.add_argument("--limit", type=int, default=0, help="analyze only the first N")
    a.add_argument("--no-recursive", action="store_true", help="do not walk subfolders")
    a.add_argument("--overwrite", action="store_true", help="reconvert existing XML")
    a.add_argument("--oracle-home", default=None, help="explicit ORACLE_HOME")
    a.add_argument("--title", default="Oracle Forms portfolio", help="report title")
    a.add_argument(
        "--hours-per-point",
        type=float,
        default=HOURS_PER_POINT_DEFAULT,
        help="point->hour calibration factor (an ASSUMPTION until measured)",
    )
    a.set_defaults(func=cmd_assess)

    i = sub.add_parser("inspect", help="detail of a single module")
    i.add_argument("path", help=".fmb/.mmb/.xml file")
    i.add_argument("-o", "--out", default="formslang-out", help="working directory")
    i.add_argument("--oracle-home", default=None, help="explicit ORACLE_HOME")
    i.set_defaults(func=cmd_inspect)

    c = sub.add_parser("catalog", help="Forms->APEX catalog coverage")
    c.set_defaults(func=cmd_catalog)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
