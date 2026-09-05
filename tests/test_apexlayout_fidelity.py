"""apexlayout / apexlang: high-fidelity layout -- native components, grids,
the mapping report, and the invariants a rendered page depends on.

Synthetic modules only. Every APEXlang keyword asserted here was accepted by
``apex validate`` on APEX 26.1 (probes 2-4 of the layout milestone, and the
full showcase export) before it went into the exporter.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from formslang.apexlang import _lovs_text, _page_items, export_apexlang
from formslang.apexlayout import (
    APPROXIMATION,
    FAITHFUL,
    GRID_COLUMNS,
    UNSUPPORTED,
    build_layout,
    layout_report,
)
from formslang.formui import render_html
from formslang.model import Block, Canvas, FormModule, Graphic, Item, RadioButton
from formslang.parser import parse_xml
from formslang.store import Store

SHOWCASE = Path(__file__).parent / "fixtures" / "showcase" / "module.xml"


def _module(blocks, canvases=None, **kw) -> FormModule:
    return FormModule(
        name="M",
        canvases=canvases or [Canvas(name="CV", width=600, height=200)],
        blocks=blocks,
        **kw,
    )


def _item(name, x, y, width=50, height=14, canvas="CV", **kw) -> Item:
    return Item(name=name, item_type="Text Item", canvas=canvas, x=x, y=y, width=width,
                height=height, **kw)


def _page_text(module) -> str:
    chunks, _ = _page_items(module, 1)
    return "\n".join(chunks)


def _chunk(text: str, header: str) -> str:
    """One ``pageItem X (`` / ``region x (`` / ``column X (`` block of the page."""
    start = text.index(header)
    depth, i = 0, start
    while True:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1


def _grid_block(name="IT", table="TAB_ITEM", records=5, **kw) -> Block:
    """A multi-record block on a table: three visible columns, a hidden key."""
    return Block(
        name=name,
        query_data_source_name=table,
        records_displayed=records,
        items=[
            _item("SEQ", 20, 20, 40, data_type="Number", prompt="Seq"),
            _item("DESCR", 70, 20, 200, prompt="Descrição", required=True, max_length=80),
            Item(name="TOTAL", item_type="Display Item", canvas="CV", x=280, y=20, width=80,
                 height=14, data_type="Number", prompt="Total", database_item=False),
            _item("ID", 0, 0, visible=False, data_type="Number", primary_key=True),
        ],
        **kw,
    )


# -- multi-record blocks -> Interactive Grid ----------------------------------------


def test_a_multi_record_block_on_a_table_becomes_an_interactive_grid():
    """Forms shows five records of a table block at once: that is an
    Interactive Grid on the block's table, one column per item in the
    left-to-right order Forms draws the record, the hidden key riding along
    as a hidden column -- and none of those items doubles as a page item."""
    module = _module([_grid_block()])
    layout = build_layout(module)
    grid = next(r for r in layout.regions() if r.kind == "grid")

    assert grid.template == "interactive-report"
    assert [p.item.name for p in grid.columns] == ["SEQ", "DESCR", "TOTAL"]
    assert [p.item.name for p in grid.hidden] == ["ID"]

    text = _page_text(module)
    region = _chunk(text, "region it (")
    assert "type: interactiveGrid" in region
    assert "location: localDatabase\n            tableName: TAB_ITEM" in region
    assert "template: @/interactive-report" in region
    assert "savedReport primary (" in region
    assert region.index("column: @SEQ") < region.index("column: @DESCR") < region.index(
        "column: @TOTAL"
    )
    assert 'heading: "Descrição"' in region
    assert "valueRequired: true\n                maxLength: 80" in region
    assert "databaseColumn: DESCR\n                dataType: varchar2" in region
    # a display item with no column behind it is a column with no source
    total = _chunk(region, "column TOTAL (")
    assert "type: displayOnly" in total and "source {\n                type: none" in total
    # the hidden primary key is a hidden column, declared as the key
    key = _chunk(region, "column ID (")
    assert "type: hidden" in key and "primaryKey: true" in key
    assert "pageItem P1_SEQ" not in text and "pageItem P1_ID" not in text


def test_a_grid_that_is_all_its_frame_holds_takes_the_frames_place_and_caption():
    """A frame drawn around nothing but the record rows is the grid itself:
    the region keeps the frame's caption instead of nesting an untitled
    grid inside an otherwise empty group box."""
    canvas = Canvas(name="CV", width=600, height=200, graphics=[
        Graphic("FR_ITENS", "Frame", x=10, y=5, width=400, height=120, title="Itens do pedido"),
    ])
    module = _module([_grid_block()], canvases=[canvas])
    root = build_layout(module).roots[0]

    assert [(s.id, s.kind, s.title) for s in root.subs] == [
        ("itens-do-pedido", "grid", "Itens do pedido")
    ]
    assert "showing block IT" in root.subs[0].source
    text = _page_text(module)
    region = _chunk(text, "region itens-do-pedido (")
    assert 'title: "Itens do pedido"' in region and "type: interactiveGrid" in region
    # a titled grid keeps its header; only an untitled one hides it
    assert "t-IRR-region--hideHeader" not in region


def test_a_multi_record_control_block_stays_one_record_with_the_shared_note():
    """No table behind the block -> no grid to build: the first record's row
    is laid out as page items and the region says why, in the one wording
    the exporter and the preview share."""
    block = _grid_block(database_block=False)
    module = _module([block])
    layout = build_layout(module)

    assert not [r for r in layout.regions() if r.kind == "grid"]
    text = _page_text(module)
    assert "Forms shows 5 records of block IT at once here (tabular)" in text
    assert "the block is a control block, with no table behind it" in text
    assert "Forms shows 5 records of block IT at once here (tabular)" in render_html(module)


def test_an_item_shown_once_stays_outside_its_blocks_grid():
    """``ItemsDisplay=1`` on the audit fields of a grid block: Forms paints
    them once, so they are page items next to the grid, not columns."""
    block = _grid_block()
    block.items.append(_item("USUARIO", 20, 150, 100, items_displayed=1, prompt="Usuário"))
    module = _module([block])
    layout = build_layout(module)
    grid = next(r for r in layout.regions() if r.kind == "grid")

    assert [p.item.name for p in grid.columns] == ["SEQ", "DESCR", "TOTAL"]
    assert "pageItem P1_USUARIO (" in _page_text(module)
    entry = next(c for c in layout_report(layout)["controls"] if c["source"] == "IT.USUARIO")
    assert entry["status"] == APPROXIMATION
    assert any("ItemsDisplay" in a for a in entry["approximations"])


# -- native item types and their properties ---------------------------------------


def test_date_and_number_items_get_their_native_types_and_format_masks():
    module = _module([Block(name="B", items=[
        _item("DT", 10, 10, 80, data_type="Date", format_mask="DD/MM/YYYY", prompt="Data"),
        _item("VL", 100, 10, 80, data_type="Number", format_mask="FM999G990D00",
              justification="Right", prompt="Valor"),
        _item("TS", 200, 10, 80, data_type="Datetime", prompt="Quando"),
    ])])
    text = _page_text(module)

    dt = _chunk(text, "pageItem P1_DT (")
    assert "type: datePicker" in dt and 'formatMask: "DD/MM/YYYY"' in dt
    vl = _chunk(text, "pageItem P1_VL (")
    assert "type: numberField" in vl and 'formatMask: "FM999G990D00"' in vl
    assert "numberAlignment: end" in vl
    ts = _chunk(text, "pageItem P1_TS (")
    assert "type: datePicker" in ts and "formatMask" not in ts
    report = layout_report(build_layout(module))
    ts_entry = next(c for c in report["controls"] if c["source"] == "B.TS")
    assert ts_entry["status"] == APPROXIMATION and any(
        "format mask" in a for a in ts_entry["approximations"]
    )


def test_multiline_height_and_width_are_written_in_characters_of_the_module_cell():
    module = _module([Block(name="B", items=[
        _item("OBS", 10, 10, 300, 70, multi_line=True, prompt="Obs"),
    ])])
    obs = _chunk(_page_text(module), "pageItem P1_OBS (")

    assert "type: textarea" in obs
    assert re.search(r"width: \d+\n\s+height: 5\n", obs)


def test_disabled_items_are_read_only_not_disabled_and_hints_become_help():
    """``Enabled=false`` keeps the item on the page and in the submit; a
    disabled item would drop out of the submit. Hint and tooltip are the
    only help copy the .fmb carries."""
    module = _module([Block(name="B", items=[
        _item("COD", 10, 10, 80, enabled=False, prompt="Código", hint="Gerado pelo sistema",
              tooltip="Chave do produto", case_restriction="Upper"),
        Item(name="ATIVO", item_type="Check Box", canvas="CV", x=100, y=10, width=80,
             height=14, label="Ativo", checked_value="S", unchecked_value="N"),
    ])])
    text = _page_text(module)

    cod = _chunk(text, "pageItem P1_COD (")
    assert "readOnly {\n            type: always" in cod
    assert "disabled: true" not in cod
    assert "textCase: upper" in cod
    assert 'helpText: "Gerado pelo sistema Chave do produto"' in cod
    ativo = _chunk(text, "pageItem P1_ATIVO (")
    assert 'useDefaults: false\n            checkedValue: "S"\n            uncheckedValue: "N"' in ativo


def test_radio_group_columns_follow_how_forms_lays_the_buttons_out():
    """Three buttons side by side in Forms -> three columns in APEX; stacked
    buttons keep the one-column default."""
    def group(name, x, positions):
        return Item(
            name=name, item_type="Radio Group", canvas="CV", x=x, y=10, width=200, height=40,
            radio_buttons=[
                RadioButton(f"RB{i}", label=f"Opção {i}", value=str(i), x=bx, y=by, width=60,
                            height=14)
                for i, (bx, by) in enumerate(positions, 1)
            ],
        )

    module = _module([Block(name="B", items=[
        group("LADO", 10, [(10, 10), (80, 10), (150, 10)]),
        group("PILHA", 300, [(300, 10), (300, 30), (300, 50)]),
    ])])
    text = _page_text(module)

    assert "noOfCols: 3" in _chunk(text, "pageItem P1_LADO (")
    assert "noOfCols" not in _chunk(text, "pageItem P1_PILHA (")


def test_static_lov_return_values_come_from_the_fmb_when_it_declares_them():
    """``ListItemElement Value`` / ``RadioButton Value`` are the codes the
    Forms item stores: the LOV returns those. Without them the display text
    stands in, and the report flags the item for review."""
    module = _module([Block(name="B", items=[
        Item(name="UN", item_type="List Item", canvas="CV", x=10, y=10, width=100, height=16,
             choices=["Unidade", "Caixa"], choice_values=["UN", "CX"]),
        Item(name="ST", item_type="List Item", canvas="CV", x=150, y=10, width=100, height=16,
             choices=["Ativo", "Inativo"], choice_values=["", ""]),
    ])])
    layout = build_layout(module)
    lovs = {lov.id: lov for lov in layout.lovs}

    assert lovs["lov-b-un"].declared and lovs["lov-b-un"].entries == [
        ("Unidade", "UN"), ("Caixa", "CX")
    ]
    assert not lovs["lov-b-st"].declared and lovs["lov-b-st"].entries == [
        ("Ativo", "Ativo"), ("Inativo", "Inativo")
    ]
    lov_text = _lovs_text(layout.lovs)
    assert 'display: "Caixa"\n        return: "CX"' in lov_text
    assert 'display: "Inativo"\n        return: "Inativo"' in lov_text
    report = layout_report(layout)
    by_source = {c["source"]: c for c in report["controls"]}
    assert by_source["B.UN"]["status"] == FAITHFUL
    assert by_source["B.ST"]["status"] == APPROXIMATION
    assert any("return value" in a for a in by_source["B.ST"]["approximations"])


def test_unsupported_item_types_keep_their_place_and_are_reported_as_such():
    module = _module([Block(name="B", items=[
        Item(name="FOTO", item_type="Image", canvas="CV", x=10, y=10, width=100, height=100,
             prompt="Foto"),
        _item("NOME", 150, 10, 200, prompt="Nome"),
    ])])
    layout = build_layout(module)
    report = layout_report(layout)
    foto = next(c for c in report["controls"] if c["source"] == "B.FOTO")

    assert foto["status"] == UNSUPPORTED
    assert any("no native component for a Forms Image" in u for u in foto["unsupported"])
    assert foto["target"]["type"] == "textField"  # the placeholder keeps the cell
    assert report["totals"]["controls"] == {
        "total": 2, FAITHFUL: 1, APPROXIMATION: 0, UNSUPPORTED: 1
    }
    assert "pageItem P1_FOTO (" in _page_text(module)


# -- regions, tabs, template options ------------------------------------------


def test_tab_pages_take_their_title_from_the_fmb_label():
    tabs = Canvas(name="TABS", canvas_type="Tab", width=400, height=200,
                  tab_pages=["TP_GERAL", "TP_EXTRA"],
                  tab_page_labels={"TP_GERAL": "Dados  gerais", "TP_EXTRA": ""})
    module = _module([Block(name="B", items=[
        _item("A", 10, 10, canvas="TABS", tab_page="TP_GERAL"),
        _item("B", 10, 10, canvas="TABS", tab_page="TP_EXTRA"),
    ])], canvases=[tabs])
    node = build_layout(module).roots[0]

    assert [(s.slot, s.title) for s in node.subs] == [
        ("tabs", "Dados gerais"),  # the label, whitespace normalised
        ("tabs", "Tp Extra"),  # no label: the name, spelled out
    ]


def test_template_options_are_universal_theme_classes_written_as_a_list():
    """A region without a caption drops its header; a form region stretches
    its inputs to the cell; an untitled grid hides the report header. Each
    option is the class Universal Theme defines, accepted by validate."""
    canvas = Canvas(name="CV", width=600, height=300, graphics=[
        Graphic("FR", "Frame", x=10, y=5, width=400, height=60, title="Dados"),
    ])
    module = _module([
        Block(name="B", items=[_item("A", 20, 20, 100, prompt="A")]),
        _grid_block(),
    ], canvases=[canvas])
    module.blocks[1].items[0].y = 150  # the grid rows sit below the frame
    for it in module.blocks[1].items[1:3]:
        it.y = 150
    text = _page_text(module)

    dados = _chunk(text, "region dados (")
    assert (
        "templateOptions: [\n                #DEFAULT#\n"
        "                t-Form--stretchInputs\n            ]"
    ) in dados
    grid = _chunk(text, "region it (")
    assert "t-IRR-region--hideHeader js-addHiddenHeadingRoleDesc" in grid
    # the canvas root has no caption of its own on this screen
    root = _chunk(text, "region cv (")
    assert "t-Region--removeHeader js-removeLandmark" in root or 'title: "' in root
    for line in text.splitlines():
        if "templateOptions:" in line:
            assert line.strip() in {"templateOptions: #DEFAULT#", "templateOptions: ["}


# -- invariants over a dense screen -------------------------------------------------


def _placements(text: str) -> list[tuple[str, int, int, int]]:
    """(name, column, columnSpan, labelColumnSpan) of every page item."""
    out = []
    for m in re.finditer(r"pageItem (\w+) \(", text):
        chunk = _chunk(text, m.group(0))
        col = re.search(r"\n\s+column: (\d+)", chunk)
        span = re.search(r"\n\s+columnSpan: (\d+)", chunk)
        label = re.search(r"labelColumnSpan: (\d+)", chunk)
        if col and span:
            out.append((m.group(1), int(col.group(1)), int(span.group(1)),
                        int(label.group(1)) if label else 0))
    return out


def test_showcase_labels_never_claim_the_whole_cell_and_cells_stay_on_the_grid():
    """``LABEL_COLUMN_SPAN_TOO_BIG`` is a render-time defect: a label span
    equal to or above the item's column span breaks the page in APEX and
    passes ``apex validate``. Every placement also has to end inside the
    12-column grid of its parent."""
    module = parse_xml(str(SHOWCASE))
    text = _page_text(module)
    placements = _placements(text)

    assert placements, "no page items with a grid cell"
    for name, column, span, label in placements:
        assert 1 <= column <= GRID_COLUMNS, name
        assert column + span - 1 <= GRID_COLUMNS, name
        assert label < span, (name, label, span)
    for m in re.finditer(r"region ([\w-]+) \(", text):
        chunk = _chunk(text, m.group(0))
        col = re.search(r"\n\s+column: (\d+)", chunk)
        span = re.search(r"\n\s+columnSpan: (\d+)", chunk)
        if col and span:
            assert int(col.group(1)) + int(span.group(1)) - 1 <= GRID_COLUMNS, m.group(1)


def test_showcase_places_every_visible_control_exactly_once():
    """Every visible item on an exported canvas is one page item, button or
    grid column -- not zero, not two -- and the report says so with the
    denominator it counted, not a percentage."""
    module = parse_xml(str(SHOWCASE))
    layout = build_layout(module)
    report = layout_report(layout)
    text = _page_text(module)

    exported_canvases = {c.name for c in module.canvases} - {
        s.split(" ")[1] for s in layout.skipped if s.startswith("canvas ")
    }
    visible = [
        f"{b.name}.{it.name}"
        for b in module.blocks
        for it in b.items
        if it.visible and it.canvas in exported_canvases
    ]
    reported = [c["source"] for c in report["controls"]]
    assert sorted(reported) == sorted(visible)
    assert len(set(reported)) == len(reported)
    totals = report["totals"]
    assert totals["controls_placed_twice"] == []
    assert totals["controls"]["total"] == len(visible)
    assert totals["controls"]["total"] == sum(
        totals["controls"][s] for s in (FAITHFUL, APPROXIMATION, UNSUPPORTED)
    )
    assert totals["controls"][UNSUPPORTED] == 0
    assert totals["groups"]["total"] == sum(
        totals["groups"][s] for s in (FAITHFUL, APPROXIMATION, UNSUPPORTED)
    )
    # each control names one component the page actually contains
    for entry in report["controls"]:
        target = entry["target"]
        if target["component"] == "gridColumn":
            assert f"column {target['name']} (" in _chunk(text, f"region {target['region']} (")
        else:
            assert f"{target['component']} {target['name']} (" in text
    assert report["viewport"].startswith("desktop, 1280 CSS px")


def test_repeated_item_names_across_blocks_stay_apart():
    module = _module([
        Block(name="CAB", items=[_item("ID", 10, 10, 60, prompt="Pedido")]),
        Block(name="END", items=[_item("ID", 10, 40, 60, prompt="Endereço")]),
    ])
    layout = build_layout(module)
    text = _page_text(module)
    report = layout_report(layout)

    assert [c["source"] for c in report["controls"]] == ["CAB.ID", "END.ID"]
    names = {c["source"]: c["target"]["name"] for c in report["controls"]}
    assert len(set(names.values())) == 2
    for name in names.values():
        assert f"pageItem {name} (" in text


def test_an_item_without_geometry_is_still_placed_and_flagged():
    module = _module([Block(name="B", items=[
        _item("A", 10, 10, 100, prompt="A"),
        Item(name="SEM_POS", item_type="Text Item", canvas="CV", prompt="Sem posição"),
    ])])
    report = layout_report(build_layout(module))
    entry = next(c for c in report["controls"] if c["source"] == "B.SEM_POS")

    assert entry["geometry"] is None
    assert entry["status"] == APPROXIMATION
    assert "geometry" in entry["missing"]
    assert "pageItem P1_SEM_POS (" in _page_text(module)


# -- the manifest, and preview/export consistency -----------------------------------


def test_the_manifest_carries_the_mapping_report_and_grid_regions(tmp_path):
    module = _module([_grid_block()])
    store = Store(tmp_path / "M.session.db")
    store.init_session(module.name, "M.xml")
    try:
        result = export_apexlang(store, module, tmp_path / "export", {"alias": "grid-demo"})
    finally:
        store.close()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    layout = manifest["layout"]
    grid = next(r for r in layout["regions"] if r["kind"] == "grid")
    assert grid["template_options"] == ["t-IRR-region--hideHeader js-addHiddenHeadingRoleDesc"]
    assert grid["columns"] == ["SEQ", "DESCR", "TOTAL"]
    report = layout["mapping_report"]
    assert report["totals"]["controls"]["total"] == 3
    assert {c["target"]["component"] for c in report["controls"]} == {"gridColumn"}
    assert report["hidden"][0]["source"] == "IT.ID"


def test_the_preview_draws_the_same_grid_columns_the_export_writes():
    module = _module([_grid_block()])
    html = render_html(module).split("<h2>APEX preview", 1)[1]
    text = _page_text(module)

    heads = re.findall(r"<th[^>]*>(.*?)</th>", html)
    heads = [re.sub("<[^>]+>", "", h) for h in heads]
    assert heads[:3] == ["Seq", "Descrição*", "Total"]
    assert heads[3] == "ID"  # the hidden column, listed last as in the export
    assert [h for h in re.findall(r'heading: "([^"]+)"', text)] == ["Seq", "Descrição", "Total"]
    assert "interactive grid" in html and "4 column(s)" in html
    assert "Interactive Grid on TAB_ITEM: 3 column(s)" in html
