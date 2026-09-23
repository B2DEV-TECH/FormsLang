"""Target-neutral assessment package and Reports as one persisted journey.

Real parser -> Blueprint -> assessment -> human review -> Generic package ->
every report format -> close -> reopen -> export again. The package and the
reports must say the same thing about the same findings, keep recorded human
decisions distinct from engine proposals, and never distribute source bodies,
view SQL, private notes or host paths by default.
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from formslang import rbac
from formslang.adapters.generic import (
    PACKAGE_NAME,
    GenericModernizationAdapter,
    build_package,
    validate_package,
)
from formslang.project_intake import ProjectIntake
from formslang.project_model import GENERIC_TARGET, ProjectError
from formslang.project_reports import FORMATS, ProjectReportService
from formslang.project_service import ProjectService

ESTATE = Path(__file__).parent / "fixtures" / "estate"
CANARIES = ("CANARY_VIEW_LITERAL", "CANARY_SOURCE_BODY", "CANARY_PRIVATE_NOTE", "CANARY_RATIONALE",
            "C:\\private\\canary", "tigerSECRET", "K3YCANARY")


def canary_estate(root: Path) -> Path:
    shutil.copytree(ESTATE, root)
    (root / "database" / "views.sql").write_text(
        "create or replace view open_items as select item_id, 'CANARY_VIEW_LITERAL' tag "
        "from work_items where status <> 'CLOSED';\n", encoding="utf-8")
    intake = root / "forms" / "intake.xml"
    intake.write_text(intake.read_text(encoding="utf-8").replace(
        "BEGIN INSERT INTO staging_rows", "BEGIN /* CANARY_SOURCE_BODY */ INSERT INTO staging_rows"),
        encoding="utf-8")
    # Integration literals name graph entities; they are source, not identifiers.
    totals = root / "forms" / "totals.xml"
    totals.write_text(totals.read_text(encoding="utf-8").replace(
        "BEGIN :total.net", "BEGIN HOST('sqlplus scott/tigerSECRET@prod @purge.sql'); "
        "WEB.SHOW_DOCUMENT('https://intra.example/api?apikey=K3YCANARY'); :total.net"), encoding="utf-8")
    return root


class Journey:
    def __init__(self, tmp_path: Path, target=GENERIC_TARGET):
        self.tmp = tmp_path
        self.source = canary_estate(tmp_path / "estate")
        self.intake = ProjectIntake(tmp_path / "data", tmp_path / "config")
        selections = [self.intake.select_source(self.source / "forms", "forms"),
                      self.intake.select_source(self.source / "database", "database")]
        self.pid = self.intake.create("Estate", selections, target=target)["project"]["id"]
        self.service = self.open()
        self.service.analyze(expected_revision=None, expected_configuration=0)

    def open(self):
        authorize = lambda: self.intake.access(self.pid, rbac.RUN_CONVERSION)
        return ProjectService(authorize(), authorize=authorize)

    def reopen(self):
        self.service.close()
        self.service = self.open()

    def binding(self):
        a = self.service.assessment()
        return {k: a[k] for k in ("project_id", "analysis_revision", "source_revision", "review_revision")}

    def finding(self, predicate):
        rows = self.service.inventory("findings", limit=200)["rows"]
        return next(r for r in rows if predicate(r))

    def decide(self, finding_id, **command):
        detail = self.service.review_detail(finding_id)
        return self.service.review_decide(finding_id, {**detail["binding"], **command})

    def annotate(self, finding_id, **command):
        detail = self.service.review_detail(finding_id)
        return self.service.review_annotate(finding_id, {**detail["binding"], **command})

    def export(self, kind, **options):
        status = self.service.report_overview()
        return self.service.report_export(kind, status["binding"], **options)


@pytest.fixture
def journey(tmp_path):
    value = Journey(tmp_path)
    try:
        yield value
    finally:
        value.service.close()


def members(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def record_decisions(journey):
    bypass = journey.finding(lambda r: "DIRECT_DML_BYPASSES_API" in r["signals"])
    assert bypass["risk"] == "CRITICAL" and bypass["recommendation"] == "MANUAL_REVIEW"
    journey.decide(bypass["id"], action="MODIFY", recommendation="PRESERVE",
                   rationale="CANARY_RATIONALE keep the form write for now", critical_confirmed=True)
    journey.annotate(bypass["id"], kind="NEEDS_BUSINESS_OWNER_DECISION",
                     note="CANARY_PRIVATE_NOTE see C:\\private\\canary\\notes.txt")
    duplicated = journey.finding(lambda r: "LOGIC_DUPLICATED_FORMULA" in r["signals"])
    journey.decide(duplicated["id"], action="DEFER")
    return bypass, duplicated


def test_generic_package_preserves_identity_risk_and_human_decisions(journey):
    bypass, duplicated = record_decisions(journey)
    metadata = journey.service.generate(journey.binding())
    assert metadata["artifact_kind"] == "generic-assessment-package"
    assert metadata["package_name"] == PACKAGE_NAME and "source_id" not in metadata
    assert "target_revision" not in metadata and "code_revision" not in metadata
    download = journey.service.generation_download(metadata["artifact_id"])
    assert download.filename == PACKAGE_NAME
    assert validate_package(download.body) == {"valid": True, "diagnostics": []}
    content = members(download.body)
    rows = {r["finding_id"]: r for r in json.loads(content["assessment/findings.json"])["rows"]}
    changed = rows[bypass["id"]]
    assert changed["module"].endswith("intake.xml") and changed["module"] != "all"
    assert changed["observed_risk"] == "CRITICAL"
    assert changed["engine_recommendation"] == "MANUAL_REVIEW"
    assert changed["engine_recommendation_status"] == "PROPOSED"
    assert changed["human_decision"] == "PRESERVE" and changed["review_status"] == "Changed"
    assert changed["unresolved"] is False and changed["stale"] is False
    assert changed["hotspot_ids"] and changed["evidence_refs"]
    deferred = rows[duplicated["id"]]
    assert deferred["review_status"] == "Deferred" and deferred["unresolved"] is True
    assert deferred["human_decision"] is None
    pending = [r for r in rows.values() if r["review_status"] == "Pending"]
    assert pending and all(r["human_decision"] is None for r in pending)
    # Nothing missing becomes a safer-looking value.
    assert all(r["observed_risk"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"} for r in rows.values())
    assert "UNKNOWN" in {r["observed_risk"] for r in rows.values()}
    records = json.loads(content["assessment/decision-records.json"])["rows"]
    recorded = {r["finding_id"]: r for r in records if r["kind"] == "RECORDED"}
    assert recorded[bypass["id"]]["engine_recommendation"] == "MANUAL_REVIEW"
    assert recorded[bypass["id"]]["human_decision"] == "PRESERVE"
    proposed = [r for r in records if r["kind"] == "PROPOSED"]
    assert len(proposed) == 3 and all(r["decision"].startswith("Not decided") for r in proposed)
    markdown = content["assessment/decision-records.md"].decode()
    assert "PROPOSED" in markdown and "Enforces" not in markdown
    groups = json.loads(content["assessment/investigation-groups.json"])
    assert "not a migration schedule" in groups["disclaimer"]
    names = {g["name"] for g in groups["groups"]}
    assert not names & {"Quick Wins", "Independent Foundations", "Core Domain Services"}
    # Overview, Review and the package agree on the same findings.
    overview = journey.service.overview()
    assert len(rows) == overview["inventory"]["modernization_findings"]
    assert json.loads(content["manifest.json"])["counts"]["hotspot_candidates"] == overview["hotspots"]["total"]


def test_default_package_and_reports_do_not_disclose_source_or_notes(journey):
    record_decisions(journey)
    metadata = journey.service.generate(journey.binding())
    package = journey.service.generation_download(metadata["artifact_id"]).body
    exports = {kind: journey.export(kind).body for kind in FORMATS}
    exports["package+artifacts"] = journey.export("package", include_artifacts=True).body
    for name, data in {"generic": package, **exports}.items():
        text = data.decode("utf-8", "replace") if not name.startswith("package") and name != "generic" else \
            "\n".join(v.decode("utf-8", "replace") for v in members(data).values())
        for canary in CANARIES:
            assert canary not in text, (name, canary)
    catalog = json.loads(members(package)["assessment/interface-catalog.json"])
    assert {"name", "findings", "highest_risk"} == set(catalog["views"][0])
    # The explicit sensitive option still works and is labelled.
    sensitive = journey.export("decisions", include_notes=True)
    assert sensitive.filename.endswith("-sensitive.json") and b"CANARY_RATIONALE" in sensitive.body


def test_generic_to_reports_survives_close_and_reopen(journey):
    record_decisions(journey)
    metadata = journey.service.generate(journey.binding())
    validation = journey.service.generation_validate(metadata["artifact_id"])
    assert validation["status"] == "Package Verified" and validation["mode"] == "package-structure"
    first = {kind: journey.export(kind).body for kind in ("executive", "technical", "dossier-md", "package")}
    with_artifacts = journey.export("package", include_artifacts=True).body
    included = members(with_artifacts)
    prefix = f"assessment-package/{metadata['artifact_id']}/"
    assert {n for n in included if n.startswith(prefix)} == {prefix + n for n in metadata["files"]}
    manifest = json.loads(included["manifest.json"])
    (artifact,) = manifest["artifacts"]
    assert artifact["artifact_kind"] == "generic-assessment-package"
    assert artifact["target_revision"] == "Not applicable" and artifact["inclusion"] == "Included"
    executive = first["executive"].decode()
    assert "Possible API bypass" in executive and "Areas to Investigate First" in executive
    assert "Target-neutral assessment" in executive and "migration pitch" not in executive.lower()
    technical = first["technical"].decode()
    assert "Module Relationships" in technical and "Hotspot Evidence" in technical
    assert "Package Verified" in executive
    journey.reopen()
    assert journey.service.open().target == GENERIC_TARGET
    again = {kind: journey.export(kind).body for kind in first}
    assert again == first
    assert members(journey.export("package", include_artifacts=True).body).keys() == included.keys()
    rows = json.loads(members(journey.service.generation_download(metadata["artifact_id"]).body)
                      ["assessment/findings.json"])["rows"]
    assert any(r["human_decision"] == "PRESERVE" for r in rows)


def test_reanalysis_keeps_history_without_applying_stale_decisions(journey):
    bypass, _ = record_decisions(journey)
    old = journey.service.generate(journey.binding())
    intake = journey.source / "forms" / "intake.xml"
    intake.write_text(intake.read_text(encoding="utf-8").replace("'checked'", "'reviewed'"), encoding="utf-8")
    descriptor = journey.service.open()
    journey.service.analyze(expected_revision=descriptor.analysis_revision,
                            expected_configuration=journey.service._store.configuration_revision())
    decisions = json.loads(journey.export("decisions").body)["rows"]
    history = next(d for d in decisions if d["finding_id"] == bypass["id"])
    assert history["history"], "the ledger must keep the earlier decision"
    new = journey.service.generate(journey.binding())
    rows = {r["finding_id"]: r for r in json.loads(members(
        journey.service.generation_download(new["artifact_id"]).body)["assessment/findings.json"])["rows"]}
    current = rows[bypass["id"]]
    # The earlier decision is history, not a current approval of changed evidence.
    assert current["review_status"] == "Needs Revalidation" and current["stale"] is True
    assert current["human_decision"] is None and current["unresolved"] is True
    assert current["engine_recommendation"] == "MANUAL_REVIEW"
    assert [e["applicable"] for e in history["history"]] == [False]
    excluded = json.loads(members(journey.export("package", include_artifacts=True).body)["manifest.json"])
    reasons = {e["artifact_id"]: e["reason"] for e in excluded["exclusions"]}
    assert reasons.get(old["artifact_id"]) == "ARTIFACT_REVISION_STALE"


def test_generation_rejects_scopes_and_unselected_projects(tmp_path, journey):
    with pytest.raises(ProjectError):
        journey.service.generate({**journey.binding(), "scope": "source:orders"})
    with pytest.raises(ProjectError):
        journey.service.generate({**journey.binding(), "scopes": [{"source_id": "x"}]})
    with pytest.raises(ProjectError):
        GenericModernizationAdapter().generate_deliverables("source:orders", {}, str(tmp_path))
    from formslang.project_model import UNSELECTED_TARGET
    neutral = Journey(tmp_path / "neutral", target=UNSELECTED_TARGET)
    try:
        with pytest.raises(ProjectError, match="unselected"):
            neutral.service.generate(neutral.binding())
        assert neutral.export("executive").body.count(b"Target not selected") >= 1
    finally:
        neutral.service.close()


def snapshot_of(journey):
    from formslang.project_generation import digest
    from formslang.project_lock import project_worker_lock

    with project_worker_lock(journey.service.access.root):
        snapshot, _, _ = ProjectReportService(journey.service).capture()
    snapshot["snapshot_revision"] = digest(snapshot)
    return snapshot


def test_package_csv_neutralizes_formulas_and_validator_rejects_contract_breaks(journey):
    snapshot = snapshot_of(journey)
    formulas = ["=1+1", "+cmd", "-2", "@SUM(A1)", "\t=x", "\r=x", "\ufeff=x", " =A\u00c7\u00c3O()"]
    for row, value in zip(snapshot["inventory"]["findings"], formulas, strict=False):
        row["name"] = value
    data, _ = build_package(snapshot)
    cells = [row["component"] for row in csv.DictReader(io.StringIO(
        members(data)["assessment/findings.csv"].decode("utf-8-sig")))]
    for value in formulas:
        rendered = next(c for c in cells if c.endswith((value.strip(), value)))
        assert rendered.startswith("'"), (value, rendered)

    def rebuilt(mutate):
        content = members(data)
        mutate(content)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for name, value in content.items():
                archive.writestr(name, value)
        return stream.getvalue()

    breaks = [
        lambda c: c.__setitem__("assessment/findings.json", b"null"),
        lambda c: c.__setitem__("assessment/investigation-groups.json", b"42"),
        lambda c: c.pop("assessment/hotspot-candidates.json"),
        lambda c: c.__setitem__("../escape.txt", b"x"),
        lambda c: c.__setitem__("assessment/findings.csv", b"tampered"),
        lambda c: c.__setitem__("manifest.json", b'{"schema": "other/1"}'),
    ]
    for mutate in breaks:
        assert validate_package(rebuilt(mutate))["valid"] is False
    assert validate_package(b"not a zip")["valid"] is False
    duplicate = io.BytesIO()
    with zipfile.ZipFile(duplicate, "w") as archive:
        for name, value in members(data).items():
            archive.writestr(name, value)
        with pytest.warns(UserWarning):
            archive.writestr("README.md", b"again")
    assert validate_package(duplicate.getvalue())["valid"] is False


PACKAGE_BYTES = r'''
import hashlib, sys
from pathlib import Path
from formslang import rbac
from formslang.project_intake import ProjectIntake
from formslang.project_service import ProjectService
tmp, pid = Path(sys.argv[1]), sys.argv[2]
intake = ProjectIntake(tmp / "data", tmp / "config")
auth = lambda: intake.access(pid, rbac.RUN_CONVERSION)
service = ProjectService(auth(), authorize=auth)
a = service.assessment()
binding = {k: a[k] for k in ("project_id", "analysis_revision", "source_revision", "review_revision")}
meta = service.generate(binding)
report = service.report_overview()
package = service.report_export("package", report["binding"]).body
print(meta["sha256"], hashlib.sha256(package).hexdigest())
service.close()
'''


def test_package_bytes_do_not_depend_on_hash_seed_or_clock(journey):
    record_decisions(journey)
    journey.service.close()
    shas = set()
    for seed in ("0", "7", "123"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run([sys.executable, "-c", PACKAGE_BYTES, str(journey.tmp), journey.pid],
                              capture_output=True, text=True, env=env, timeout=300, check=False)
        assert done.returncode == 0, done.stderr[-2000:]
        shas.add(done.stdout.split()[0])
    assert len(shas) == 1
    journey.service = journey.open()


def test_cli_generates_downloads_and_verifies_the_package(journey, monkeypatch, capsys, tmp_path):
    from formslang.cli import main

    monkeypatch.setenv("FORMSLANG_DATA_DIR", str(journey.tmp / "data"))
    monkeypatch.setenv("FORMSLANG_CONFIG_DIR", str(journey.tmp / "config"))
    root = journey.tmp / "data" / "projects" / journey.pid
    request = tmp_path / "request.json"
    request.write_text(json.dumps(journey.binding()), encoding="utf-8")
    journey.service.close()
    try:
        assert main(["project", "generation", "generate", str(root), "--request", str(request), "--json"]) == 0
        artifact = json.loads(capsys.readouterr().out)["artifact_id"]
        output = tmp_path / "assessment-package.zip"
        assert main(["project", "generation", "download", str(root), "--artifact", artifact,
                     "--output", str(output), "--json"]) == 0
        capsys.readouterr()
        assert validate_package(output.read_bytes())["valid"] is True
        assert main(["project", "generation", "validate", str(root), "--artifact", artifact, "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "Package Verified"
    finally:
        journey.service = journey.open()


def test_reports_disclose_unsupported_artifact_records_instead_of_crashing(journey):
    """Records written by the pre-remediation Generic path carry no module scope."""
    legacy = {**journey.binding(), "artifact_id": "a" * 32, "status": "Generated",
              "validation_status": "Not Validated", "created_at": "2026-09-21T00:00:00+00:00",
              "target": {}, "sha256": "0" * 64, "size_bytes": 0, "mode": "generic-modernization-package",
              "files": {}}
    with journey.service._store._write() as db:
        db.execute("INSERT INTO project_artifact VALUES (?,?,?)",
                   (legacy["artifact_id"], legacy["created_at"], json.dumps(legacy)))
    assert b"Executive Modernization Assessment" in journey.export("executive").body
    manifest = json.loads(members(journey.export("package", include_artifacts=True).body)["manifest.json"])
    assert {"artifact_id": "a" * 32, "reason": "ARTIFACT_KIND_UNSUPPORTED"} in manifest["exclusions"]
    (row,) = manifest["artifacts"]
    assert row["source_id"] == "Not recorded" and row["artifact_kind"] == "unsupported"
