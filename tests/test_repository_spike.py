"""WP-10 transaction and checkpoint spike, outside the product path."""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest


def spike(root):
    from examples.verify.repository_spike import RepositorySpike

    return RepositorySpike(root)


def test_source_object_id_binds_kind_and_exact_bytes(tmp_path):
    repository = spike(tmp_path)
    try:
        original = repository.put_object("source", b"A\r\n")
        assert original == repository.put_object("source", b"A\r\n")
        assert original != repository.put_object("source", b"A\n")
        assert original != repository.put_object("analysis", b"A\r\n")
        assert repository.read_object(original) == b"A\r\n"
    finally:
        repository.close()


def test_crash_before_commit_keeps_no_accepted_event(tmp_path):
    repository = spike(tmp_path)
    source_id = repository.put_object("source", b"original bytes")
    try:
        with pytest.raises(RuntimeError, match="injected before commit"):
            repository.publish(0, [source_id], {"action": "analyze"}, fail_at="before_commit")
        assert repository.status() == {"revision": 0, "publication": None}
    finally:
        repository.close()
    reopened = spike(tmp_path)
    try:
        assert reopened.status() == {"revision": 0, "publication": None}
        assert reopened.read_object(source_id) == b"original bytes"  # harmless orphan
    finally:
        reopened.close()


def test_commit_before_checkpoint_is_recoverable_without_rewriting_event(tmp_path):
    repository = spike(tmp_path)
    source_id = repository.put_object("source", b"original bytes")
    try:
        with pytest.raises(RuntimeError, match="injected after commit"):
            repository.publish(0, [source_id], {"action": "analyze"}, fail_at="after_commit")
        assert repository.status() == {"revision": 1, "publication": "PENDING"}
        assert not (tmp_path / "checkpoint.json").exists()
    finally:
        repository.close()
    reopened = spike(tmp_path)
    try:
        assert reopened.recover() == 1
        manifest = (tmp_path / "checkpoint.json").read_bytes()
        assert manifest.endswith(b"\n")
        assert json.loads(manifest) == {
            "schema": "formslang-spike-checkpoint/1", "revision": 1,
            "objects": [source_id], "events": [{"action": "analyze"}],
        }
        assert manifest == (b'{"events":[{"action":"analyze"}],"objects":["'
                            + source_id.encode("ascii")
                            + b'"],"revision":1,"schema":"formslang-spike-checkpoint/1"}\n')
        assert reopened.recover() == 0
        assert (tmp_path / "checkpoint.json").read_bytes() == manifest
        assert reopened.status() == {"revision": 1, "publication": "PUBLISHED"}
    finally:
        reopened.close()


def test_two_publishers_cannot_accept_same_revision(tmp_path):
    first, second = spike(tmp_path), spike(tmp_path)
    try:
        source_id = first.put_object("source", b"same source")
        accepted = first.publish(0, [source_id], {"action": "analyze"})
        with pytest.raises(ValueError, match="revision changed"):
            second.publish(0, [source_id], {"action": "conflicting analyze"})
        assert first.status() == {"revision": 1, "publication": "PUBLISHED"}
        assert second.status() == first.status()
        assert hashlib.sha256((tmp_path / "checkpoint.json").read_bytes()).hexdigest() == accepted["checkpoint_sha256"]
    finally:
        first.close()
        second.close()


def test_recovery_refuses_checkpoint_with_missing_accepted_object(tmp_path):
    repository = spike(tmp_path)
    source_id = repository.put_object("source", b"must remain available")
    try:
        with pytest.raises(RuntimeError, match="injected after commit"):
            repository.publish(0, [source_id], {"action": "analyze"}, fail_at="after_commit")
        repository._object_path(source_id).unlink()
        with pytest.raises(ValueError, match="missing accepted object"):
            repository.recover()
        assert repository.status() == {"revision": 1, "publication": "PENDING"}
        assert not (tmp_path / "checkpoint.json").exists()
    finally:
        repository.close()


def test_interrupted_object_flush_never_accepts_a_revision(tmp_path, monkeypatch):
    from examples.verify import repository_spike

    repository = spike(tmp_path)
    def interrupted(_descriptor):
        raise OSError("synthetic flush interruption")
    monkeypatch.setattr(repository_spike.os, "fsync", interrupted)
    try:
        with pytest.raises(OSError, match="synthetic flush interruption"):
            repository.put_object("source", b"not durable")
        assert repository.status() == {"revision": 0, "publication": None}
        assert not list((tmp_path / "objects" / "source").iterdir())
    finally:
        repository.close()


def test_concurrent_publishers_have_exactly_one_winner(tmp_path):
    repository = spike(tmp_path)
    source_id = repository.put_object("source", b"shared bytes")
    repository.close()
    ready = threading.Barrier(2)

    def publish(actor):
        participant = spike(tmp_path)
        try:
            ready.wait(timeout=5)
            try:
                return participant.publish(0, [source_id], {"actor": actor})["revision"]
            except ValueError as exc:
                return str(exc)
        finally:
            participant.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, ("one", "two")))
    assert sorted(results, key=str) == [1, "revision changed"]
    reopened = spike(tmp_path)
    try:
        assert reopened.status() == {"revision": 1, "publication": "PUBLISHED"}
    finally:
        reopened.close()
