"""Local HTTP server behind the conversion workbench.

Standard library only, bound to the loopback interface, no authentication
and no remote access by design: the server holds the customer's source code
and the only thing allowed to reach it is a browser on the same machine.

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
from urllib.parse import parse_qs

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
from .apexlang import export_apexlang
from .config import config_path, load_config, save_config
from .convert import Proposal, build_tasks, propose
from .oracle import OracleToolchainError, convert_module, detect_toolchain, expected_xml_name
from .parser import parse_xml
from .store import STATES, Store
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
    ):
        self.store = store
        self.provider = provider
        self.export_dir = Path(export_dir)
        self.out_dir = Path(out_dir or self.export_dir.parent)
        self.browse_root = Path(browse_root or Path.cwd()).resolve()
        self.oracle_home = oracle_home
        self._lock = threading.Lock()
        self.job = {
            "running": False, "done": 0, "failed": 0, "total": 0,
            "error": "", "last_error": "",
        }
        self.module = self._module_from_session()

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
            if target.suffix.lower() == ".xml":
                module = parse_xml(target)
            else:
                # Oracle writes the XML next to the .fmb, so convert in our
                # own directory and never touch the customer's tree.
                toolchain = detect_toolchain(self.oracle_home)
                xml, log = convert_module(target, self.out_dir / "xml", toolchain, overwrite=False)
                module = parse_xml(xml, convert_log=log)
            store = Store(self.out_dir / f"{module.name}.session.db")
            store.init_session(module.name, str(target))
            added = store.add_tasks(build_tasks(module))

        old = self.store
        self.store = store
        self.export_dir = self.out_dir / "export"
        if old is not store:
            old.close()
        self.browse_root = target.parent
        self.module = module if module is not None else self._module_from_session()
        return {"title": store.session().get("title", ""), "added": added, "stats": store.stats()}

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
        return export_apexlang(self.store, module, self.export_dir, config).to_dict()

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
            "key_source": "env" if env_key else ("config" if cfg.get("api_key") else ""),
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
            save_config(cfg)
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
        home = str(Path.home())  # never the customer's source tree
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
        with self._lock:
            if self.job["running"]:
                return False
            self.job = {
                "running": True, "done": 0, "failed": 0, "total": len(task_ids),
                "error": "", "last_error": "",
            }
        threading.Thread(target=self._run_job, args=(task_ids,), daemon=True).start()
        return True

    def _run_job(self, task_ids: list[str]) -> None:
        seen: dict[str, str] = {}  # fingerprint -> task already converted here
        try:
            for task_id in task_ids:
                task = self.store.get_task(task_id)
                if task is None:
                    continue
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
                        )
                        self.store.save_proposal(task_id, reused)
                        with self._lock:
                            self.job["done"] += 1
                        continue
                result = propose(task, self.provider)
                self.store.save_proposal(task_id, result)
                if task.fingerprint and result.ok:
                    seen.setdefault(task.fingerprint, task_id)
                with self._lock:
                    self.job["done"] += 1
                    if not result.ok:
                        self.job["failed"] += 1
                        self.job["last_error"] = result.error
        except Exception as e:  # noqa: BLE001 - a job must not take the server down
            with self._lock:
                self.job["error"] = f"{type(e).__name__}: {e}"
        finally:
            with self._lock:
                self.job["running"] = False

    def job_state(self) -> dict:
        with self._lock:
            return dict(self.job)


class Handler(BaseHTTPRequestHandler):
    server_version = "FormsLang"
    workbench: Workbench  # injected by serve()
    quiet = True

    def log_message(self, *_args) -> None:
        if not self.quiet:
            super().log_message(*_args)

    # -- helpers ---------------------------------------------------------

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: dict, code: int = 200) -> None:
        self._send(code, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

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

    # -- routes ----------------------------------------------------------

    def do_GET(self) -> None:
        if not self._host_is_local():
            self._json({"error": "forbidden host"}, 403)
            return
        wb = self.workbench
        path, _, query = self.path.partition("?")
        try:
            if path in ("/", "/index.html"):
                self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._json(wb.state())
            elif path == "/api/job":
                self._json(wb.job_state())
            elif path == "/api/providers":
                self._json({"providers": wb.providers()})
            elif path == "/api/settings":
                self._json(wb.settings_state())
            elif path == "/api/browse":
                where = parse_qs(query).get("dir", [""])[0]
                self._json(wb.browse(where))
            elif path == "/api/exports":
                self._json(wb.list_exports())
            else:
                self._json({"error": "not found"}, 404)
        except ValueError as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001 - return a safe HTTP error
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self) -> None:
        if not self._host_is_local():
            self._json({"error": "forbidden host"}, 403)
            return
        wb = self.workbench
        path, _, query = self.path.partition("?")
        # CSRF gate: neither content type below can come out of a plain HTML
        # form, and a cross-origin fetch that sets one triggers a CORS
        # preflight this server never answers.
        expected = "application/octet-stream" if path == "/api/upload" else "application/json"
        if self._content_type() != expected:
            self._json({"error": f"content-type must be {expected}"}, 415)
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
            if self.path == "/api/propose":
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
        except (ValueError, OracleToolchainError) as e:
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
        # Not a default -- a rule. The workbench holds customer source and
        # has no authentication, so it binds the loopback interface or not
        # at all.
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
