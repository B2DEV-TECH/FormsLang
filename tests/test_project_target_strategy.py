"""Target strategy tests for FormsLang 2.1+.

Validates target-unselected, generic modernization, and APEX target profiles,
descriptor serialization round-trips, and fail-closed generation gates.
"""

import tempfile
from pathlib import Path

import pytest

from formslang.project_generation import ProjectGenerationService
from formslang.project_model import (
    SUPPORTED_TARGET_PROFILES,
    ProjectDescriptor,
    ProjectError,
    SourceRoot,
    TargetProfile,
    descriptor_from_dict,
    descriptor_to_dict,
    validate_descriptor,
)
from formslang.project_service import ProjectService
from formslang.projects import local_project_access


def make_descriptor(target: TargetProfile) -> ProjectDescriptor:
    return ProjectDescriptor(
        id="a" * 32,
        name="Target Strategy Test",
        source_roots=(SourceRoot("forms", "forms", "."),),
        target=target,
    )


def test_supported_target_profiles_are_valid():
    for profile in SUPPORTED_TARGET_PROFILES:
        desc = make_descriptor(profile)
        validate_descriptor(desc)
        payload = descriptor_to_dict(desc)
        restored = descriptor_from_dict(payload)
        assert restored.target == profile


def test_unsupported_target_profile_rejected():
    invalid_profiles = [
        TargetProfile(platform="Java", version="17", representation="Spring"),
        TargetProfile(platform="DotNet", version="8.0", representation="C#"),
        TargetProfile(platform="Oracle APEX", version="99.9", representation="APEXlang"),
        TargetProfile(platform="UNSELECTED", version="26.1", representation="none"),
    ]
    for invalid in invalid_profiles:
        with pytest.raises(ProjectError, match="Unsupported target profile"):
            validate_descriptor(make_descriptor(invalid))


def test_descriptor_from_dict_maps_unselected_and_generic():
    base = {
        "id": "b" * 32,
        "name": "Unselected Estate",
        "source_roots": [{"id": "forms", "kind": "forms", "path": "."}],
    }
    # Unselected mapping
    unselected_payload = {**base, "target_platform": "UNSELECTED"}
    desc_unselected = descriptor_from_dict(unselected_payload)
    assert desc_unselected.target.platform == "UNSELECTED"
    assert desc_unselected.target.version == "none"

    # Generic mapping
    generic_payload = {**base, "target_platform": "Generic Modernization"}
    desc_generic = descriptor_from_dict(generic_payload)
    assert desc_generic.target.platform == "Generic Modernization"
    assert desc_generic.target.version == "1.0"
    assert desc_generic.target.representation == "Neutral Backlog"

    # Default fallback remains APEX 26.1
    default_desc = descriptor_from_dict(base)
    assert default_desc.target.platform == "Oracle APEX"
    assert default_desc.target.version == "26.1"


def test_project_service_creates_unselected_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        access = local_project_access(root, approved_roots=(root,))
        service = ProjectService(access)
        unselected_target = TargetProfile(platform="UNSELECTED", version="none", representation="none")

        try:
            created = service.create(
                "Intelligence Only",
                roots=(SourceRoot("src", "forms", "."),),
                target=unselected_target,
            )
            assert created.target == unselected_target
        finally:
            service.close()

        # Reopen and verify persistence
        reopened_service = ProjectService(access)
        try:
            opened = reopened_service.open()
            assert opened.target == unselected_target
        finally:
            reopened_service.close()


def test_generation_service_fails_closed_when_target_unselected():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        access = local_project_access(root, approved_roots=(root,))
        service = ProjectService(access)
        unselected_target = TargetProfile(platform="UNSELECTED", version="none", representation="none")
        try:
            service.create(
                "Intelligence Only",
                roots=(SourceRoot("src", "forms", "."),),
                target=unselected_target,
            )

            gen_service = ProjectGenerationService(service)
            # Detail checks report blocker
            assessment = {
                "project_id": "test_proj_id",
                "status": "Current",
                "analysis_revision": "c" * 64,
                "source_revision": "d" * 64,
                "review_revision": 0,
                "target": {"platform": "UNSELECTED", "version": "none", "representation": "none"},
                "blueprint": {"entities": [{"id": "form:dummy", "type": "FORM", "module": "src/dummy.xml"}], "findings": [], "edges": []},
                "source_manifest": [{"source_id": "source:dummy", "root_id": "src", "relative_path": "dummy.xml", "selected": True, "status": "available", "representation": "xml"}],
            }
            detail = gen_service._detail(assessment, {"status": "CURRENT"}, "source:dummy")
            assert not detail["ready"]
            assert any(b["code"] == "TARGET_STRATEGY_UNSELECTED" for b in detail["blockers"])

            # Operation checks fail closed
            with pytest.raises(ProjectError, match="Target strategy is unselected"):
                gen_service.prepare("source:dummy", {})

            with pytest.raises(ProjectError, match="Target strategy is unselected"):
                gen_service.configure("source:dummy", {})

            with pytest.raises(ProjectError, match="Target strategy is unselected"):
                gen_service.code("source:dummy", "task:1", {})

            with pytest.raises(ProjectError, match="Target strategy is unselected"):
                gen_service.generate({})
        finally:
            service.close()
