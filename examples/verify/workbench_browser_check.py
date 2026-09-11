"""Exercise the real Workbench in an isolated browser and capture evidence.

Requires Python, Node 22+ and Edge (or ``--browser`` pointing to Chromium).
Run from a source checkout::

    python examples/verify/workbench_browser_check.py --output out/browser-check

Every run creates a fresh directory beneath the output directory. It uses
only the synthetic showcase fixture and a clearly labelled offline provider;
no personal settings, source files, provider credentials or model are used.
Screenshots and result.json describe UI behavior, not Oracle runtime parity.
The browser profile and session are retained for diagnosis. The processes
are stopped on success, failure, timeout and keyboard interruption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def browser_path(explicit: str | None) -> str:
    candidates = [explicit] if explicit else [
        shutil.which("msedge"), shutil.which("chromium"), shutil.which("google-chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise RuntimeError("Edge/Chromium not found; pass --browser with its executable path")


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        # Fallback for interrupted CDP: terminate only this launched process tree.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW, check=False,
        )
        process.wait(timeout=10)
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser")
    parser.add_argument("--node", default="node")
    args = parser.parse_args()
    browser = browser_path(args.browser)
    args.output.mkdir(parents=True, exist_ok=True)
    run = args.output.resolve() / f"run-{uuid.uuid4().hex[:12]}"
    run.mkdir()
    print(f"Browser evidence: {run}", flush=True)

    # Set these before any FormsLang import. Never load the user's config.
    os.environ["FORMSLANG_CONFIG_DIR"] = str(run / "config")
    os.environ["FORMSLANG_SECRET_BACKEND"] = "memory"
    sys.path.insert(0, str(REPO))
    from formslang.ai import EchoProvider
    from formslang.convert import build_tasks
    from formslang.parser import parse_xml
    from formslang.store import Store
    from formslang.ui import INDEX_HTML
    from formslang.workbench import Handler, Workbench

    class BrowserCheckProvider(EchoProvider):
        type_id = "browser_check"
        label = "Offline browser check (no model)"
        default_model = "synthetic response"

        def complete(self, messages, **kwargs):
            try:
                payload = json.loads(messages[-1].content)
            except (ValueError, IndexError):
                return super().complete(messages, **kwargs)
            if "component_sample" in payload:
                # Long enough to exercise closing/reopening a running AI job.
                time.sleep(1.2)
                sample = payload["component_sample"]
                aliases = [sample[0]["alias"]] if sample else []
                return json.dumps({"sections": [
                    {"title": "Offline acceptance fixture", "text":
                     "This is a deterministic browser-test response; no AI model ran. "
                     "Source references connect screen behavior to reusable logic.",
                     "components": aliases},
                    {"title": "Questions for the reviewer", "text":
                     "Confirm transaction ownership and unavailable callee behavior "
                     "before accepting a target architecture.", "components": []},
                ]})
            if "classification" in payload:
                return "Offline browser-test response. Inspect source evidence before deciding."
            return super().complete(messages, **kwargs)

    source = REPO / "tests" / "fixtures" / "showcase" / "module.xml"
    module = parse_xml(source)
    store = Store(run / "showcase.session.db")
    store.init_session(module.name, str(source))
    store.add_tasks(build_tasks(module))
    wb = Workbench(store, BrowserCheckProvider(), run / "export", out_dir=run)
    wb.build_blueprint(enterprise=True)
    handler = type("BrowserCheckHandler", (Handler,), {"workbench": wb})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    # Reserve an available local CDP port. This is an isolated temporary profile.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        debug_port = reservation.getsockname()[1]
    url = f"http://127.0.0.1:{server.server_port}"
    (run / "state.json").write_text(json.dumps({
        "url": url, "debug_port": debug_port,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "ui_sha256": hashlib.sha256(INDEX_HTML.encode()).hexdigest(),
    }), encoding="utf-8")
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    edge = node = None
    try:
        with (run / "browser.log").open("w", encoding="utf-8") as log, \
                (run / "node.log").open("w", encoding="utf-8") as node_log:
            edge = subprocess.Popen([
                browser, "--headless=new", "--disable-gpu", "--no-first-run",
                "--disable-extensions", "--disable-background-networking", "--disable-sync",
                "--remote-debugging-address=127.0.0.1", f"--remote-debugging-port={debug_port}",
                "--window-size=1366,768", f"--user-data-dir={run / 'browser-profile'}", "about:blank",
            ], creationflags=hidden, stdout=log, stderr=log)
            node = subprocess.Popen([
                args.node, str(Path(__file__).with_suffix(".mjs")), str(run),
            ], creationflags=hidden, stdout=node_log, stderr=node_log)
            deadline = time.monotonic() + 240
            next_update = time.monotonic() + 20
            while node.poll() is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Browser acceptance exceeded four minutes; inspect result.json and logs")
                if time.monotonic() >= next_update:
                    print("Browser acceptance is still running...", flush=True)
                    next_update = time.monotonic() + 20
                time.sleep(0.2)
            print((run / "node.log").read_text(encoding="utf-8"), flush=True)
            return node.returncode
    finally:
        stop(node)
        # The CDP script closes the browser normally; allow helpers to settle
        # before falling back to termination on failure/interruption.
        if edge is not None:
            try:
                edge.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        stop(edge)
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
