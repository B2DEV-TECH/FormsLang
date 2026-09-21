"""Tests for Knowledge Asset Engine & Enterprise Reporting (Phase 2.3)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from formslang import rbac
from formslang.project_intake import ProjectIntake
from formslang.project_reports import FORMATS, ProjectReportService
from formslang.project_service import ProjectService


@pytest.fixture
def analyzed_project(tmp_path: Path):
    intake = ProjectIntake(tmp_path / "data", tmp_path / "config")
    created = intake.create_demo(destination=tmp_path / "demo")
    pid = created["project"]["id"]
    access = intake.access(pid, rbac.RUN_CONVERSION)
    service = ProjectService(access, authorize=lambda: intake.access(pid, rbac.RUN_CONVERSION))
    service.analyze(expected_revision=None, expected_configuration=0)
    try:
        yield service
    finally:
        service.close()


def test_formats_registered_and_overview(analyzed_project: ProjectService):
    report_svc = ProjectReportService(analyzed_project)
    overview = report_svc.overview()

    format_ids = {f["id"] for f in overview["formats"]}
    assert "dossier-md" in format_ids
    assert "waves-md" in format_ids
    assert "waves-json" in format_ids
    assert "adrs-md" in format_ids
    assert "pitch-deck" in format_ids
    assert "package" in format_ids

    assert FORMATS["dossier-md"][0] == "modernization-dossier.md"
    assert FORMATS["waves-md"][0] == "migration-waves.md"
    assert FORMATS["waves-json"][0] == "migration-waves.json"
    assert FORMATS["adrs-md"][0] == "architectural-decisions.md"
    assert FORMATS["pitch-deck"][0] == "migration-pitch-deck.html"


def test_export_modernization_dossier(analyzed_project: ProjectService):
    report_svc = ProjectReportService(analyzed_project)
    overview = report_svc.overview()
    binding = overview["binding"]

    download = report_svc.export("dossier-md", binding)
    assert download.filename == "modernization-dossier.md"
    assert "text/markdown" in download.content_type

    text = download.body.decode("utf-8")
    assert "# Modernization Dossier" in text
    assert "Chapter 1: Executive Estate Scorecard" in text
    assert "Chapter 2: Estate Inventory & Risk Profile" in text
    assert "Chapter 3: Architectural Hotspots & Anti-Patterns" in text
    assert "Chapter 4: Target-Neutral Modernization Backlog" in text
    assert "Chapter 5: 3-Wave Phased Migration Roadmap" in text
    assert "Chapter 6: Governance & Architectural Decisions" in text


def test_export_migration_waves(analyzed_project: ProjectService):
    report_svc = ProjectReportService(analyzed_project)
    overview = report_svc.overview()
    binding = overview["binding"]

    # Markdown
    download_md = report_svc.export("waves-md", binding)
    assert download_md.filename == "migration-waves.md"
    assert "text/markdown" in download_md.content_type
    md_text = download_md.body.decode("utf-8")
    assert "# Migration Waves Roadmap" in md_text
    assert "Wave 1: Independent Foundations" in md_text
    assert "Wave 2: Core Domain Services" in md_text
    assert "Wave 3: Coupled Hotspots & Redesign" in md_text

    # JSON
    download_json = report_svc.export("waves-json", binding)
    assert download_json.filename == "migration-waves.json"
    assert "application/json" in download_json.content_type
    waves = json.loads(download_json.body.decode("utf-8"))
    assert "wave_1_foundations" in waves
    assert "wave_2_services" in waves
    assert "wave_3_coupled" in waves


def test_export_adrs_and_pitch_deck(analyzed_project: ProjectService):
    report_svc = ProjectReportService(analyzed_project)
    overview = report_svc.overview()
    binding = overview["binding"]

    # ADRs
    adrs = report_svc.export("adrs-md", binding)
    assert adrs.filename == "architectural-decisions.md"
    assert "# Architectural Decision Records" in adrs.body.decode("utf-8")

    # Pitch Deck
    deck = report_svc.export("pitch-deck", binding)
    assert deck.filename == "migration-pitch-deck.html"
    assert "text/html" in deck.content_type
    deck_html = deck.body.decode("utf-8")
    assert "Migration Pitch Deck" in deck_html
    assert "Executive Summary: Estate Modernization Scorecard" in deck_html
    assert "slide-card" in deck_html


def test_package_bundle_includes_all_assets(analyzed_project: ProjectService):
    report_svc = ProjectReportService(analyzed_project)
    overview = report_svc.overview()
    binding = overview["binding"]

    pkg = report_svc.export("package", binding)
    assert pkg.filename == "modernization-package.zip"

    with zipfile.ZipFile(io.BytesIO(pkg.body), "r") as archive:
        names = set(archive.namelist())
        assert "dossier/modernization-dossier.md" in names
        assert "architecture/migration-waves.md" in names
        assert "architecture/migration-waves.json" in names
        assert "architecture/architectural-decisions.md" in names
        assert "assessment/migration-pitch-deck.html" in names
        assert "assessment/executive-summary.html" in names
        assert "assessment/technical-assessment.html" in names
        assert "backlog/modernization-backlog.csv" in names
        assert "manifest.json" in names
