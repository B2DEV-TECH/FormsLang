"""Deterministic builder for the "medium" and "large" golden-corpus tiers.

Hand-typing 50-200+ Forms XML objects is how a fixture silently drifts from
what it claims to cover. This module builds them instead, from small,
readable Python loops -- no randomness, no wall clock, nothing that would
make two runs disagree. "tiny", "small" and "pathological" stay
hand-authored (small enough to read at a glance, and each one demonstrates
something specific that a loop would obscure); see tests/fixtures/README.md
for the full corpus layout.

Run once, by hand, whenever medium/large need to be regenerated:

    py tests/fixtures/generate_corpus.py

It is never imported by a test and never called by update_golden.py -- the
XML files it writes are committed, and tests read those files, not this
script.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

NS = "http://xmlns.oracle.com/Forms"
ET.register_namespace("", NS)

CORPUS_DIR = Path(__file__).parent / "corpus"


def _module_root(name: str, title: str, first_block: str = "") -> ET.Element:
    root = ET.Element(f"{{{NS}}}Module", {"version": "12.2.1.4.0"})
    attrs = {"Name": name, "Title": title}
    if first_block:
        attrs["FirstNavigationBlockName"] = first_block
    ET.SubElement(root, f"{{{NS}}}FormModule", attrs)
    return root


def _fm(root: ET.Element) -> ET.Element:
    return root.find(f"{{{NS}}}FormModule")


def _trigger(parent: ET.Element, name: str, text: str) -> ET.Element:
    return ET.SubElement(parent, f"{{{NS}}}Trigger", {"Name": name, "TriggerText": text})


def _write(root: ET.Element, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    tree = ET.ElementTree(root)
    tree.write(path, encoding="UTF-8", xml_declaration=True)


# -- medium: ~50 objects, one block per Forms trigger family + a spread of
#    builtins, so the corpus exercises as much of rules.py's catalog as a
#    single small module reasonably can. --------------------------------

# (trigger name, builtin call the body makes) -- real Oracle Forms trigger
# names and real Forms builtins, picked to spread across rules.py's verdict
# and category catalog rather than to hit every one of it by brute force.
_MEDIUM_TRIGGERS = [
    ("WHEN-NEW-FORM-INSTANCE", "GO_BLOCK('B_01')"),
    ("WHEN-NEW-BLOCK-INSTANCE", "GO_ITEM('B_01.ITEM_01')"),
    ("WHEN-NEW-RECORD-INSTANCE", "SET_ITEM_PROPERTY('B_01.ITEM_01', ENABLED, PROPERTY_TRUE)"),
    ("WHEN-VALIDATE-ITEM", "MESSAGE('validated')"),
    ("WHEN-VALIDATE-RECORD", "CHECK_RECORD_UNIQUENESS"),
    ("POST-QUERY", "SET_BLOCK_PROPERTY('B_01', DEFAULT_WHERE, 'ID=1')"),
    ("PRE-QUERY", "SET_BLOCK_PROPERTY('B_01', ORDER_BY, 'ID')"),
    ("PRE-INSERT", "GET_APPLICATION_PROPERTY(USERNAME)"),
    ("POST-INSERT", "DBMS_OUTPUT.PUT_LINE('inserted')"),
    ("PRE-UPDATE", "COPY('X', 'B_01.ITEM_01')"),
    ("POST-UPDATE", "NAME_IN('B_01.ITEM_01')"),
    ("PRE-DELETE", "DELETE_RECORD"),
    ("POST-DELETE", "COMMIT_FORM"),
    ("KEY-COMMIT", "COMMIT_FORM"),
    ("KEY-NEXT-ITEM", "NEXT_ITEM"),
    ("KEY-EXIT", "EXIT_FORM"),
    ("WHEN-BUTTON-PRESSED", "SHOW_ALERT('AL_CONFIRM')"),
    ("WHEN-CHECKBOX-CHANGED", "SET_ITEM_PROPERTY('B_01.ITEM_01', VISIBLE, PROPERTY_TRUE)"),
    ("WHEN-LIST-CHANGED", "POPULATE_GROUP('RG_STATUS')"),
    ("WHEN-RADIO-CHANGED", "GET_ITEM_PROPERTY('B_01.ITEM_01', VALUE)"),
    ("WHEN-WINDOW-ACTIVATED", "SHOW_WINDOW('WIN_MAIN')"),
    ("WHEN-WINDOW-CLOSED", "HIDE_WINDOW('WIN_MAIN')"),
    ("WHEN-TIMER-EXPIRED", "CREATE_TIMER('T1', 1000, NO_REPEAT)"),
    ("WHEN-MOUSE-CLICK", "SET_CANVAS_PROPERTY('CV_MAIN', VISIBLE, PROPERTY_TRUE)"),
    ("ON-ERROR", "GET_APPLICATION_PROPERTY(TIMER_NAME)"),
    ("ON-MESSAGE", "MESSAGE('on message')"),
    ("ON-INSERT", "INSERT INTO B_01_TBL (ID) VALUES (1)"),
    ("ON-UPDATE", "UPDATE B_01_TBL SET ID = 1"),
    ("ON-DELETE", "DELETE FROM B_01_TBL"),
    ("ON-LOCK", "LOCK_RECORD"),
    ("KEY-LISTVAL", "LIST_VALUES"),
    ("WHEN-IMAGE-ACTIVATED", "OPEN_FORM('OTHER_FORM')"),
    ("WHEN-CUSTOM-ITEM-EVENT", "WEBUTIL_CORE.CUSTOMEVENTHANDLER"),
]

_UNKNOWN_TRIGGER = ("WHEN-BANANA-EVENT", "NULL")


def build_medium(out_path: Path) -> None:
    root = _module_root("MEDIUM_FORM", "Medium Fixture", "B_01")
    fm = _fm(root)
    _trigger(fm, "WHEN-NEW-FORM-INSTANCE", "GO_BLOCK('B_01');")
    _trigger(fm, *_UNKNOWN_TRIGGER)

    for i, (trig_name, call) in enumerate(_MEDIUM_TRIGGERS, start=1):
        block = ET.SubElement(fm, f"{{{NS}}}Block", {
            "Name": f"B_{i:02d}", "DatabaseBlock": "true",
            "QueryDataSourceName": f"TBL_{i:02d}", "RecordsDisplayCount": "1",
        })
        _trigger(block, trig_name, f"BEGIN&#10;  {call};&#10;END;")
        item = ET.SubElement(block, f"{{{NS}}}Item", {
            "Name": "ITEM_01", "ItemType": "Text Item", "DataType": "Char",
            "ColumnName": "ITEM_01", "DatabaseItem": "true",
            "Required": "true" if i % 2 == 0 else "false",
        })
        if i % 5 == 0:
            _trigger(item, "WHEN-VALIDATE-ITEM", "MESSAGE('required');")

    prog = ET.SubElement(fm, f"{{{NS}}}ProgramUnit", {
        "Name": "P_HELPER", "ProgramUnitType": "Function",
        "ProgramUnitText": (
            "FUNCTION P_HELPER RETURN NUMBER IS&#10;"
            "  v_n NUMBER;&#10;"
            "BEGIN&#10;"
            "  SELECT COUNT(*) INTO v_n FROM TBL_01;&#10;"
            "  RETURN v_n;&#10;"
            "END;"
        ),
    })
    del prog

    ET.SubElement(fm, f"{{{NS}}}RecordGroup", {
        "Name": "RG_STATUS", "RecordGroupType": "Query",
        "RecordGroupQuery": "SELECT LABEL, CODE FROM STATUS_LOOKUP",
    })
    lov = ET.SubElement(fm, f"{{{NS}}}LOV", {
        "Name": "LOV_STATUS", "RecordGroupName": "RG_STATUS", "Title": "Status",
    })
    ET.SubElement(lov, f"{{{NS}}}LOVColumnMapping", {"Name": "LABEL"})
    ET.SubElement(lov, f"{{{NS}}}LOVColumnMapping", {"Name": "CODE"})

    ET.SubElement(fm, f"{{{NS}}}Canvas", {"Name": "CV_MAIN"})
    ET.SubElement(fm, f"{{{NS}}}Window", {"Name": "WIN_MAIN"})
    ET.SubElement(fm, f"{{{NS}}}Alert", {"Name": "AL_CONFIRM"})
    ET.SubElement(fm, f"{{{NS}}}AttachedLibrary", {"Name": "MEDIUM_LIB"})
    ET.SubElement(fm, f"{{{NS}}}ModuleParameter", {"Name": "P_MODE"})

    _write(root, out_path)


# -- large: 200+ graph objects. A hub block fans out to every other block
#    with a literal GO_BLOCK per target (breadth), and the blocks also
#    chain B_01 -> B_02 -> ... -> B_N (a walk past MAX_DEPTH=4 hops). ------

_LARGE_BLOCK_COUNT = 60


def build_large(out_path: Path) -> None:
    root = _module_root("LARGE_FORM", "Large Fixture", "B_01")
    fm = _fm(root)
    _trigger(fm, "WHEN-NEW-FORM-INSTANCE", "GO_BLOCK('B_01');")

    names = [f"B_{i:02d}" for i in range(1, _LARGE_BLOCK_COUNT + 1)]

    for i, name in enumerate(names, start=1):
        block = ET.SubElement(fm, f"{{{NS}}}Block", {
            "Name": name, "DatabaseBlock": "true",
            "QueryDataSourceName": f"TBL_{i:02d}", "RecordsDisplayCount": "1",
        })
        lines = ["BEGIN"]
        if i == 1:
            # The hub: one literal GO_BLOCK per remaining block (fan-out).
            for other in names[1:]:
                lines.append(f"  GO_BLOCK('{other}');")
        else:
            # The chain: each block also reaches the next one (depth walk).
            nxt = names[i] if i < len(names) else names[0]
            lines.append(f"  GO_BLOCK('{nxt}');")
        lines.append(f"  INSERT INTO AUDIT_{i:02d} (ID) VALUES (1);")
        lines.append("END;")
        _trigger(block, "WHEN-NEW-BLOCK-INSTANCE", "&#10;".join(lines))
        item = ET.SubElement(block, f"{{{NS}}}Item", {
            "Name": "ID", "ItemType": "Text Item", "DataType": "Number",
            "ColumnName": "ID", "DatabaseItem": "true",
            "Required": "true" if i % 2 == 0 else "false",
        })
        del item

    _write(root, out_path)


def main() -> None:
    build_medium(CORPUS_DIR / "medium" / "module.xml")
    build_large(CORPUS_DIR / "large" / "module.xml")
    print("wrote medium/module.xml and large/module.xml")


if __name__ == "__main__":
    main()
