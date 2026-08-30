"""The structured catalog: one row per construct, no invented knowledge."""

from __future__ import annotations

import pytest

from formslang import rules


def test_every_builtin_and_system_var_has_a_catalog_row():
    for name in (*rules.BUILTINS, *rules.SYSTEM_VARS):
        assert name in rules.CATALOG, name


def test_catalog_never_disagrees_with_the_verdict_tables():
    """One source of truth. The catalog derives, it does not restate."""
    for name, (verdict, target) in rules.BUILTINS.items():
        spec = rules.CATALOG[name]
        assert spec.verdict == verdict, name
        assert spec.apex == target, name


def test_every_row_carries_a_known_category_and_class():
    for spec in rules.CATALOG.values():
        assert spec.category in rules.CATEGORIES, spec.name
        assert spec.migration_class in rules.MIGRATION_CLASSES, spec.name
        assert 0.0 <= spec.risk <= 1.0, spec.name
        assert spec.forms_behavior.strip(), spec.name


def test_every_category_explains_itself():
    for cat in rules.CATEGORIES.values():
        assert cat.label.strip() and cat.forms_behavior.strip()
        assert cat.risk_reason.strip() and cat.review_area.strip()
        assert cat.assisted in rules.MIGRATION_CLASSES
        assert cat.manual in rules.MIGRATION_CLASSES


@pytest.mark.parametrize(
    "name,migration_class",
    [
        ("EXECUTE_QUERY", rules.DIRECT_EQUIVALENT),
        ("HOST", rules.UNSUPPORTED),
        ("SYNCHRONIZE", rules.NOT_REQUIRED),
        ("GO_BLOCK", rules.CLIENT_SIDE_REPLACEMENT),
        ("NAME_IN", rules.SERVER_SIDE_REPLACEMENT),
        ("CREATE_TIMER", rules.ARCHITECTURAL_REDESIGN),
        ("FORMS_DDL", rules.MANUAL_REVIEW),
    ],
)
def test_known_constructs_land_in_the_expected_class(name, migration_class):
    assert rules.spec_for(name).migration_class == migration_class


def test_a_dropped_construct_is_not_filed_as_a_missing_feature():
    """DROP is a gain, not a gap. Counting it as UNSUPPORTED would lie."""
    for name, (verdict, _) in rules.BUILTINS.items():
        if verdict == rules.DROP:
            assert rules.CATALOG[name].migration_class == rules.NOT_REQUIRED, name


def test_unknown_names_come_back_honest_not_invented():
    spec = rules.spec_for("NOT_A_REAL_BUILTIN")
    assert spec.known is False
    assert spec.verdict == rules.UNKNOWN
    assert spec.migration_class == rules.MANUAL_REVIEW
    assert spec.category == "unknown"


def test_thick_client_packages_resolve_through_their_prefix():
    spec = rules.spec_for("WEBUTIL_FILE.FILE_OPEN_DIALOG")
    assert spec.known is True
    assert spec.verdict == rules.MANUAL
    assert spec.migration_class == rules.UNSUPPORTED


def test_lookup_is_case_insensitive():
    assert rules.spec_for("commit_form").name == rules.spec_for("COMMIT_FORM").name


def test_trigger_risk_answers_for_every_catalogued_trigger():
    for name in rules.TRIGGERS:
        weight, _reason = rules.trigger_risk(name)
        assert 0.0 <= weight <= 1.0, name


def test_an_uncatalogued_trigger_is_priced_as_unknown():
    weight, reason = rules.trigger_risk("WHEN-SOMETHING-INVENTED")
    assert weight == rules._VERDICT_RISK[rules.UNKNOWN]
    assert "catalog" in reason.lower()


def test_coverage_counts_every_row_exactly_once():
    assert sum(rules.catalog_coverage().values()) == len(rules.CATALOG)
