"""Domain model of an Oracle Forms module.

Only what matters for analysis and conversion. Layout properties (font,
color, pixel position) are deliberately ignored: they do not survive a
migration to APEX and would only add noise to the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Trigger:
    """A Forms trigger, at any scope."""

    name: str
    text: str
    scope: str  # "form" | "block" | "item"
    owner: str  # owning block or item name; "" at form scope

    @property
    def lines(self) -> int:
        return self.text.count("\n") + 1 if self.text else 0


@dataclass
class ProgramUnit:
    """Procedure/function/package declared inside the .fmb."""

    name: str
    kind: str  # Procedure | Function | Package Spec | Package Body
    text: str

    @property
    def lines(self) -> int:
        return self.text.count("\n") + 1 if self.text else 0


@dataclass
class Item:
    name: str
    item_type: str = ""
    data_type: str = ""
    column_name: str = ""
    database_item: bool = True
    required: bool = False
    max_length: int | None = None
    prompt: str = ""
    canvas: str = ""
    lov_name: str = ""
    list_elements: int = 0
    triggers: list[Trigger] = field(default_factory=list)
    subclassed: bool = False


@dataclass
class Block:
    name: str
    database_block: bool = True
    query_data_source_name: str = ""
    query_data_source_type: str = ""
    where_clause: str = ""
    order_by_clause: str = ""
    insert_allowed: bool = True
    update_allowed: bool = True
    delete_allowed: bool = True
    records_displayed: int = 1
    items: list[Item] = field(default_factory=list)
    triggers: list[Trigger] = field(default_factory=list)

    @property
    def is_tabular(self) -> bool:
        return self.records_displayed > 1


@dataclass
class Relation:
    name: str
    detail_block: str = ""
    join_condition: str = ""
    deferred: bool = False
    delete_record: str = ""


@dataclass
class RecordGroup:
    name: str
    kind: str = ""
    query: str = ""


@dataclass
class Lov:
    name: str
    record_group: str = ""
    title: str = ""
    columns: int = 0


@dataclass
class FormModule:
    """A whole .fmb, already normalized."""

    name: str
    source_path: str = ""
    title: str = ""
    comment: str = ""
    menu_module: str = ""
    first_block: str = ""
    blocks: list[Block] = field(default_factory=list)
    triggers: list[Trigger] = field(default_factory=list)  # form scope
    program_units: list[ProgramUnit] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    record_groups: list[RecordGroup] = field(default_factory=list)
    lovs: list[Lov] = field(default_factory=list)
    attached_libraries: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    canvases: list[str] = field(default_factory=list)
    windows: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    editors: list[str] = field(default_factory=list)
    object_groups: list[str] = field(default_factory=list)
    reports: list[str] = field(default_factory=list)
    tab_pages: list[str] = field(default_factory=list)
    graphics_count: int = 0
    convert_warnings: list[str] = field(default_factory=list)

    # -- aggregates used by the assessment -------------------------------

    @property
    def all_triggers(self) -> list[Trigger]:
        out = list(self.triggers)
        for b in self.blocks:
            out.extend(b.triggers)
            for it in b.items:
                out.extend(it.triggers)
        return out

    @property
    def all_items(self) -> list[Item]:
        return [it for b in self.blocks for it in b.items]

    @property
    def plsql_lines(self) -> int:
        return sum(t.lines for t in self.all_triggers) + sum(
            p.lines for p in self.program_units
        )

    @property
    def plsql_text(self) -> str:
        parts = [t.text for t in self.all_triggers]
        parts += [p.text for p in self.program_units]
        return "\n".join(p for p in parts if p)
