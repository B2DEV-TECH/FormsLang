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
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "tests" / "fixtures" / "showcase" / "module.xml"
REVIEWER = "installer QA"
APPROVED_CODE = "begin null; end;"
BLUEPRINT_COMMENT = "Synthetic pre-upgrade architecture decision"
EXPORT = {"alias": "installer-qa", "app_id": 190122}


class CheckFailed(AssertionError):
    """A verification step observed something other than what it expected."""


def check(condition: bool, message: str, detail: object = None) -> None:
    if not condition:
        raise CheckFailed(message if detail is None else f"{message}: {detail!r}")


def _check_blueprint_decision(decision: dict, *, entity: str, revision: str,
                              source_revision: str, engine_version: str,
                              comment: str) -> None:
    check((decision.get("entity"), decision.get("revision"), decision.get("action")) ==
          (entity, revision, "DEFER"), "Blueprint decision binding or action changed", decision)
    check(decision.get("reviewer") == REVIEWER and decision.get("comment") == comment,
          "Blueprint decision attribution changed", decision)
    snapshot = decision.get("finding_snapshot") or {}
    check(snapshot.get("engine_version") == engine_version and
          snapshot.get("source_revision") == source_revision,
          "Blueprint decision snapshot changed", snapshot)


def verify_preserved_blueprint_review(
    prior: dict, seed: dict, *, stale_engine: bool, current_source_revision: str
) -> None:
    """Keep the historical decision while respecting its current applicability."""
    check(current_source_revision == seed["blueprint_source_revision"],
          "baseline Blueprint source revision changed without explicit reanalysis")
    check(prior.get("entity") == seed["blueprint_entity"], "baseline Blueprint entity changed")
    check(prior.get("revision") == seed["blueprint_revision"],
          "baseline Blueprint finding revision changed")
    history = prior.get("review_history")
    check(isinstance(history, list) and len(history) == 1,
          "baseline Blueprint decision history changed", history)
    _check_blueprint_decision(history[0], entity=seed["blueprint_entity"],
        revision=seed["blueprint_revision"], source_revision=seed["blueprint_source_revision"],
        engine_version=seed["blueprint_engine_version"], comment=BLUEPRINT_COMMENT)
    expected_state = "STALE" if stale_engine else "DEFER"
    check(prior.get("review_state") == expected_state,
          "baseline Blueprint decision applicability changed unexpectedly", prior.get("review_state"))
    check(not prior.get("human_decision"), "baseline Blueprint decision was promoted to approval")


def verify_reinstalled_blueprint_reviews(
    prior: dict, seed: dict, candidate: dict, *, stale_engine: bool, current_source_revision: str
) -> None:
    """After reinstall, preserve both the old history and the fresh candidate decision."""
    check(not stale_engine, "reinstalled candidate Blueprint engine became stale")
    check(current_source_revision == candidate["blueprint_source_revision"],
          "reinstalled candidate Blueprint source revision changed")
    check(prior.get("entity") == seed["blueprint_entity"], "reinstalled Blueprint entity changed")
    check(prior.get("revision") == candidate["blueprint_revision"],
          "reinstalled candidate Blueprint finding revision changed")
    history = prior.get("review_history")
    check(isinstance(history, list) and len(history) == 2,
          "reinstalled Blueprint decision history changed", history)
    _check_blueprint_decision(history[0], entity=seed["blueprint_entity"],
        revision=candidate["blueprint_revision"], source_revision=candidate["blueprint_source_revision"],
        engine_version=candidate["blueprint_engine_version"],
        comment="Installer acceptance: investigate after upgrade")
    _check_blueprint_decision(history[1], entity=seed["blueprint_entity"],
        revision=seed["blueprint_revision"], source_revision=seed["blueprint_source_revision"],
        engine_version=seed["blueprint_engine_version"], comment=BLUEPRINT_COMMENT)
    check(prior.get("review_state") == "DEFER", "reinstalled candidate decision is not current")
    check(not prior.get("human_decision"), "reinstalled decision was promoted to approval")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_port() -> int:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


def verify_key_session(engine, work, phase, env):
    """Use a separate minimal bound form; the showcase has no bindable region."""
    source = work / 'key-control.xml'
    output = work / 'key-control'
    session = output / 'KEY_CONTROL.session.db'
    if phase == 'seed':
        source.write_text('<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="KEY_CONTROL">'
            '<Canvas Name="MAIN" CanvasType="Content" Width="400" Height="200"/>'
            '<Block Name="ORDERS" DatabaseBlock="true" QueryDataSourceName="ORDERS" RecordsDisplayCount="1">'
            '<Item Name="ORDER_ID" ItemType="Text Item" DataType="Number" ColumnName="ORDER_ID" '
            'DatabaseItem="true" CanvasName="MAIN" XPosition="10" YPosition="10" Width="100" Height="20"/>'
            '</Block></FormModule></Module>', encoding='utf-8')
        arguments = [str(source), '-o', str(output), '--key', 'ORDERS=ORDER_ID', '--key-by', REVIEWER]
    else:
        check(session.is_file(), 'key-confirmed session missing after upgrade')
        arguments = [str(session)]
    completed = subprocess.run([str(engine), 'export', *arguments, '--json'], env=env,
                               capture_output=True, text=True, timeout=60, check=False)
    check(completed.returncode == 0, 'key session export failed', completed.stderr)
    connection = sqlite3.connect(session.as_uri() + '?mode=ro', uri=True)
    try:
        row = connection.execute('SELECT key_column,confirmed_by FROM block_key WHERE block=?', ('ORDERS',)).fetchone()
        check(row == ('ORDER_ID', REVIEWER), 'confirmed key or reviewer lost', row)
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--phase", choices=["seed", "verify", "reinstall"], required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    engine = args.engine.resolve()

    reported = subprocess.check_output([str(engine), "--version"], text=True, timeout=30).strip()
    check(reported == f"FormsLang {args.version}", "installed engine reports another version", reported)

    seed_result = work / "seed-result.json"
    seed = json.loads(seed_result.read_text(encoding="utf-8")) if args.phase != "seed" else {}
    if args.phase != "seed":
        check("task_id" in seed, "seed phase left no task id to verify", seed_result)

    port = free_port()
    env = dict(os.environ, FORMSLANG_CONFIG_DIR=str(work / "config"), FORMSLANG_DATA_DIR=str(work / 'data'),
               FORMSLANG_AUTH='0', FORMSLANG_SECRET_BACKEND="memory")
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

        def reject_stale_context(route: str, body: dict | None = None) -> None:
            try:
                request(route, body)
            except urllib.error.HTTPError as error:
                check(error.code == 400, "stale context was not rejected as an invalid request", error.code)
                response = json.load(error)
                check("session changed" in response.get("error", ""), "stale context rejection was not explicit", response)
            else:
                raise CheckFailed("stale context request unexpectedly succeeded")

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
                settings = request('/api/settings', {'provider': 'echo', 'deployment': 'synthetic-upgrade-setting'})
                check(settings['deployment'] == 'synthetic-upgrade-setting', 'safe setting was not saved')
                context = state['context_id']
                baseline_blueprint = request('/api/blueprint/build', {'context_id': context})
                entity = baseline_blueprint['guide']['start_here'][0]['id']
                finding = request('/api/blueprint/explore?node=' + entity + '&context_id=' + context)['selected']['finding']
                request('/api/blueprint/review', {'context_id': context, 'entity': finding['entity'],
                    'revision': finding['revision'], 'action': 'DEFER', 'reviewer': REVIEWER,
                    'comment': BLUEPRINT_COMMENT})
                reviewed = request('/api/blueprint/explore?node=' + entity + '&context_id=' + context)['selected']['finding']
                snapshot = reviewed['review_history'][0]['finding_snapshot']
                result.update(settings_seeded=True, blueprint_entity=finding['entity'],
                    blueprint_revision=finding['revision'],
                    blueprint_source_revision=baseline_blueprint['source_revision'],
                    blueprint_engine_version=snapshot['engine_version'])
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
                check(request('/api/settings')['deployment'] == 'synthetic-upgrade-setting', 'saved setting lost')
                if args.phase == 'reinstall':
                    candidate_result = work / 'verify-result.json'
                    check(candidate_result.is_file(), 'candidate phase left no result to verify')
                    candidate = json.loads(candidate_result.read_text(encoding='utf-8'))
                    prior = request('/api/blueprint/explore?node=' + seed['blueprint_entity'] +
                                    '&context_id=' + state['context_id'])['selected']['finding']
                    current_blueprint = request('/api/blueprint')
                    verify_reinstalled_blueprint_reviews(
                        prior, seed, candidate, stale_engine=current_blueprint['stale_engine'],
                        current_source_revision=current_blueprint['source_revision'],
                    )
                    result.update(settings_preserved=True, blueprint_history_preserved=True,
                                  blueprint_candidate_review_preserved=True)
                else:
                    prior = request('/api/blueprint/explore?node=' + seed['blueprint_entity'] +
                                    '&context_id=' + state['context_id'])['selected']['finding']
                    blueprint_before_reanalysis = request('/api/blueprint')
                    verify_preserved_blueprint_review(
                        prior, seed, stale_engine=blueprint_before_reanalysis['stale_engine'],
                        current_source_revision=blueprint_before_reanalysis['source_revision'],
                    )
                    result.update(settings_preserved=True, blueprint_history_preserved=True,
                                  blueprint_review_stale=blueprint_before_reanalysis['stale_engine'])

                    # Exercise the new modules inside the frozen candidate, not only
                    # the editable Python checkout. Baseline versions need not have
                    # the guided projection, so this belongs to the verify phase.
                    context = state.get("context_id", "")
                    check(isinstance(context, str) and len(context) == 64
                          and all(c in "0123456789abcdef" for c in context),
                          "session context is missing or is not an opaque identifier")
                    initial = request("/api/blueprint")
                    check(initial.get("context_id") == context, "initial Blueprint points to another session")
                    blueprint = request("/api/blueprint/build", {"context_id": context})
                    check(blueprint.get("context_id") == context, "Blueprint regeneration changed session identity")
                    check(blueprint["guide"]["code_total"] > 0, "Blueprint has no code reading guide")
                    check(bool(blueprint["guide"]["paths"]), "Blueprint has no observed paths")
                    ai = request("/api/blueprint/ai?scope=application&context_id=" + context)
                    check(ai == {"status": "idle"}, "reading AI status started or returned a provider request", ai)
                    page = request("/api/blueprint/explore?entity_type=TRIGGER&context_id=" + context)
                    check(bool(page["nodes"]), "Blueprint explorer returned no triggers")
                    check(all("source_text" not in node["attributes"] for node in page["nodes"]),
                          "Blueprint list repeats source bodies")
                    entity = blueprint["guide"]["start_here"][0]["id"]
                    detail_route = "/api/blueprint/explore?node=" + entity + "&context_id=" + context
                    detail = request(detail_route)["selected"]
                    check(bool(detail["source_context"]["text"]), "Blueprint lost decoded source context")
                    finding = detail["finding"]
                    review = {
                        "entity": finding["entity"], "revision": finding["revision"],
                        "action": "DEFER", "reviewer": REVIEWER,
                        "comment": "Installer acceptance: investigate after upgrade",
                        "context_id": context,
                    }
                    wrong_context = "0" * 64 if context != "0" * 64 else "1" * 64
                    reject_stale_context("/api/blueprint/explore?context_id=" + wrong_context)
                    reject_stale_context("/api/blueprint/ai?scope=application&context_id=" + wrong_context)
                    reject_stale_context("/api/blueprint/review", {**review, "context_id": wrong_context})
                    check(request(detail_route)["selected"]["finding"] == finding,
                          "rejected context changed a Blueprint review")
                    request("/api/blueprint/review", review)
                    saved = request(detail_route)["selected"]["finding"]
                    check(saved["review_state"] == "DEFER", "Blueprint review was not retained")
                    candidate_snapshot = saved['review_history'][0]['finding_snapshot']
                    check(candidate_snapshot['source_revision'] == blueprint['source_revision'],
                          'candidate Blueprint decision bound to another source revision')
                    result.update(blueprint_guide=True, blueprint_source_context=True, blueprint_review=True,
                                  opaque_session_context=True, blueprint_ai_idle=True,
                                  blueprint_context_rejected=True, blueprint_list_compact=True,
                                  blueprint_revision=finding['revision'],
                                  blueprint_source_revision=candidate_snapshot['source_revision'],
                                  blueprint_engine_version=candidate_snapshot['engine_version'])

            zip_path = Path(request("/api/export", EXPORT)["zip"])
            first = sha256(zip_path)
            request("/api/export", EXPORT)
            check(sha256(zip_path) == first, "second export differs from the first")
            check(sha256(SOURCE) == source_hash, "source file was modified")
            result.update(deterministic_export=True, source_unchanged=True, export_sha256=first)
            if args.phase != 'seed':
                check(first == seed['export_sha256'], 'upgrade changed the approved legacy export bytes')
                result['baseline_export_preserved'] = True

            verify_key_session(engine, work, args.phase, env)
            result['key_confirmation_seeded' if args.phase == 'seed' else 'key_confirmation_preserved'] = True
            (work / f"{args.phase}-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result))
        finally:
            # Only the process tree launched above, including PyInstaller's child.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False)
            process.wait(timeout=30)


if __name__ == "__main__":
    main()
