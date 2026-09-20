import copy
import json

import pytest

from formslang.project_model import ProjectError, RevisionConflict
from formslang.project_projection import (
    inventory_detail,
    inventory_page,
    overview,
    prepare_projection,
)

DESCRIPTOR = {
    "id": "a" * 32,
    "name": "Order Modernization",
    "description": "Synthetic assessment",
    "client_label": "Example Corp",
    "target_platform": "Oracle APEX",
    "target_version": "26.1",
    "target_representation": "APEXlang",
}
CURRENT = {"status": "CURRENT", "reasons": [], "analysis_revision": "1" * 64}


def entity(identity, kind, name, module, *, risk=None, **attributes):
    if risk is not None:
        attributes["risk"] = {"level": risk, "basis": "Synthetic evidence"}
    return {
        "id": identity,
        "type": kind,
        "name": name,
        "module": module,
        "attributes": attributes,
        "evidence": [],
        "review_state": "PENDING",
    }


@pytest.fixture
def assessment_fixture():
    entities = [
        entity("form:one", "FORM", "ORDERS", "forms-a/orders.xml"),
        entity("form:two", "FORM", "ORDERS", "forms-b/orders.xml"),
        entity("trigger:critical", "TRIGGER", "WHEN-VALIDATE-ITEM", "forms-a/orders.xml",
               risk="CRITICAL", source_text="SECRET_SOURCE_BODY"),
        entity("trigger:high", "TRIGGER", "PRE-INSERT", "forms-a/orders.xml",
               risk="HIGH"),
        entity("package_spec:api", "PACKAGE_SPEC", "ORDER_API", "db/order_api.pks"),
        entity("package_body:api", "PACKAGE_BODY", "ORDER_API", "db/order_api.pkb"),
        entity("package_spec:archive", "PACKAGE_SPEC", "ORDER_API",
               "archive/order_api.pks"),
        entity("package_subprogram:save", "PACKAGE_SUBPROGRAM", "ORDER_API.SAVE",
               "db/order_api.pks", package="ORDER_API", subprogram_type="PROCEDURE"),
        entity("subprogram_body:save", "SUBPROGRAM_BODY", "ORDER_API.SAVE",
               "db/order_api.pkb", package="ORDER_API", subprogram_type="PROCEDURE"),
        entity("table:orders", "TABLE", "ORDERS", "db/tables.sql", columns=[
            {"name": "ORDER_ID"}, {"name": "STATUS"},
        ], constraints=[{"name": "ORDERS_PK"}]),
        entity("view:open_orders", "VIEW", "OPEN_ORDERS", "db/views.sql"),
    ]
    findings = [
        {
            "id": "finding:critical", "entity": "trigger:critical",
            "recommendation": "MANUAL_REVIEW", "execution_verdict": "MANUAL",
            "reason": "Approval control requires a human decision.",
            "classification": ["BUSINESS_RULE"],
            "statements": [{
                "level": "INFERENCE",
                "text": "[DIRECT_DML_BYPASSES_API] Form DML bypasses ORDER_API.",
                "evidence": [],
            }],
            "review_state": "PENDING", "dependencies": [], "evidence": [],
            "unresolved_questions": ["Confirm approval ownership."],
        },
        {
            "id": "finding:high", "entity": "trigger:high",
            "recommendation": "MOVE_TO_PLSQL_API", "execution_verdict": "ASSISTED",
            "reason": "Reuse ORDER_API.", "classification": ["BUSINESS_RULE"],
            "review_state": "PENDING", "dependencies": [], "evidence": [],
            "unresolved_questions": [],
        },
        {
            "id": "finding:unknown", "entity": "package_spec:api",
            "recommendation": "NEW_FUTURE_VALUE", "reason": "Unclassified evidence.",
            "classification": [], "review_state": "PENDING", "dependencies": [],
            "evidence": [], "unresolved_questions": [],
        },
        {
            "id": "finding:auto", "entity": "table:orders",
            "recommendation": "PRESERVE", "execution_verdict": "AUTO",
            "reason": "Preserve observed table.", "classification": [],
            "review_state": "APPROVE", "dependencies": [], "evidence": [],
            "unresolved_questions": [],
        },
    ]
    return {
        "schema_version": "project-assessment/1",
        "project_id": DESCRIPTOR["id"],
        "source_revision": "2" * 64,
        "analysis_revision": "1" * 64,
        "review_revision": 7,
        "analyzed_at": "2026-09-20T12:00:00Z",
        "status": "Current",
        "completion_state": "COMPLETE",
        "target": {
            "platform": "Oracle APEX", "version": "26.1", "representation": "APEXlang",
        },
        "source_manifest": [
            {"source_id": "source:xml-a", "root_id": "forms-a", "relative_path": "orders.xml",
             "representation": "xml", "selected": True, "status": "available"},
            {"source_id": "source:xml-b", "root_id": "forms-b", "relative_path": "orders.xml",
             "representation": "xml", "selected": True, "status": "available"},
            {"source_id": "source:pll", "root_id": "forms-a", "relative_path": "common.pll",
             "representation": "binary", "selected": False, "status": "available"},
            {"source_id": "source:db", "root_id": "db", "relative_path": "order_api.pks",
             "representation": "database", "selected": True, "status": "available"},
        ],
        "inventory": {
            "candidates": 4,
            "forms": {"discovered": 3, "parseable": 2, "analyzed": 2,
                      "fmb_without_xml": 0},
            "database": {"packages": 1, "package_specs": 1, "package_bodies": 1,
                         "tables": 1, "views": 1, "analyzed": 1},
            "warnings": 1,
        },
        "diagnostics": [{
            "source_id": "source:pll", "relative_path": "common.pll",
            "stage": "DISCOVERY", "error_code": "UNSUPPORTED_REPRESENTATION",
            "safe_message": "Library needs a semantic representation.",
            "remediation": "Supply a supported representation.",
        }],
        "engine_identity": {"blueprint": "blueprint/1"},
        "blueprint": {
            "entities": entities,
            "edges": [
                {"id": "edge:contains", "source": "form:one", "target": "trigger:critical",
                 "type": "CONTAINS", "evidence": []},
                {"id": "edge:calls", "source": "trigger:critical", "target": "package_subprogram:save",
                 "type": "CALLS", "evidence": []},
                {"id": "edge:duplicates", "source": "trigger:critical",
                 "target": "subprogram_body:save", "type": "DUPLICATES_LOGIC",
                 "evidence": []},
                {"id": "edge:writes", "source": "subprogram_body:save", "target": "table:orders",
                 "type": "WRITES", "evidence": []},
            ],
            "findings": findings,
            "failures": [],
            "evidence": [],
        },
    }


def test_overview_uses_findings_and_keeps_unknown_visible(assessment_fixture):
    prepared = prepare_projection(DESCRIPTOR, assessment_fixture, CURRENT,
                                  store_scope="store-a")
    result = overview(prepared)

    assert result["inventory"]["modernization_findings"] == 4
    assert result["risk_distribution"] == {
        "CRITICAL": 1, "HIGH": 1, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 2,
    }
    assert result["recommendation_distribution"]["UNKNOWN"] == 1
    assert result["intervention_distribution"] == {
        "AUTO": 1, "ASSISTED": 1, "MANUAL": 1, "UNKNOWN": 1,
    }


def test_overview_counts_reconcile_with_projected_rows(assessment_fixture):
    prepared = prepare_projection(DESCRIPTOR, assessment_fixture, CURRENT,
                                  store_scope="store-a")
    summary = overview(prepared)["inventory"]

    assert summary["forms_modules"] == len(prepared.rows["forms"]) == 2
    assert summary["database_packages"] == len(prepared.rows["packages"]) == 2
    assert summary["package_specs"] == 2
    assert summary["package_bodies"] == 1
    assert summary["dependencies"] == len(prepared.rows["dependencies"]) == 3
    assert summary["business_rule_candidates"] == len(prepared.rows["business_rules"]) == 2
    assert [row["id"] for row in prepared.rows["forms"]] == ["form:one", "form:two"]


def test_overview_excludes_source_bodies_absolute_paths_and_credentials(assessment_fixture):
    assessment_fixture["blueprint"]["entities"][2]["attributes"]["source_path"] = (
        "C:\\customer\\orders.xml"
    )
    assessment_fixture["blueprint"]["entities"][2]["attributes"]["password"] = "TOP_SECRET"

    payload = json.dumps(overview(prepare_projection(
        DESCRIPTOR, assessment_fixture, CURRENT, store_scope="store-a",
    )))

    assert "SECRET_SOURCE_BODY" not in payload
    assert "C:\\\\customer" not in payload
    assert "TOP_SECRET" not in payload
    assert "2026-09-20T12:00:00Z" in payload
    assert "\"review_revision\": 7" in payload


def test_inventory_paginates_stably_and_rejects_revision_mixing(assessment_fixture):
    assessment = copy.deepcopy(assessment_fixture)
    template_entity = assessment["blueprint"]["entities"][2]
    template_finding = assessment["blueprint"]["findings"][0]
    assessment["blueprint"]["entities"] = []
    assessment["blueprint"]["findings"] = []
    for index in range(205):
        node = copy.deepcopy(template_entity)
        node.update(id=f"trigger:{index:03d}", name=f"TRIGGER {index:03d}")
        finding = copy.deepcopy(template_finding)
        finding.update(id=f"finding:{index:03d}", entity=node["id"])
        assessment["blueprint"]["entities"].append(node)
        assessment["blueprint"]["findings"].append(finding)
    prepared = prepare_projection(DESCRIPTOR, assessment, CURRENT, store_scope="store-a")

    first = inventory_page(prepared, "findings")
    second = inventory_page(prepared, "findings", offset=50,
                            expected_revision="1" * 64)

    assert len(first["rows"]) == len(second["rows"]) == 50
    assert first["total"] == second["total"] == 205
    assert {row["id"] for row in first["rows"]}.isdisjoint(
        row["id"] for row in second["rows"]
    )
    with pytest.raises(RevisionConflict):
        inventory_page(prepared, "findings", offset=50,
                       expected_revision="0" * 64)
    with pytest.raises(ProjectError):
        inventory_page(prepared, "findings", limit=201)
    with pytest.raises(ProjectError):
        inventory_page(prepared, "findings", offset=True)


def test_inventory_search_filters_and_sort_are_composable(assessment_fixture):
    prepared = prepare_projection(DESCRIPTOR, assessment_fixture, CURRENT,
                                  store_scope="store-a")

    result = inventory_page(
        prepared, "findings", query="approval",
        filters={"risk": "CRITICAL", "recommendation": "MANUAL_REVIEW",
                 "module": "forms-a", "intervention": "MANUAL"},
        sort="risk",
    )

    assert result["total"] == 1
    assert result["rows"][0]["id"] == "finding:critical"
    assert result["analysis_revision"] == "1" * 64
    assert result["source_revision"] == "2" * 64
    assert result["review_revision"] == 7
    with pytest.raises(ProjectError):
        inventory_page(prepared, "findings", filters={"risk": "IMPOSSIBLE"})
    with pytest.raises(ProjectError):
        inventory_page(prepared, "unknown-category")


def test_priority_queue_exposes_factors_and_reconciles_with_overview(assessment_fixture):
    prepared = prepare_projection(DESCRIPTOR, assessment_fixture, CURRENT,
                                  store_scope="store-a")

    queue = inventory_page(prepared, "findings", filters={"priority": "unresolved"})
    summary = overview(prepared)["priority"]

    assert summary["total"] == queue["total"] == 3
    assert summary["first_finding_id"] == queue["rows"][0]["id"] == "finding:critical"
    assert queue["rows"][0]["priority_factors"][0] == "UNRESOLVED_CRITICAL"
    assert "MANUAL_INTERVENTION" in queue["rows"][0]["priority_factors"]
    assert "API_BYPASS" in queue["rows"][0]["priority_factors"]
    assert "DUPLICATED_LOGIC" in queue["rows"][0]["priority_factors"]
    assert "CROSS_MODULE_IMPACT" in queue["rows"][0]["priority_factors"]


def test_selected_forms_representations_exclude_unselected_binaries(assessment_fixture):
    prepared = prepare_projection(DESCRIPTOR, assessment_fixture, CURRENT,
                                  store_scope="store-a")

    result = overview(prepared)

    assert result["inventory"]["forms_representations"] == 2
    assert result["source_coverage"]["forms"]["representations"] == 2


def test_package_highest_risk_comes_from_related_findings(assessment_fixture):
    assessment_fixture["blueprint"]["entities"][4]["attributes"]["risk"] = {
        "level": "MEDIUM", "basis": "Package ownership requires review",
    }
    prepared = prepare_projection(DESCRIPTOR, assessment_fixture, CURRENT,
                                  store_scope="store-a")

    package = next(row for row in prepared.rows["packages"]
                   if row["id"] == "package:db:order_api")

    assert package["findings"] == 1
    assert package["highest_risk"] == "MEDIUM"


def test_overview_warnings_are_bounded_with_total(assessment_fixture):
    assessment_fixture["diagnostics"] = [
        {
            "source_id": f"source:{index}", "relative_path": f"bad-{index}.xml",
            "stage": "FORMS_PARSING", "error_code": "INVALID_XML",
            "safe_message": f"Source {index} could not be parsed.",
            "remediation": "Repair or exclude the source.",
        }
        for index in range(75)
    ]
    result = overview(prepare_projection(
        DESCRIPTOR, assessment_fixture, CURRENT, store_scope="store-a",
    ))

    assert len(result["warnings"]) == 50
    assert result["warning_summary"] == {"total": 75, "shown": 50, "truncated": True}


def test_inventory_detail_is_bounded_and_excludes_source_body(assessment_fixture):
    prepared = prepare_projection(DESCRIPTOR, assessment_fixture, CURRENT,
                                  store_scope="store-a")

    result = inventory_detail(prepared, "forms", "form:one",
                              expected_revision="1" * 64)
    payload = json.dumps(result)

    assert result["item"]["id"] == "form:one"
    assert result["dependencies_total"] == 0
    assert result["related_findings_total"] == 0
    assert "source_text" not in payload
    with pytest.raises(LookupError):
        inventory_detail(prepared, "forms", "form:missing")
    with pytest.raises(RevisionConflict):
        inventory_detail(prepared, "forms", "form:one", expected_revision="0" * 64)
