"""Descriptor reconciliation must serialize with publication, also on Windows."""

import json
import multiprocessing
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from formslang import project_store
from formslang.project_model import ProjectDescriptor, SourceRoot
from formslang.project_store import ProjectStore


def test_open_does_not_republish_an_already_current_descriptor(tmp_path, monkeypatch):
    ProjectStore.create(tmp_path, ProjectDescriptor(id='d' * 32, name='Concurrent')).close()

    def unexpected_publication(_store):
        raise AssertionError('a current descriptor must not request a second writer transaction')

    monkeypatch.setattr(ProjectStore, 'sync_descriptor', unexpected_publication)
    reopened = ProjectStore.open(tmp_path)
    try:
        assert reopened.descriptor().id == 'd' * 32
    finally:
        reopened.close()


def test_open_does_not_read_descriptor_during_replacement(tmp_path, monkeypatch):
    ProjectStore.create(tmp_path, ProjectDescriptor(id='d' * 32, name='Concurrent')).close()
    publishing, release, attempting, overlapping = (threading.Event() for _ in range(4))
    original_replace = project_store.replace_mirror
    original_read = Path.read_text

    def paused_replace(source, destination):
        if threading.current_thread().name == 'descriptor-publisher':
            publishing.set()
            assert release.wait(10)
        return original_replace(source, destination)

    def observed_read(path, *args, **kwargs):
        if path.name == 'project.json' and publishing.is_set() and not release.is_set():
            overlapping.set()
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(project_store, 'replace_mirror', paused_replace)
    monkeypatch.setattr(Path, 'read_text', observed_read)

    def publish():
        threading.current_thread().name = 'descriptor-publisher'
        store = ProjectStore.open(tmp_path)
        try:
            store.replace_roots((SourceRoot('f', 'forms', 'new-source'),), expected_configuration=0)
        finally:
            store.close()

    def reopen():
        attempting.set()
        store = ProjectStore.open(tmp_path)
        try:
            assert store.descriptor().source_roots[0].path == 'new-source'
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(publish)
        try:
            assert publishing.wait(10)
            reader = pool.submit(reopen)
            assert attempting.wait(10)
            unsafe_overlap = overlapping.wait(.25)
        finally:
            release.set()
        writer.result(timeout=10)
        reader.result(timeout=10)
    assert not unsafe_overlap, 'open read project.json while another connection was publishing it'


def test_concurrent_descriptor_readers_and_publication(tmp_path):
    ProjectStore.create(tmp_path, ProjectDescriptor(id='d' * 32, name='Concurrent')).close()
    start = threading.Barrier(5)

    def reader():
        start.wait(timeout=10)
        for _ in range(100):
            store = ProjectStore.open(tmp_path)
            try:
                assert store.descriptor().id == 'd' * 32
                assert store.load_assessment() is None
            finally:
                store.close()
        return 100

    with ThreadPoolExecutor(max_workers=4) as pool:
        readers = [pool.submit(reader) for _ in range(4)]
        store = ProjectStore.open(tmp_path)
        try:
            start.wait(timeout=10)
            for revision in range(50):
                store.replace_roots((SourceRoot('f', 'forms', f'source-{revision}'),),
                                    expected_configuration=revision)
        finally:
            store.close()
        assert sum(task.result() for task in readers) == 400
    reopened = ProjectStore.open(tmp_path)
    try:
        assert reopened.configuration_revision() == 50
        assert json.loads((tmp_path / '.formslang/project.json').read_text())['source_roots'][0]['path'] == 'source-49'
    finally:
        reopened.close()


def _process_reader(root, start, results):
    try:
        start.wait(timeout=20)
        for _ in range(100):
            store = ProjectStore.open(root)
            try:
                assert store.descriptor().id == 'd' * 32
            finally:
                store.close()
        results.put(None)
    except Exception:  # noqa: BLE001 - return the original child traceback to the test process
        results.put(traceback.format_exc())


def test_descriptor_publication_with_other_process_readers(tmp_path):
    ProjectStore.create(tmp_path, ProjectDescriptor(id='d' * 32, name='Concurrent')).close()
    context = multiprocessing.get_context('spawn')
    start, results = context.Barrier(3), context.Queue()
    readers = [context.Process(target=_process_reader, args=(tmp_path, start, results)) for _ in range(2)]
    for reader in readers:
        reader.start()
    store = ProjectStore.open(tmp_path)
    try:
        start.wait(timeout=20)
        for revision in range(50):
            store.replace_roots((SourceRoot('f', 'forms', f'source-{revision}'),),
                                expected_configuration=revision)
        outcomes = [results.get(timeout=30) for _ in readers]
        assert outcomes == [None, None], outcomes
    finally:
        store.close()
        for reader in readers:
            reader.join(timeout=30)
            if reader.is_alive():
                reader.terminate()
                reader.join(timeout=5)
        results.close()
        results.join_thread()
    assert all(reader.exitcode == 0 for reader in readers)
