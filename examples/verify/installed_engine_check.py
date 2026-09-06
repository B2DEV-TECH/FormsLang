"""Smoke-test an installed engine before/after upgrade using synthetic source only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--phase", choices=["seed", "verify"], required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    engine = args.engine.resolve()
    version = subprocess.check_output([str(engine), "--version"], text=True, timeout=30)
    assert version.strip() == f"FormsLang {args.version}", version
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = dict(os.environ, FORMSLANG_CONFIG_DIR=str(work / "config"),
               FORMSLANG_SECRET_BACKEND="memory")
    source = Path("tests/fixtures/showcase/module.xml").resolve()
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with (work / f"{args.phase}-engine.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [str(engine), "workbench", str(source), "-o", str(work / "session"),
             "--provider", "echo", "--port", str(port), "--no-browser"],
            env=env, stdout=log, stderr=log,
        )

        def request(route: str, body: dict | None = None) -> dict:
            data = None if body is None else json.dumps(body).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{route}", data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)

        try:
            deadline = time.monotonic() + 60
            while True:
                try:
                    state = request("/api/state")
                    break
                except (OSError, urllib.error.URLError):
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("installed engine did not become ready; inspect log") from None
                    time.sleep(0.25)
            assert state["session"]["title"] == "DEMO_ALL_ELEMENTS"
            assert state["can_export_apex"]
            task = state["tasks"][0]
            task_id = task["id"]
            code = "begin null; end;"
            if args.phase == "seed":
                request("/api/decision", {"task_id": task_id, "state": "approved",
                                         "code": code, "reviewer": "installer QA"})
            else:
                assert task["state"] == "approved", task
                assert task["final_code"] == code, task
                assert task["reviewer"] == "installer QA", task
            result = request("/api/export", {"alias": "installer-qa", "app_id": 190122})
            zip_path = Path(result["zip"])
            first = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            request("/api/export", {"alias": "installer-qa", "app_id": 190122})
            assert hashlib.sha256(zip_path.read_bytes()).hexdigest() == first
            assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
            summary = {"phase": args.phase, "version": args.version,
                       "tasks": state["stats"]["tasks"], "approval_preserved": True,
                       "deterministic_export": True, "source_unchanged": True}
            (work / f"{args.phase}-result.json").write_text(
                json.dumps(summary, indent=2) + "\n", encoding="utf-8",
            )
            print(json.dumps(summary))
        finally:
            # Only the process tree launched above, including PyInstaller's child.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False)
            process.wait(timeout=30)


if __name__ == "__main__":
    main()
