"""Corporate assessment reports: truthful formats over one saved snapshot."""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from formslang import rbac
from formslang.project_intake import ProjectIntake
from formslang.project_model import UNSELECTED_TARGET
from formslang.project_reports import FORMATS, ProjectReportService
from formslang.project_service import ProjectService

UNSUPPORTED_CLAIMS = ("Quick Win", "Independent Foundation", "Core Domain Service", "Wave 1",
                      "cloud migration", "Enforces architectural ownership", "ROI", "percent complete")


@pytest.fixture(params=["apex", "unselected"])
def analyzed_project(request, tmp_path: Path):
    intake = ProjectIntake(tmp_path / "data", tmp_path / "config")
    target = UNSELECTED_TARGET if request.param == "unselected" else None
    created = intake.create_demo(destination=tmp_path / "demo", target=target)
    pid = created["project"]["id"]
    authorize = lambda: intake.access(pid, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    service.analyze(expected_revision=None, expected_configuration=0)
    try:
        yield service
    finally:
        service.close()


def export(service, kind, **options):
    status = ProjectReportService(service).overview()
    return service.report_export(kind, status["binding"], **options)


def test_formats_are_the_supported_2_1_set(analyzed_project):
    ids = {f["id"] for f in ProjectReportService(analyzed_project).overview()["formats"]}
    assert ids == set(FORMATS)
    assert {"dossier-md", "investigation-md", "investigation-json", "decision-records-md"} <= ids
    assert not ids & {"pitch-deck", "waves-md", "waves-json", "adrs-md"}


def test_no_report_makes_unsupported_planning_or_business_claims(analyzed_project):
    for kind in FORMATS:
        body = export(analyzed_project, kind).body
        if kind == "package":
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                texts = [archive.read(n).decode("utf-8", "replace") for n in archive.namelist()]
        else:
            texts = [body.decode("utf-8", "replace")]
        for text in texts:
            # The stated limitation is a negation, not a claim.
            text = text.replace("No cost, schedule, ROI or migration-percentage estimate is made.", "")
            for claim in UNSUPPORTED_CLAIMS:
                pattern = r'\b' + re.escape(claim) + r'\b'
                assert not re.search(pattern, text, re.IGNORECASE), (kind, claim)


def test_executive_and_technical_reports_carry_the_2_1_sections(analyzed_project):
    executive = export(analyzed_project, "executive").body.decode()
    for heading in ("Executive Modernization Assessment", "Application Inventory", "Source Coverage",
                    "Risk Distribution", "Architectural Hotspot Candidates", "Unresolved Critical Findings",
                    "Areas to Investigate First", "Known Limitations", "Provenance"):
        assert heading in executive, heading
    technical = export(analyzed_project, "technical").body.decode()
    for heading in ("Technical Modernization Assessment", "Database Packages", "Module Relationships",
                    "Hotspot Evidence", "Business Rule Candidates", "Unresolved Decisions"):
        assert heading in technical, heading
    target = analyzed_project.open().target.platform
    if target == "UNSELECTED":
        assert "Target not selected" in executive and "Target: Oracle APEX applications" not in executive
    else:
        assert "Target: Oracle APEX applications" in executive


def test_investigation_groups_and_decision_records_are_labelled(analyzed_project):
    groups = json.loads(export(analyzed_project, "investigation-json").body)
    assert "not a migration schedule" in groups["disclaimer"]
    assert [g["id"] for g in groups["groups"]] == [
        "INVESTIGATE_FIRST", "ARCHITECTURE_DECISIONS", "EVIDENCE_INCOMPLETE", "REMAINING_REVIEW", "REVIEWED"]
    records = export(analyzed_project, "decision-records-md").body.decode()
    assert "## Recorded human decisions" in records and "No human decisions have been recorded" in records
    dossier = export(analyzed_project, "dossier-md").body.decode()
    assert "Suggested investigation groups" in dossier and "Wave" not in dossier


def test_package_bundle_includes_every_format_once(analyzed_project):
    body = export(analyzed_project, "package").body
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
    for name in ("assessment/executive-summary.html", "assessment/technical-assessment.html",
                 "assessment/hotspot-candidates.json", "dossier/modernization-dossier.md",
                 "architecture/investigation-groups.md", "architecture/investigation-groups.json",
                 "architecture/module-relationships.json", "review/decision-records.md",
                 "backlog/modernization-backlog.csv", "manifest.json"):
        assert name in names, name
    assert set(manifest["files"]) == names - {"manifest.json"}
