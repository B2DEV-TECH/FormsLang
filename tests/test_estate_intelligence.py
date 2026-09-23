"""Estate Intelligence through the real parser, Blueprint, assessment and services.

Every positive and negative case below starts from Forms XML and PL/SQL files,
never from dictionaries shaped like what a detector expects.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from formslang import rbac
from formslang.hotspots import (
    HOTSPOT_API_BYPASS,
    HOTSPOT_DUPLICATED_RULE,
    HOTSPOT_GLOBAL_STATE,
)
from formslang.project_intake import ProjectIntake
from formslang.project_model import ProjectError, TargetProfile
from formslang.project_service import ProjectService
from tests.test_project_http import project_server  # noqa: F401 - shared loopback fixture

ESTATE = Path(__file__).parent / "fixtures" / "estate"
UNSELECTED = TargetProfile("UNSELECTED", "none", "none")


def open_estate(tmp_path, forms=ESTATE / "forms", database=ESTATE / "database", *, target=UNSELECTED):
    intake = ProjectIntake(tmp_path / "data", tmp_path / "config")
    selections = [intake.select_source(forms, "forms"), intake.select_source(database, "database")]
    created = intake.create("Synthetic estate", selections, target=target)
    pid = created["project"]["id"]
    authorize = lambda: intake.access(pid, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    service.analyze(expected_revision=None, expected_configuration=0)
    return intake, pid, service


@pytest.fixture
def estate(tmp_path):
    _, _, service = open_estate(tmp_path)
    try:
        yield service
    finally:
        service.close()


def hotspots_of(service):
    page = service.inventory("hotspots", limit=200)
    return {row["hotspot_type"]: row for row in page["rows"]}, page["rows"]


def test_real_estate_produces_expected_hotspots_with_verifiable_evidence(estate):
    overview = estate.overview()
    assert overview["hotspots"]["by_type"] == {"api_bypass": 1, "duplicated_rules": 1, "global_state": 1}
    assert overview["inventory"]["architectural_hotspots"] == 3
    by_type, rows = hotspots_of(estate)
    blueprint = estate.assessment()["blueprint"]
    evidence_ids = {e["id"] for e in blueprint["evidence"]}
    edge_ids = {e["id"] for e in blueprint["edges"]}
    finding_ids = {f["id"] for f in blueprint["findings"]}
    for row in rows:
        assert row["classification"] == "CANDIDATE"
        assert row["severity"] in {"HIGH", "MEDIUM"}
        assert row["uncertainty"] and row["recommended_action"].startswith("Architecture review required")
        assert set(row["finding_ids"]) <= finding_ids and row["finding_ids"]
        assert set(row["evidence_refs"]) <= evidence_ids and row["evidence_refs"]
        assert set(row["edge_refs"]) <= edge_ids and row["edge_refs"]

    bypass = by_type[HOTSPOT_API_BYPASS]
    assert bypass["label"] == "Possible API bypass"
    assert bypass["evidence"]["table"] == "WORK_ITEMS"
    assert bypass["evidence"]["potential_existing_api_owners"] == ["WORK_API.CLOSE_ITEM"]
    assert bypass["evidence"]["guard_gap"] >= 1 and bypass["severity"] == "HIGH"
    assert "authoritative" not in bypass["statement"].lower()

    duplicated = by_type[HOTSPOT_DUPLICATED_RULE]
    assert duplicated["evidence"]["database_subprogram"] == "WORK_API.NET_AMOUNT"
    assert duplicated["evidence"]["modules"] == ["REVIEWS", "TOTALS"]
    assert duplicated["severity"] == "HIGH"

    coupling = by_type[HOTSPOT_GLOBAL_STATE]
    assert coupling["evidence"]["variable"] == ":GLOBAL.CURRENT_ITEM"
    assert coupling["evidence"]["observed_writers"] == ["INTAKE"]
    assert coupling["evidence"]["observed_readers"] == ["REVIEWS"]

    # Metric -> hotspot -> evidence -> review: the hotspot opens its findings.
    detail = estate.inventory_detail("hotspots", bypass["id"])
    assert {row["id"] for row in detail["related_findings"]} >= set(bypass["finding_ids"])
    finding = estate.review_detail(bypass["finding_ids"][0])
    assert finding["engine_recommendation"] == "MANUAL_REVIEW"
    findings = {row["id"]: row for row in estate.inventory("findings", limit=200)["rows"]}
    assert bypass["id"] in findings[bypass["finding_ids"][0]]["hotspot_ids"]
    assert "DIRECT_DML_BYPASSES_API" in findings[bypass["finding_ids"][0]]["signals"]


def test_negative_controls_do_not_become_hotspots(estate):
    _, rows = hotspots_of(estate)
    text = json.dumps(rows)
    # Delegation to the API, writes to a table no package owns, a variable that
    # only appears in a comment and a literal, and a same-named local unit.
    assert "LOG_NOTE" not in text and "AUDIT_NOTES" not in text
    assert "STAGING_ROWS" not in text
    assert "GHOST_FLAG" not in text.upper()
    assert all("WORK.NOTE" not in unit for row in rows for unit in row["evidence"].get("units", []))
    assert len([r for r in rows if r["hotspot_type"] == HOTSPOT_API_BYPASS]) == 1


def write_estate(root, trigger_text, package_body):
    forms, database = root / "forms", root / "database"
    forms.mkdir(parents=True)
    database.mkdir(parents=True)
    (forms / "entry.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="ENTRY">
<Block Name="ROW_BLOCK" QueryDataSourceName="LEDGER_ROWS">
<Item Name="ROW_ID" ItemType="Text Item" DataType="Number"/>
<Item Name="SAVE" ItemType="Push Button"><Trigger Name="WHEN-BUTTON-PRESSED" TriggerText="{trigger_text}"/></Item>
</Block></FormModule></Module>''', encoding="utf-8")
    (database / "tables.sql").write_text(
        "create table ledger_rows (row_id number primary key, state varchar2(20));\n", encoding="utf-8")
    (database / "ledger_api.pks").write_text(
        "create or replace package ledger_api as procedure touch(p_id in number); end ledger_api;\n/\n",
        encoding="utf-8")
    (database / "ledger_api.pkb").write_text(package_body, encoding="utf-8")
    return forms, database


def test_plain_co_writer_is_a_medium_candidate_never_critical(tmp_path):
    forms, database = write_estate(
        tmp_path / "src",
        "BEGIN UPDATE ledger_rows SET state = 'DONE' WHERE row_id = :row_block.row_id; END;",
        "create or replace package body ledger_api as\n"
        "  procedure touch(p_id in number) is begin\n"
        "    update ledger_rows set state = 'TOUCHED' where row_id = p_id;\n"
        "  end touch;\nend ledger_api;\n/\n")
    _, _, service = open_estate(tmp_path, forms, database)
    try:
        _, rows = hotspots_of(service)
        bypass = [r for r in rows if r["hotspot_type"] == HOTSPOT_API_BYPASS]
        assert len(bypass) == 1
        assert bypass[0]["severity"] == "MEDIUM" and bypass[0]["evidence"]["guard_gap"] <= 0
        assert all(r["severity"] != "CRITICAL" for r in rows)
    finally:
        service.close()


def test_trigger_calling_the_writer_is_not_a_bypass(tmp_path):
    forms, database = write_estate(
        tmp_path / "src",
        "BEGIN ledger_api.touch(:row_block.row_id); END;",
        "create or replace package body ledger_api as\n"
        "  procedure touch(p_id in number) is begin\n"
        "    update ledger_rows set state = 'TOUCHED' where row_id = p_id;\n"
        "  end touch;\nend ledger_api;\n/\n")
    _, _, service = open_estate(tmp_path, forms, database)
    try:
        assert service.overview()["hotspots"]["total"] == 0
    finally:
        service.close()


def test_system_map_folds_form_components_into_module_dependencies(estate):
    forms = {f["name"]: f["id"] for f in estate.system_map()["available_forms"]}
    result = estate.system_map(focus=forms["INTAKE"], depth=1)
    assert result["mode"] == "MODULE_ARCHITECTURE"
    nodes = {n["id"]: n for n in result["nodes"]}
    names = {n["name"]: n for n in result["nodes"]}
    assert names["WORK_ITEMS"]["layer"] == "DATABASE" and names["WORK_ITEMS"]["type"] == "TABLE"
    assert names["WORK_API"]["type"] == "PACKAGE" and names["WORK_API"]["layer"] == "DATABASE"
    assert names["REVIEWS"]["layer"] == "FORM"
    assert all(n["layer"] != "OTHER" for n in result["nodes"])
    edges = {(nodes[e["source"]]["name"], nodes[e["target"]]["name"], e["classification"]): e
             for e in result["edges"]}
    writes = edges[("INTAKE", "WORK_ITEMS", "WRITES")]
    assert writes["is_hotspot"] and "WHEN-BUTTON-PRESSED" in writes["components"]
    assert ("INTAKE", "REVIEWS", "OPENS_FORM") in edges
    assert ("INTAKE", "WORK_API", "CALLS") in edges
    assert ("INTAKE", "STAGING_ROWS", "WRITES") in edges
    assert not any(e["classification"] == "CONTAINS" for e in result["edges"])
    # Findings count once, on the module their component folds into.
    intake_findings = [r for r in estate.inventory("findings", limit=200)["rows"]
                       if r["module"].endswith("intake.xml")]
    assert names["INTAKE"]["findings_count"] == len(intake_findings)


def test_system_map_limits_and_invalid_inputs_are_explicit(estate):
    forms = {f["name"]: f["id"] for f in estate.system_map()["available_forms"]}
    capped = estate.system_map(focus=forms["INTAKE"], depth=2, edge_limit=1)
    assert len(capped["edges"]) == 1 and capped["truncated"]
    assert {t["reason"] for t in capped["truncation"]} >= {"EDGE_LIMIT"}
    small = estate.system_map(focus=forms["INTAKE"], depth=2, limit=2)
    assert len(small["nodes"]) == 2 and any(t["reason"] == "NODE_LIMIT" for t in small["truncation"])
    database_only = estate.system_map(focus=forms["INTAKE"], layer="DATABASE")
    assert all(n["layer"] == "DATABASE" or n["is_focus"] for n in database_only["nodes"])
    for kwargs in ({"depth": 0}, {"depth": 9}, {"limit": 0}, {"limit": 201}, {"edge_limit": 401},
                   {"layer": "SERVICES"}, {"edge_type": "EVERYTHING"}, {"focus": "NO_SUCH_FORM"}):
        with pytest.raises(ProjectError):
            estate.system_map(**kwargs)


def test_search_limits_are_enforced_by_the_service(estate):
    result = estate.search("work", limit=5)
    assert 0 < len(result["results"]) <= 5 and result["project_id"]
    assert any(r["category"] == "hotspots" for r in estate.search("bypass", limit=50)["results"])
    for query, limit in (("work", 0), ("work", -1), ("work", 51), ("work", 1_000_000), ("x" * 201, 5)):
        with pytest.raises(ProjectError):
            estate.search(query, limit=limit)


DETERMINISM = r'''
import json, sys
from pathlib import Path
from formslang import rbac
from formslang.project_intake import ProjectIntake
from formslang.project_service import ProjectService
tmp, pid = Path(sys.argv[1]), sys.argv[2]
intake = ProjectIntake(tmp / "data", tmp / "config")
auth = lambda: intake.access(pid, rbac.RUN_CONVERSION)
service = ProjectService(auth(), authorize=auth)
descriptor = service.open()
# Re-run the complete analysis in this process, then project it.
service.analyze(expected_revision=descriptor.analysis_revision,
                expected_configuration=service._store.configuration_revision())
rows = service.inventory("hotspots", limit=200)["rows"]
edges = service.system_map(depth=3)["edges"]
print(json.dumps({"analysis": service.open().analysis_revision,
                  "hotspots": [(r["id"], r["severity"], r["finding_ids"]) for r in rows],
                  "map": [(e["id"], e["count"]) for e in edges]}))
service.close()
'''


def test_hotspot_and_map_identities_do_not_depend_on_hash_seed(tmp_path):
    intake = ProjectIntake(tmp_path / "data", tmp_path / "config")
    selections = [intake.select_source(ESTATE / "forms", "forms"),
                  intake.select_source(ESTATE / "database", "database")]
    pid = intake.create("Estate", selections, target=UNSELECTED)["project"]["id"]
    outputs = []
    for seed in ("0", "1", "42"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        completed = subprocess.run([sys.executable, "-c", DETERMINISM, str(tmp_path), pid],
                                   capture_output=True, text=True, env=env, timeout=300, check=False)
        assert completed.returncode == 0, completed.stderr[-2000:]
        outputs.append(completed.stdout.strip().splitlines()[-1])
    assert outputs[0] == outputs[1] == outputs[2]
    assert len(json.loads(outputs[0])["hotspots"]) == 3


def create_estate_over_http(client, root, target):
    shutil.copytree(ESTATE, root)
    selections = []
    for kind in ("forms", "database"):
        response = client.post("/api/v2/source-selections", {"path": str(root / kind), "kind": kind})
        assert response.status == 200, response.json
        selections.append(response.json["selection"])
    created = client.post("/api/v2/projects", {"name": "Estate", "sources": selections, "target": target})
    assert created.status == 201, created.json
    pid = created.json["project"]["id"]
    job = client.post(f"/api/v2/projects/{pid}/analyze", {"expected_revision": None, "expected_configuration": 0})
    assert job.status == 202, job.json
    assert client.wait_job(pid, job.json["job_id"])["status"] == "COMPLETED"
    return pid, created.json


def test_http_overview_map_and_search_come_from_the_real_assessment(project_server, tmp_path):  # noqa: F811
    client, _ = project_server
    pid, _ = create_estate_over_http(client, tmp_path / "estate", "unselected")
    overview = client.get(f"/api/v2/projects/{pid}/overview").json["overview"]
    assert overview["hotspots"]["total"] == 3
    assert {h["label"] for h in overview["hotspots"]["items"]} == {
        "Possible API bypass", "Duplicated business-rule candidate", "Global state coupling"}
    inventory = client.get(f"/api/v2/projects/{pid}/inventory?category=hotspots").json
    assert inventory["total"] == 3
    forms = client.get(f"/api/v2/projects/{pid}/system-map").json["available_forms"]
    intake_id = next(f["id"] for f in forms if f["name"] == "INTAKE")
    mapped = client.get(f"/api/v2/projects/{pid}/system-map?focus={intake_id}&depth=1").json
    assert any(e["classification"] == "WRITES" and e["target_name"] == "WORK_ITEMS" for e in mapped["edges"])
    for query in ("depth=0", "limit=500", "edge_limit=9999", "layer=CLOUD", "focus=missing", "bogus=1"):
        assert client.get(f"/api/v2/projects/{pid}/system-map?{query}").status == 400, query
    for query in ("limit=0", "limit=-1", "limit=1000000", "q=work", "other=1"):
        assert client.get(f"/api/v2/projects/{pid}/search?query=work&{query}").status == 400, query
    assert client.get(f"/api/v2/projects/{pid}/search?query={'x' * 201}").status == 400
    found = client.get(f"/api/v2/projects/{pid}/search?query=work&limit=3").json
    assert len(found["results"]) <= 3 and found["project_id"] == pid


def test_duplicated_rule_owner_comes_from_the_duplication_not_the_top_signal(tmp_path):
    """A unit that both bypasses an API and copies a formula joins the formula's cluster."""
    source = tmp_path / "estate"
    shutil.copytree(ESTATE, source)
    totals = source / "forms" / "totals.xml"
    totals.write_text(totals.read_text(encoding="utf-8").replace(
        "BEGIN :total.net", "BEGIN UPDATE work_items SET status = 'TOTALLED' WHERE item_id = 1; :total.net"),
        encoding="utf-8")
    _, _, service = open_estate(tmp_path, source / "forms", source / "database")
    try:
        _, rows = hotspots_of(service)
        clusters = {r["evidence"]["database_subprogram"]: r for r in rows
                    if r["hotspot_type"] == HOTSPOT_DUPLICATED_RULE}
        assert set(clusters) == {"WORK_API.NET_AMOUNT"}
        assert clusters["WORK_API.NET_AMOUNT"]["evidence"]["modules"] == ["REVIEWS", "TOTALS"]
        assert clusters["WORK_API.NET_AMOUNT"]["edge_refs"]
    finally:
        service.close()
