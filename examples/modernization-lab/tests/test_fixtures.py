"""
Structural tests for the LOM modernization lab's Forms2XML fixtures.

These exercise the REAL FormsLang parser (formslang.parser.parse_xml)
against forms/xml/*.xml, the same code path a user runs FormsLang's CLI
through. They are not a substitute for FormsLang's own test suite --
they exist to keep this lab's fixtures and its documentation (this
directory's README, the metrics script, the ground-truth JSON) from
drifting apart silently.

Run from the repo root:
    python -m unittest examples.modernization-lab.tests.test_fixtures -v
(or, since "modernization-lab" is not a valid Python package name with a
hyphen, run directly by path instead:)
    python -m unittest discover -s examples/modernization-lab/tests -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import formslang.parser as formslang_parser  # noqa: E402

XML_DIR = LAB_ROOT / "forms" / "xml"

EXPECTED_STRUCTURE = {
    "CUSTOMERS": {
        "items": 9,
        "block_triggers": 3,
        "item_triggers": 4,
        "lovs": 1,
        "relations": 0,
        "alerts": 1,
    },
    "ORDERS": {
        "items": 26,
        "block_triggers": 6,
        "item_triggers": 11,
        "lovs": 3,
        "relations": 1,
        "alerts": 2,
    },
    "INVENTORY": {
        "items": 11,
        "block_triggers": 2,
        "item_triggers": 1,
        "lovs": 0,
        "relations": 0,
        "alerts": 0,
    },
    "APPROVALS": {
        "items": 10,
        "block_triggers": 1,
        "item_triggers": 2,
        "lovs": 0,
        "relations": 0,
        "alerts": 2,
    },
}


class ParsesWithoutError(unittest.TestCase):
    """Every fixture must be well-formed Forms2XML that FormsLang can parse."""

    def test_all_four_modules_parse(self):
        for name in EXPECTED_STRUCTURE:
            with self.subTest(module=name):
                module = formslang_parser.parse_xml(str(XML_DIR / f"{name}.xml"))
                self.assertEqual(module.name, name)


class StructuralCountsMatchDocumentation(unittest.TestCase):
    """
    Guards against the exact class of bug this lab already hit once: a
    module's header comment or a generator script claiming an item/trigger
    exists that was never actually wired into the committed XML (see
    LOM-MOD-016 / INVENTORY.fmb's BT_ADJUST in the project handoff notes).
    If a fixture legitimately changes, update EXPECTED_STRUCTURE above AND
    every doc that quotes these numbers (metrics/compute_metrics.py's
    output, docs/*.md) in the same change.
    """

    def test_counts(self):
        for name, expected in EXPECTED_STRUCTURE.items():
            with self.subTest(module=name):
                module = formslang_parser.parse_xml(str(XML_DIR / f"{name}.xml"))
                items = sum(len(b.items) for b in module.blocks)
                block_triggers = sum(len(b.triggers) for b in module.blocks)
                item_triggers = sum(
                    sum(len(i.triggers) for i in b.items) for b in module.blocks
                )
                self.assertEqual(items, expected["items"], f"{name} item count")
                self.assertEqual(
                    block_triggers, expected["block_triggers"], f"{name} block trigger count"
                )
                self.assertEqual(
                    item_triggers, expected["item_triggers"], f"{name} item trigger count"
                )
                self.assertEqual(len(module.lovs), expected["lovs"], f"{name} LOV count")
                self.assertEqual(
                    len(module.relations), expected["relations"], f"{name} relation count"
                )
                self.assertEqual(len(module.alerts), expected["alerts"], f"{name} alert count")


class SpecificBusinessRulesArePresent(unittest.TestCase):
    """
    Spot-checks a handful of the specific LOM-MOD cases that depend on one
    exact trigger existing with one exact call in it -- not just "some
    trigger exists somewhere". These are the cases most likely to silently
    break if a fixture is hand-edited later.
    """

    def test_inventory_bt_adjust_calls_the_api(self):
        module = formslang_parser.parse_xml(str(XML_DIR / "INVENTORY.xml"))
        block = next(b for b in module.blocks if b.name == "BK_INVENTORY")
        button = next(i for i in block.items if i.name == "BT_ADJUST")
        trigger = next(t for t in button.triggers if t.name == "WHEN-BUTTON-PRESSED")
        self.assertIn("lom_inventory_api.adjust_quantity", trigger.text)
        self.assertIn("LOM-MOD-016", trigger.text)

    def test_orders_product_validation_checks_active_flag(self):
        module = formslang_parser.parse_xml(str(XML_DIR / "ORDERS.xml"))
        block = next(b for b in module.blocks if b.name == "BK_ORDER_LINE")
        product_item = next(i for i in block.items if i.name == "PRODUCT_ID")
        trigger = next(t for t in product_item.triggers if t.name == "WHEN-VALIDATE-ITEM")
        self.assertIn("active_flag", trigger.text.lower())

    def test_orders_line_total_formula_is_duplicated_as_documented(self):
        """LOM-MOD-027: the same formula must appear on BOTH QUANTITY and
        DISCOUNT_AMOUNT triggers -- that duplication is the finding."""
        module = formslang_parser.parse_xml(str(XML_DIR / "ORDERS.xml"))
        block = next(b for b in module.blocks if b.name == "BK_ORDER_LINE")
        formula_snippet = "quantity"
        hits = 0
        for item in block.items:
            if item.name in ("QUANTITY", "DISCOUNT_AMOUNT"):
                for trig in item.triggers:
                    if "unit_price" in trig.text.lower() and "discount_amount" in trig.text.lower():
                        hits += 1
        self.assertEqual(hits, 2, "expected the line-total formula duplicated on exactly 2 triggers")

    def test_approvals_reject_bypasses_the_api_as_documented(self):
        """LOM-MOD-042: the reject action must NOT call lom_approval_api.reject --
        that bypass is the finding this fixture exists to demonstrate."""
        module = formslang_parser.parse_xml(str(XML_DIR / "APPROVALS.xml"))
        all_text = json.dumps(
            [t.text for b in module.blocks for i in b.items for t in i.triggers]
            + [t.text for b in module.blocks for t in b.triggers]
        )
        self.assertNotIn("lom_approval_api.reject(", all_text.lower())
        self.assertIn("update lom_approvals", all_text.lower())


class GroundTruthRegistryIsConsistent(unittest.TestCase):
    """Every LOM-MOD id referenced anywhere in forms/ or database/ must have
    a corresponding entry in expected/modernization-ground-truth.json, and
    every case in the registry must use a value from the documented
    taxonomy -- see metrics/compute_metrics.py for the live cross-check
    this duplicates as an assertion."""

    @classmethod
    def setUpClass(cls):
        gt_path = LAB_ROOT / "expected" / "modernization-ground-truth.json"
        cls.ground_truth = json.loads(gt_path.read_text(encoding="utf-8"))

    def test_every_case_uses_documented_taxonomy_values(self):
        taxonomy = self.ground_truth["taxonomy"]
        valid_classifications = set(taxonomy["classification"])
        valid_risks = set(taxonomy["risk"])
        valid_categories = set(taxonomy["category"])
        for case in self.ground_truth["cases"]:
            with self.subTest(case=case["id"]):
                self.assertIn(case["classification"], valid_classifications)
                self.assertIn(case["risk"], valid_risks)
                self.assertIn(case["category"], valid_categories)

    def test_case_ids_are_unique(self):
        ids = [c["id"] for c in self.ground_truth["cases"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_referenced_ids_all_have_registry_entries(self):
        import re

        pattern = re.compile(r"LOM-MOD-(\d{3})")
        referenced: set[str] = set()
        for sub in ("database", "forms"):
            for path in (LAB_ROOT / sub).rglob("*"):
                if path.is_file():
                    try:
                        referenced |= set(pattern.findall(path.read_text(encoding="utf-8")))
                    except (UnicodeDecodeError, OSError):
                        continue
        registered = {c["id"].rsplit("-", 1)[1] for c in self.ground_truth["cases"]}
        missing = referenced - registered
        self.assertEqual(
            missing,
            set(),
            f"IDs referenced in fixtures but missing from the registry: {sorted(missing)}",
        )


if __name__ == "__main__":
    unittest.main()
