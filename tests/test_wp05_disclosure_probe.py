"""Synthetic disclosure probes for the two unmeasured M0 output paths."""

import json
import shutil
from pathlib import Path

import pytest

from formslang import rbac
from formslang.convert import ConversionTask, build_prompt
from formslang.project_intake import ProjectIntake
from formslang.project_service import ProjectService

FIXTURE_FORMS = Path(__file__).parent / "fixtures" / "ecosystem" / "visual_hierarchy"
SYNTHETIC_PATH = r"C:\Users\ProbeOwner\Private\SECRET_FORM"
SYNTHETIC_CREDENTIAL = "synthetic_password_do_not_disclose_8472"


def test_local_system_map_json_probe_for_literal_host_path(tmp_path, monkeypatch):
    """A symbolic CALL_FORM target must reveal whether the map exports its literal."""
    monkeypatch.setenv("FORMSLANG_AUTH", "0")
    forms = tmp_path / "forms"
    shutil.copytree(FIXTURE_FORMS, forms)
    source = forms / "SCREENS.xml"
    source.write_text(source.read_text(encoding="utf-8").replace("NOT_SUPPLIED", SYNTHETIC_PATH),
                      encoding="utf-8")
    intake = ProjectIntake(tmp_path / "data", tmp_path / "config")
    project_id = intake.create("Synthetic disclosure probe", [intake.select_source(forms, "forms")])["project"]["id"]
    authorize = lambda: intake.access(project_id, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    try:
        assert service.analyze(expected_revision=None, expected_configuration=0)["status"] == "COMPLETED"
        result = service.system_map(focus="SCREENS")
        assert any("SECRET_FORM" in node["name"] for node in result["nodes"])
        payload = json.dumps(result)
        assert SYNTHETIC_PATH not in payload
        assert "ProbeOwner" not in payload
        assert "Private" not in payload
    finally:
        service.close()


@pytest.mark.xfail(strict=True, reason="WP-05 probe: raw selected source is included in the AI prompt; consent contract belongs to WP-47")
def test_conversion_prompt_probe_for_embedded_credential_and_host_path():
    """The selected source unit may contain data outside structural evidence."""
    task = ConversionTask(
        id="synthetic-task", module="SYNTHETIC", kind="trigger", name="WHEN-BUTTON-PRESSED",
        owner="", source=f"BEGIN p('{SYNTHETIC_CREDENTIAL}', '{SYNTHETIC_PATH}'); END;",
        lines=1, fingerprint="synthetic-fingerprint", verdict="MANUAL", apex_hint="",
    )
    prompt = "\n".join(message.content for message in build_prompt(task))
    assert SYNTHETIC_CREDENTIAL not in prompt
    assert SYNTHETIC_PATH not in prompt
