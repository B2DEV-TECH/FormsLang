"""ailayout: the AI layout assistant -- which regions it is asked about, what
it is told, what it accepts back, and what stands when it cannot help."""

from __future__ import annotations

import json

import pytest

from formslang import ai, ailayout, cli, policy
from formslang.ai import EchoProvider, ProviderError
from formslang.apexlang import ApexExportConfig, export_apexlang, last_export_config
from formslang.apexlayout import build_layout
from formslang.convert import Proposal, build_tasks
from formslang.formui import render_html
from formslang.model import Block, Canvas, FormModule, Item
from formslang.parser import parse_xml
from formslang.store import APPROVED, Store


def _module(items, width=600) -> FormModule:
    return FormModule(
        name="M",
        canvases=[Canvas(name="CV", width=width, height=200)],
        blocks=[Block(name="B", items=items)],
    )


def _item(name, x, y=20, width=80, **kw) -> Item:
    return Item(
        name=name, item_type="Text Item", canvas="CV", x=x, y=y, width=width, height=14,
        column_name=f"COL_{name}", **kw,
    )


def _dense(**kw) -> FormModule:
    """Five fields on one Forms row: nothing to push or wrap, but dense enough
    to be worth a second opinion. The rules give them columns 1,3,5,7,9."""
    return _module([_item(n, x, **kw) for n, x in zip("ABCDE", (0, 100, 200, 300, 400))])


def _rules(module) -> list[tuple[int, int]]:
    return [(p.grid.column, p.grid.span) for p in build_layout(module).roots[0].body]


def user_json(messages) -> dict:
    return json.loads(next(m.content for m in messages if m.role == "user"))


def plan_for(req: dict, span: int = 1) -> dict:
    """A plan built from a request: every control of every Forms row, one
    column each, left to right -- a placement the rules never produce."""
    regions = []
    for region in req["regions"]:
        rows = []
        for row in region["rows"]:
            cells: list[dict] = []
            for control in row:
                if cells and cells[-1]["column"] + 2 * span - 1 > 12:
                    rows.append({"cells": cells})
                    cells = []
                column = 1 if not cells else cells[-1]["column"] + span
                cells.append(
                    {"name": control["name"], "column": column, "columnSpan": span,
                     "labelColumnSpan": 0}
                )
            rows.append({"cells": cells})
        regions.append({"id": region["id"], "rows": rows})
    return {"regions": regions, "notes": "one column each"}


class Planner(ai.Provider):
    """Records each request and answers with ``answer`` -- a dict, a string,
    or, by default, a plan built from the request itself."""

    type_id = "planner"

    def __init__(self, answer=None):
        super().__init__(model="planner-1")
        self.answer = answer
        self.requests: list[dict] = []

    def complete(self, messages, max_tokens=0):
        req = user_json(messages)
        self.requests.append(req)
        if isinstance(self.answer, str):
            return self.answer
        return json.dumps(self.answer if self.answer is not None else plan_for(req))


# -- which regions ------------------------------------------------------------


def test_a_region_the_rules_placed_cleanly_needs_no_assistant():
    layout = build_layout(_module([_item("A", 0), _item("B", 200)]))
    assert ailayout.hard_regions(layout) == []


def test_a_dense_row_or_a_concession_makes_a_region_hard():
    assert [n.id for n in ailayout.hard_regions(build_layout(_dense()))] == ["cv"]
    pushed = build_layout(_module([_item("A", 0, width=100), _item("B", 60, width=100)]))
    assert [n.id for n in ailayout.hard_regions(pushed)] == ["cv"]


# -- what is sent ----------------------------------------------------------------


def test_the_request_carries_geometry_and_the_rules_placement_but_no_code():
    layout = build_layout(_dense())
    req = ailayout.request(layout, ailayout.hard_regions(layout))
    text = json.dumps(req)

    assert req["grid"] == 12 and [r["id"] for r in req["regions"]] == ["cv"]
    rows = req["regions"][0]["rows"]
    assert [[c["name"] for c in row] for row in rows] == [["P1_A", "P1_B", "P1_C", "P1_D", "P1_E"]]
    first = rows[0][0]
    assert first["rules"] == {"column": 1, "columnSpan": 2, "labelColumnSpan": 0, "flags": []}
    assert (first["x"], first["width"], first["type"], first["kind"]) == (
        0, 80, "textField", "Text Item"
    )
    assert "COL_" not in text  # no column names, no code, no data
    assert ailayout.digest(req) == ailayout.digest(json.loads(text))

    system, user = ailayout.messages(req)
    assert system.role == "system" and "front-end developer" in system.content
    assert user.role == "user" and json.loads(user.content) == req


# -- the plan ---------------------------------------------------------------------


def test_parse_plan_takes_the_json_out_of_fences_and_prose():
    plan = {"regions": [], "notes": "n"}
    assert ailayout.parse_plan(json.dumps(plan)) == plan
    assert ailayout.parse_plan("```json\n" + json.dumps(plan) + "\n```") == plan
    assert ailayout.parse_plan("Here is the plan: " + json.dumps(plan) + " -- done") == plan
    assert ailayout.parse_plan("no plan here") is None
    assert ailayout.parse_plan("[1, 2]") is None


def test_validate_plan_rejects_what_the_grid_cannot_take():
    layout = build_layout(_dense())
    regions = ailayout.hard_regions(layout)
    good = plan_for(ailayout.request(layout, regions))
    assert ailayout.validate_plan(good, regions) == []

    def broken(mutate) -> list[str]:
        plan = json.loads(json.dumps(good))
        mutate(plan)
        return ailayout.validate_plan(plan, regions)

    def cells(plan) -> list[dict]:
        return plan["regions"][0]["rows"][0]["cells"]

    assert "unknown control" in broken(lambda p: cells(p)[0].update(name="P1_ZZ"))[0]
    assert "overlaps" in broken(lambda p: cells(p)[1].update(column=1))[0]
    assert "labelColumnSpan" in broken(lambda p: cells(p)[0].update(labelColumnSpan=1))[0]
    assert "column must be" in broken(lambda p: cells(p)[0].update(column=0))[0]
    assert "columnSpan must be" in broken(lambda p: cells(p)[-1].update(columnSpan=12))[0]
    assert "not placed: P1_E" in broken(lambda p: cells(p).pop())[0]
    assert "placed twice: P1_A" in broken(
        lambda p: cells(p).append(dict(cells(p)[0], column=12))
    )[0]
    assert "a left label needs" in broken(lambda p: cells(p)[0].update(label="left"))[0]
    assert "label must be" in broken(lambda p: cells(p)[0].update(label="inside"))[0]
    assert "not in the plan" in broken(lambda p: p["regions"].clear())[0]
    assert "planned twice" in broken(lambda p: p["regions"].append(p["regions"][0]))[0]
    assert "unknown region" in broken(lambda p: p["regions"][0].update(id="nope"))[0]
    assert "no rows" in broken(lambda p: p["regions"][0].update(rows=[]))[0]
    assert ailayout.validate_plan({"regions": "x"}, regions) == [
        "plan is not an object with a regions list"
    ]
    assert ailayout.validate_plan(None, regions) == ["plan is not an object with a regions list"]


def test_apply_plan_puts_the_cells_on_the_layout_in_reading_order():
    layout = build_layout(_dense(prompt="Cod"))
    regions = ailayout.hard_regions(layout)
    plan = {
        "regions": [{
            "id": "cv",
            "rows": [
                {"cells": [
                    {"name": "P1_E", "column": 1, "columnSpan": 6},
                    {"name": "P1_D", "column": 7, "columnSpan": 6},
                ]},
                {"cells": [
                    {"name": "P1_A", "column": 2, "columnSpan": 3, "labelColumnSpan": 1,
                     "label": "left"},
                    {"name": "P1_B", "column": 5, "columnSpan": 4, "label": "above"},
                    {"name": "P1_C", "column": 9, "columnSpan": 4},
                ]},
            ],
        }],
        "notes": "wide pair first",
    }
    assert ailayout.validate_plan(plan, regions) == []

    ailayout.apply_plan(plan, regions)
    body = regions[0].body

    assert [p.apex_name for p in body] == ["P1_E", "P1_D", "P1_A", "P1_B", "P1_C"]
    assert [(p.grid.new_row, p.grid.column, p.grid.span) for p in body] == [
        (True, 1, 6), (False, 7, 6), (True, 2, 3), (False, 5, 4), (False, 9, 4)
    ]
    assert all(p.placement == "ai" and p.flags == [] for p in body)
    assert [p.sequence for p in body] == [10, 20, 30, 40, 50]
    by_name = {p.apex_name: p for p in body}
    assert (by_name["P1_A"].side, by_name["P1_A"].label_span, by_name["P1_A"].align) == (
        "left", 1, "right"
    )
    assert (by_name["P1_B"].side, by_name["P1_B"].label_span, by_name["P1_B"].align) == (
        "above", 0, "left"
    )
    assert (by_name["P1_C"].side, by_name["P1_C"].label_span) == ("above", 0)


# -- at export time -----------------------------------------------------------------


def test_assist_applies_a_good_plan_and_caches_it_on_the_session(tmp_path):
    store = Store(tmp_path / "s.db")
    provider = Planner()
    layout = build_layout(_dense())

    summary = ailayout.assist(layout, provider, store, 1)

    assert (summary["status"], summary["provider"], summary["model"]) == (
        "applied", "planner", "planner-1"
    )
    assert summary["regions"] == ["cv"] and summary["notes"] == "one column each"
    assert layout.ai is summary
    assert [(p.grid.column, p.grid.span, p.placement) for p in layout.roots[0].body] == [
        (1, 1, "ai"), (2, 1, "ai"), (3, 1, "ai"), (4, 1, "ai"), (5, 1, "ai")
    ]
    cached = ailayout.cached_plan(store, 1)
    assert cached["digest"] == summary["digest"] and cached["version"] == ailayout.PLAN_VERSION
    assert cached["plan"]["notes"] == "one column each" and cached["provider"] == "planner"
    assert len(provider.requests) == 1

    # the next export replays the cache: no call, even to a provider that would fail
    again = build_layout(_dense())
    bad = Planner(answer="garbage")
    replay = ailayout.assist(again, bad, store, 1)
    assert replay["status"] == "cached" and replay["digest"] == summary["digest"]
    assert replay["notes"] == "one column each" and bad.requests == []
    assert [p.grid.column for p in again.roots[0].body] == [1, 2, 3, 4, 5]


def test_the_preview_replays_the_cached_plan_when_it_still_matches(tmp_path):
    store = Store(tmp_path / "s.db")
    ailayout.assist(build_layout(_dense()), Planner(), store, 1)
    cached = ailayout.cached_plan(store, 1)

    layout = build_layout(_dense())
    assert ailayout.apply_cached(layout, cached) is True
    assert layout.ai["status"] == "cached" and layout.ai["provider"] == "planner"
    assert [p.grid.column for p in layout.roots[0].body] == [1, 2, 3, 4, 5]
    assert 'style="grid-column:5/span 1"' in render_html(_dense(), ai_plan=cached)
    assert 'style="grid-column:9/span 2"' in render_html(_dense())

    # a different screen: the plan is stale and the rules stand
    other = build_layout(_module([_item(n, x) for n, x in zip("ABCDE", (0, 100, 200, 300, 450))]))
    assert ailayout.apply_cached(other, cached) is False and other.ai == {}
    assert ailayout.apply_cached(build_layout(_dense()), None) is False


def test_assist_keeps_the_rules_when_the_provider_is_offline_fails_or_answers_badly(tmp_path):
    store = Store(tmp_path / "s.db")
    rules = _rules(_dense())

    class Failing(ai.Provider):
        type_id = "failing"

        def complete(self, messages, max_tokens=0):
            raise ProviderError("boom")

    half = {"regions": [{"id": "cv", "rows": [{"cells": [
        {"name": "P1_A", "column": 1, "columnSpan": 12}
    ]}]}]}
    cases = [
        (EchoProvider(), "offline", "no AI provider configured"),
        (Failing(), "error", "provider error: boom"),
        (Planner(answer="I would rather not."), "rejected", "plan rejected: plan is not an object"),
        (Planner(answer=half), "rejected", "controls not placed: P1_B, P1_C, P1_D, P1_E"),
    ]
    for provider, status, reason in cases:
        layout = build_layout(_dense())
        summary = ailayout.assist(layout, provider, store, 1)
        assert summary["status"] == status, (provider.type_id, summary)
        assert reason in summary["reason"]
        assert [(p.grid.column, p.grid.span) for p in layout.roots[0].body] == rules
        assert all(p.placement == "rules" for p in layout.roots[0].body)
        assert ailayout.cached_plan(store, 1) is None


def test_assist_says_so_when_no_region_needed_it(tmp_path):
    store = Store(tmp_path / "s.db")
    provider = Planner()
    layout = build_layout(_module([_item("A", 0), _item("B", 200)]))

    summary = ailayout.assist(layout, provider, store, 1)

    assert summary["status"] == "not-needed" and summary["regions"] == []
    assert "without a compromise" in summary["reason"] and provider.requests == []


def test_enterprise_mode_blocks_a_cloud_provider_before_anything_is_sent(tmp_path, monkeypatch):
    monkeypatch.setenv(policy.ENTERPRISE_ENV, "1")
    store = Store(tmp_path / "s.db")
    provider = Planner()  # no base_url: fail-closed, classed as cloud

    with pytest.raises(policy.PolicyViolation):
        ailayout.assist(build_layout(_dense()), provider, store, 1)
    assert provider.requests == []


# -- the export and the CLI ----------------------------------------------------------


def _manifest(out_dir) -> dict:
    path = next(out_dir.rglob("apexlang-manifest.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def test_export_with_ai_layout_writes_the_assistants_summary_to_the_manifest(tmp_path):
    module = _dense()
    store = Store(tmp_path / "M.session.db")
    store.init_session(module.name, "M_fmb.xml")
    provider = Planner()

    export_apexlang(
        store, module, tmp_path / "ai", {"app_id": "300", "alias": "dense", "ai_layout": "1"},
        provider,
    )
    manifest = _manifest(tmp_path / "ai")
    layout = manifest["layout"]

    assert layout["ai_layout"]["status"] == "applied"
    assert layout["ai_layout"]["provider"] == "planner"
    assert layout["mapping_report"]["totals"]["placed_by_ai"] == 5
    entry = next(c for c in layout["mapping_report"]["controls"] if c["target"]["name"] == "P1_A")
    assert entry["target"]["placement"] == "ai" and entry["status"] == "approximation"
    assert any("AI layout assistant" in a for a in entry["approximations"])
    assert "--ai-layout" in json.dumps(manifest)
    assert last_export_config(store).get("ai_layout")
    assert len(provider.requests) == 1

    # without the switch nothing is asked and the manifest says the assistant did not run
    export_apexlang(store, module, tmp_path / "plain", {"app_id": "300", "alias": "plain"}, provider)
    plain = _manifest(tmp_path / "plain")["layout"]
    assert plain["ai_layout"] == {} and plain["mapping_report"]["totals"]["placed_by_ai"] == 0
    assert len(provider.requests) == 1
    assert not last_export_config(store).get("ai_layout")


def test_the_export_config_reads_the_switch_as_a_flag():
    module = _dense()
    assert ApexExportConfig.from_dict({"ai_layout": "1"}, module).ai_layout is True
    assert ApexExportConfig.from_dict({"ai_layout": True}, module).ai_layout is True
    assert ApexExportConfig.from_dict({"ai_layout": "0"}, module).ai_layout is False
    assert ApexExportConfig.from_dict({}, module).ai_layout is False


def test_the_cli_switch_runs_the_assistant_with_the_environments_provider(
    tmp_path, sample_xml, monkeypatch
):
    monkeypatch.setenv("FORMSLANG_AI_PROVIDER", "echo")
    module = parse_xml(sample_xml)
    db = tmp_path / "DEMO_ORDER.session.db"
    store = Store(db)
    store.init_session(module.name, str(sample_xml))
    store.add_tasks(build_tasks(module))
    first = store.task_ids()[0]
    store.save_proposal(first, Proposal(code="begin null; end;", apex_target="Page process"))
    store.set_decision(first, APPROVED, code="begin null; end;", reviewer="ana")
    store.close()

    assert cli.main(["export", str(db), "--alias", "demo", "--app-id", "200", "--ai-layout"]) == 0
    manifest = _manifest(tmp_path / "export" / "demo-review")
    ai_layout = manifest["layout"]["ai_layout"]
    assert ai_layout["enabled"] is True and ai_layout["status"] in {"offline", "not-needed"}
    assert "--ai-layout" in json.dumps(manifest)

    assert cli.main(["export", str(db), "--alias", "plain", "--app-id", "200"]) == 0
    assert _manifest(tmp_path / "export" / "plain-review")["layout"]["ai_layout"] == {}
