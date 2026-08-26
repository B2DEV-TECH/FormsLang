"""The catalog is the product. These tests guard its contract."""

from __future__ import annotations

import pytest

from formslang import rules


def test_every_entry_carries_a_known_verdict_and_a_target():
    for table in (rules.BUILTINS, rules.TRIGGERS, rules.SYSTEM_VARS):
        for name, (verdict, target) in table.items():
            assert verdict in rules.VERDICT_ORDER, name
            assert target.strip(), name


def test_every_verdict_has_a_weight():
    for verdict in rules.VERDICT_ORDER:
        assert rules.VERDICT_WEIGHT[verdict] > 0


def test_unknown_is_never_cheaper_than_assisted():
    """Catalog debt must never look like an easy win."""
    assert rules.VERDICT_WEIGHT[rules.UNKNOWN] > rules.VERDICT_WEIGHT[rules.ASSISTED]
    assert rules.VERDICT_WEIGHT[rules.UNKNOWN] > rules.VERDICT_WEIGHT[rules.AUTO]


@pytest.mark.parametrize(
    "name,verdict",
    [
        ("EXECUTE_QUERY", rules.AUTO),
        ("execute_query", rules.AUTO),
        ("SYNCHRONIZE", rules.DROP),
        ("CALL_FORM", rules.ASSISTED),
        ("HOST", rules.MANUAL),
        ("WEBUTIL_FILE.FILE_OPEN_DIALOG", rules.MANUAL),
        ("SYSTEM.RECORD_STATUS", rules.ASSISTED),
        ("NOT_A_REAL_BUILTIN", rules.UNKNOWN),
    ],
)
def test_builtin_classification(name, verdict):
    assert rules.classify_builtin(name)[0] == verdict


@pytest.mark.parametrize(
    "name,verdict",
    [
        ("WHEN-VALIDATE-ITEM", rules.AUTO),
        ("WHEN-MOUSE-MOVE", rules.DROP),
        ("PRE-QUERY", rules.ASSISTED),
        ("ON-LOCK", rules.MANUAL),
        ("KEY-NXTBLK", rules.DROP),
        ("KEY-F7", rules.ASSISTED),
        ("WHEN-BANANA-SPLIT", rules.UNKNOWN),
    ],
)
def test_trigger_classification(name, verdict):
    assert rules.classify_trigger(name)[0] == verdict


def test_worst_picks_the_most_expensive():
    assert rules.worst([rules.AUTO, rules.MANUAL, rules.DROP]) == rules.MANUAL
    assert rules.worst([rules.AUTO, rules.DROP]) == rules.DROP
    assert rules.worst([]) == rules.AUTO


def test_catalog_size_reports_every_table():
    size = rules.catalog_size()
    assert size["builtins"] == len(rules.BUILTINS)
    assert size["triggers"] == len(rules.TRIGGERS)
    assert size["system_vars"] == len(rules.SYSTEM_VARS)
    assert size["client_prefixes"] == len(rules.CLIENT_SIDE_PREFIXES)
