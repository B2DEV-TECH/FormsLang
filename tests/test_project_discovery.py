"""Source inventory must not confuse file extensions with supported semantics."""

import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from formslang.project_model import ProjectDescriptor, ProjectError, SourceRoot
from formslang.projects import local_project_access


def discover(root, *, roots=None, preview=True, **kwargs):
    from formslang.project_discovery import discover_sources

    access = local_project_access(root / 'project', approved_roots=(root,))
    descriptor = ProjectDescriptor(id='a'*32, name='Orders', source_roots=roots or (
        SourceRoot('forms', 'forms', str(root / 'forms')),
    ))
    return discover_sources(access, descriptor, checkpoint=lambda: None,
                            progress=lambda event: None, preview=preview, **kwargs)


def test_pair_prefers_xml_without_claiming_binary_freshness(tmp_path, sample_xml):
    forms = tmp_path / 'forms'
    forms.mkdir()
    (forms / 'orders.fmb').write_bytes(b'synthetic-not-an-oracle-binary')
    (forms / 'orders_fmb.xml').write_bytes(sample_xml.read_bytes())
    result = discover(tmp_path)
    selected = [entry for entry in result.entries if entry.candidate.selected]
    assert len(selected) == 1
    assert selected[0].candidate.representation == 'xml'
    assert selected[0].original_binary_id
    assert not selected[0].freshness_verified
    assert result.inventory['forms']['parseable'] == 1
    assert result.inventory['forms']['fmb_without_xml'] == 0


@pytest.mark.parametrize('suffix', ['.fmb', '.pll', '.mmb', '.olb'])
def test_binary_discovery_does_not_claim_parsing(tmp_path, suffix):
    forms = tmp_path / 'forms'
    forms.mkdir()
    (forms / ('module' + suffix)).write_bytes(b'synthetic')
    result = discover(tmp_path)
    assert len(result.entries) == 1
    assert result.entries[0].support == 'UNSUPPORTED_REPRESENTATION'
    assert not result.entries[0].candidate.selected
    assert result.inventory['forms']['parseable'] == 0
    assert result.diagnostics[0].remediation


@pytest.mark.parametrize(('suffix', 'content', 'supported'), [
    ('.sql', 'create table orders (id number);', True),
    ('.pks', 'create or replace package api as procedure save; end api; /', True),
    ('.pkb', 'create or replace package body api as procedure save is begin null; end; end api; /', True),
    ('.vw', 'create view orders_v as select id from orders;', True),
    ('.prc', 'create procedure save is begin null; end; /', False),
    ('.fnc', 'create function price return number is begin return 1; end; /', False),
    ('.trg', 'create trigger aud before insert on orders begin null; end; /', False),
    ('.sql', 'select 1 from dual;', False),
])
def test_database_support_depends_on_content(tmp_path, suffix, content, supported):
    db = tmp_path / 'db'
    db.mkdir()
    (db / ('object' + suffix)).write_text(content, encoding='utf-8')
    result = discover(tmp_path, roots=(SourceRoot('db', 'database', str(db)),))
    assert len(result.entries) == 1
    assert (result.entries[0].support == 'SUPPORTED') == supported
    if not supported:
        assert result.diagnostics[0].error_code == 'UNSUPPORTED_SQL'


@pytest.mark.parametrize(('xml', 'code'), [
    ('<broken>', 'INVALID_XML'),
    ('<Module><MenuModule /></Module>', 'UNSUPPORTED_XML'),
])
def test_bad_xml_is_safe_diagnostic(tmp_path, xml, code):
    forms = tmp_path / 'forms'
    forms.mkdir()
    (forms / 'bad.xml').write_text(xml, encoding='utf-8')
    result = discover(tmp_path)
    assert result.diagnostics[0].error_code == code
    assert str(tmp_path) not in result.diagnostics[0].safe_message
    assert result.diagnostics[0].relative_path == 'bad.xml'


def test_ambiguous_pair_is_not_guessed(tmp_path, sample_xml):
    forms = tmp_path / 'forms'
    forms.mkdir()
    (forms / 'orders.fmb').write_bytes(b'synthetic')
    for name in ('orders.xml', 'orders_fmb.xml'):
        (forms / name).write_bytes(sample_xml.read_bytes())
    result = discover(tmp_path)
    assert any(d.error_code == 'AMBIGUOUS_XML_PAIR' for d in result.diagnostics)
    assert all(e.original_binary_id is None for e in result.entries)


def test_overlapping_roots_rejected(tmp_path):
    root = tmp_path / 'forms'
    (root / 'nested').mkdir(parents=True)
    for path in (root, root / 'nested'):
        with pytest.raises(ProjectError, match='overlap|Duplicate'):
            discover(tmp_path, roots=(SourceRoot('a', 'forms', str(root)),
                                     SourceRoot('b', 'forms', str(path))))


def test_same_basename_different_roots_stays_distinct(tmp_path, sample_xml):
    roots = []
    for name in ('a', 'b'):
        path = tmp_path / name
        path.mkdir()
        (path / 'orders.xml').write_bytes(sample_xml.read_bytes())
        roots.append(SourceRoot(name, 'forms', str(path)))
    result = discover(tmp_path, roots=tuple(roots))
    assert len([e for e in result.entries if e.candidate.selected]) == 2
    assert {e.candidate.root_id for e in result.entries} == {'a', 'b'}


def test_ignored_directories_and_explicit_benchmark_output(tmp_path, sample_xml):
    root = tmp_path / 'forms'
    for name in ('.git', '.formslang', 'build', 'dist', 'artifacts', 'reports', 'node_modules', 'benchmark/outputs'):
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        (path / 'hidden.xml').write_bytes(sample_xml.read_bytes())
    assert not discover(tmp_path).entries
    explicit = root / 'benchmark/outputs'
    assert len(discover(tmp_path, roots=(SourceRoot('f', 'forms', str(explicit)),)).entries) == 1


def test_descriptor_path_does_not_authorize_source(tmp_path):
    from formslang.project_discovery import discover_sources

    (tmp_path / 'forms').mkdir()
    access = local_project_access(tmp_path / 'project', approved_roots=())
    descriptor = ProjectDescriptor(id='a'*32, name='Unsafe', source_roots=(
        SourceRoot('forms', 'forms', str(tmp_path / 'forms')),))
    with pytest.raises(PermissionError):
        discover_sources(access, descriptor, checkpoint=lambda: None, progress=lambda e: None)
    restricted = replace(access, source_roots=(tmp_path,))
    assert restricted.root == access.root


def test_preview_false_never_parses(tmp_path, sample_xml, monkeypatch):
    from formslang import database, parser

    forms = tmp_path / 'forms'
    forms.mkdir()
    (forms / 'orders.xml').write_bytes(sample_xml.read_bytes())
    def forbidden(*a, **k):
        raise AssertionError('freshness discovery must not parse')
    monkeypatch.setattr(parser, 'parse_xml', forbidden)
    monkeypatch.setattr(database, 'parse_database_file', forbidden)
    result = discover(tmp_path, preview=False)
    assert result.entries[0].candidate.selected


def test_discovery_cancellation_propagates(tmp_path):
    from formslang.project_discovery import discover_sources

    (tmp_path / 'forms').mkdir()
    access = local_project_access(tmp_path / 'project', approved_roots=(tmp_path,))
    descriptor = ProjectDescriptor(id='a'*32, name='Cancel', source_roots=(
        SourceRoot('f', 'forms', str(tmp_path / 'forms')),))
    def cancelled():
        raise InterruptedError('cancelled')
    with pytest.raises(InterruptedError):
        discover_sources(access, descriptor, checkpoint=cancelled, progress=lambda e: None)


def test_hardlink_alias_is_disclosed_not_double_analyzed(tmp_path, sample_xml):
    forms = tmp_path / 'forms'
    forms.mkdir()
    original = forms / 'a.xml'
    original.write_bytes(sample_xml.read_bytes())
    os.link(original, forms / 'b.xml')
    result = discover(tmp_path)
    assert len(result.entries) == 2
    assert sum(e.candidate.selected for e in result.entries) == 1
    assert any(d.error_code == 'DUPLICATE_FILE' for d in result.diagnostics)


def test_source_size_limit_is_explicit(tmp_path, monkeypatch):
    from formslang import project_discovery

    forms = tmp_path / 'forms'
    forms.mkdir()
    (forms / 'big.xml').write_bytes(b'x' * 11)
    monkeypatch.setattr(project_discovery, 'MAX_SOURCE_BYTES', 10)
    result = discover(tmp_path)
    assert result.entries[0].lifecycle == 'FAILED'
    assert result.diagnostics[0].error_code == 'SOURCE_TOO_LARGE'


def test_file_limit_reports_incomplete_traversal(tmp_path, sample_xml, monkeypatch):
    from formslang import project_discovery

    forms = tmp_path / 'forms'
    forms.mkdir()
    for name in ('a.xml', 'b.xml', 'c.xml'):
        (forms / name).write_bytes(sample_xml.read_bytes())
    monkeypatch.setattr(project_discovery, 'MAX_FILES', 2)
    result = discover(tmp_path)
    assert len(result.entries) == 2
    assert any(d.error_code == 'FILE_LIMIT' for d in result.diagnostics)


def test_depth_limit_reports_excluded_scope(tmp_path, sample_xml, monkeypatch):
    from formslang import project_discovery

    deep = tmp_path / 'forms/nested/deeper'
    deep.mkdir(parents=True)
    (deep / 'orders.xml').write_bytes(sample_xml.read_bytes())
    monkeypatch.setattr(project_discovery, 'MAX_DEPTH', 1)
    result = discover(tmp_path)
    assert not result.entries
    assert any(d.error_code == 'DEPTH_LIMIT' for d in result.diagnostics)


def test_denied_directory_safe_error(tmp_path, monkeypatch):
    from formslang import project_discovery

    forms = tmp_path / 'forms'
    forms.mkdir()
    def denied(path):
        raise PermissionError('SECRET-credential-and-path')
    monkeypatch.setattr(project_discovery.os, 'scandir', denied)
    result = discover(tmp_path)
    assert result.diagnostics[0].error_code == 'UNREADABLE_DIRECTORY'
    assert 'SECRET' not in repr(result)


def test_missing_root_is_diagnostic_not_empty_success(tmp_path):
    result = discover(tmp_path)
    assert result.diagnostics[0].error_code == 'MISSING_ROOT'


def test_symlink_escape_and_loop_never_followed(tmp_path, sample_xml):
    forms = tmp_path / 'forms'
    forms.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'secret.xml').write_bytes(sample_xml.read_bytes())
    try:
        (forms / 'escape').symlink_to(outside, target_is_directory=True)
        (forms / 'loop').symlink_to(forms, target_is_directory=True)
    except OSError:
        pytest.skip('OS does not permit symlinks')
    result = discover(tmp_path)
    assert not result.entries
    assert len([d for d in result.diagnostics if d.error_code == 'REDIRECTED_PATH']) == 2


@pytest.mark.skipif(os.name != 'nt', reason='Windows NTFS junction regression')
def test_ntfs_junction_escape_and_root_redirect(tmp_path, sample_xml):
    forms = tmp_path / 'forms'
    forms.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'secret.xml').write_bytes(sample_xml.read_bytes())
    junction = forms / 'escape'
    command = f"New-Item -ItemType Junction -Path '{junction}' -Target '{outside}' | Out-Null"
    subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                   check=True, capture_output=True)
    try:
        result = discover(tmp_path)
        assert not result.entries
        assert result.diagnostics[0].error_code == 'REDIRECTED_PATH'
        with pytest.raises(ProjectError, match='redirected'):
            discover(tmp_path, roots=(SourceRoot('f', 'forms', str(junction)),))
    finally:
        os.rmdir(junction)  # Removes only the junction, never its target.
    assert (outside / 'secret.xml').is_file()


def test_project_storage_is_never_explicit_source(tmp_path):
    storage = tmp_path / 'project/.formslang'
    storage.mkdir(parents=True)
    with pytest.raises(ProjectError, match='storage'):
        discover(tmp_path, roots=(SourceRoot('f', 'forms', str(storage)),))


def test_irrelevant_directory_entries_are_bounded(tmp_path, monkeypatch):
    from formslang import project_discovery

    forms = tmp_path / 'forms'
    forms.mkdir()
    for i in range(10):
        (forms / f'{i}.txt').write_text('not a source')
    monkeypatch.setattr(project_discovery, 'MAX_FILES', 2)
    result = discover(tmp_path)
    assert any(d.error_code == 'FILE_LIMIT' for d in result.diagnostics)


def test_missing_authority_checked_before_filesystem_probe(tmp_path, monkeypatch):
    from formslang.project_discovery import discover_sources

    access = local_project_access(tmp_path / 'project', approved_roots=())
    descriptor = ProjectDescriptor(id='a'*32, name='Unsafe', source_roots=(
        SourceRoot('f', 'forms', str(tmp_path / 'private')),))
    original = Path.is_dir
    def is_dir(path):
        if path.name == 'private':
            raise AssertionError('private directory probed before authorization')
        return original(path)
    monkeypatch.setattr(Path, 'is_dir', is_dir)
    with pytest.raises(PermissionError):
        discover_sources(access, descriptor, checkpoint=lambda: None, progress=lambda e: None)


def test_cancel_while_enumerating_is_not_swallowed(tmp_path):
    from formslang.project_discovery import discover_sources

    forms = tmp_path / 'forms'
    forms.mkdir()
    (forms / 'orders.xml').write_text('<broken>')
    access = local_project_access(tmp_path / 'project', approved_roots=(forms,))
    descriptor = ProjectDescriptor(id='a'*32, name='Cancel', source_roots=(
        SourceRoot('f', 'forms', str(forms)),))
    calls = 0
    def cancel():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise InterruptedError('cancelled')
    with pytest.raises(InterruptedError):
        discover_sources(access, descriptor, checkpoint=cancel, progress=lambda e: None)


@pytest.mark.parametrize('name', ['artifacts', 'reports'])
def test_owned_outputs_cannot_be_selected_as_roots(tmp_path, name):
    output = tmp_path / 'project' / name
    output.mkdir(parents=True)
    with pytest.raises(ProjectError, match='storage|output'):
        discover(tmp_path, roots=(SourceRoot('f', 'forms', str(output)),))


def test_packages_count_specs_and_bodies_without_double_counting(tmp_path):
    db = tmp_path / 'db'
    db.mkdir()
    (db / 'api.pks').write_text('create or replace package api as procedure save; end api; /')
    (db / 'api.pkb').write_text('create or replace package body api as procedure save is begin null; end; end api; /')
    result = discover(tmp_path, roots=(SourceRoot('db', 'database', str(db)),))
    assert result.inventory['database']['packages'] == 1
    assert result.inventory['database']['package_specs'] == 1
    assert result.inventory['database']['package_bodies'] == 1


def test_unreadable_file_keeps_inventory_identity(tmp_path, sample_xml, monkeypatch):
    from formslang import project_discovery

    forms = tmp_path / 'forms'
    forms.mkdir()
    (forms / 'orders.xml').write_bytes(sample_xml.read_bytes())
    def denied(path):
        raise PermissionError('PRIVATE details')
    monkeypatch.setattr(project_discovery, '_inspect', denied)
    result = discover(tmp_path)
    assert len(result.entries) == 1
    assert result.entries[0].candidate.relative_path == 'orders.xml'
    assert result.entries[0].lifecycle == 'FAILED'
    assert result.diagnostics[0].error_code == 'UNREADABLE_SOURCE'
    assert 'PRIVATE' not in repr(result)
