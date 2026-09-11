"""Evidence, review and reproducibility contracts for application blueprints."""

from __future__ import annotations

import copy
import json

import pytest

from formslang import blueprint as bp
from formslang import blueprint_ai, blueprint_io, plsql
from formslang.ai import EchoProvider
from formslang.cli import main
from formslang.model import Block, FormModule, Item, ProgramUnit, Trigger
from formslang.parser import parse_xml
from formslang.store import Store


def form(name="ORDERS", code="BEGIN XX_CREDIT_PKG.CHECK_LIMIT(:ORDERS.AMOUNT); END;"):
    return FormModule(name=name, source_path=name + ".xml",
                      triggers=[Trigger("WHEN-VALIDATE-ITEM", code, "form", "")],
                      blocks=[Block(name="ORDERS", items=[Item(name="AMOUNT")])])


def event_names(source, kind="CALL"):
    return {e["name"] for e in plsql.evidence(source)["events"] if e["kind"] == kind}


@pytest.mark.parametrize("literal", ["'XX_BAD.RUN(); -- test'", "q'[XX_BAD.RUN();]'", "q'{a'' -- XX_BAD.RUN();}'", "'/* XX_BAD.RUN(); */'"])
def test_comments_strings_and_alternative_quotes_are_not_dependencies(literal):
    source = f"BEGIN MESSAGE({literal}); -- XX_BAD.RUN();\n/* XX_BAD.RUN(); */ APPS.XX_REAL.RUN(); END;"
    assert event_names(source) == {"MESSAGE", "APPS.XX_REAL.RUN"}


def test_declarations_and_sql_target_column_lists_are_not_calls():
    source = "PROCEDURE p(x NUMBER) IS a VARCHAR2(10); BEGIN INSERT INTO orders(id) VALUES(1); helper; END;"
    assert event_names(source) == {"HELPER"}
    assert event_names(source, "WRITES") == {"ORDERS"}


def test_reads_writes_cte_alias_and_dynamic_sql():
    source = """BEGIN
      WITH local_rows AS (SELECT id FROM source_table)
      SELECT id INTO v FROM local_rows JOIN another_table ON 1=1;
      DELETE FROM destination;
      UPDATE destination SET id=1;
      MERGE INTO destination USING source_table ON (1=1) WHEN MATCHED THEN UPDATE SET id=2;
      EXECUTE IMMEDIATE 'DELETE FROM hidden_table';
    END;"""
    assert event_names(source, "READS") == {"SOURCE_TABLE", "ANOTHER_TABLE"}
    assert event_names(source, "WRITES") == {"DESTINATION"}
    assert event_names(source, "DYNAMIC_SQL") == {"EXECUTE IMMEDIATE"}
    assert "HIDDEN_TABLE" not in json.dumps(plsql.evidence(source)["events"])


def test_literals_are_resolved_per_call_site_and_locations_are_body_relative():
    events = plsql.evidence("-- comment\nGO_ITEM('ORDERS.AMOUNT');\nGO_ITEM(v_item);\nOPEN_FORM(q'[OTHER]');")["events"]
    literal = [e for e in events if e["kind"] == "LITERAL_TARGET"]
    unknown = [e for e in events if e["kind"] == "UNRESOLVED_TARGET"]
    assert [(e["name"], e["line"]) for e in literal] == [("ORDERS.AMOUNT", 2), ("OTHER", 4)]
    assert [(e["name"], e["line"]) for e in unknown] == [("GO_ITEM", 3)]


def test_sql_expression_from_is_not_a_table_and_merge_using_is_a_read():
    source = "SELECT EXTRACT(YEAR FROM invoice_date), TRIM('x' FROM value) FROM invoices; MERGE INTO dest USING src ON (1=1) WHEN MATCHED THEN UPDATE SET x=1;"
    assert event_names(source, "READS") == {"INVOICES", "SRC"}
    assert event_names(source, "WRITES") == {"DEST"}


def test_risk_catalog_uses_same_evidence_as_dependency_graph():
    source = "BEGIN MESSAGE(q'[It's only text: HOST('rm');]'); END;"
    measured = plsql.analyze_evidence(source)
    assert "HOST" not in measured.builtins
    assert measured.builtins["MESSAGE"] == 1
    payload = bp.build([form(code=source)])
    assert not any(n["name"] == "HOST" for n in payload["entities"])
    assert all("INTEGRATION" not in f["classification"] for f in payload["findings"])


def test_query_source_expression_is_not_invented_as_a_database_object():
    module = form()
    module.blocks[0].query_data_source_name = "(select * from app.orders)"
    module.blocks[0].query_data_source_type = "FROM clause query"
    payload = bp.build([module])
    assert not any(n["name"].startswith("(SELECT") for n in payload["entities"])
    assert any(n["name"] == "APP.ORDERS" for n in payload["entities"])
    events = plsql.evidence("DELETE FROM orders@remote; SELECT * FROM orders@remote;")
    assert not any(e["kind"] in {"READS", "WRITES"} for e in events["events"])
    assert len(events["unknown"]) == 2


def test_twenty_forms_share_one_qualified_package_and_api_score_is_explainable():
    result = bp.build([form(f"FORM_{i}", "BEGIN APPS.XX_PKG.SAVE(); END;") for i in range(20)])
    package = [n for n in result["entities"] if n["type"] == "PACKAGE_REFERENCE"]
    assert len(package) == 1
    assert package[0]["name"] == "APPS.XX_PKG"
    candidate = result["api_candidates"][0]
    assert len(candidate["forms"]) == len(candidate["callers"]) == 20
    assert candidate["score"] == sum(candidate["components"].values()) == 13
    assert candidate["observed_callee_coupling"] == "UNKNOWN"
    assert all(f["recommendation"] != "PRESERVE" for f in result["findings"] if f["entity"] == package[0]["id"])


def test_schemas_are_not_collapsed():
    result = bp.build([form("A", "BEGIN ONE.PKG.RUN(); END;"), form("B", "BEGIN TWO.PKG.RUN(); END;")])
    assert {n["name"] for n in result["entities"] if n["type"] == "PACKAGE_REFERENCE"} == {"ONE.PKG", "TWO.PKG"}
    assert not result["api_candidates"]


def test_local_bare_calls_recursion_and_cross_form_navigation():
    a = form("A", "BEGIN helper; OPEN_FORM('B'); END;")
    a.program_units = [ProgramUnit("helper", "Procedure", "PROCEDURE helper IS BEGIN helper; END;")]
    result = bp.build([a, form("B", "NULL;")])
    assert any(e["type"] == "USES_PROGRAM_UNIT" and e["source"] == e["target"] for e in result["edges"])
    b_id = next(n["id"] for n in result["entities"] if n["type"] == "FORM" and n["name"] == "B")
    assert any(e["type"] == "OPENS_FORM" and e["target"] == b_id for e in result["edges"])


def test_duplicate_module_names_have_distinct_local_ids_and_ambiguous_navigation():
    a, b = form(), form()
    result = bp.build([a, b], source_keys=["one/ORDERS.xml", "two/ORDERS.xml"])
    assert result["summary"]["entities"]["FORM"] == 2
    assert result["summary"]["entities"]["TRIGGER"] == 2
    with pytest.raises(ValueError, match="uniquely"):
        bp.build([a, b])


def test_business_rule_is_candidate_based_on_conditional_rejection_not_trigger_name():
    simple = bp.build([form(code="BEGIN GO_ITEM('ORDERS.AMOUNT'); END;")])
    assert not any(n["type"] == "BUSINESS_RULE" for n in simple["entities"])
    source = "IF :ORDERS.AMOUNT > XX_CREDIT_PKG.GET_LIMIT(:ORDERS.CUSTOMER_ID) THEN MESSAGE('too high'); RAISE FORM_TRIGGER_FAILURE; END IF;"
    result = bp.build([form(code=source)])
    rule = next(n for n in result["entities"] if n["type"] == "BUSINESS_RULE")
    assert rule["attributes"]["classification"] == "INFERENCE"
    assert rule["attributes"]["inputs"] == ["ORDERS.AMOUNT", "ORDERS.CUSTOMER_ID"]
    evidence = [e["text"] for e in result["evidence"] if e["id"] in rule["evidence"]]
    assert any(text.startswith("IF :ORDERS.AMOUNT") for text in evidence)
    assert "RAISE FORM_TRIGGER_FAILURE" in evidence
    finding = bp.explore(result, node=rule["id"])["selected"]["finding"]
    assert finding["recommendation"] == "REFACTOR"
    assert finding["execution_verdict"] == "AUTO"


def test_short_unit_is_kept_and_mixed_body_is_not_dropped():
    result = bp.build([form(code="SYNCHRONIZE;")])
    unit = next(f for f in result["findings"] if f.get("execution_verdict"))
    assert unit["recommendation"] == "DROP"
    mixed = bp.build([form(code="BEGIN SYNCHRONIZE; INSERT INTO orders(id) VALUES(1); END;")])
    assert all(f["recommendation"] != "DROP" for f in mixed["findings"])


def test_enterprise_detection_is_opt_in_and_never_claims_installation():
    module = form(code="BEGIN APPS.FND_GLOBAL.APPS_INITIALIZE(1,2,3); XX_HELPER.RUN(); END;")
    assert bp.build([module])["enterprise_context"] == {"enabled": False}
    ctx = bp.build([module], enterprise=True)["enterprise_context"]
    assert ctx["detections"] and all(d["level"] == "INFERENCE" and d["evidence"] for d in ctx["detections"])
    assert "do not establish" in ctx["statement"]
    assert not bp.build([form(code="BEGIN APPLY(); END;")], enterprise=True)["enterprise_context"]["detections"]


def test_supplied_metadata_and_body_are_provenance_not_live_database_proof():
    result = bp.build([form()], metadata=[{"name": "XX_CREDIT_PKG", "type": "PACKAGE", "body": "PROCEDURE check_limit IS BEGIN COMMIT; END;"}])
    n = next(n for n in result["entities"] if n["type"] == "DATABASE_OBJECT")
    assert n["attributes"]["provenance"] == "USER_SUPPLIED_METADATA"
    f = next(f for f in result["findings"] if f["entity"] == n["id"])
    assert "TRANSACTION_CONTROL" in f["classification"]
    assert f["recommendation"] == "MANUAL_REVIEW"


def test_reports_are_reproducible_and_escape_untrusted_source(tmp_path):
    module = form("</script><img src=x onerror=alert(1)>")
    result = bp.build([module], source_keys=["module.xml"])
    a = blueprint_io.write(result, tmp_path / "a")
    b = blueprint_io.write(result, tmp_path / "b")
    left = {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    right = {p.relative_to(b).as_posix(): p.read_bytes() for p in b.rglob("*") if p.is_file()}
    assert left == right
    assert len(left) == 16
    assert b"</script><img" not in left["blueprint.html"]
    assert b"onerror" not in left["diagrams/dependencies.mmd"]
    assert b"https://" not in left["blueprint.html"]
    hostile = bp.build([form("![tracking](https://example.invalid/image)")])
    assert all("![tracking](" not in text for text in blueprint_io.documents(hostile).values())


def test_module_order_and_machine_path_do_not_change_blueprint():
    a, b = form("A"), form("B")
    first = bp.build([a, b], source_keys=["a.xml", "b.xml"])
    a.source_path = "/different/machine/a.xml"
    b.source_path = "/different/machine/b.xml"
    second = bp.build([b, a], source_keys=["b.xml", "a.xml"])
    assert bp.canonical(first) == bp.canonical(second)


def test_review_survives_reopen_but_source_change_invalidates_it(tmp_path):
    path = tmp_path / "session.db"
    result = bp.build([form()])
    f = result["findings"][0]
    store = Store(path)
    store.init_session("Existing session")
    store.save_blueprint(result)
    store.review_blueprint(entity=f["entity"], revision=f["revision"], action="APPROVE", reviewer="reviewer", comment="Reviewed architecture")
    assert store.blueprint()["findings"][0]["coverage"]["status"] == "REQUIRES_REVIEW"
    assert store.task_ids() == []  # Architecture approval never approves conversion.
    store.close()
    store = Store(path)
    try:
        assert store.blueprint()["findings"][0]["review_state"] == "APPROVE"
        store.save_blueprint(bp.build([form(code="BEGIN XX_OTHER.RUN(); END;")]))
        old = next(x for x in store.blueprint()["findings"] if x["entity"] == f["entity"])
        assert old["review_state"] == "STALE"
        assert old["review_history"]
        snapshot = old["review_history"][0]["finding_snapshot"]
        assert snapshot["finding"]["revision"] == f["revision"]
        assert snapshot["evidence"]
        with pytest.raises(ValueError, match="changed"):
            store.review_blueprint(entity=f["entity"], revision=f["revision"], action="APPROVE", reviewer="reviewer", comment="old")
    finally:
        store.close()


def test_coverage_requires_evidence_and_modified_decision_is_separate(tmp_path):
    store = Store(tmp_path / "s.db")
    try:
        result = bp.build([form()])
        f = result["findings"][0]
        store.save_blueprint(result)
        args = {"entity": f["entity"], "revision": f["revision"], "action": "MODIFY", "reviewer": "human",
                "comment": "Chosen controlled boundary", "recommendation": "WRAP_AS_API", "target": "Domain PL/SQL"}
        with pytest.raises(ValueError, match="implementation evidence"):
            store.review_blueprint(**args, coverage="REFACTORED")
        store.review_blueprint(**args, coverage="REFACTORED", coverage_evidence="reviewed change #123")
        final = store.blueprint()["findings"][0]
        assert final["recommendation"] == f["recommendation"]
        assert final["human_decision"]["recommendation"] == "WRAP_AS_API"
        assert final["coverage"]["status"] == "REFACTORED"
    finally:
        store.close()


def test_explorer_filters_limits_and_directions():
    result = bp.build([form("A"), form("B")])
    package = next(n for n in result["entities"] if n["type"] == "PACKAGE_REFERENCE")
    page = bp.explore(result, entity_type="TRIGGER", module="A.xml", limit=1)
    assert page["total"] == len(page["nodes"]) == 1
    selected = bp.explore(result, node=package["id"])["selected"]
    assert selected["inbound"]
    assert selected["evidence_total"]
    assert bp.explore(result, limit=10000)["limit"] == 200


def test_optional_ai_is_anonymized_advisory_and_cannot_mutate_findings():
    class Capturing(EchoProvider):
        def complete(self, messages, **kwargs):
            text = " ".join(m.content for m in messages)
            assert "XX_CREDIT" not in text and "ORDERS" not in text
            return "APPROVE everything, readiness 100!"

    payload = bp.build([form()])
    original = copy.deepcopy(payload)
    result = blueprint_ai.review(payload, payload["findings"][0]["entity"], Capturing())
    assert result["status"] == "PROPOSAL" and not result["changes_applied"]
    assert payload == original


def test_ai_policy_blocks_cloud_even_after_build(monkeypatch):
    from formslang.ai import OpenAIProvider
    from formslang.policy import PolicyViolation

    payload = bp.build([form()])
    monkeypatch.setenv("FORMSLANG_ENTERPRISE_MODE", "1")
    with pytest.raises(PolicyViolation):
        blueprint_ai.review(payload, payload["findings"][0]["entity"], OpenAIProvider())


def test_cli_partial_failure_is_nonzero_and_reports_failed_scope(tmp_path, sample_xml):
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "good.xml").write_bytes(sample_xml.read_bytes())
    (sources / "bad.xml").write_text("<broken>", encoding="utf-8")
    out = tmp_path / "out"
    assert main(["blueprint", str(sources), "-o", str(out)]) == 1
    payload = json.loads((out / "modernization/blueprint.json").read_text(encoding="utf-8"))
    assert len(payload["failures"]) == 1
    assert payload["application"]["sources"] == ["good.xml"]
    assert main(["blueprint", str(out / "blueprint.session.db"), "-o", str(out)]) == 1


def test_existing_parser_coverage_and_plan_have_no_dangling_evidence(sample_xml):
    result = bp.build([parse_xml(sample_xml)])
    ids = {e["id"] for e in result["evidence"]}
    nodes = {n["id"] for n in result["entities"]}
    for edge in result["edges"]:
        assert edge["source"] in nodes and edge["target"] in nodes
        assert set(edge["evidence"]) <= ids
    for f in result["findings"]:
        assert set(f["evidence"]) <= ids
        assert f["human_review_required"]
        assert f["coverage"]["status"] == "REQUIRES_REVIEW"


def test_package_specification_and_body_have_independent_review_identity():
    from formslang.convert import build_tasks

    module = form(code="NULL;")
    module.program_units = [ProgramUnit("API", "Package Spec", "PACKAGE api IS PROCEDURE save; END;"),
                            ProgramUnit("API", "Package Body", "PACKAGE BODY api IS PROCEDURE save IS BEGIN NULL; END; END;")]
    result = bp.build([module])
    units = [n for n in result["entities"] if n["type"] == "PROGRAM_UNIT"]
    assert len(units) == 2
    verdicts = {t.verdict for t in build_tasks(module) if t.kind == "program_unit"}
    assert {n["attributes"]["migration_verdict"] for n in units} == verdicts
    spec = next(n for n in units if n["attributes"]["subtype"] == "Package Spec")
    finding = next(f for f in result["findings"] if f["entity"] == spec["id"])
    assert finding["recommendation"] != "PRESERVE"


def test_engine_change_invalidates_review_and_coverage(tmp_path):
    store = Store(tmp_path / "s.db")
    try:
        payload = bp.build([form()])
        f = payload["findings"][0]
        store.save_blueprint(payload)
        store.review_blueprint(entity=f["entity"], revision=f["revision"], action="APPROVE",
                               reviewer="human", comment="checked", coverage="CONVERTED", coverage_evidence="change-1")
        payload["engine_version"] = "older-engine"
        store.save_blueprint(payload)
        result = store.blueprint()
        assert result["stale_engine"]
        assert result["findings"][0]["review_state"] == "STALE"
        assert result["findings"][0]["coverage"]["status"] == "REQUIRES_REVIEW"
    finally:
        store.close()


def test_readiness_uses_conversion_reviews_not_architecture_approvals(tmp_path):
    from formslang.convert import build_tasks
    from formslang.store import APPROVED

    module = form(code="BEGIN MESSAGE('hello'); END;")
    store = Store(tmp_path / "s.db")
    try:
        tasks = build_tasks(module)
        store.add_tasks(tasks)
        payload = bp.build([module])
        store.save_blueprint(payload)
        before = store.blueprint()["readiness"]["score"]
        f = payload["findings"][0]
        store.review_blueprint(entity=f["entity"], revision=f["revision"], action="APPROVE",
                               reviewer="architect", comment="proposal only")
        assert store.blueprint()["readiness"]["score"] == before
        store.set_decision(tasks[0].id, APPROVED, reviewer="developer")
        after = store.blueprint()["readiness"]["score"]
        assert after == before + 55
        store.save_blueprint(bp.build([form(code="BEGIN MESSAGE('changed'); END;")]))
        assert store.blueprint()["readiness"]["score"] < after
    finally:
        store.close()


def test_binary_adapter_is_reused_and_same_basenames_have_distinct_caches(tmp_path, sample_xml, monkeypatch):
    sources = tmp_path / "sources"
    for name in ("a", "b"):
        folder = sources / name
        folder.mkdir(parents=True)
        (folder / "orders.fmb").write_bytes(name.encode())
    caches = []

    def convert(path, out, toolchain):
        caches.append(out)
        return sample_xml, ""

    monkeypatch.setattr(blueprint_io, "detect_toolchain", lambda *_: object())
    monkeypatch.setattr(blueprint_io, "convert_module", convert)
    result = blueprint_io.load(sources, tmp_path / "out")
    assert len(set(caches)) == 2
    assert result["summary"]["entities"]["FORM"] == 2
    assert not result["failures"]


def test_output_directory_symlink_cannot_escape(tmp_path):
    out, foreign = tmp_path / "out", tmp_path / "foreign"
    out.mkdir()
    foreign.mkdir()
    try:
        (out / "modernization").symlink_to(foreign, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable to this Windows account")
    with pytest.raises(ValueError, match="escapes"):
        blueprint_io.write(bp.build([form()]), out)
    assert not list(foreign.iterdir())
