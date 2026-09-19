"""Foundation acceptance: real parser, Store, review, relocation and process races."""

import multiprocessing
import shutil

from formslang import blueprint
from formslang.parser import parse_xml
from formslang.project_assessment import bind_assessment, current_assessment
from formslang.project_manifest import SourceCandidate, engine_identity, fingerprint_sources
from formslang.project_model import ProjectDescriptor, RevisionConflict, SourceRoot
from formslang.project_store import ProjectStore


def _publish(root, assessment, ready, release, results):
    store = ProjectStore.open(root)
    try:
        ready.put(True)
        if not release.wait(15):
            raise RuntimeError("acceptance synchronization timed out")
        try:
            store.save_assessment(assessment, expected_revision=None)
            results.put("published")
        except RevisionConflict:
            results.put("conflict")
    finally:
        store.close()


def prepare(root, sample_xml):
    forms = root / "forms"
    forms.mkdir(parents=True)
    xml = forms / "orders.xml"
    xml.write_bytes(sample_xml.read_bytes())
    descriptor = ProjectDescriptor(id="f" * 32, name="Orders",
        source_roots=(SourceRoot("forms", "forms", "forms"),))
    manifest = fingerprint_sources(root, descriptor.source_roots,
        (SourceCandidate("forms", "orders.xml", "xml"),))
    payload = blueprint.build([parse_xml(xml)], source_keys=["forms/orders.xml"])
    engines = engine_identity()
    assessment = bind_assessment(descriptor, manifest, payload, engines=engines,
        options={}, analyzed_at="2026-09-19T12:00:00Z", status="Current")
    return descriptor, assessment, engines


def test_reopen_relocation_keeps_real_assessment_and_review(tmp_path, sample_xml):
    root = tmp_path / "project"
    descriptor, assessment, engines = prepare(root, sample_xml)
    store = ProjectStore.create(root, descriptor)
    observer = ProjectStore.open(root)
    store.save_assessment(assessment, expected_revision=None)
    assert observer.load_assessment()["analysis_revision"] == assessment["analysis_revision"]
    observer.close()
    finding = assessment["blueprint"]["findings"][0]
    store.session.review_blueprint(entity=finding["entity"], revision=finding["revision"],
        action="DEFER", reviewer="Synthetic reviewer", comment="Business owner input required")
    store.close()
    relocated = tmp_path / "relocated"
    shutil.copytree(root, relocated)
    reopened = ProjectStore.open(relocated)
    try:
        saved = current_assessment(reopened, expected_engines=engines)
        assert saved["analysis_revision"] == assessment["analysis_revision"]
        found = next(f for f in saved["blueprint"]["findings"] if f["entity"] == finding["entity"])
        assert found["review_state"] == "DEFER"
        assert found["review_history"][0]["reviewer"] == "Synthetic reviewer"
        manifest = fingerprint_sources(relocated, descriptor.source_roots,
            (SourceCandidate("forms", "orders.xml", "xml"),))
        assert manifest[0].sha256 == saved["source_manifest"][0]["sha256"]
    finally:
        reopened.close()


def test_two_processes_publish_only_one_assessment(tmp_path, sample_xml):
    root = tmp_path / "project"
    descriptor, assessment, _ = prepare(root, sample_xml)
    ProjectStore.create(root, descriptor).close()
    ctx = multiprocessing.get_context("spawn")
    ready, results, release = ctx.Queue(), ctx.Queue(), ctx.Event()
    workers = [ctx.Process(target=_publish, args=(root, assessment, ready, release, results)) for _ in range(2)]
    try:
        for worker in workers:
            worker.start()
        assert ready.get(timeout=20) and ready.get(timeout=20)
        release.set()
        assert sorted([results.get(timeout=20), results.get(timeout=20)]) == ["conflict", "published"]
        for worker in workers:
            worker.join(timeout=20)
            assert worker.exitcode == 0
    finally:
        release.set()
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=5)
        ready.close()
        results.close()
