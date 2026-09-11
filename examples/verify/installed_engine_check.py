"""Smoke-test an installed engine before and after an upgrade.

Runs against the synthetic showcase fixture only. ``--phase seed`` drives
the baseline installation and records an approval; ``--phase verify``
drives the upgraded installation and checks that the approval survived.
Every check raises on failure, so the outcome does not depend on whether
Python runs with ``-O``. Each phase writes ``<work>/<phase>-result.json``
listing only what that phase actually checked.
"""

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

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "tests" / "fixtures" / "showcase" / "module.xml"
REVIEWER = "installer QA"
APPROVED_CODE = "begin null; end;"
EXPORT = {"alias": "installer-qa", "app_id": 190122}


class CheckFailed(AssertionError):
    """A verification step observed something other than what it expected."""


def check(condition: bool, message: str, detail: object = None) -> None:
    if not condition:
        raise CheckFailed(message if detail is None else f"{message}: {detail!r}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_port() -> int:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


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

    reported = subprocess.check_output([str(engine), "--version"], text=True, timeout=30).strip()
    check(reported == f"FormsLang {args.version}", "installed engine reports another version", reported)

    seed_result = work / "seed-result.json"
    seed = json.loads(seed_result.read_text(encoding="utf-8")) if args.phase == "verify" else {}
    if args.phase == "verify":
        check("task_id" in seed, "seed phase left no task id to verify", seed_result)

    port = free_port()
    env = dict(os.environ, FORMSLANG_CONFIG_DIR=str(work / "config"), FORMSLANG_SECRET_BACKEND="memory")
    source_hash = sha256(SOURCE)
    with (work / f"{args.phase}-engine.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [str(engine), "workbench", str(SOURCE), "-o", str(work / "session"),
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
                        raise RuntimeError("installed engine did not become ready; inspect the engine log") from None
                    time.sleep(0.25)
            check(state["session"]["title"] == "DEMO_ALL_ELEMENTS", "unexpected session", state["session"])
            check(state["can_export_apex"], "session cannot export")
            check(bool(state["tasks"]), "session has no review units")

            result = {"phase": args.phase, "version": args.version, "tasks": state["stats"]["tasks"]}
            if args.phase == "seed":
                task = state["tasks"][0]
                request("/api/decision", {"task_id": task["id"], "state": "approved",
                                         "code": APPROVED_CODE, "reviewer": REVIEWER})
                saved = next(t for t in request("/api/state")["tasks"] if t["id"] == task["id"])
                check(saved["state"] == "approved", "approval was not recorded", saved)
                result.update(task_id=task["id"], approval_recorded=True)
            else:
                task = next((t for t in state["tasks"] if t["id"] == seed["task_id"]), None)
                check(task is not None, "approved unit disappeared after upgrade", seed["task_id"])
                check(task["state"] == "approved", "approval lost after upgrade", task)
                check(task["final_code"] == APPROVED_CODE, "approved code changed after upgrade", task)
                check(task["reviewer"] == REVIEWER, "reviewer changed after upgrade", task)
                check(state["stats"]["tasks"] == seed["tasks"], "unit count changed after upgrade",
                      (seed["tasks"], state["stats"]["tasks"]))
                result.update(task_id=task["id"], approval_preserved=True,
                              baseline_export_sha256=seed.get("export_sha256"))

                # Exercise the new modules inside the frozen candidate, not only
                # the editable Python checkout. Baseline versions need not have
                # the guided projection, so this belongs to the verify phase.
                blueprint = request("/api/blueprint/build", {})
                check(blueprint["guide"]["code_total"] > 0, "Blueprint has no code reading guide")
                check(bool(blueprint["guide"]["paths"]), "Blueprint has no observed paths")
                entity = blueprint["guide"]["start_here"][0]["id"]
                detail = request("/api/blueprint/explore?node=" + entity)["selected"]
                check(bool(detail["source_context"]["text"]), "Blueprint lost decoded source context")
                finding = detail["finding"]
                request("/api/blueprint/review", {
                    "entity": finding["entity"], "revision": finding["revision"],
                    "action": "DEFER", "reviewer": REVIEWER,
                    "comment": "Installer acceptance: investigate after upgrade",
                })
                saved = request("/api/blueprint/explore?node=" + entity)["selected"]["finding"]
                check(saved["review_state"] == "DEFER", "Blueprint review was not retained")
                result.update(blueprint_guide=True, blueprint_source_context=True, blueprint_review=True)

            zip_path = Path(request("/api/export", EXPORT)["zip"])
            first = sha256(zip_path)
            request("/api/export", EXPORT)
            check(sha256(zip_path) == first, "second export differs from the first")
            check(sha256(SOURCE) == source_hash, "source file was modified")
            result.update(deterministic_export=True, source_unchanged=True, export_sha256=first)

            (work / f"{args.phase}-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result))
        finally:
            # Only the process tree launched above, including PyInstaller's child.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False)
            process.wait(timeout=30)


if __name__ == "__main__":
    main()
