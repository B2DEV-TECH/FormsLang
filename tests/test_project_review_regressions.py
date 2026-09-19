"""Independent-review reproductions: authority and complete revision binding."""

import copy
import os
import subprocess

import pytest

from formslang import blueprint, dashboard, rbac
from formslang.model import FormModule, Trigger
from formslang.project_assessment import bind_assessment
from formslang.project_manifest import (
    ManifestEntry,
    analysis_revision,
    engine_identity,
    source_id,
    source_revision,
)
from formslang.project_model import ProjectDescriptor, ProjectError
from formslang.project_store import ProjectStore
from formslang.projects import authorized_project_access


def assessment(descriptor, engines):
    entry = ManifestEntry(source_id("forms", "orders.xml"), "forms", "orders.xml", "xml",
                          True, "available", 10, "1" * 64)
    payload = blueprint.build([FormModule(name="Orders", triggers=[
        Trigger("WHEN-BUTTON-PRESSED", "AUDIT_API.save;", "form", ""),
    ])])
    return bind_assessment(descriptor, (entry,), payload, engines=engines, options={},
                           analyzed_at="2026-09-19T12:00:00Z", status="Current")


def test_new_manifest_cannot_reuse_prior_finding_revision(tmp_path):
    descriptor = ProjectDescriptor(id="a" * 32, name="Orders")
    store = ProjectStore.create(tmp_path, descriptor)
    try:
        first = assessment(descriptor, {"rules": "v1"})
        store.save_assessment(first, expected_revision=None)
        finding = first["blueprint"]["findings"][0]
        store.session.review_blueprint(entity=finding["entity"], revision=finding["revision"],
            action="APPROVE", reviewer="Analyst", comment="Accepted architecture")
        changed = copy.deepcopy(first)
        changed["source_manifest"][0]["sha256"] = "2" * 64
        changed["source_revision"] = source_revision(tuple(ManifestEntry(**e) for e in changed["source_manifest"]), {})
        changed["analysis_revision"] = analysis_revision(changed["source_revision"], changed["engine_identity"], changed["analysis_options"])
        changed["blueprint"]["source_revision"] = changed["source_revision"]
        changed["blueprint"]["project_analysis_revision"] = changed["analysis_revision"]
        with pytest.raises(ProjectError, match="finding|Finding"):
            store.save_assessment(changed, expected_revision=first["analysis_revision"])
        assert store.load_assessment() == first
    finally:
        store.close()


def test_dashboard_version_changes_project_analysis_identity(monkeypatch):
    descriptor = ProjectDescriptor(id="a" * 32, name="Orders")
    first = assessment(descriptor, engine_identity())
    monkeypatch.setattr(dashboard, "READINESS_VERSION", "readiness/review-regression")
    second = assessment(descriptor, engine_identity())
    assert first["blueprint"]["readiness"] != second["blueprint"]["readiness"]
    assert first["analysis_revision"] != second["analysis_revision"]


def test_adopted_project_junction_cannot_cross_tenant(auth_store, tmp_path):
    data = tmp_path / "data"
    a, b = data / "a", data / "b"
    ProjectStore.create(a, ProjectDescriptor(id="a" * 32, name="Tenant A")).close()
    ProjectStore.create(b, ProjectDescriptor(id="b" * 32, name="Tenant B private")).close()
    owner = auth_store.bootstrap_owner("a@example.test", "correct horse battery staple")
    registered = auth_store.register_external_project(owner["organization_id"], "Tenant A",
        a / ".formslang/project.session.db", created_by=owner["user_id"])
    auth_store.mark_project_adopted(registered["id"], str(a / ".formslang/project.session.db"))
    a.rename(data / "original-a")
    if os.name == "nt":
        env = {**os.environ, "FORMSLANG_TEST_JUNCTION": str(a), "FORMSLANG_TEST_TARGET": str(b)}
        result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
            "New-Item -ItemType Junction -Path $env:FORMSLANG_TEST_JUNCTION -Target $env:FORMSLANG_TEST_TARGET | Out-Null"],
            env=env, capture_output=True, timeout=20, check=False)
        if result.returncode:
            pytest.skip("OS does not permit directory junctions")
    else:
        a.symlink_to(b, target_is_directory=True)
    try:
        with pytest.raises(ProjectError, match="redirect"):
            authorized_project_access(auth_store, registered["id"],
                active_org_id=owner["organization_id"], user_id=owner["user_id"],
                action=rbac.VIEW_PROJECT, data_dir=data, approved_roots=(data,))
    finally:
        if os.name == "nt":
            a.rmdir()  # remove only this test-owned junction, never its target
        else:
            a.unlink()
