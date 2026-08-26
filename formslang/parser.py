"""Forms2XML output -> domain model.

Two details that break naive parsers, both handled here:

1. **Double-escaped newlines.** Forms2XML stores trigger and program-unit
   bodies in an XML ATTRIBUTE, escaping newline and tab as the literal
   entities ``&#10;`` / ``&#9;``. After the normal XML unescape the text
   still contains the seven-character string ``&#10;``. Without a second
   decoding pass every trigger collapses into a single line.

2. **Accent mojibake.** The .fmb stores text in cp1252; Forms2XML declares
   UTF-8 but emits the original bytes reinterpreted, so ``Conexão`` arrives
   as ``ConexÃ£o``. The repair is reversible and only applied when it yields
   valid text.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .model import (
    Block,
    FormModule,
    Item,
    Lov,
    ProgramUnit,
    RecordGroup,
    Relation,
    Trigger,
)

NS = "{http://xmlns.oracle.com/Forms}"

# Numeric entities that survive the XML unescape (see module docstring).
_ENTITY = re.compile(r"&#(x[0-9A-Fa-f]+|[0-9]+);")
_MOJIBAKE = re.compile(r"[ÂÃ][\x80-\xbf]")


def _fix_mojibake(text: str) -> str:
    """Undo cp1252-read-as-UTF8, but only when the result is valid."""
    if not text or not _MOJIBAKE.search(text):
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def decode_forms_text(raw: str | None) -> str:
    """Normalize a code body coming from a Forms XML attribute."""
    if not raw:
        return ""

    def sub(m: re.Match[str]) -> str:
        code = m.group(1)
        value = int(code[1:], 16) if code[0] in "xX" else int(code)
        return chr(value)

    text = _ENTITY.sub(sub, raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return _fix_mojibake(text)


def _s(el: ET.Element, attr: str, default: str = "") -> str:
    return _fix_mojibake(el.get(attr, default) or default)


def _b(el: ET.Element, attr: str, default: bool) -> bool:
    raw = el.get(attr)
    if raw is None:
        return default
    return raw.strip().lower() == "true"


def _i(el: ET.Element, attr: str, default: int | None = None) -> int | None:
    raw = el.get(attr)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _kids(el: ET.Element, tag: str) -> list[ET.Element]:
    return el.findall(f"{NS}{tag}")


def _names(el: ET.Element, tag: str) -> list[str]:
    return [_s(k, "Name") for k in el.iter(f"{NS}{tag}")]


def _parse_triggers(parent: ET.Element, scope: str, owner: str) -> list[Trigger]:
    return [
        Trigger(
            name=_s(t, "Name").upper(),
            text=decode_forms_text(t.get("TriggerText")),
            scope=scope,
            owner=owner,
        )
        for t in _kids(parent, "Trigger")
    ]


def _parse_item(el: ET.Element, block_name: str) -> Item:
    name = _s(el, "Name")
    return Item(
        name=name,
        item_type=_s(el, "ItemType"),
        data_type=_s(el, "DataType"),
        column_name=_s(el, "ColumnName"),
        database_item=_b(el, "DatabaseItem", True),
        required=_b(el, "Required", False),
        max_length=_i(el, "MaximumLength"),
        prompt=_s(el, "Prompt"),
        canvas=_s(el, "CanvasName"),
        lov_name=_s(el, "LOVName"),
        list_elements=len(_kids(el, "ListItemElement")),
        triggers=_parse_triggers(el, "item", f"{block_name}.{name}"),
        subclassed=bool(el.get("ParentName")),
    )


def _parse_block(el: ET.Element) -> Block:
    name = _s(el, "Name")
    return Block(
        name=name,
        database_block=_b(el, "DatabaseBlock", True),
        query_data_source_name=_s(el, "QueryDataSourceName"),
        query_data_source_type=_s(el, "QueryDataSourceType"),
        where_clause=decode_forms_text(el.get("WhereClause")),
        order_by_clause=decode_forms_text(el.get("OrderByClause")),
        insert_allowed=_b(el, "InsertAllowed", True),
        update_allowed=_b(el, "UpdateAllowed", True),
        delete_allowed=_b(el, "DeleteAllowed", True),
        records_displayed=_i(el, "RecordsDisplayCount", 1) or 1,
        items=[_parse_item(i, name) for i in _kids(el, "Item")],
        triggers=_parse_triggers(el, "block", name),
    )


def parse_xml(path: str | Path, *, convert_log: str = "") -> FormModule:
    """Read a Forms module XML and return the normalized FormModule."""
    path = Path(path)
    root = ET.parse(path).getroot()
    fm = root.find(f"{NS}FormModule")
    if fm is None:
        raise ValueError(f"{path.name}: no <FormModule> element (menu or library?)")

    mod = FormModule(
        name=_s(fm, "Name"),
        source_path=str(path),
        title=_s(fm, "Title"),
        comment=_s(fm, "Comment"),
        menu_module=_s(fm, "MenuModule"),
        first_block=_s(fm, "FirstNavigationBlockName"),
        blocks=[_parse_block(b) for b in _kids(fm, "Block")],
        triggers=_parse_triggers(fm, "form", ""),
        program_units=[
            ProgramUnit(
                name=_s(p, "Name"),
                kind=_s(p, "ProgramUnitType"),
                text=decode_forms_text(p.get("ProgramUnitText")),
            )
            for p in _kids(fm, "ProgramUnit")
        ],
        relations=[
            Relation(
                name=_s(r, "Name"),
                detail_block=_s(r, "DetailBlock"),
                join_condition=decode_forms_text(r.get("JoinCondition")),
                deferred=_b(r, "Deferred", False),
                delete_record=_s(r, "DeleteRecord"),
            )
            for r in fm.iter(f"{NS}Relation")
        ],
        record_groups=[
            RecordGroup(
                name=_s(g, "Name"),
                kind=_s(g, "RecordGroupType"),
                query=decode_forms_text(g.get("RecordGroupQuery")),
            )
            for g in fm.iter(f"{NS}RecordGroup")
        ],
        lovs=[
            Lov(
                name=_s(v, "Name"),
                record_group=_s(v, "RecordGroupName"),
                title=_s(v, "Title"),
                columns=len(_kids(v, "LOVColumnMapping")),
            )
            for v in fm.iter(f"{NS}LOV")
        ],
        attached_libraries=_names(fm, "AttachedLibrary"),
        parameters=_names(fm, "ModuleParameter"),
        canvases=_names(fm, "Canvas"),
        windows=_names(fm, "Window"),
        alerts=_names(fm, "Alert"),
        editors=_names(fm, "Editor"),
        object_groups=_names(fm, "ObjectGroup"),
        reports=_names(fm, "Report"),
        tab_pages=_names(fm, "TabPage"),
        graphics_count=len(list(fm.iter(f"{NS}Graphics"))),
    )

    if convert_log:
        mod.convert_warnings = [
            line.strip()
            for line in convert_log.splitlines()
            if line.strip().startswith("ERROR")
        ]
    return mod
