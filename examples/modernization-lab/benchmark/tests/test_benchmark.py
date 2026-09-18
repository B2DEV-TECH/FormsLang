"""Unit and integration test suite for FormsLang Modernization Benchmark.

Tests cover:
- Sanitizer determinism, semantic preservation, and answer-key stripping.
- Leakage detector and deliberate contamination rejection.
- Manifest completeness and hash integrity.
- Observability categorization of all 41 cases.
- Prediction schema conformance.
- Offline evaluator correctness with synthetic edge cases.
- Ground truth immutability.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Set up path imports
TESTS_DIR = Path(__file__).resolve().parent
BENCHMARK_DIR = TESTS_DIR.parent
LAB_ROOT = BENCHMARK_DIR.parent
REPO_ROOT = LAB_ROOT.parent

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BENCHMARK_DIR))

import discover
import evaluate
import sanitize

from formslang.parser import parse_xml

GROUND_TRUTH_PATH = LAB_ROOT / "expected" / "modernization-ground-truth.json"
CANONICAL_XML_DIR = LAB_ROOT / "forms" / "xml"


@pytest.fixture
def workspace_tmp():
    """Temporary directory located strictly inside the workspace."""
    d = BENCHMARK_DIR / "generated" / "test_scratch"
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestSanitizer:
    """Validate sanitizer correctness, determinism, and semantic preservation."""

    def test_sanitizer_removes_answer_keys(self):
        sample = (
            '<!-- LOM-MOD-013 (CONVERT, category A): sequence default -->\n'
            '<Trigger Name="PRE-INSERT" TriggerText="-- LOM-MOD-013 (CONVERT, LOW risk):\n'
            ':BK.ID := SEQ.NEXTVAL;\n" />'
        )
        cleaned = sanitize.sanitize_text(sample)
        assert "LOM-MOD-013" not in cleaned
        assert "category A" not in cleaned
        assert "(CONVERT, LOW risk)" not in cleaned
        assert ":BK.ID := SEQ.NEXTVAL;" in cleaned

    def test_sanitizer_is_byte_deterministic(self, workspace_tmp):
        for xml_file in CANONICAL_XML_DIR.glob("*.xml"):
            out1 = workspace_tmp / f"pass1_{xml_file.name}"
            out2 = workspace_tmp / f"pass2_{xml_file.name}"
            hash1 = sanitize.sanitize_file(xml_file, out1)
            hash2 = sanitize.sanitize_file(xml_file, out2)
            assert hash1 == hash2, f"Sanitization non-deterministic for {xml_file.name}"
            assert out1.read_bytes() == out2.read_bytes()

    def test_sanitizer_preserves_semantic_structure(self, workspace_tmp):
        for xml_file in sorted(CANONICAL_XML_DIR.glob("*.xml")):
            out_file = workspace_tmp / xml_file.name
            sanitize.sanitize_file(xml_file, out_file)

            orig_mod = parse_xml(xml_file)
            san_mod = parse_xml(out_file)

            assert len(orig_mod.blocks) == len(san_mod.blocks), f"Block mismatch in {xml_file.name}"
            orig_items = sum(len(b.items) for b in orig_mod.blocks)
            san_items = sum(len(b.items) for b in san_mod.blocks)
            assert orig_items == san_items, f"Item mismatch in {xml_file.name}"

            orig_triggers = len(orig_mod.triggers) + sum(len(b.triggers) for b in orig_mod.blocks) + sum(len(i.triggers) for b in orig_mod.blocks for i in b.items)
            san_triggers = len(san_mod.triggers) + sum(len(b.triggers) for b in san_mod.blocks) + sum(len(i.triggers) for b in san_mod.blocks for i in b.items)
            assert orig_triggers == san_triggers, f"Trigger mismatch in {xml_file.name}"
            assert len(orig_mod.lovs) == len(san_mod.lovs)
            assert len(orig_mod.record_groups) == len(san_mod.record_groups)
            assert len(orig_mod.relations) == len(san_mod.relations)
            assert len(orig_mod.program_units) == len(san_mod.program_units)


class TestLeakageAndContamination:
    """Validate answer-key leakage scanning and deliberate contamination rejection."""

    def test_clean_sanitized_xml_has_zero_leakage(self, workspace_tmp):
        for xml_file in CANONICAL_XML_DIR.glob("*.xml"):
            out = workspace_tmp / xml_file.name
            sanitize.sanitize_file(xml_file, out)
        sanitize.verify_no_leakage(workspace_tmp)

    def test_contamination_is_detected_and_rejected(self, workspace_tmp):
        contaminated_file = workspace_tmp / "CONTAMINATED.xml"
        contaminated_file.write_text(
            '<Module Name="TEST">\n'
            '  <!-- LOM-MOD-999 (MANUAL_REVIEW, CRITICAL) -->\n'
            '  <Trigger Name="PRE-INSERT" TriggerText="NULL;" />\n'
            '</Module>',
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="Answer-key leakage detected"):
            sanitize.verify_no_leakage(workspace_tmp)

    def test_detect_leakage_in_text(self):
        cases = [
            "LOM-MOD-001",
            "ground truth answer key",
            "expected-decision is CONVERT",
            "expected_action: DROP",
            "MANUAL_REVIEW, CRITICAL",
            "category F architecture",
        ]
        for c in cases:
            assert len(sanitize.detect_leakage_in_text(c)) > 0, f"Failed to catch: {c}"


class TestManifest:
    """Validate input manifest structure, hashes, and file isolation."""

    def test_manifest_contains_only_allowed_files(self):
        baseline_manifest = BENCHMARK_DIR / "baselines" / "v1" / "manifest.json"
        if not baseline_manifest.exists():
            pytest.skip("Baseline v1 manifest not yet created")

        data = json.loads(baseline_manifest.read_text(encoding="utf-8"))
        assert data["protocol_version"] == "1.0"
        assert len(data["files"]) == 4

        allowed_basenames = {"APPROVALS.xml", "CUSTOMERS.xml", "INVENTORY.xml", "ORDERS.xml"}
        for f in data["files"]:
            orig_name = Path(f["original_path"]).name
            assert orig_name in allowed_basenames
            assert f["original_sha256"] != f["sanitized_sha256"]
            assert len(f["sanitized_sha256"]) == 64


class TestObservability:
    """Validate all 41 cases are categorized with valid sources and non-null reasons."""

    def test_all_41_cases_represented(self):
        obs = discover.analyze_observability(GROUND_TRUTH_PATH, CANONICAL_XML_DIR)
        assert obs["total_cases"] == 41
        assert obs["fully_observable"] == 16
        assert obs["partially_observable"] == 12
        assert obs["not_observable"] == 13

        case_ids = [c["case_id"] for c in obs["cases"]]
        assert len(case_ids) == 41
        assert len(set(case_ids)) == 41
        assert "LOM-MOD-040" not in case_ids

        for c in obs["cases"]:
            assert c["observability"] in discover.OBSERVABILITY_STATUSES
            assert len(c["reason"]) > 0
            assert len(c["required_sources"]) > 0


class TestEvaluatorLogic:
    """Prove evaluator metrics on small synthetic test cases with known answers."""

    def test_evaluator_perfect_match(self):
        synthetic_preds = {
            "source_commit": "abc1234",
            "engine_path": "mock.engine",
            "predictions": [
                {
                    "finding_id": "f1",
                    "status": "PREDICTED",
                    "source": {"module": "ORDERS", "block": "BK_ORDER_LINE", "item": "QUANTITY", "trigger": "WHEN-VALIDATE-ITEM"},
                    "classification": "REFACTOR",
                    "risk": "HIGH",
                    "verdict": "ASSISTED",
                    "evidence": [],
                    "raw_output_ref": "f1",
                }
            ]
        }
        synthetic_gt = {
            "cases": [
                {
                    "id": "LOM-MOD-026",
                    "classification": "REFACTOR",
                    "risk": "HIGH",
                    "source": "forms/xml/ORDERS.xml (BK_ORDER_LINE.QUANTITY, WHEN-VALIDATE-ITEM)",
                }
            ]
        }
        synthetic_obs = {
            "cases": [
                {"case_id": "LOM-MOD-026", "observability": "FULLY_OBSERVABLE", "reason": "visible"}
            ]
        }
        rep = evaluate.evaluate_run(synthetic_preds, synthetic_obs, synthetic_gt, "fake_hash")
        assert rep["classification_metrics"]["observable_exact_accuracy"] == 1.0
        assert rep["risk_metrics"]["exact_accuracy"] == 1.0
        assert rep["coverage"]["predicted"] == 1

    def test_evaluator_all_wrong(self):
        synthetic_preds = {
            "source_commit": "abc1234",
            "engine_path": "mock.engine",
            "predictions": [
                {
                    "finding_id": "f1",
                    "status": "PREDICTED",
                    "source": {"module": "ORDERS", "block": "BK_ORDER_LINE", "item": "QUANTITY", "trigger": "WHEN-VALIDATE-ITEM"},
                    "classification": "DROP",
                    "risk": "LOW",
                    "verdict": "DROP",
                    "evidence": [],
                    "raw_output_ref": "f1",
                }
            ]
        }
        synthetic_gt = {
            "cases": [
                {
                    "id": "LOM-MOD-026",
                    "classification": "REFACTOR",
                    "risk": "HIGH",
                    "source": "forms/xml/ORDERS.xml (BK_ORDER_LINE.QUANTITY, WHEN-VALIDATE-ITEM)",
                }
            ]
        }
        synthetic_obs = {
            "cases": [
                {"case_id": "LOM-MOD-026", "observability": "FULLY_OBSERVABLE", "reason": "visible"}
            ]
        }
        rep = evaluate.evaluate_run(synthetic_preds, synthetic_obs, synthetic_gt, "fake_hash")
        assert rep["classification_metrics"]["observable_exact_accuracy"] == 0.0
        assert rep["risk_metrics"]["exact_accuracy"] == 0.0

    def test_evaluator_safety_metrics_false_automation(self):
        # Case requires MANUAL_REVIEW, predicted as CONVERT -> false automation
        synthetic_preds = {
            "source_commit": "abc",
            "engine_path": "mock.engine",
            "predictions": [
                {
                    "finding_id": "f1",
                    "status": "PREDICTED",
                    "source": {"module": "APPROVALS", "block": "BK_APPROVAL", "item": "BT_APPROVE", "trigger": "WHEN-BUTTON-PRESSED"},
                    "classification": "CONVERT",
                    "risk": "LOW",
                    "verdict": "AUTO",
                    "evidence": [],
                    "raw_output_ref": "f1",
                }
            ]
        }
        synthetic_gt = {
            "cases": [
                {
                    "id": "LOM-MOD-041",
                    "classification": "MANUAL_REVIEW",
                    "risk": "CRITICAL",
                    "source": "forms/xml/APPROVALS.xml (BT_APPROVE, WHEN-BUTTON-PRESSED)",
                }
            ]
        }
        synthetic_obs = {
            "cases": [
                {"case_id": "LOM-MOD-041", "observability": "PARTIALLY_OBSERVABLE", "reason": "visible"}
            ]
        }
        rep = evaluate.evaluate_run(synthetic_preds, synthetic_obs, synthetic_gt, "fake_hash")
        assert rep["safety_metrics"]["manual_review_recall"] == 0.0
        assert rep["safety_metrics"]["false_automation_rate"] == 1.0
        assert rep["safety_metrics"]["critical_safety_misses_count"] == 1


class TestGroundTruthImmutability:
    """Ensure ground truth is not altered during dry run or evaluation."""

    def test_ground_truth_sha256_unmodified(self):
        initial_hash = hashlib.sha256(GROUND_TRUTH_PATH.read_bytes()).hexdigest()

        # Run dry run via subprocess
        res = subprocess.run(
            [sys.executable, str(BENCHMARK_DIR / "run_benchmark.py"), "--dry-run"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0

        final_hash = hashlib.sha256(GROUND_TRUTH_PATH.read_bytes()).hexdigest()
        assert initial_hash == final_hash, "Ground truth was modified during benchmark dry run!"
