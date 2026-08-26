"""Local HTTP server behind the conversion workbench.

Standard library only, bound to the loopback interface, no authentication
and no remote access by design: the server holds the customer's source code
and the only thing allowed to reach it is a browser on the same machine.

The Host header is checked on every request. Without that, any web page the
reviewer happens to have open could point a DNS name at 127.0.0.1 and read
the whole session -- the one attack a localhost server is genuinely exposed
to.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ai import Provider
from .convert import Proposal, propose
from .store import STATES, Store
from .ui import INDEX_HTML

MAX_BODY = 4 * 1024 * 1024


class Workbench:
    """Session state shared by every request handler."""

    def __init__(self, store: Store, provider: Provider, export_dir: Path):
        self.store = store
        self.provider = provider
        self.export_dir = Path(export_dir)
        self._lock = threading.Lock()
        self.job = {"running": False, "done": 0, "total": 0, "error": ""}

    # -- read ------------------------------------------------------------

    def state(self) -> dict:
        return {
            "session": self.store.session(),
            "stats": self.store.stats(),
            "provider": self.provider.describe(),
            "tasks": [v.to_dict() for v in self.store.all_views()],
        }

    # -- conversion ------------------------------------------------------

    def start_job(self, task_ids: list[str]) -> bool:
        """Run the conversions off the request thread. One job at a time."""
        with self._lock:
            if self.job["running"]:
                return False
            self.job = {"running": True, "done": 0, "total": len(task_ids), "error": ""}
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
        except Exception as e:  # a broken job must not take the server down
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

    def log_message(self, *_args) -> None:  # noqa: D102 - silence stdout noise
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

    def _host_is_local(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0].strip("[]")
        return host in {"127.0.0.1", "localhost", "::1", ""}

    # -- routes ----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if not self._host_is_local():
            self._json({"error": "forbidden host"}, 403)
            return
        wb = self.workbench
        if self.path in ("/", "/index.html"):
            self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self._json(wb.state())
        elif self.path == "/api/job":
            self._json(wb.job_state())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if not self._host_is_local():
            self._json({"error": "forbidden host"}, 403)
            return
        wb = self.workbench
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

            elif self.path == "/api/export":
                sql_path, json_path = wb.store.export(wb.export_dir)
                self._json({
                    "sql": str(sql_path),
                    "json": str(json_path),
                    "approved": wb.store.stats().get("approved", 0),
                })

            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:  # never leak a traceback into the browser
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def serve(
    workbench: Workbench,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Block, serving the workbench, until Ctrl+C."""
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
