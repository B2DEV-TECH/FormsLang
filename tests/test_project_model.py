"""Portable metadata validation rejects secrets, invalid targets and path redirection."""

from dataclasses import replace

import pytest

from formslang.project_model import (
    ProjectDescriptor,
    ProjectError,
    SourceRoot,
    TargetProfile,
    canonical_json,
    descriptor_from_dict,
    descriptor_to_dict,
)


def descriptor():
    return ProjectDescriptor(id="a" * 32, name="Órders",
                             source_roots=(SourceRoot("forms", "forms", "../Legacy Forms"),))


def test_round_trip_preserves_unicode_and_flat_target():
    project = descriptor()
    payload = descriptor_to_dict(project)
    assert payload["target_version"] == "26.1"
    assert payload["target_platform"] == "Oracle APEX"
    assert payload["target_representation"] == "APEXlang"
    assert "target" not in payload
    assert descriptor_from_dict(payload) == project


@pytest.mark.parametrize("change", [
    {"name": ""}, {"name": "  "}, {"name": "a" * 201}, {"name": 12},
    {"description": "a" * 4001}, {"client_label": "a" * 201}, {"name": "x\0y"},
    {"id": "../x"}, {"project_version": "formslang-project/99"},
    {"store": "../outside.db"}, {"store": "C:/outside.db"}, {"store": "nested/session.db"},
    {"target": TargetProfile(version="99")}, {"analysis_revision": "invalid"},
    {"source_roots": (SourceRoot("f", "forms", "."), SourceRoot("f", "forms", "a"))},
    {"source_roots": (SourceRoot("f", "unknown", "."),)},
    {"source_roots": (SourceRoot("../f", "forms", "."),)},
    {"source_roots": (SourceRoot("f", "forms", "x\0y"),)},
    {"source_roots": tuple(SourceRoot(f"f{i}", "forms", ".") for i in range(129))},
])
def test_invalid_metadata_is_not_serialized(change):
    with pytest.raises(ProjectError):
        descriptor_to_dict(replace(descriptor(), **change))


@pytest.mark.parametrize("field", ["password", "api_key", "source_text", "target"])
def test_unknown_fields_rejected_without_value_leak(field):
    with pytest.raises(ProjectError) as error:
        descriptor_from_dict({**descriptor_to_dict(descriptor()), field: "private-sentinel"})
    assert "private-sentinel" not in str(error.value)


def test_nested_unknown_and_wrong_types_rejected():
    payload = descriptor_to_dict(descriptor())
    payload["source_roots"][0]["password"] = "private"
    with pytest.raises(ProjectError):
        descriptor_from_dict(payload)
    for payload in ([], None, {"name": "x"}):
        with pytest.raises(ProjectError):
            descriptor_from_dict(payload)


def test_canonical_json_is_sorted_unicode_and_rejects_nan():
    assert canonical_json({"z": 1, "a": "ç"}) == '{"a":"ç","z":1}'
    with pytest.raises(ValueError):
        canonical_json({"score": float("nan")})
