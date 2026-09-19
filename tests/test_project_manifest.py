"""Fingerprints bind real bytes, not paths or mtime, to review provenance."""

import os
from dataclasses import replace
from pathlib import Path

import pytest

from formslang import modernization
from formslang.project_manifest import (
    SourceCandidate,
    analysis_revision,
    engine_identity,
    fingerprint_sources,
    source_id,
    source_revision,
)
from formslang.project_model import ProjectError, SourceRoot


def test_db_edits_relocation_and_same_size_mtime(tmp_path):
    roots = (SourceRoot("db", "database", "db"),)
    candidates = (SourceCandidate("db", "api.pkb", "database"),)
    revisions = []
    for dirname in ("one", "two"):
        root = tmp_path / dirname
        (root / "db").mkdir(parents=True)
        (root / "db/api.pkb").write_bytes(b"BEGIN NULL; END;")
        revisions.append(source_revision(fingerprint_sources(root, roots, candidates), {}))
    assert revisions[0] == revisions[1]
    path = tmp_path / "two/db/api.pkb"
    before = path.stat()
    path.write_bytes(b"BEGIN BEEP; END;")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert source_revision(fingerprint_sources(tmp_path / "two", roots, candidates), {}) != revisions[0]
    assert source_id("one", "ORDERS.xml") != source_id("two", "ORDERS.xml")


def test_order_selection_options_ddl_and_missing(tmp_path):
    roots = (SourceRoot("db", "database", "."),)
    candidates = tuple(SourceCandidate("db", name, "database") for name in ("a.sql", "b.pks"))
    (tmp_path / "a.sql").write_bytes(b"CREATE TABLE t (id NUMBER);")
    (tmp_path / "b.pks").write_bytes(b"")
    first = fingerprint_sources(tmp_path, roots, candidates)
    assert first == fingerprint_sources(tmp_path, roots, tuple(reversed(candidates)))
    empty = next(x for x in first if x.relative_path == "b.pks")
    assert empty.sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert source_revision(first, {}) != source_revision(first, {"enterprise": True})
    selected = tuple(replace(x, selected=False) for x in first)
    assert source_revision(first, {}) != source_revision(selected, {})
    (tmp_path / "a.sql").write_bytes(b"CREATE TABLE t (id VARCHAR2(10));")
    assert first != fingerprint_sources(tmp_path, roots, candidates)
    (tmp_path / "b.pks").unlink()
    last = fingerprint_sources(tmp_path, roots, candidates)
    assert next(x for x in last if x.relative_path == "b.pks").status == "missing"


@pytest.mark.parametrize("path", ["../escape", "/root", "C:/outside", "C:outside", "\\\\host\\share", "x\0y", "a/../b", ".", "a:stream"])
def test_invalid_source_identity_is_rejected(path):
    with pytest.raises(ProjectError):
        source_id("forms", path)


def test_duplicate_unknown_root_and_size_limit(tmp_path):
    roots = (SourceRoot("forms", "forms", "."),)
    candidate = SourceCandidate("forms", "large.xml", "xml")
    (tmp_path / "large.xml").write_bytes(b"12345")
    assert fingerprint_sources(tmp_path, roots, (candidate,), max_bytes=4)[0].status == "too_large"
    with pytest.raises(ProjectError):
        fingerprint_sources(tmp_path, roots, (candidate, candidate))
    with pytest.raises(ProjectError):
        fingerprint_sources(tmp_path, roots, (replace(candidate, root_id="other"),))


def test_symlink_escape_has_no_digest(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"private")
    try:
        (root / "link.xml").symlink_to(outside)
    except OSError:
        pytest.skip("OS does not permit symlinks")
    result = fingerprint_sources(root, (SourceRoot("f", "forms", "."),),
                                 (SourceCandidate("f", "link.xml", "xml"),))
    assert result[0].status == "blocked"
    assert result[0].sha256 is None


def test_growth_during_open_is_bounded(tmp_path, monkeypatch):
    path = tmp_path / "a.xml"
    path.write_bytes(b"1")
    real_open = Path.open

    def growing_open(self, *args, **kwargs):
        if self == path and args == ("rb",):
            with real_open(self, "ab") as writer:
                writer.write(b"23456")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", growing_open)
    result = fingerprint_sources(tmp_path, (SourceRoot("f", "forms", "."),),
                                 (SourceCandidate("f", "a.xml", "xml"),), max_bytes=4)
    assert result[0].status in {"changed", "too_large"}
    assert result[0].sha256 is None


def test_complete_engine_identity_and_missing_resource(monkeypatch):
    import formslang.project_manifest as manifest

    before = engine_identity()
    monkeypatch.setattr(modernization, "VERSION", "synthetic-rule-change")
    after = engine_identity()
    assert analysis_revision("a" * 64, before, {}) != analysis_revision("a" * 64, after, {})
    assert "parser.sha256" in before and "database.sha256" in before

    def unavailable(*args):
        raise FileNotFoundError("private-path")

    monkeypatch.setattr(manifest.resources, "files", unavailable)
    with pytest.raises(ProjectError, match="ENGINE_IDENTITY_UNAVAILABLE") as error:
        engine_identity()
    assert "private-path" not in str(error.value)
