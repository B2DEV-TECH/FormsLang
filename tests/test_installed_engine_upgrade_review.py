"""An engine upgrade can stale a review without deleting its decision history."""

from __future__ import annotations

import pytest

from examples.verify.installed_engine_check import (
    CheckFailed,
    verify_preserved_blueprint_review,
    verify_reinstalled_blueprint_reviews,
)

SEED = {
    "blueprint_entity": "trigger:original",
    "blueprint_revision": "finding-revision-1",
    "blueprint_source_revision": "source-revision-1",
    "blueprint_engine_version": "blueprint-analysis/1",
}
CANDIDATE = {
    "blueprint_revision": "finding-revision-2",
    "blueprint_source_revision": "source-revision-2",
    "blueprint_engine_version": "blueprint-analysis/4",
}


def _prior(state: str = "STALE") -> dict:
    return {
        "entity": SEED["blueprint_entity"],
        "revision": SEED["blueprint_revision"],
        "review_state": state,
        "review_history": [
            {
                "entity": SEED["blueprint_entity"],
                "revision": SEED["blueprint_revision"],
                "action": "DEFER",
                "reviewer": "installer QA",
                "comment": "Synthetic pre-upgrade architecture decision",
                "finding_snapshot": {
                    "engine_version": SEED["blueprint_engine_version"],
                    "source_revision": SEED["blueprint_source_revision"],
                },
            }
        ],
    }


@pytest.mark.parametrize(("stale_engine", "state"), [(True, "STALE"), (False, "DEFER")])
def test_upgrade_keeps_original_review_with_correct_applicability(
    stale_engine: bool, state: str
) -> None:
    verify_preserved_blueprint_review(
        _prior(state), SEED, stale_engine=stale_engine,
        current_source_revision=SEED["blueprint_source_revision"],
    )


@pytest.mark.parametrize("damage", ["missing_history", "promoted", "source_changed"])
def test_upgrade_rejects_lost_or_rewritten_review(damage: str) -> None:
    prior = _prior()
    source = SEED["blueprint_source_revision"]
    if damage == "missing_history":
        prior["review_history"] = []
    elif damage == "promoted":
        prior["review_history"][0]["action"] = "APPROVE"
    else:
        source = "source-revision-2"

    with pytest.raises(CheckFailed):
        verify_preserved_blueprint_review(
            prior, SEED, stale_engine=True, current_source_revision=source,
        )


def _reinstalled() -> dict:
    prior = _prior("DEFER")
    prior["revision"] = CANDIDATE["blueprint_revision"]
    prior["review_history"].insert(0, {
        "entity": SEED["blueprint_entity"],
        "revision": CANDIDATE["blueprint_revision"],
        "action": "DEFER",
        "reviewer": "installer QA",
        "comment": "Installer acceptance: investigate after upgrade",
        "finding_snapshot": {
            "engine_version": CANDIDATE["blueprint_engine_version"],
            "source_revision": CANDIDATE["blueprint_source_revision"],
        },
    })
    return prior


def test_reinstall_keeps_both_bound_reviews() -> None:
    verify_reinstalled_blueprint_reviews(
        _reinstalled(), SEED, CANDIDATE, stale_engine=False,
        current_source_revision=CANDIDATE["blueprint_source_revision"],
    )


@pytest.mark.parametrize("damage", ["baseline_lost", "candidate_lost", "promoted", "source_changed", "engine_stale"])
def test_reinstall_rejects_lost_or_inapplicable_review(damage: str) -> None:
    prior = _reinstalled()
    source = CANDIDATE["blueprint_source_revision"]
    stale = False
    if damage == "baseline_lost":
        prior["review_history"].pop()
    elif damage == "candidate_lost":
        prior["review_history"].pop(0)
    elif damage == "promoted":
        prior["review_history"][0]["action"] = "APPROVE"
    elif damage == "source_changed":
        source = "unexpected-source"
    else:
        stale = True
    with pytest.raises(CheckFailed):
        verify_reinstalled_blueprint_reviews(
            prior, SEED, CANDIDATE, stale_engine=stale,
            current_source_revision=source,
        )
