"""FormsLang command line.

    formslang assess <dir|file>...   -> convert, analyze and write the report
    formslang inspect <file.fmb>     -> detail of a single module, in the terminal
    formslang doc <file.fmb>         -> HTML technical documentation of a module
    formslang preview <file.fmb>     -> read-only Forms UI vs. APEX default mapping
    formslang diff <a.fmb> <b.fmb>   -> structural diff between two versions of a module
    formslang catalog                -> catalog size and coverage
    formslang convert <file.fmb>     -> AI proposals for every code body, headless
    formslang workbench <file.fmb>   -> the review UI, in the browser
    formslang export <session.db>    -> APEXlang 26.1 project + import ZIP from approved work
    formslang apex validate <zip>    -> check the ZIP against a workspace through SQLcl
    formslang apex import <zip>      -> import it, through SQLcl
    formslang ai                     -> which provider is configured, and does it answer
    formslang auth ...               -> multi-user mode: the first Owner, break-glass recovery

``export`` and ``apex`` are the CI pair (docs/ci-cd.md): a pipeline rebuilds
the application from a committed session, validates it against a real APEX
and imports it -- with the same bytes the workbench would have produced,
and with the database password read from the environment, the credential
store or a prompt, never from the command line.

Assessment runs in parallel because each module is an independent Java
process: the bottleneck is process I/O, not Python CPU.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import getpass
import json
import os
import sys
from pathlib import Path

from . import __version__, apeximport, authstore, config, formdiff, formdoc, formui, rules
from .ai import PROVIDERS, check_provider, provider_from_env
from .apexlang import export_apexlang, last_export_config
from .assess import (
    HOURS_PER_POINT_DEFAULT,
    TIERS,
    PortfolioAssessment,
    assess_module,
)
from .convert import build_tasks, propose_many
from .model import FormModule
from .oracle import (
    OracleToolchainError,
    Toolchain,
    convert_module,
    detect_toolchain,
    expected_xml_name,
)
from .parser import parse_xml
from .report import write_reports
from .secrets import SecureStorageUnavailable, get_secret
from .store import Store
from .workbench import Workbench, serve

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
            except Exception as e:  # noqa: BLE001 -- one bad module must not kill the batch
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


def _load_module(path: Path, out_dir: Path, oracle_home: str | None) -> FormModule:
    """Parse a module, converting it through Oracle first if needed."""
    if path.suffix.lower() == ".xml":
        return parse_xml(path)
    tc = detect_toolchain(oracle_home)
    xml, log = convert_module(path, out_dir / "xml", tc, overwrite=False)
    return parse_xml(xml, convert_log=log)


def _work_dir(args: argparse.Namespace) -> Path:
    """Where session and export files belong.

    An explicit --out always wins. Otherwise a resumed session keeps its own
    folder, so approved SQL lands beside the session it came from instead of
    in the caller's current directory.
    """
    if args.out:
        return Path(args.out)
    target = Path(args.path)
    if target.suffix.lower() == ".db":
        return target.resolve().parent
    return Path("formslang-out")


def _open_session(args: argparse.Namespace) -> tuple[Store, int]:
    """Open (or create) the session for the given module. Returns (store, new)."""
    target = Path(args.path)
    out_dir = _work_dir(args)

    if target.suffix.lower() == ".db":
        store = Store(target)
        if not store.session():
            store.init_session(target.stem, str(target))
        return store, 0

    if target.is_dir():
        # Started on a folder: open with nothing loaded and let the reviewer
        # pick the module in the browser.
        out_dir.mkdir(parents=True, exist_ok=True)
        return Store(out_dir / "_workbench.session.db"), 0

    mod = _load_module(target, out_dir, args.oracle_home)
    store = Store(out_dir / f"{mod.name}.session.db")
    store.init_session(mod.name, str(target))
    added = store.add_tasks(build_tasks(mod))
    return store, added


def cmd_doc(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    try:
        fm = _load_module(Path(args.path), out_dir, args.oracle_home)
    except OracleToolchainError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    path = formdoc.write_report(fm, out_dir / "doc")
    print(f"{fm.name}: {len(fm.blocks)} blocks, {len(fm.all_items)} items, "
          f"{len(fm.all_triggers)} triggers, {len(fm.program_units)} program units")
    print(f"HTML : {path}")
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    try:
        fm = _load_module(Path(args.path), out_dir, args.oracle_home)
    except OracleToolchainError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    path = formui.write_report(fm, out_dir / "preview")
    print(f"{fm.name}: {len(fm.canvases)} canvases, {len(fm.all_items)} items")
    print(f"HTML : {path}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    try:
        a = _load_module(Path(args.path_a), out_dir, args.oracle_home)
        b = _load_module(Path(args.path_b), out_dir, args.oracle_home)
    except OracleToolchainError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    diff = formdiff.compare_modules(a, b)
    path = formdiff.write_report(diff, out_dir / "diff")

    print(f"{diff.name_a} -> {diff.name_b}")
    sections = [
        ("Blocks", diff.blocks),
        ("Form triggers", diff.triggers),
        ("Program units", diff.program_units),
        ("LOVs", diff.lovs),
        ("Record groups", diff.record_groups),
        ("Relations", diff.relations),
    ]
    for label, c in sections:
        if c.added or c.removed or c.modified:
            print(f"  {label:<14} +{len(c.added)}  -{len(c.removed)}  ~{len(c.modified)}  ={c.unchanged}")
    if not diff.has_changes:
        print("  no structural changes")
    print(f"HTML : {path}")
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    """Headless conversion: propose for everything still unconverted."""
    try:
        store, added = _open_session(args)
    except OracleToolchainError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    provider = provider_from_env(args.provider)
    if args.model:
        provider.model = args.model

    pending = store.pending_tasks()
    if args.limit:
        pending = pending[: args.limit]

    print(f"Session     : {store.path}")
    print(f"Provider    : {provider.describe()}")
    print(f"Tasks       : {store.stats()['tasks']} ({added} new)")
    print(f"To convert  : {len(pending)}\n")
    if not pending:
        print("Nothing to convert. Open the workbench to review.")
        store.close()
        return 0

    def progress(i: int, total: int, task, proposal) -> None:
        mark = "ok  " if proposal.ok else "FAIL"
        conf = f"{proposal.confidence:.2f}" if proposal.ok else "----"
        print(f"[{i:>4}/{total}] {mark} {conf}  {task.title}")

    results = propose_many(pending, provider, on_progress=progress)
    for task_id, proposal in results.items():
        store.save_proposal(task_id, proposal)

    failed = sum(1 for p in results.values() if not p.ok)
    low = sum(1 for p in results.values() if p.ok and p.confidence < 0.5)
    print("\n" + "=" * 64)
    print(f"Converted   : {len(results) - failed}   Failed: {failed}")
    print(f"Low confidence (<0.50): {low} -- these need a human first")
    print("=" * 64)
    print(f"Review with : formslang workbench {store.path}")
    store.close()
    return 0


def cmd_workbench(args: argparse.Namespace) -> int:
    """Open the review UI for a module or an existing session."""
    try:
        store, added = _open_session(args)
    except OracleToolchainError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    provider = provider_from_env(args.provider)
    if args.model:
        provider.model = args.model

    target = Path(args.path)
    work = _work_dir(args)
    stats = store.stats()
    print(f"Module      : {store.session().get('title', '') or '(pick one in the browser)'}")
    print(f"Tasks       : {stats['tasks']} ({added} new, {stats['unproposed']} unconverted)")
    auth_store = None
    auth_data_dir = None
    if authstore.auth_enabled():
        auth_store = authstore.AuthStore(authstore.default_db_path())
        auth_data_dir = config.data_dir()
    wb = Workbench(
        store,
        provider,
        work / "export",
        out_dir=work,
        browse_root=target if target.is_dir() else target.parent,
        oracle_home=args.oracle_home,
        auth_store=auth_store,
        auth_data_dir=auth_data_dir,
    )
    try:
        serve(wb, host=args.host, port=args.port, open_browser=not args.no_browser)
    finally:
        wb.store.close()  # open_module may have swapped the store since
        if wb.auth_store is not None:
            wb.auth_store.close()
    return 0


def _session_module(store: Store, out_dir: Path, oracle_home: str | None) -> FormModule:
    """The module a session was built from, without reconverting it when the
    Forms2XML output is still cached beside the session."""
    source = Path(store.session().get("source_path") or "")
    if not source.name or source.suffix.lower() == ".db":
        raise ValueError(
            "this session has no Forms module yet: open one in the workbench, "
            "or pass the .fmb/.xml itself"
        )
    if source.suffix.lower() == ".xml":
        return parse_xml(source)
    cached = out_dir / "xml" / expected_xml_name(source)
    if cached.is_file():
        return parse_xml(cached)
    return _load_module(source, out_dir, oracle_home)


def _export_config(args: argparse.Namespace, store: Store) -> dict:
    """Deployment choices: what the last export used, then what the flags say."""
    raw = last_export_config(store)
    for key in ("app_id", "name", "alias", "workspace", "schema", "page"):
        value = getattr(args, key)
        if value not in (None, ""):
            raw[key] = value
    return raw


def cmd_export(args: argparse.Namespace) -> int:
    """Build the APEXlang project and import ZIP from a session's approved work.

    Headless twin of the workbench's Export button: same exporter, same
    choices (remembered on the session, overridable per flag), same bytes.
    """
    try:
        store, _ = _open_session(args)
    except OracleToolchainError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    work = _work_dir(args)
    try:
        module = _session_module(store, work, args.oracle_home)
        result = export_apexlang(store, module, work / "export", _export_config(args, store))
    except (OracleToolchainError, ValueError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    finally:
        store.close()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0
    print(f"Session  : {store.path}")
    print(f"Module   : {module.name}")
    print(f"Project  : {result.project}")
    print(f"ZIP      : {result.zip_path}")
    print(f"Review   : {result.manifest_path.parent}")
    print(f"Approved : {result.approved} component(s)")
    print(f"Next     : formslang apex validate \"{result.zip_path}\"")
    return 0


def _apex_password(username: str, connect_string: str) -> str:
    """The database password, from the places a password is allowed to be.

    In order: the environment (CI), the OS credential store the workbench's
    *Remember this connection* saved to, then a hidden prompt when a person
    is at the terminal. Never a command-line argument -- see apeximport.py.
    """
    from_env = os.environ.get(apeximport.ENV_APEX_PASSWORD, "")
    if from_env:
        return from_env
    try:
        saved = get_secret(apeximport.SERVICE, apeximport.account_key(username, connect_string))
    except SecureStorageUnavailable:
        saved = ""
    if saved:
        return saved
    if sys.stdin.isatty():
        return getpass.getpass(f"Password for {username}@{connect_string}: ")
    return ""


def _cmd_apex(args: argparse.Namespace, validate_only: bool) -> int:
    """``apex validate`` / ``apex import`` of one exported ZIP through SQLcl.

    Exit 0 when SQLcl succeeded, 1 when it failed -- including the case
    where SQLcl exits 0 but prints ``APEXlang Compile Errors`` and imports
    nothing -- and 2 when the command could not be run at all.
    """
    zip_path = Path(args.zip)
    connect_string, username = apeximport.connection_defaults()
    connect_string = args.connect or connect_string
    username = args.user or username
    if not connect_string or not username:
        print(
            "ERROR: a connection string and a username are required: --connect/--user, "
            f"{apeximport.ENV_APEX_CONNECT}/{apeximport.ENV_APEX_USER}, or the workbench Settings",
            file=sys.stderr,
        )
        return 2
    password = _apex_password(username, connect_string)
    if not password:
        print(
            f"ERROR: no password for {username}@{connect_string}: set "
            f"{apeximport.ENV_APEX_PASSWORD}, save the connection from the workbench, "
            "or run from a terminal to be prompted",
            file=sys.stderr,
        )
        return 2

    try:
        result = apeximport.run_import(
            zip_path,
            connect_string=connect_string,
            username=username,
            password=password,
            validate_only=validate_only,
            sqlcl=args.sqlcl,
            timeout=args.timeout,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    verb = "validate" if validate_only else "import"
    if args.json:
        print(
            json.dumps(
                {
                    "command": verb,
                    "zip": str(zip_path),
                    "target": f"{username}@{connect_string}",
                    "ok": result.ok,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
                indent=2,
            )
        )
        return 0 if result.ok else 1

    print(f"{verb.capitalize():<9}: {zip_path.name}")
    print(f"Target   : {username}@{connect_string}")
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output)
    if result.ok:
        status = "OK"
    elif result.exit_code == 0:
        status = "FAILED (SQLcl reported errors; nothing was imported)"
    else:
        status = f"FAILED (exit {result.exit_code})"
    print(f"Result   : {status}")
    return 0 if result.ok else 1


def cmd_apex_validate(args: argparse.Namespace) -> int:
    return _cmd_apex(args, validate_only=True)


def cmd_apex_import(args: argparse.Namespace) -> int:
    return _cmd_apex(args, validate_only=False)


def cmd_ai(args: argparse.Namespace) -> int:
    """Show the configured provider and, on request, prove it answers."""
    provider = provider_from_env(args.provider)
    print(f"Provider    : {provider.describe()}")
    print(f"Endpoint    : {provider.base_url or '(default)'}")
    print(f"Key         : {'set' if provider.api_key else 'NOT SET'}")
    print(f"Available   : {', '.join(sorted(PROVIDERS))}")
    if not args.check:
        print("\nAdd --check to send one short request and confirm it answers.")
        return 0
    ok, detail = check_provider(provider)
    print(f"\nCheck       : {'OK' if ok else 'FAILED'} -- {detail}")
    return 0 if ok else 1


def cmd_auth_bootstrap_owner(args: argparse.Namespace) -> int:
    """Create the first Owner of an organization. Host CLI only -- never an HTTP route.

    The password is set interactively, never taken as a command-line
    argument: a ``--password`` flag would end up in shell history and
    process listings, which the design doc treats as a leak on the same
    footing as one in a log line.
    """
    email = args.email.strip()
    if not email:
        print("ERROR: email must not be empty", file=sys.stderr)
        return 2
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("ERROR: passwords do not match", file=sys.stderr)
        return 2

    store = authstore.AuthStore(authstore.default_db_path())
    try:
        result = store.bootstrap_owner(
            email, password, org_slug=args.org_slug, org_name=args.org_name
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    finally:
        store.close()

    print(f"Owner created : {result['email']}")
    print(f"Organization  : {result['organization_slug']} ({result['organization_id']})")
    print(f"User id       : {result['user_id']}")
    return 0


def cmd_auth_reset_owner(args: argparse.Namespace) -> int:
    """Last-Owner recovery (design doc SS7.5): reset an Owner's password
    directly on the host. Host CLI only -- local host access *is* the
    authentication, the same trust boundary as bootstrap-owner.

    ``--clear-mfa`` is the accompanying break-glass for an Owner who also
    lost their authenticator: it removes the enrollment outright, so use it
    only when the device is truly gone, never as a routine reset step.
    """
    email = args.email.strip()
    if not email:
        print("ERROR: email must not be empty", file=sys.stderr)
        return 2
    password = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm new password: ")
    if password != confirm:
        print("ERROR: passwords do not match", file=sys.stderr)
        return 2

    store = authstore.AuthStore(authstore.default_db_path())
    try:
        try:
            result = store.reset_owner_password_cli(email, password)
        except (ValueError, PermissionError, authstore.UserNotFound) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2

        print(f"Owner password reset : {result['email']}")
        print(f"Sessions revoked      : {result['sessions_revoked']}")

        if args.clear_mfa:
            store.mfa_disable_cli(result["user_id"])
            print("MFA cleared           : this account must enroll again at next login")
    finally:
        store.close()
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

    d = sub.add_parser("doc", help="HTML technical documentation for one module")
    d.add_argument("path", help=".fmb/.mmb/.xml file")
    d.add_argument("-o", "--out", default="formslang-out", help="output directory")
    d.add_argument("--oracle-home", default=None, help="explicit ORACLE_HOME")
    d.set_defaults(func=cmd_doc)

    pv = sub.add_parser("preview", help="read-only Forms UI vs. APEX default mapping")
    pv.add_argument("path", help=".fmb/.mmb/.xml file")
    pv.add_argument("-o", "--out", default="formslang-out", help="output directory")
    pv.add_argument("--oracle-home", default=None, help="explicit ORACLE_HOME")
    pv.set_defaults(func=cmd_preview)

    df = sub.add_parser("diff", help="structural diff between two versions of a module")
    df.add_argument("path_a", help=".fmb/.mmb/.xml file (before)")
    df.add_argument("path_b", help=".fmb/.mmb/.xml file (after)")
    df.add_argument("-o", "--out", default="formslang-out", help="output directory")
    df.add_argument("--oracle-home", default=None, help="explicit ORACLE_HOME")
    df.set_defaults(func=cmd_diff)

    c = sub.add_parser("catalog", help="Forms->APEX catalog coverage")
    c.set_defaults(func=cmd_catalog)

    def add_session_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("path", help=".fmb/.xml module, or an existing .session.db")
        # No default: resuming a session should write next to that session file,
        # not into whatever directory the reviewer happened to be standing in.
        sp.add_argument("-o", "--out", default=None, help="working directory")
        sp.add_argument("--oracle-home", default=None, help="explicit ORACLE_HOME")
        sp.add_argument("--provider", default="", help="override FORMSLANG_AI_PROVIDER")
        sp.add_argument("--model", default="", help="override the provider's model")

    cv = sub.add_parser("convert", help="AI proposals for every code body (headless)")
    add_session_args(cv)
    cv.add_argument("--limit", type=int, default=0, help="convert only the first N")
    cv.set_defaults(func=cmd_convert)

    w = sub.add_parser("workbench", help="review proposals in the browser")
    add_session_args(w)
    w.add_argument("--port", type=int, default=8765, help="port to listen on")
    w.add_argument("--host", default="127.0.0.1", help="bind address (loopback only)")
    w.add_argument("--no-browser", action="store_true", help="do not open a browser")
    w.set_defaults(func=cmd_workbench)

    ex = sub.add_parser(
        "export",
        help="APEXlang 26.1 project + import ZIP from a session's approved work",
        description=(
            "Builds exactly what the workbench's Export button builds, from a "
            ".session.db (or a module, for a session that is still to be reviewed). "
            "Choices default to the session's previous export, so re-running with "
            "no flags reproduces it byte for byte."
        ),
    )
    ex.add_argument("path", help="an existing .session.db, or a .fmb/.xml module")
    ex.add_argument("-o", "--out", default=None, help="working directory (default: beside the session)")
    ex.add_argument("--oracle-home", default=None, help="explicit ORACLE_HOME")
    ex.add_argument("--app-id", dest="app_id", type=int, default=None, help="APEX application id (default: last export, else 100)")
    ex.add_argument("--name", default="", help="application name (default: last export, else the module title)")
    ex.add_argument("--alias", default="", help="application alias (default: last export, else from the module name)")
    ex.add_argument("--workspace", default="", help="workspace, or leave it to be resolved at import")
    ex.add_argument("--schema", default="", help="parsing schema, or leave it to be resolved at import")
    ex.add_argument("--page", type=int, default=None, help="page number (default: last export, else 1)")
    ex.add_argument("--json", action="store_true", help="print the result as JSON")
    ex.set_defaults(func=cmd_export)

    ap = sub.add_parser(
        "apex",
        help="validate or import an exported ZIP through SQLcl",
        description=(
            "Drives your own SQLcl against one <alias>.apex.zip. The password is never "
            f"an argument: {apeximport.ENV_APEX_PASSWORD}, the connection saved from the "
            "workbench, or a hidden prompt."
        ),
    )
    ap_sub = ap.add_subparsers(dest="apex_cmd", required=True)

    def add_apex_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("zip", help="an <alias>.apex.zip built by export")
        sp.add_argument("--connect", default="", help=f"host:port/service (default: {apeximport.ENV_APEX_CONNECT}, then Settings)")
        sp.add_argument("--user", default="", help=f"database user (default: {apeximport.ENV_APEX_USER}, then Settings)")
        sp.add_argument("--sqlcl", default="", help=f"SQLcl binary (default: {apeximport.ENV_SQLCL_PATH}, Settings, then PATH)")
        sp.add_argument("--timeout", type=int, default=apeximport.TIMEOUT_SECONDS, help="seconds to allow SQLcl (default: %(default)s)")
        sp.add_argument("--json", action="store_true", help="print the result as JSON")

    av = ap_sub.add_parser("validate", help="check the ZIP against the target workspace; changes nothing")
    add_apex_args(av)
    av.set_defaults(func=cmd_apex_validate)

    ai_ = ap_sub.add_parser("import", help="import the ZIP into the target workspace")
    add_apex_args(ai_)
    ai_.set_defaults(func=cmd_apex_import)

    ai = sub.add_parser("ai", help="show and test the AI provider configuration")
    ai.add_argument("--provider", default="", help="override FORMSLANG_AI_PROVIDER")
    ai.add_argument("--check", action="store_true", help="send one short request")
    ai.set_defaults(func=cmd_ai)

    auth = sub.add_parser("auth", help="control-plane identity: organizations, users, sessions")
    auth_sub = auth.add_subparsers(dest="auth_cmd", required=True)

    bo = auth_sub.add_parser(
        "bootstrap-owner", help="create the first Owner (host CLI only, never HTTP)"
    )
    bo.add_argument("email", help="the new Owner's email address")
    bo.add_argument("--org-slug", default="local", help="organization slug (default: local)")
    bo.add_argument("--org-name", default="Local", help="organization display name (default: Local)")
    bo.set_defaults(func=cmd_auth_bootstrap_owner)

    ro = auth_sub.add_parser(
        "reset-owner",
        help="last-Owner password recovery (host CLI only, never HTTP)",
    )
    ro.add_argument("email", help="the Owner's email address")
    ro.add_argument(
        "--clear-mfa", action="store_true",
        help="also remove this Owner's MFA enrollment (break-glass -- use only if the device is lost)",
    )
    ro.set_defaults(func=cmd_auth_reset_owner)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
