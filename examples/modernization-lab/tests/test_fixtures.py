"""
Structural tests for the LOM modernization lab: its Forms2XML fixtures, its
PL/SQL, its ground-truth registry and the documents that quote them.

These exercise the REAL FormsLang parser (formslang.parser.parse_xml)
against forms/xml/*.xml, the same code path a user runs FormsLang's CLI
through. They are not a substitute for FormsLang's own test suite --
they exist to keep this lab's fixtures, its registry and its documentation
(README, the rollup, the metrics script, the ground-truth JSON) from
drifting apart silently. Nothing here executes SQL: every PL/SQL fact is
pinned by reading the committed source as text.

Run from the lab root ("modernization-lab" contains a hyphen, so it is not
importable as a package and must be run by path):
    cd examples/modernization-lab
    python -m unittest tests/test_fixtures.py -v
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import formslang.parser as formslang_parser

XML_DIR = LAB_ROOT / "forms" / "xml"
GROUND_TRUTH = LAB_ROOT / "expected" / "modernization-ground-truth.json"
ROLLUP = LAB_ROOT / "assessment" / "complexity-and-risk-rollup.md"
README = LAB_ROOT / "README.md"
ORDER_API_BODY = LAB_ROOT / "database" / "packages" / "lom_order_api.pkb"
ORDER_API_SPEC = LAB_ROOT / "database" / "packages" / "lom_order_api.pks"
LOOKUP_SEED = LAB_ROOT / "database" / "seed" / "01_lookup_data.sql"

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

# PRESERVE positive controls: (module, block, item or None for a block-level
# trigger, trigger names, the API call the trigger must contain). The point
# of a positive control is that a classifier which flags every trigger as
# "logic to move" is wrong here -- the call is already in the right place.
POSITIVE_CONTROLS = {
    "LOM-MOD-016": (
        "INVENTORY", "BK_INVENTORY", "BT_ADJUST",
        ("WHEN-BUTTON-PRESSED",), "lom_inventory_api.adjust_quantity",
    ),
    "LOM-MOD-019": (
        "ORDERS", "BK_ORDER", "CUSTOMER_ID",
        ("WHEN-VALIDATE-ITEM",), "lom_customer_api.can_place_order",
    ),
    "LOM-MOD-021": (
        "ORDERS", "BK_ORDER", "BT_SUBMIT",
        ("WHEN-BUTTON-PRESSED",), "lom_order_api.submit_order",
    ),
    "LOM-MOD-028": (
        "ORDERS", "BK_ORDER_LINE", None,
        ("POST-INSERT", "POST-UPDATE", "POST-DELETE"), "lom_order_api.recalc_order_totals",
    ),
}

# Negative controls: the button writes the table directly instead of calling
# the API procedure that exists for exactly that purpose. That bypass IS the
# finding; a fixture edit that "fixes" it would silently delete the case.
NEGATIVE_CONTROLS = {
    "LOM-MOD-041": ("BT_APPROVE", "lom_approval_api.approve("),
    "LOM-MOD-042": ("BT_REJECT", "lom_approval_api.reject("),
}

# The lifecycle matrix as committed in lom_order_api.is_valid_transition.
# Pinned verbatim so that changing the matrix forces ADR-002 and
# docs/business-rules.md to be revisited in the same change.
LEGAL_TRANSITIONS = {
    ("DRAFT", "SUBMITTED"),
    ("SUBMITTED", "PENDING_APPROVAL"),
    ("SUBMITTED", "APPROVED"),
    ("PENDING_APPROVAL", "APPROVED"),
    ("PENDING_APPROVAL", "REJECTED"),
    ("APPROVED", "RELEASED"),
    ("RELEASED", "SHIPPED"),
    ("DRAFT", "CANCELLED"),
    ("SUBMITTED", "CANCELLED"),
    ("PENDING_APPROVAL", "CANCELLED"),
}

# Transitions that a "SEQUENCE_NO must increase" shortcut would admit but the
# matrix rejects -- the reason SEQUENCE_NO is descriptive, not authoritative.
INCREASING_BUT_ILLEGAL = {
    ("DRAFT", "SHIPPED"),
    ("REJECTED", "APPROVED"),
    ("APPROVED", "CANCELLED"),
    ("RELEASED", "CANCELLED"),
}

LOM_MOD_LABEL = re.compile(r"LOM-MOD-(\d{3}) \(([^)]*)\)")
SOURCE_PATH = re.compile(r"(?:forms|database)/[\w/.-]+\.(?:xml|sql|pks|pkb|md)")
BARE_XML = re.compile(r"(?<![\w/])([A-Z_]+\.xml)")
SEED_STATUS_ROW = re.compile(
    r"insert into lom_order_status \(status_code, description, sequence_no\)"
    r"\s+values \('(\w+)', '[^']*', (\d+)\);"
)
TRANSITION_PAIR = re.compile(r"\(p_from = '(\w+)'\s+and p_to = '(\w+)'\)")


def _load_ground_truth() -> dict:
    return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))


def _load_metrics_module():
    """metrics/ is not a package; load compute_metrics.py by path so these
    tests pin the exact attribution rule the rollup document uses."""
    spec = importlib.util.spec_from_file_location(
        "lab_compute_metrics", LAB_ROOT / "metrics" / "compute_metrics.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse(name: str):
    return formslang_parser.parse_xml(str(XML_DIR / f"{name}.xml"))


def _trigger_text(module, block_name: str, item_name: str | None, trigger_name: str) -> str:
    block = next(b for b in module.blocks if b.name == block_name)
    owner = block if item_name is None else next(i for i in block.items if i.name == item_name)
    trigger = next(t for t in owner.triggers if t.name == trigger_name)
    return trigger.text


def _fixture_files():
    for sub in ("database", "forms"):
        for path in sorted((LAB_ROOT / sub).rglob("*")):
            if path.is_file():
                yield path


def _rollup_rows() -> list[tuple[str, str, int, str]]:
    """Every data row of every table in the rollup document as
    (section heading, first cell without backticks, count, third cell)."""
    rows = []
    section = ""
    for line in ROLLUP.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not cells[1].isdigit():
            continue  # header or separator row
        third = cells[2] if len(cells) > 2 else ""
        rows.append((section, cells[0].strip("`"), int(cells[1]), third))
    return rows


class ParsesWithoutError(unittest.TestCase):
    """Every fixture must be well-formed Forms2XML that FormsLang can parse."""

    def test_all_four_modules_parse(self):
        for name in EXPECTED_STRUCTURE:
            with self.subTest(module=name):
                module = _parse(name)
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
                module = _parse(name)
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
        text = _trigger_text(
            _parse("INVENTORY"), "BK_INVENTORY", "BT_ADJUST", "WHEN-BUTTON-PRESSED"
        )
        self.assertIn("lom_inventory_api.adjust_quantity", text)
        self.assertIn("LOM-MOD-016", text)

    def test_orders_product_validation_checks_active_flag(self):
        text = _trigger_text(
            _parse("ORDERS"), "BK_ORDER_LINE", "PRODUCT_ID", "WHEN-VALIDATE-ITEM"
        )
        self.assertIn("active_flag", text.lower())

    def test_orders_line_total_formula_is_duplicated_as_documented(self):
        """LOM-MOD-027: the same formula must appear on BOTH QUANTITY and
        DISCOUNT_AMOUNT triggers -- that duplication is the finding."""
        module = _parse("ORDERS")
        block = next(b for b in module.blocks if b.name == "BK_ORDER_LINE")
        hits = 0
        for item in block.items:
            if item.name in ("QUANTITY", "DISCOUNT_AMOUNT"):
                for trig in item.triggers:
                    text = trig.text.lower()
                    if "unit_price" in text and "discount_amount" in text:
                        hits += 1
        self.assertEqual(hits, 2, "expected the line-total formula duplicated on 2 triggers")

    def test_approvals_reject_bypasses_the_api_as_documented(self):
        """LOM-MOD-042: the reject action must NOT call lom_approval_api.reject --
        that bypass is the finding this fixture exists to demonstrate."""
        module = _parse("APPROVALS")
        all_text = json.dumps(
            [t.text for b in module.blocks for i in b.items for t in i.triggers]
            + [t.text for b in module.blocks for t in b.triggers]
        )
        self.assertNotIn("lom_approval_api.reject(", all_text.lower())
        self.assertIn("update lom_approvals", all_text.lower())


class ControlsMatchTheirRegistryEntries(unittest.TestCase):
    """The positive and negative controls are what make the registry a
    benchmark rather than a list of complaints: a classifier must leave the
    PRESERVE cases alone and must catch the bypasses. Each control is checked
    both in the fixture (the call is / is not there) and in the registry (the
    classification says so)."""

    @classmethod
    def setUpClass(cls):
        cls.by_id = {c["id"]: c for c in _load_ground_truth()["cases"]}

    def test_positive_controls_call_the_api_and_are_preserve(self):
        for case_id, (form, block, item, triggers, call) in POSITIVE_CONTROLS.items():
            module = _parse(form)
            for trigger_name in triggers:
                with self.subTest(case=case_id, trigger=trigger_name):
                    text = _trigger_text(module, block, item, trigger_name)
                    self.assertIn(call, text.lower())
                    self.assertIn(case_id, text, "control trigger must carry its own label")
            with self.subTest(case=case_id, registry="classification"):
                self.assertEqual(self.by_id[case_id]["classification"], "PRESERVE")

    def test_negative_controls_bypass_the_api_and_are_critical_manual_review(self):
        module = _parse("APPROVALS")
        for case_id, (button, forbidden_call) in NEGATIVE_CONTROLS.items():
            with self.subTest(case=case_id):
                text = _trigger_text(module, "BK_APPROVAL", button, "WHEN-BUTTON-PRESSED")
                self.assertIn("update lom_approvals", text.lower())
                self.assertNotIn(forbidden_call, text.lower())
                self.assertIn(case_id, text)
                self.assertEqual(self.by_id[case_id]["classification"], "MANUAL_REVIEW")
                self.assertEqual(self.by_id[case_id]["risk"], "CRITICAL")

    def test_010_and_011_are_the_documented_contrast_pair(self):
        """Both are WHEN-VALIDATE-ITEM checks on CUSTOMERS.fmb. 010 mirrors a
        CHECK constraint (nothing to centralize: CONVERT/LOW/B); 011
        re-implements a status rule the API owns (MOVE_TO_PLSQL_API/HIGH/E).
        A classifier that gives both the same label is wrong on one of them."""
        ten, eleven = self.by_id["LOM-MOD-010"], self.by_id["LOM-MOD-011"]
        self.assertEqual(
            (ten["classification"], ten["risk"], ten["category"]), ("CONVERT", "LOW", "B")
        )
        self.assertEqual(
            (eleven["classification"], eleven["risk"], eleven["category"]),
            ("MOVE_TO_PLSQL_API", "HIGH", "E"),
        )
        self.assertIn("LOM-MOD-011", ten.get("related") or [])


class RiskAndClassificationSetsAreExact(unittest.TestCase):
    """The docs name these sets explicitly (rollup, ADR-003, ADR-004,
    modernization-challenges). Pinning them here means a registry edit that
    adds or drops a HIGH/CRITICAL case cannot leave the prose stale."""

    @classmethod
    def setUpClass(cls):
        cls.cases = _load_ground_truth()["cases"]

    def _ids_where(self, field: str, value: str) -> set[str]:
        return {c["id"] for c in self.cases if c[field] == value}

    def test_critical_cases(self):
        self.assertEqual(
            self._ids_where("risk", "CRITICAL"),
            {"LOM-MOD-002", "LOM-MOD-031", "LOM-MOD-041", "LOM-MOD-042"},
        )

    def test_high_risk_cases(self):
        self.assertEqual(
            self._ids_where("risk", "HIGH"),
            {"LOM-MOD-011", "LOM-MOD-026", "LOM-MOD-027", "LOM-MOD-037"},
        )

    def test_move_to_plsql_api_cases(self):
        self.assertEqual(
            self._ids_where("classification", "MOVE_TO_PLSQL_API"),
            {
                "LOM-MOD-011", "LOM-MOD-025", "LOM-MOD-026",
                "LOM-MOD-027", "LOM-MOD-037", "LOM-MOD-039",
            },
        )

    def test_positive_controls_are_a_subset_of_preserve(self):
        preserve = self._ids_where("classification", "PRESERVE")
        self.assertLessEqual(set(POSITIVE_CONTROLS), preserve)


class GroundTruthRegistryIsConsistent(unittest.TestCase):
    """Every LOM-MOD id referenced anywhere in the lab must resolve, every
    case must use a value from the documented taxonomy, and every file a
    case cites must exist -- see metrics/compute_metrics.py for the live
    cross-check this duplicates as assertions."""

    @classmethod
    def setUpClass(cls):
        cls.ground_truth = _load_ground_truth()
        cls.by_id = {c["id"]: c for c in cls.ground_truth["cases"]}
        cls.metrics = _load_metrics_module()

    def _registered_numbers(self) -> set[str]:
        return {c["id"].rsplit("-", 1)[1] for c in self.ground_truth["cases"]}

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

    def test_id_range_has_exactly_the_documented_gap(self):
        """IDs are never resequenced (see `id_notes`); the only hole inside
        001..042 is the one the registry itself documents, and no ID above
        the last case is used anywhere."""
        unfilled = self.metrics.DOCUMENTED_UNFILLED_IDS
        expected = {f"LOM-MOD-{n:03d}" for n in range(1, 43)} - {
            f"LOM-MOD-{i}" for i in unfilled
        }
        self.assertEqual(set(self.by_id), expected)
        for unfilled_id in unfilled:
            with self.subTest(unfilled=unfilled_id):
                self.assertIn(unfilled_id, self.ground_truth["id_notes"])
                self.assertNotIn(f"LOM-MOD-{unfilled_id}", self.by_id)

    def test_referenced_ids_all_have_registry_entries(self):
        """forms/ and database/ are the answer key: every id they mention
        must be a case (the documented-unfilled ids are not allowed here)."""
        refs = self.metrics.count_lom_mod_refs(self.metrics.FIXTURE_DIRS)
        missing = set(refs["referenced_ids"]) - self._registered_numbers()
        self.assertEqual(
            missing,
            set(),
            f"IDs referenced in fixtures but missing from the registry: {sorted(missing)}",
        )

    def test_narrative_docs_reference_only_registered_or_documented_ids(self):
        """docs/, blueprint/, assessment/, README, HANDOFF and REVIEW may
        mention a documented-unfilled id; anything else must be a case."""
        refs = self.metrics.count_lom_mod_refs(self.metrics.DOC_SOURCES)
        missing = (
            set(refs["referenced_ids"])
            - self._registered_numbers()
            - self.metrics.DOCUMENTED_UNFILLED_IDS
        )
        self.assertEqual(
            missing,
            set(),
            f"IDs referenced in the narrative docs but unknown to the registry: "
            f"{sorted(missing)}",
        )

    def test_source_fields_cite_files_that_exist(self):
        for case in self.ground_truth["cases"]:
            with self.subTest(case=case["id"]):
                source = case["source"]
                paths = SOURCE_PATH.findall(source)
                bare = [
                    b for b in BARE_XML.findall(source)
                    if not any(p.endswith("/" + b) for p in paths)
                ]
                self.assertTrue(paths or bare, f"no file path in source: {source!r}")
                for rel in paths:
                    self.assertTrue((LAB_ROOT / rel).is_file(), f"{rel} cited but not committed")
                for name in bare:
                    self.assertTrue((XML_DIR / name).is_file(), f"{name} cited but not committed")

    def test_related_ids_resolve_and_are_not_self(self):
        for case in self.ground_truth["cases"]:
            for related in case.get("related") or []:
                with self.subTest(case=case["id"], related=related):
                    self.assertIn(related, self.by_id)
                    self.assertNotEqual(related, case["id"])


class InlineLabelsMatchRegistry(unittest.TestCase):
    """Fixture comments of the form `LOM-MOD-### (CLASSIFICATION, RISK risk,
    category X)` are the answer key a reader sees first. Whatever taxonomy
    tokens a label carries must agree with the registry; free-text tokens
    ("candidate", "this lab's canonical example") are ignored."""

    def test_every_inline_label_agrees_with_the_registry(self):
        ground_truth = _load_ground_truth()
        by_id = {c["id"]: c for c in ground_truth["cases"]}
        classifications = set(ground_truth["taxonomy"]["classification"])
        risks = set(ground_truth["taxonomy"]["risk"])
        seen = 0
        for path in _fixture_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, label in LOM_MOD_LABEL.findall(text):
                case = by_id[f"LOM-MOD-{number}"]
                where = f"{path.relative_to(LAB_ROOT)}: LOM-MOD-{number} ({label})"
                tokens = [t.strip() for t in label.split(",")]
                seen += 1
                with self.subTest(label=where):
                    first_word = tokens[0].split(" ")[0]
                    if first_word in classifications:
                        self.assertEqual(first_word, case["classification"], where)
                    for token in tokens:
                        risk = re.fullmatch(r"(\w+)(?: risk)?", token)
                        if risk and risk.group(1) in risks:
                            self.assertEqual(risk.group(1), case["risk"], where)
                        category = re.fullmatch(r"category ([A-F])", token)
                        if category:
                            self.assertEqual(category.group(1), case["category"], where)
        self.assertGreater(seen, 20, "expected the fixtures to carry inline labels")


class StatusMachineIsPinned(unittest.TestCase):
    """ADR-002 and docs/business-rules.md state that LOM_ORDER_STATUS.
    SEQUENCE_NO is descriptive and lom_order_api.is_valid_transition is the
    only authority. Those are claims about committed PL/SQL and seed data,
    so they are checked against that text -- no database is involved."""

    @classmethod
    def setUpClass(cls):
        seed = LOOKUP_SEED.read_text(encoding="utf-8")
        cls.sequence_no = {code: int(seq) for code, seq in SEED_STATUS_ROW.findall(seed)}
        body = ORDER_API_BODY.read_text(encoding="utf-8")
        start = body.index("function is_valid_transition(")
        end = body.index("end is_valid_transition;", start)
        cls.matrix = set(TRANSITION_PAIR.findall(body[start:end]))
        cls.body = body

    def test_seed_defines_the_eight_statuses_with_the_documented_sequence(self):
        self.assertEqual(
            self.sequence_no,
            {
                "DRAFT": 10, "SUBMITTED": 20, "PENDING_APPROVAL": 30, "REJECTED": 35,
                "APPROVED": 40, "RELEASED": 50, "SHIPPED": 60, "CANCELLED": 90,
            },
        )

    def test_legal_matrix_is_exactly_the_ten_documented_pairs(self):
        self.assertEqual(self.matrix, LEGAL_TRANSITIONS)
        self.assertEqual(len(self.matrix), 10)
        for status in {s for pair in self.matrix for s in pair}:
            self.assertIn(status, self.sequence_no, f"{status} used but not seeded")

    def test_sequence_no_is_descriptive_not_authoritative(self):
        """Every legal pair increases SEQUENCE_NO, so an "increase only"
        shortcut never rejects a legal move -- but it admits moves the
        matrix forbids. The matrix is therefore the only authority."""
        seq = self.sequence_no
        for pair in LEGAL_TRANSITIONS:
            with self.subTest(pair=pair):
                self.assertLess(seq[pair[0]], seq[pair[1]])
        increasing = {(a, b) for a in seq for b in seq if a != b and seq[a] < seq[b]}
        self.assertTrue(LEGAL_TRANSITIONS < increasing, "legal set must be a strict subset")
        for pair in INCREASING_BUT_ILLEGAL:
            with self.subTest(pair=pair):
                self.assertIn(pair, increasing)
                self.assertNotIn(pair, self.matrix)

    def test_transition_status_defaults_identity_to_the_database_user(self):
        """The premise of ADR-004: unless the caller passes p_changed_by,
        history rows are attributed to the session's database user, which
        under APEX is the engine's pool account, not the end user. The
        submit/release/ship procedures expose no identity parameter at all
        (documented as an open limitation, not fixed by this lab)."""
        self.assertRegex(self.body, r"p_changed_by\s+in\s+varchar2\s+default\s+user")
        spec = ORDER_API_SPEC.read_text(encoding="utf-8")
        for proc in ("submit_order", "release_order", "ship_order"):
            with self.subTest(procedure=proc):
                signature = re.search(rf"procedure\s+{proc}\s*\((.*?)\)\s*;", spec, re.DOTALL)
                self.assertIsNotNone(signature, f"{proc} not declared in the spec")
                self.assertNotIn("p_changed_by", signature.group(1))


class RollupTablesMatchRegistry(unittest.TestCase):
    """assessment/complexity-and-risk-rollup.md says its tables are recomputed
    here. Every count in it is compared with the registry via the same
    functions metrics/compute_metrics.py prints."""

    @classmethod
    def setUpClass(cls):
        cls.registry = _load_metrics_module().count_registry_cases()
        cls.rows = _rollup_rows()
        cls.text = ROLLUP.read_text(encoding="utf-8")

    def _table(self, keys: set[str]) -> dict[str, int]:
        return {name: count for _, name, count, _ in self.rows if name in keys}

    def test_classification_table(self):
        expected = self.registry["by_classification"]
        self.assertEqual(self._table(set(expected)), expected)

    def test_risk_table(self):
        expected = self.registry["by_risk"]
        self.assertEqual(self._table(set(expected)), expected)

    def test_category_table(self):
        expected = self.registry["by_category"]
        self.assertEqual(self._table(set(expected)), expected)

    def test_module_table_counts_and_dominant_classifications(self):
        by_module = self.registry["by_module"]
        module_rows = [r for r in self.rows if r[0].startswith("By module")]
        self.assertEqual({name for _, name, _, _ in module_rows}, set(by_module))
        for _, name, count, dominant in module_rows:
            with self.subTest(module=name):
                per_class = by_module[name]
                self.assertEqual(count, sum(per_class.values()))
                top = max(per_class.values())
                if dominant.startswith("1 each of"):
                    self.assertEqual(top, 1)
                    self.assertEqual(set(re.findall(r"`(\w+)`", dominant)), set(per_class))
                else:
                    listed = {
                        c: int(n) for c, n in re.findall(r"`(\w+)` \((\d+)\)", dominant)
                    }
                    self.assertEqual(listed, {c: n for c, n in per_class.items() if n == top})

    def test_derived_sentences_use_registry_numbers(self):
        by_class = self.registry["by_classification"]
        total = self.registry["count"]
        human = by_class["MANUAL_REVIEW"] + by_class["MOVE_TO_PLSQL_API"]
        controls = by_class["PRESERVE"] + by_class["CONVERT"]
        self.assertIn(
            f"{human} of {total} cases (`MANUAL_REVIEW` + `MOVE_TO_PLSQL_API`)", self.text
        )
        self.assertIn(f"`PRESERVE`/`CONVERT` rows ({controls} cases)", self.text)


class ReadmeInventoryClaimsAreMeasured(unittest.TestCase):
    """The README's headline inventory (modules, tables, views, packages,
    cases) is quoted from measurements, and this pins the quote to them."""

    def test_readme_numbers_match_the_committed_artifacts(self):
        metrics = _load_metrics_module()
        database = metrics.count_sql_objects()
        views = 0
        for path in (LAB_ROOT / "database" / "views").glob("*.sql"):
            text = path.read_text(encoding="utf-8")
            views += len(re.findall(r"(?im)^create or replace (?:force )?view\s", text))
        registry = metrics.count_registry_cases()
        readme = README.read_text(encoding="utf-8")
        last_id = registry["ids"][-1]
        self.assertEqual(len(metrics.FORMS), 4)
        self.assertEqual(
            sorted(XML_DIR.glob("*.xml")), sorted(XML_DIR / f"{n}.xml" for n in metrics.FORMS)
        )
        self.assertIn(
            f"{registry['count']} modernization cases (`LOM-MOD-001`..`{last_id}`", readme
        )
        self.assertIn(
            f"{database['tables']} tables (DDL), {views} views, "
            f"{database['packages']} PL/SQL API packages",
            readme,
        )
        self.assertEqual(database["packages"], database["package_bodies"])
        self.assertIn(f"{len(metrics.FORMS)} Oracle Forms modules", readme)


if __name__ == "__main__":
    unittest.main()
