"""Local HTTP server behind the conversion workbench.

Standard library only, bound to the loopback interface, no authentication
and no remote access by design: the server holds the source code under
review and the only thing allowed to reach it is a browser on the same
machine.

The Host header is checked on every request, and every POST must carry the
right Content-Type. Together those close the two attacks a localhost server
is genuinely exposed to: DNS rebinding (a web page pointing a name it owns
at 127.0.0.1 to read the session) and cross-site request forgery (a plain
HTML form can smuggle JSON as text/plain without any preflight; demanding
the real content type forces a CORS preflight this server never answers).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, urlsplit

from . import (
    authcrypto,
    authstore,
    authui,
    dashboard,
    depgraph,
    formdiff,
    formdoc,
    policy,
    projects,
    rbac,
    secrets,
    telemetry,
    testspec,
)
from . import behavior as behavior_model
from . import risk as risk_model
from .ai import (
    ENV_FOR,
    PROVIDERS,
    CliProvider,
    EchoProvider,
    OllamaProvider,
    Provider,
    build_provider,
    check_provider,
    provider_catalog,
    provider_from_env,
    setting,
)
from .analysis import analyze_task, summarize
from .apexlang import export_apexlang
from .config import (
    SecureStorageUnavailable,
    config_path,
    key_location,
    load_config,
    migrate_plaintext_key,
    save_config,
)
from .convert import Proposal, build_tasks, propose
from .oracle import OracleToolchainError, convert_module, detect_toolchain, expected_xml_name
from .parser import parse_xml
from .policy import PolicyViolation
from .store import JOB_CANCELLED, JOB_COMPLETED, JOB_CRASHED, STATES, Store
from .ui import INDEX_HTML

MAX_BODY = 4 * 1024 * 1024
MAX_UPLOAD = 256 * 1024 * 1024
MODULE_SUFFIXES = (".fmb", ".mmb", ".xml")

# The only things /api/terminal will ever run. The browser sends a provider
# id and nothing else; the command line is decided here, on the server, so
# no request can ever smuggle an argument into a shell.
TERMINAL_COMMANDS = {
    "claude_cli": "claude",
    "codex_cli": "codex",
}


class Workbench:
    """Session state shared by every request handler."""

    def __init__(
        self,
        store: Store,
        provider: Provider,
        export_dir: Path,
        out_dir: Path | None = None,
        browse_root: Path | None = None,
        oracle_home: str | None = None,
        auth_store: authstore.AuthStore | None = None,
        auth_data_dir: Path | None = None,
    ):
        self.store = store
        self.provider = provider
        self.export_dir = Path(export_dir)
        self.out_dir = Path(out_dir or self.export_dir.parent)
        self.browse_root = Path(browse_root or Path.cwd()).resolve()
        self.oracle_home = oracle_home
        # None when auth is off -- every request-handling method below
        # treats that as "the auth subsystem does not exist", never
        # "logged out", so local single-user mode stays byte-for-byte
        # what it was before this existed.
        self.auth_store = auth_store
        self.auth_data_dir = Path(auth_data_dir) if auth_data_dir is not None else None
        self._lock = threading.Lock()
        # An upgrade must not leave a key sitting in plaintext: move it
        # into the OS credential store the first time we come up.
        migrate_plaintext_key()
        # Same shape a live run reports, so a reader never has to guess
        # whether a field is missing or empty.
        self.job = {
            "running": False, "done": 0, "failed": 0, "total": 0,
            "error": "", "last_error": "", "run_id": 0,
            "current": "", "current_id": "", "queue": [], "provider": "",
        }
        self.module = self._module_from_session()
        # A session file written before the risk engine existed, or under an
        # older rule set, still has to open with the analysis on screen.
        self.refresh_analysis()
        self.graph = self.refresh_graph()
        self.refresh_tests()

    # -- analysis ---------------------------------------------------------

    def refresh_analysis(self, force: bool = False) -> dict:
        """Compute the deterministic analysis for whatever is missing or stale.

        Cheap and offline -- no provider is contacted here. Recomputing only
        what the current rules have not already produced keeps opening a
        large session fast, while ``force`` rebuilds everything after the
        rules themselves change.
        """
        ids = self.store.task_ids() if force else self.store.stale_task_ids()
        with telemetry.stage(self.store.record_stage, "analysis", item_count=len(ids)):
            for task_id in ids:
                task = self.store.get_task(task_id)
                if task is None:
                    continue
                self.store.save_analysis(analyze_task(task))
        return self.store.analysis_coverage()

    # -- dependencies -----------------------------------------------------

    def refresh_graph(self):
        """Rebuild the dependency graph for the module on screen.

        Structure comes from the parsed module, so this can only run while
        the XML is still reachable. When it is not -- a session opened from
        its .db alone -- the graph saved with the session is loaded instead,
        and if there is none the explorer says so rather than showing an
        empty form that looks like a form with no dependencies.
        """
        module_name = self.store.session().get("title", "")
        if self.module is None:
            return self.store.graph(module_name)
        task_ids, risks = {}, {}
        for view in self.store.all_views():
            t = view.task
            key = f"{t['kind']}|{t['owner']}|{t['name']}".upper()
            task_ids[key] = t["id"]
            level = ((view.analysis or {}).get("risk") or {}).get("level", "")
            if level:
                risks[t["id"]] = level
        with telemetry.stage(self.store.record_stage, "depgraph"):
            graph = depgraph.build(self.module, task_ids=task_ids, risks=risks)
            self.store.save_graph(self.module.name, graph)
        return graph

    def deps_state(self, task_id: str = "", node: str = "", depth: int = 2) -> dict:
        """One node's neighbourhood, or the module rollup when none is named."""
        if self.graph is None:
            return {"available": False, "reason": "no dependency graph for this session"}
        out = {"available": True, "summary": self.graph.summary()}
        if task_id:
            out["explore"] = self.graph.for_task(task_id, depth)
        elif node:
            out["explore"] = self.graph.explore(node, depth)
        return out

    # -- test specifications ----------------------------------------------

    def refresh_tests(self, force: bool = False) -> dict:
        """Write the specification for whatever has none, or an outdated one.

        Deterministic and offline, like the analysis: the cases come from the
        original Forms behaviour, so nothing here waits on a provider or on a
        proposal existing. Reviewed cases survive -- see
        :meth:`formslang.store.Store.save_test_cases`.
        """
        items = testspec.items_of(self.module) if self.module is not None else None
        ids = self.store.task_ids() if force else self.store.stale_test_task_ids()
        with telemetry.stage(self.store.record_stage, "testspec", item_count=len(ids)):
            for task_id in ids:
                task = self.store.get_task(task_id)
                if task is None:
                    continue
                cases = testspec.generate(
                    task, analysis=self.store.get_analysis(task_id), items=items
                )
                self.store.save_test_cases(task_id, cases)
        return self.store.test_coverage()

    def tests_state(self, task_id: str = "") -> dict:
        """One unit's specification, or the whole session's rollup."""
        out = {
            "coverage": self.store.test_coverage(),
            "origins": testspec.ORIGIN_LABEL,
            "states": list(testspec.CASE_STATES),
            "run_states": list(testspec.RUN_STATES),
            # Without the module on disk, nothing could be asserted about
            # required values or lengths; say so rather than let a reviewer
            # read "needs confirmation" as a finding about their code.
            "item_metadata": self.module is not None,
        }
        if task_id:
            out["cases"] = self.store.test_cases(task_id)
        return out

    def decide_test_case(self, case_id: str, state: str, reviewer: str = "",
                         comment: str = "") -> dict:
        if state not in testspec.CASE_STATES:
            return {"ok": False, "error": "unknown state"}
        if not self.store.decide_test_case(case_id, state, reviewer, comment):
            return {"ok": False, "error": "unknown test case"}
        return {"ok": True, "coverage": self.store.test_coverage()}

    def record_test_run(self, case_id: str, run_state: str, run_by: str = "",
                        run_notes: str = "") -> dict:
        if run_state not in testspec.RUN_STATES:
            return {"ok": False, "error": "unknown run state"}
        if not self.store.record_test_run(case_id, run_state, run_by, run_notes):
            return {"ok": False, "error": "unknown test case"}
        return {"ok": True, "coverage": self.store.test_coverage()}

    def dashboard_state(self) -> dict:
        """The project view. Recomputed per request: it is only arithmetic."""
        return dashboard.build(self.store, self.graph)

    def analysis_state(self) -> dict:
        """Portfolio-level rollup plus the published formula behind the score."""
        return {
            "coverage": self.store.analysis_coverage(),
            "summary": summarize(self.store.all_analyses()),
            "risk_model": risk_model.explain(),
        }

    # -- read ------------------------------------------------------------

    def state(self) -> dict:
        return {
            "session": self.store.session(),
            "stats": self.store.stats(),
            "provider": self.provider.describe(),
            "provider_id": self.provider.type_id,
            "model": self.provider.model,
            "browse_root": str(self.browse_root),
            "can_export_apex": self.module is not None,
            "tasks": [v.to_dict() for v in self.store.all_views()],
        }

    def _module_from_session(self):
        """Recover structure for an existing session without reconverting it."""
        source = Path(self.store.session().get("source_path") or "")
        if not source.name:
            return None
        try:
            if source.suffix.lower() == ".xml" and source.is_file():
                return parse_xml(source)
            cached = self.out_dir / "xml" / expected_xml_name(source)
            if cached.is_file():
                return parse_xml(cached)
        except (OSError, ValueError):
            return None
        return None

    # -- documentation / diff ----------------------------------------------

    def doc_html(self) -> str:
        """Technical documentation for the module currently on screen."""
        if self.module is None:
            raise ValueError("no module open")
        return formdoc.render_html(self.module)

    def _load_other_module(self, path: str):
        """Parse a second module for /api/diff, without touching the open session."""
        target = Path(path).expanduser().resolve()
        if not target.is_file():
            raise ValueError(f"not a file: {target}")
        if target.suffix.lower() not in MODULE_SUFFIXES:
            raise ValueError(f"not a Forms module: {target.name}")
        if target.suffix.lower() == ".xml":
            return parse_xml(target)
        toolchain = detect_toolchain(self.oracle_home)
        xml, log = convert_module(target, self.out_dir / "xml", toolchain, overwrite=False)
        return parse_xml(xml, convert_log=log)

    def diff_html(self, other_path: str) -> str:
        """Structural diff between the module on screen and another one."""
        if self.module is None:
            raise ValueError("no module open")
        other = self._load_other_module(other_path)
        diff = formdiff.compare_modules(self.module, other)
        return formdiff.render_html(diff)

    # -- choosing a module -----------------------------------------------

    def browse(self, where: str = "") -> dict:
        """List sub-folders and Forms modules so the UI can pick one.

        Only names are returned -- never file contents. Reaching a module's
        code takes an explicit ``open``.
        """
        target = Path(where).expanduser() if where else self.browse_root
        target = target.resolve()
        if not target.is_dir():
            raise ValueError(f"not a folder: {target}")

        dirs, modules = [], []
        try:
            entries = sorted(target.iterdir(), key=lambda p: p.name.lower())
        except PermissionError:
            raise ValueError(f"no permission to read {target}") from None
        for entry in entries:
            try:
                if entry.is_dir():
                    if not entry.name.startswith("."):
                        dirs.append({"name": entry.name, "path": str(entry)})
                elif entry.suffix.lower() in MODULE_SUFFIXES:
                    session = self.out_dir / f"{entry.stem.replace('_fmb', '')}.session.db"
                    modules.append({
                        "name": entry.name,
                        "path": str(entry),
                        "kb": round(entry.stat().st_size / 1024),
                        "has_session": session.exists(),
                    })
            except OSError:
                continue  # a file that vanished or that we cannot stat
        parent = target.parent
        return {
            "dir": str(target),
            "parent": str(parent) if parent != target else "",
            "dirs": dirs,
            "modules": modules,
        }

    def open_module(self, path: str) -> dict:
        """Parse a module and make its session the one on screen."""
        with self._lock:
            if self.job["running"]:
                raise ValueError("a conversion is running; wait for it to finish")

        target = Path(path).expanduser().resolve()
        if not target.is_file():
            raise ValueError(f"not a file: {target}")
        if target.suffix.lower() not in (*MODULE_SUFFIXES, ".db"):
            raise ValueError(f"not a Forms module: {target.name}")

        self.out_dir.mkdir(parents=True, exist_ok=True)
        if target.suffix.lower() == ".db":
            store = Store(target)
            added = 0
            module = None
        else:
            # A fresh store has no rows yet to time a stage against, so the
            # parse itself is measured with a throwaway recorder and folded
            # into the real store's stage_timing once it exists below.
            timings: list[tuple[str, float, int, bool, str]] = []
            with telemetry.stage(
                lambda *a: timings.append(a), "parse",
            ):
                if target.suffix.lower() == ".xml":
                    module = parse_xml(target)
                else:
                    # Oracle writes the XML next to the .fmb, so convert in
                    # our own directory and never touch the source tree.
                    toolchain = detect_toolchain(self.oracle_home)
                    xml, log = convert_module(
                        target, self.out_dir / "xml", toolchain, overwrite=False
                    )
                    module = parse_xml(xml, convert_log=log)
            store = Store(self.out_dir / f"{module.name}.session.db")
            for name, duration_ms, item_count, ok, error_kind in timings:
                store.record_stage(name, duration_ms, item_count, ok, error_kind)
            store.init_session(module.name, str(target))
            added = store.add_tasks(build_tasks(module))

        old = self.store
        self.store = store
        self.export_dir = self.out_dir / "export"
        if old is not store:
            old.close()
        self.browse_root = target.parent
        self.module = module if module is not None else self._module_from_session()
        coverage = self.refresh_analysis()
        self.graph = self.refresh_graph()
        return {
            "title": store.session().get("title", ""),
            "added": added,
            "stats": store.stats(),
            "analysis": coverage,
        }

    def upload_module(self, name: str, content: bytes) -> dict:
        """Accept a browser-selected module into our own staging directory."""
        clean = Path(name or "").name
        if not clean or clean != name or Path(clean).suffix.lower() not in MODULE_SUFFIXES:
            raise ValueError("choose an .fmb, .mmb or Forms2XML .xml file")
        if not content:
            raise ValueError("the selected module is empty")
        uploads = self.out_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        target = uploads / clean
        with target.open("wb") as handle:
            handle.write(content)
        return self.open_module(str(target))

    def export(self, config: dict | None = None) -> dict:
        """Export review artifacts plus an APEXlang 26.1 import ZIP."""
        module = self.module or self._module_from_session()
        if module is None:
            raise ValueError("open a Forms module before exporting APEX")
        self.module = module
        with telemetry.stage(self.store.record_stage, "export"):
            result = export_apexlang(self.store, module, self.export_dir, config)
        return result.to_dict()

    def list_exports(self) -> dict:
        """Every APEXlang ZIP built so far, newest first."""
        exports = []
        if self.export_dir.is_dir():
            for path in self.export_dir.glob("*.apex.zip"):
                info = path.stat()
                exports.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "size": info.st_size,
                        "mtime": info.st_mtime,
                    }
                )
        exports.sort(key=lambda e: e["mtime"], reverse=True)
        return {"exports": exports, "dir": str(self.export_dir)}

    def reveal_export(self, name: str) -> dict:
        """Open the OS file manager with one exported ZIP selected.

        Only a bare ``*.apex.zip`` name that exists inside the export
        directory is accepted -- ``Path(name).name`` throws away any
        directory part, so a traversal attempt turns into a miss.
        """
        clean = Path(str(name or "")).name
        target = self.export_dir / clean
        if not clean.endswith(".apex.zip") or not target.is_file():
            raise ValueError("no such export -- build one with Export APEX 26.1")
        spot = str(target.resolve())
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{spot}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", spot])
        else:
            subprocess.Popen(["xdg-open", str(target.resolve().parent)])
        return {"ok": True, "path": spot}

    # -- provider --------------------------------------------------------

    def set_provider(self, type_id: str, model: str = "") -> str:
        """Swap the model mid-session, without persisting anything."""
        with self._lock:
            if self.job["running"]:
                raise ValueError("a conversion is running; wait for it to finish")
            provider = provider_from_env(type_id)
            if model:
                provider.model = model
            self.provider = provider
        return self.provider.describe()

    @staticmethod
    def providers() -> list[dict]:
        return provider_catalog()

    # -- settings --------------------------------------------------------

    def settings_state(self) -> dict:
        """What the Settings sheet shows. The API key never leaves the server."""
        cfg = load_config()
        env_key = bool(os.environ.get(ENV_FOR["api_key"], "").strip())
        return {
            "provider": self.provider.type_id,
            "model": self.provider.model,
            "base_url": setting("base_url", cfg),
            "deployment": setting("deployment", cfg),
            "api_version": setting("api_version", cfg),
            "has_key": bool(setting("api_key", cfg)),
            "key_source": "env" if env_key else key_location(),
            "secure_storage": {
                "available": secrets.available(),
                "backend": secrets.backend_name(),
                "label": secrets.backend_label(),
                "message": secrets.UNAVAILABLE_MESSAGE,
            },
            "config_path": str(config_path()),
            "env_overrides": sorted(
                name for name, var in ENV_FOR.items()
                if os.environ.get(var, "").strip()
            ),
        }

    def save_settings(self, body: dict) -> dict:
        """Persist settings and rebuild the live provider.

        The API key is write-only: sending a value stores it, sending an
        empty string forgets it, not sending the field keeps whatever is
        stored. Nothing about the key comes back in the answer.

        The key goes to the OS credential store. When the platform has none,
        the save is refused rather than downgraded to plaintext.
        """
        with self._lock:
            if self.job["running"]:
                raise ValueError("a conversion is running; wait for it to finish")
            chosen = str(body.get("provider") or "").strip().lower()
            if chosen and chosen not in PROVIDERS:
                known = ", ".join(sorted(PROVIDERS))
                raise ValueError(f"unknown AI provider {chosen!r} (known: {known})")
            cfg = load_config()
            for name in ("provider", "model", "api_key", "base_url", "deployment", "api_version"):
                if name in body:
                    value = str(body.get(name) or "").strip()
                    if value:
                        cfg[name] = value
                    else:
                        cfg.pop(name, None)
            # Checked before the write, not after: a blocked combination must
            # never reach config.json, the same as the unknown-provider check
            # above -- a refused save has to leave nothing behind to explain.
            check_type = setting("provider", cfg) or "echo"
            check_cls = PROVIDERS.get(check_type)
            check_base = setting("base_url", cfg) or (check_cls.default_base_url if check_cls else "")
            try:
                policy.check(check_type, check_base)
            except PolicyViolation as e:
                raise ValueError(str(e)) from None
            try:
                save_config(cfg)
            except (SecureStorageUnavailable, ValueError) as e:
                raise ValueError(str(e)) from None
            self.provider = provider_from_env()
        return self.settings_state()

    def test_settings(self, body: dict) -> dict:
        """Round-trip the values in the form, saving nothing.

        Fields left blank fall back to what is already configured, so
        "does what I have actually answer?" is the same call as "does what
        I just typed answer?".
        """
        cfg = load_config()
        type_id = str(body.get("provider") or "").strip() or self.provider.type_id
        kwargs = {
            name: (str(body.get(name) or "").strip() or setting(name, cfg))
            for name in ("model", "base_url", "deployment", "api_version")
        }
        api_key = str(body.get("api_key") or "").strip() or setting("api_key", cfg)
        # A test is a health check, not a conversion: it must come back in
        # a couple of minutes even for a CLI that boots a whole agent.
        provider = build_provider(type_id, api_key=api_key, timeout=120.0, **kwargs)
        ok, message = check_provider(provider)
        return {"ok": ok, "message": message, "provider": provider.describe()}

    def open_terminal(self, provider_id: str) -> dict:
        """Open a native terminal running a whitelisted CLI, for signing in."""
        provider_id = str(provider_id or "").strip().lower()
        binary_name = TERMINAL_COMMANDS.get(provider_id)
        if binary_name is None:
            allowed = ", ".join(sorted(TERMINAL_COMMANDS))
            raise ValueError(f"no terminal setup for this provider (only: {allowed})")
        binary = shutil.which(binary_name)
        if binary is None:
            raise ValueError(f"{binary_name!r} is not installed. {PROVIDERS[provider_id].install_hint}")
        home = str(Path.home())  # never the source tree under review
        if os.name == "nt":
            subprocess.Popen(
                ["cmd.exe", "/k", binary],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=home,
            )
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Terminal", binary], cwd=home)
        else:
            for term in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm"):
                if shutil.which(term):
                    subprocess.Popen([term, "-e", binary], cwd=home)
                    break
            else:
                raise ValueError(f"no terminal emulator found; run `{binary_name}` yourself")
        return {"ok": True, "command": binary_name}

    # -- conversion ------------------------------------------------------

    def start_job(self, task_ids: list[str]) -> bool:
        """Run the conversions off the request thread. One job at a time."""
        # Refuse to start a run that can only fail: an HTTP provider with no
        # key would produce one 401 per task and nothing to review.
        needs_key = not isinstance(self.provider, (CliProvider, EchoProvider, OllamaProvider))
        if needs_key and not getattr(self.provider, "api_key", ""):
            raise ValueError(
                f"{self.provider.label} needs an API key. Open Settings (the gear), "
                "paste the key and press Test — or pick a CLI provider instead."
            )
        try:
            policy.check(self.provider.type_id, getattr(self.provider, "base_url", ""))
        except PolicyViolation as e:
            raise ValueError(str(e)) from None
        with self._lock:
            if self.job["running"]:
                return False
            run_id = self.store.start_job_run(len(task_ids))
            self.job = {
                "running": True, "done": 0, "failed": 0, "total": len(task_ids),
                "error": "", "last_error": "", "run_id": run_id,
                # What the UI needs to show a run honestly: the unit the model
                # is reading right now, and everything still waiting in line.
                "current": "", "current_id": "", "queue": list(task_ids),
                "provider": self.provider.label,
            }
        threading.Thread(target=self._run_job, args=(task_ids, run_id), daemon=True).start()
        return True

    def cancel_job(self) -> dict:
        """Ask the running job to stop after its current unit.

        Never aborts mid-task: the task in flight always finishes and its
        proposal is saved normally, so a cancel can never leave a half
        written proposal behind. Only the units still in the queue are
        skipped.
        """
        with self._lock:
            running = self.job["running"]
            run_id = self.job.get("run_id")
        if not running or not run_id:
            raise ValueError("no conversion is running")
        self.store.request_job_cancel(run_id)
        return {"ok": True}

    def _sync_job_run(self, run_id: int) -> None:
        with self._lock:
            done, failed = self.job["done"], self.job["failed"]
        self.store.update_job_run(run_id, done, failed)

    def _job_advance(self, task_id: str, counted: bool = True, error: str = "") -> None:
        """One unit is finished: count it and take it out of the queue."""
        with self._lock:
            if counted:
                self.job["done"] += 1
            if error:
                self.job["failed"] += 1
                self.job["last_error"] = error
            self.job["queue"] = [i for i in self.job.get("queue", []) if i != task_id]
            if self.job.get("current_id") == task_id:
                self.job["current_id"] = ""
                self.job["current"] = ""

    def _run_job(self, task_ids: list[str], run_id: int) -> None:
        seen: dict[str, str] = {}  # fingerprint -> task already converted here
        status = JOB_COMPLETED
        try:
            for task_id in task_ids:
                if self.store.is_job_cancel_requested(run_id):
                    # Every task before this point already has its proposal
                    # saved -- see save_proposal() below, called before the
                    # next loop iteration ever starts. Nothing in flight is
                    # torn; only the units still in the queue are skipped.
                    status = JOB_CANCELLED
                    break
                task = self.store.get_task(task_id)
                if task is None:
                    self._job_advance(task_id, counted=False)
                    continue
                with self._lock:
                    self.job["current_id"] = task_id
                    self.job["current"] = task.title
                twin = seen.get(task.fingerprint) if task.fingerprint else None
                if twin:
                    # Identical body already converted in this run: reuse the
                    # answer instead of paying for it again.
                    previous = self.store.latest_proposal(twin)
                    if previous and not previous["error"]:
                        reused = Proposal(
                            apex_target=previous["apex_target"],
                            code=previous["code"],
                            notes=[*previous["notes"], "Reused: identical body converted in this run."],
                            open_questions=previous["open_questions"],
                            confidence=previous["confidence"],
                            provider=previous["provider"],
                            model=previous["model"],
                            behavior=previous.get("behavior", ""),
                            behavior_reason=previous.get("behavior_reason", ""),
                        )
                        self.store.save_proposal(task_id, reused)
                        self._merge_behavior(task_id, reused)
                        self._job_advance(task_id)
                        self._sync_job_run(run_id)
                        continue
                # The model sees the same measured facts the reviewer sees.
                with telemetry.stage(self.store.record_stage, "ai_propose", item_count=1):
                    result = propose(task, self.provider, analysis=self.store.get_analysis(task_id))
                self.store.save_proposal(task_id, result)
                self._merge_behavior(task_id, result)
                if task.fingerprint and result.ok:
                    seen.setdefault(task.fingerprint, task_id)
                self._job_advance(task_id, error="" if result.ok else (result.error or "unknown error"))
                self._sync_job_run(run_id)
        except Exception as e:  # noqa: BLE001 - a job must not take the server down
            with self._lock:
                self.job["error"] = f"{type(e).__name__}: {e}"
            # Reusing 'crashed' for an in-process exception, not only a dead
            # process: both mean the same thing to a reviewer -- this run
            # did not finish normally, and the done/failed counts stop
            # short of total. reconcile_job_runs() only ever needs to catch
            # the case this except block could not: the process itself dying
            # before reaching here.
            status = JOB_CRASHED
        finally:
            with self._lock:
                self.job["running"] = False
                self.job["current"] = ""
                self.job["current_id"] = ""
                self.job["queue"] = []
            self._sync_job_run(run_id)
            self.store.finish_job_run(run_id, status)

    def _merge_behavior(self, task_id: str, result: Proposal) -> None:
        """Fold the model's reading of the behaviour into the stored analysis.

        :func:`formslang.behavior.merge_ai` only ever moves the answer
        towards caution, so a model that says PRESERVED about a unit the
        rules called CHANGED is ignored. Nothing is written unless the
        answer actually became more conservative.
        """
        if not result.ok or not result.behavior:
            return
        analysis = self.store.get_analysis(task_id)
        if analysis is None:
            return
        merged = behavior_model.merge_ai(
            analysis.behavior, result.behavior, result.behavior_reason
        )
        if merged is analysis.behavior:
            return
        analysis.behavior = merged
        self.store.save_analysis(analysis)

    def job_state(self) -> dict:
        with self._lock:
            state = dict(self.job)
        state["queue"] = list(state.get("queue", []))
        # The persisted half of the picture: what the last run looked like,
        # even after a restart wiped self.job back to its idle shape. A run
        # this process never saw finish shows here as status='crashed' --
        # see Store.reconcile_job_runs(), run once when the session opened.
        state["last_run"] = self.store.last_job_run()
        return state

    def stage_summary(self) -> dict:
        """Wall-clock measurements taken so far, per pipeline stage. See
        telemetry.py for why only wall-clock -- CPU/memory are not sampled."""
        return self.store.stage_summary()


class Handler(BaseHTTPRequestHandler):
    server_version = "FormsLang"
    workbench: Workbench  # injected by serve()
    quiet = True

    AUTH_COOKIE = "formslang_session"
    _AUTH_EXEMPT_GET = ("/", "/index.html", "/api/auth/whoami")
    _AUTH_EXEMPT_POST = ("/api/auth/login", "/api/auth/reset/redeem")

    # SS7.1/SS7.2: what a restricted session may reach. A scope missing from
    # this table (NORMAL) is unrestricted; a path missing from a scope's set
    # is ACCESS_DENIED until the session graduates to NORMAL.
    _SCOPE_ALLOWED_POST: ClassVar[dict[str, frozenset[str]]] = {
        authstore.BOOTSTRAP_MFA: frozenset(
            {"/api/auth/logout", "/api/auth/mfa/enroll", "/api/auth/mfa/confirm"}
        ),
        authstore.MFA_PENDING: frozenset({"/api/auth/logout", "/api/auth/mfa"}),
    }

    def log_message(self, *_args) -> None:
        if not self.quiet:
            super().log_message(*_args)

    # -- helpers ---------------------------------------------------------

    def _send(
        self, code: int, body: bytes, content_type: str, *, cookie: str | None = None,
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        # No unsafe-eval, no external origin of any kind, never framable.
        # The MFA enrollment page renders the otpauth QR under this policy.
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'unsafe-inline'; "
            "style-src 'unsafe-inline'; img-src data:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: dict, code: int = 200, *, cookie: str | None = None) -> None:
        self._send(
            code, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8",
            cookie=cookie,
        )

    def _drain(self) -> None:
        """Read and throw away the request body of a request being refused.

        A refusal that answers without emptying the socket leaves the body
        unread; the connection is then reset and the client sees a dropped
        connection instead of the 403 or 415 it was just sent. A refusal has
        to be readable to be useful. Oversized bodies are not drained -- the
        connection is closed instead.
        """
        try:
            left = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            left = 0
        if left > MAX_BODY:
            self.close_connection = True
            return
        while left > 0:
            chunk = self.rfile.read(min(left, 65536))
            if not chunk:
                break
            left -= len(chunk)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise ValueError("request body too large")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _read_upload(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise ValueError("the selected module is empty")
        if length > MAX_UPLOAD:
            raise ValueError("module is larger than the 256 MB upload limit")
        return self.rfile.read(length)

    def _host_is_local(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0].strip("[]")
        return host in {"127.0.0.1", "localhost", "::1", ""}

    def _content_type(self) -> str:
        return (self.headers.get("Content-Type") or "").partition(";")[0].strip().lower()

    # -- auth (design doc SS2, SS7.2) --------------------------------------

    def _cookie(self, name: str) -> str:
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                return value
        return ""

    def _current_session(self) -> tuple[str, dict] | None:
        """(raw_token, session) for the caller's cookie, or ``None``.

        A missing, expired or revoked token all collapse to the same
        ``None`` -- :meth:`~formslang.authstore.AuthStore.get_session` already
        makes that call; nothing here second-guesses it.
        """
        if self.workbench.auth_store is None:
            return None
        token = self._cookie(self.AUTH_COOKIE)
        if not token:
            return None
        session = self.workbench.auth_store.get_session(token)
        if session is None:
            return None
        return token, session

    def _resolve_auth(self) -> tuple[str, dict, dict] | None:
        """(raw_token, session, membership), or ``None``.

        Membership is re-read on every call rather than trusted from the
        session row -- a role change or removal takes effect on the
        caller's very next request, not at their next login.
        """
        current = self._current_session()
        if current is None:
            return None
        token, session = current
        membership = self.workbench.auth_store.get_membership(
            session["active_org_id"], session["user_id"]
        )
        if membership is None:
            return None
        return token, session, membership

    def _origin_is_allowed(self) -> bool:
        """Strict Origin check for every mutating request once auth is on.

        A same-origin fetch() always sets Origin, so the SPA is unaffected;
        a request with no Origin (curl, a non-browser client) or a foreign
        one is refused -- the same loopback allowlist ``_host_is_local``
        checks against Host, checked here against Origin instead.
        """
        origin = self.headers.get("Origin") or ""
        if not origin:
            return False
        host = urlsplit(origin).hostname or ""
        return host in {"127.0.0.1", "localhost", "::1"}

    def _session_cookie_header(self, raw_token: str) -> str:
        return (
            f"{self.AUTH_COOKIE}={raw_token}; HttpOnly; Path=/; SameSite=Lax; "
            f"Max-Age={authstore.SESSION_TTL_SECONDS}"
        )

    def _cleared_cookie_header(self) -> str:
        return f"{self.AUTH_COOKIE}=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0"

    def _whoami_payload(self) -> dict:
        resolved = self._resolve_auth()
        if resolved is None:
            return {"authenticated": False}
        _token, session, membership = resolved
        wb = self.workbench
        user = wb.auth_store.get_user(session["user_id"])
        org = wb.auth_store.get_organization(session["active_org_id"])
        return {
            "authenticated": True,
            "user_id": session["user_id"],
            "email": user["email"] if user else "",
            "active_org_id": session["active_org_id"],
            "organization": org["name"] if org else "",
            "role": membership["role"],
            "csrf_token": session["csrf_secret"],
            "scope": session["scope"],
            "mfa_confirmed": wb.auth_store.has_confirmed_mfa(session["user_id"]),
        }

    def _deny_scope(self, session: dict, path: str) -> None:
        """403 for a restricted session reaching past its scope -- audited,
        so a stolen restricted token probing other routes leaves a trail."""
        self.workbench.auth_store.record_audit(
            event_type="ACCESS_DENIED", outcome="fail",
            org_id=session["active_org_id"], user_id=session["user_id"],
            target_type="route", target_id=path, ip=self.client_address[0],
            detail={"scope": session["scope"], "reason": "restricted_scope"},
        )
        self._json({"error": "complete MFA setup or verification first"}, 403)

    # -- routes ----------------------------------------------------------

    def do_GET(self) -> None:
        if not self._host_is_local():
            self._json({"error": "forbidden host"}, 403)
            return
        wb = self.workbench
        path, _, query = self.path.partition("?")

        auth = None
        if wb.auth_store is not None and path not in self._AUTH_EXEMPT_GET:
            auth = self._resolve_auth()
            if auth is None:
                self._json({"error": "authentication required"}, 401)
                return
            if auth[1]["scope"] != authstore.NORMAL:
                self._deny_scope(auth[1], path)
                return

        try:
            if wb.auth_store is None and (
                path.startswith(("/api/auth/", "/api/projects"))
            ):
                # A 404, not a 401 -- with the subsystem off, these routes
                # simply do not exist, same as any other unknown path.
                self._json({"error": "not found"}, 404)
            elif path in ("/", "/index.html"):
                page = INDEX_HTML if wb.auth_store is None else authui.with_auth_overlay(INDEX_HTML)
                self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/auth/whoami":
                self._json(self._whoami_payload())
            elif path == "/api/projects":
                _token, session, _membership = auth
                rows = wb.auth_store.list_projects_for_org(session["active_org_id"])
                self._json({"projects": [
                    {k: p[k] for k in ("id", "name", "storage_mode", "created_at", "adopted_at")}
                    for p in rows
                ]})
            elif path == "/api/state":
                self._json(wb.state())
            elif path == "/api/job":
                self._json(wb.job_state())
            elif path == "/api/telemetry":
                self._json(wb.stage_summary())
            elif path == "/api/providers":
                self._json({"providers": wb.providers()})
            elif path == "/api/settings":
                self._json(wb.settings_state())
            elif path == "/api/browse":
                where = parse_qs(query).get("dir", [""])[0]
                self._json(wb.browse(where))
            elif path == "/api/exports":
                self._json(wb.list_exports())
            elif path == "/api/analysis":
                self._json(wb.analysis_state())
            elif path == "/api/deps":
                q = parse_qs(query)
                self._json(wb.deps_state(
                    task_id=q.get("task", [""])[0],
                    node=q.get("node", [""])[0],
                    depth=int(q.get("depth", ["2"])[0] or 2),
                ))
            elif path == "/api/tests":
                self._json(wb.tests_state(parse_qs(query).get("task", [""])[0]))
            elif path == "/api/dashboard":
                self._json(wb.dashboard_state())
            elif path == "/api/doc":
                self._send(200, wb.doc_html().encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/diff":
                other = parse_qs(query).get("other", [""])[0]
                if not other:
                    raise ValueError("missing 'other' query parameter")
                self._send(200, wb.diff_html(other).encode("utf-8"), "text/html; charset=utf-8")
            else:
                self._json({"error": "not found"}, 404)
        except authstore.ProjectNotFound:
            self._json({"error": "not found"}, 404)
        except PermissionError as e:
            self._json({"error": str(e)}, 403)
        except ValueError as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001 - return a safe HTTP error
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self) -> None:
        if not self._host_is_local():
            self._drain()
            self._json({"error": "forbidden host"}, 403)
            return
        wb = self.workbench
        path, _, query = self.path.partition("?")
        # CSRF gate: neither content type below can come out of a plain HTML
        # form, and a cross-origin fetch that sets one triggers a CORS
        # preflight this server never answers.
        expected = "application/octet-stream" if path == "/api/upload" else "application/json"
        if self._content_type() != expected:
            self._drain()
            self._json({"error": f"content-type must be {expected}"}, 415)
            return

        if wb.auth_store is None and (
            path.startswith(("/api/auth/", "/api/projects"))
        ):
            self._drain()
            self._json({"error": "not found"}, 404)
            return

        auth = None
        if wb.auth_store is not None:
            # Auth mode's own layer on top of the Content-Type gate above: a
            # strict Origin check on every mutating request, and an
            # X-CSRF-Token that has to match the caller's own session
            # (/api/auth/login has no session yet, so it is exempt from the
            # token check but not the Origin one).
            if not self._origin_is_allowed():
                self._drain()
                self._json({"error": "forbidden origin"}, 403)
                return
            if path not in self._AUTH_EXEMPT_POST:
                auth = self._resolve_auth()
                if auth is None:
                    self._drain()
                    self._json({"error": "authentication required"}, 401)
                    return
                _token, session, _membership = auth
                if not authcrypto.constant_time_eq(
                    self.headers.get("X-CSRF-Token", ""), session["csrf_secret"]
                ):
                    self._drain()
                    self._json({"error": "csrf token missing or invalid"}, 403)
                    return
                allowed = self._SCOPE_ALLOWED_POST.get(session["scope"])
                if allowed is not None and path not in allowed:
                    self._drain()
                    self._deny_scope(session, path)
                    return

        if path == "/api/upload":
            try:
                name = parse_qs(query).get("name", [""])[0]
                self._json(wb.upload_module(name, self._read_upload()))
            except (ValueError, OracleToolchainError) as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:  # noqa: BLE001 - never leak a traceback
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)
            return
        try:
            body = self._read_json()
        except (ValueError, json.JSONDecodeError) as e:
            self._json({"error": f"bad request: {e}"}, 400)
            return

        try:
            if self.path == "/api/auth/login":
                email = str(body.get("email") or "")
                password = str(body.get("password") or "")
                org_id = body.get("org_id") or None
                result = wb.auth_store.login(
                    email, password, org_id=org_id,
                    user_agent=self.headers.get("User-Agent", ""),
                    ip=self.client_address[0],
                )
                if not result.ok:
                    payload = {"ok": False, "reason": result.reason}
                    if result.organizations:
                        payload["organizations"] = [
                            {"org_id": m["org_id"]} for m in result.organizations
                        ]
                    self._json(payload, 401)
                    return
                self._json(
                    {"ok": True, "active_org_id": result.active_org_id},
                    cookie=self._session_cookie_header(result.session_token),
                )

            elif self.path == "/api/auth/logout":
                token, session, _membership = auth
                wb.auth_store.revoke_session(token)
                wb.auth_store.record_audit(
                    event_type="SESSION_REVOKED", org_id=session["active_org_id"],
                    user_id=session["user_id"], ip=self.client_address[0],
                    detail={"via": "logout"},
                )
                self._json({"ok": True}, cookie=self._cleared_cookie_header())

            elif self.path == "/api/auth/switch-org":
                token, _session, _membership = auth
                new_org_id = str(body.get("org_id") or "").strip()
                new_token, new_session = wb.auth_store.switch_organization(
                    token, new_org_id,
                    user_agent=self.headers.get("User-Agent", ""),
                    ip=self.client_address[0],
                )
                self._json(
                    {"ok": True, "active_org_id": new_session["active_org_id"]},
                    cookie=self._session_cookie_header(new_token),
                )

            elif self.path == "/api/auth/mfa/enroll":
                _token, session, _membership = auth
                enrollment = wb.auth_store.mfa_enroll(
                    session["user_id"], ip=self.client_address[0]
                )
                # The one and only place the secret and otpauth URI ever
                # appear: this authenticated response body (SS7.3). Never in
                # a URL, a log line, an audit row or browser storage.
                self._json({"ok": True, **enrollment})

            elif self.path == "/api/auth/mfa/confirm":
                token, session, _membership = auth
                codes = wb.auth_store.mfa_confirm(
                    session["user_id"],
                    str(body.get("code1") or ""), str(body.get("code2") or ""),
                    ip=self.client_address[0],
                )
                if session["scope"] == authstore.BOOTSTRAP_MFA:
                    # Password was proven at login, possession of the device
                    # by two consecutive codes just now -- both factors are
                    # done, so the restricted session graduates to NORMAL
                    # instead of forcing a second login.
                    wb.auth_store.revoke_session(token)
                    new_token, _ns = wb.auth_store.create_session(
                        session["user_id"], session["active_org_id"],
                        scope=authstore.NORMAL,
                        user_agent=self.headers.get("User-Agent", ""),
                        ip=self.client_address[0],
                    )
                    self._json(
                        {"ok": True, "recovery_codes": codes},
                        cookie=self._session_cookie_header(new_token),
                    )
                else:
                    self._json({"ok": True, "recovery_codes": codes})

            elif self.path == "/api/auth/mfa":
                token, _session, _membership = auth
                result = wb.auth_store.complete_mfa_login(
                    token, str(body.get("code") or ""),
                    user_agent=self.headers.get("User-Agent", ""),
                    ip=self.client_address[0],
                )
                self._json(
                    {"ok": True, "active_org_id": result.active_org_id},
                    cookie=self._session_cookie_header(result.session_token),
                )

            elif self.path == "/api/auth/mfa/disable":
                _token, session, _membership = auth
                wb.auth_store.mfa_disable(
                    session["user_id"],
                    str(body.get("password") or ""), str(body.get("code") or ""),
                    ip=self.client_address[0],
                )
                # mfa_disable revoked every session, this one included.
                self._json({"ok": True}, cookie=self._cleared_cookie_header())

            elif self.path == "/api/auth/mfa/recovery-codes":
                _token, session, _membership = auth
                codes = wb.auth_store.mfa_regenerate_recovery_codes(
                    session["user_id"], str(body.get("code") or ""),
                    ip=self.client_address[0],
                )
                self._json({"ok": True, "recovery_codes": codes})

            elif self.path == "/api/auth/reset/issue":
                _token, session, _membership = auth
                reset_token = wb.auth_store.issue_password_reset(
                    issued_by=session["user_id"],
                    target_user_id=str(body.get("user_id") or "").strip(),
                    org_id=session["active_org_id"],
                    ip=self.client_address[0],
                )
                # Handed to the issuing Admin/Owner to pass on out of band;
                # the server keeps only its hash.
                self._json({"ok": True, "reset_token": reset_token})

            elif self.path == "/api/auth/reset/redeem":
                # Unauthenticated by design (the caller lost their password);
                # Origin-checked above, rate-limited by IP in the store, and
                # the response never says whether the token ever existed.
                wb.auth_store.redeem_password_reset(
                    str(body.get("token") or ""),
                    str(body.get("new_password") or ""),
                    ip=self.client_address[0],
                )
                self._json({"ok": True})

            elif self.path == "/api/projects":
                _token, session, membership = auth
                if not rbac.has_permission(membership["role"], rbac.CREATE_PROJECT):
                    raise PermissionError(f"role {membership['role']} may not {rbac.CREATE_PROJECT}")
                name = str(body.get("name") or "").strip()
                external_path = str(body.get("external_path") or "").strip()
                if not name or not external_path:
                    self._json({"error": "name and external_path are required"}, 400)
                    return
                project = wb.auth_store.register_external_project(
                    session["active_org_id"], name, external_path,
                    created_by=session["user_id"],
                )
                self._json({k: project[k] for k in ("id", "name", "storage_mode", "created_at")})

            elif self.path == "/api/projects/adopt":
                _token, session, _membership = auth
                project_id = str(body.get("project_id") or "").strip()
                projects.authorize_project_access(
                    wb.auth_store, session["user_id"], session["active_org_id"],
                    project_id, rbac.ADOPT_PROJECT,
                )
                adopted = projects.adopt_project(
                    wb.auth_store, project_id,
                    data_dir=wb.auth_data_dir, actor_user_id=session["user_id"],
                )
                self._json({k: adopted[k] for k in ("id", "name", "storage_mode", "adopted_at")})

            elif self.path == "/api/propose":
                if body.get("all"):
                    ids = [t.id for t in wb.store.pending_tasks()]
                else:
                    ids = [body["task_id"]] if body.get("task_id") else []
                if not ids:
                    self._json({"error": "nothing to convert"}, 400)
                    return
                if not wb.start_job(ids):
                    self._json({"error": "a conversion is already running"}, 409)
                    return
                self._json({"started": len(ids)})

            elif self.path == "/api/job/cancel":
                self._json(wb.cancel_job())

            elif self.path == "/api/decision":
                task_id = body.get("task_id") or ""
                state = body.get("state") or ""
                if state not in STATES:
                    self._json({"error": f"unknown state {state!r}"}, 400)
                    return
                if wb.store.get_task(task_id) is None:
                    self._json({"error": "unknown task"}, 404)
                    return
                wb.store.set_decision(
                    task_id,
                    state,
                    code=body.get("code", ""),
                    comment=body.get("comment", ""),
                    reviewer=body.get("reviewer", ""),
                )
                self._json({"ok": True, "stats": wb.store.stats()})

            elif self.path == "/api/test-decision":
                out = wb.decide_test_case(
                    case_id=str(body.get("case_id") or ""),
                    state=str(body.get("state") or ""),
                    reviewer=str(body.get("reviewer") or ""),
                    comment=str(body.get("comment") or ""),
                )
                if not out.get("ok"):
                    self._json(out, 400 if out.get("error") == "unknown state" else 404)
                    return
                self._json(out)

            elif self.path == "/api/test-run":
                out = wb.record_test_run(
                    case_id=str(body.get("case_id") or ""),
                    run_state=str(body.get("run_state") or ""),
                    run_by=str(body.get("run_by") or ""),
                    run_notes=str(body.get("run_notes") or ""),
                )
                if not out.get("ok"):
                    self._json(out, 400 if out.get("error") == "unknown run state" else 404)
                    return
                self._json(out)

            elif self.path == "/api/open":
                self._json(wb.open_module(body.get("path") or ""))

            elif self.path == "/api/provider":
                described = wb.set_provider(body.get("provider") or "", body.get("model") or "")
                self._json({"provider": described})

            elif self.path == "/api/settings":
                self._json(wb.save_settings(body))

            elif self.path == "/api/settings/test":
                self._json(wb.test_settings(body))

            elif self.path == "/api/terminal":
                self._json(wb.open_terminal(str(body.get("provider") or "")))

            elif self.path == "/api/export":
                self._json({"ok": True, **wb.export(body), "stats": wb.store.stats()})

            elif self.path == "/api/exports/open":
                self._json(wb.reveal_export(str(body.get("name") or "")))

            else:
                self._json({"error": "not found"}, 404)
        except authstore.ProjectNotFound:
            self._json({"error": "not found"}, 404)
        except PermissionError as e:
            self._json({"error": str(e)}, 403)
        except authstore.SessionNotFound:
            self._json({"error": "session is invalid or expired"}, 401)
        except authstore.RateLimited as e:
            self._json(
                {"error": "too many attempts", "retry_after_seconds": e.retry_after_seconds}, 429,
            )
        except secrets.SecureStorageUnavailable as e:
            # Fail closed and say so: MFA without a reachable OS credential
            # store is an outage, never a bypass.
            self._json({"error": str(e)}, 503)
        except authstore.AuthStoreError as e:
            self._json({"error": str(e)}, 400)
        except (ValueError, projects.AdoptionError, OracleToolchainError) as e:
            # A bad path or a missing Oracle install is the caller's problem
            # to fix, and the message is the whole point of the answer.
            self._json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001 - never leak a traceback
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def serve(
    workbench: Workbench,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Block, serving the workbench, until Ctrl+C."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        # Not a default -- a rule. The workbench holds the source under
        # review and has no authentication, so it binds the loopback
        # interface or not at all.
        raise ValueError(f"the workbench binds loopback only, not {host!r}")
    handler = type("BoundHandler", (Handler,), {"workbench": workbench})
    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{httpd.server_port}/"
    print(f"Workbench   : {url}")
    print(f"Provider    : {workbench.provider.describe()}")
    print(f"Session     : {workbench.store.path}")
    print("Ctrl+C to stop.\n")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. The session file keeps every decision.")
    finally:
        httpd.server_close()
