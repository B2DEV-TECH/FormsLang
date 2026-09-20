"""Only explicit conversion may invoke Oracle tools; originals are immutable."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from formslang import oracle
from formslang.project_manifest import source_id
from formslang.project_model import ProjectError
from formslang.project_service import ProjectService


@pytest.fixture
def binary_project(project_sources):
    access, descriptor, xml = project_sources
    xml.unlink()
    binary = xml.with_suffix('.fmb')
    binary.write_bytes(b'synthetic-form-binary')
    service = ProjectService(access)
    service.create(descriptor.name, roots=descriptor.source_roots)
    try:
        yield service, binary, source_id('forms', binary.name)
    finally:
        service.close()


@pytest.fixture
def configured_converter(monkeypatch, sample_xml):
    observed = {}
    tool = oracle.Toolchain(Path('synthetic-tool'), Path('synthetic-java'), 'synthetic-classpath')
    monkeypatch.setattr(oracle, 'detect_toolchain', lambda: tool)
    def convert(module, out_dir, toolchain, **kwargs):
        assert module.name == 'module.fmb' and module.read_bytes() == b'synthetic-form-binary'
        assert toolchain == tool
        out_dir.mkdir(parents=True, exist_ok=True)
        destination = out_dir / 'module_fmb.xml'
        destination.write_bytes(sample_xml.read_bytes())
        observed['tool_finished_at'] = datetime.now(timezone.utc).isoformat()
        return destination, 'conversion log containing sensitive source must not persist'
    monkeypatch.setattr(oracle, 'convert_module', convert)
    return observed


def test_conversion_requires_explicit_confirmation(binary_project, monkeypatch):
    service, _, sid = binary_project
    def forbidden(*a, **k):
        raise AssertionError('unconfirmed tool execution')
    monkeypatch.setattr(oracle, 'detect_toolchain', forbidden)
    with pytest.raises(ProjectError):
        service.convert_source(sid, expected_configuration=0, confirmed=False)


def test_missing_tool_has_guidance_and_preserves_selection(binary_project, monkeypatch):
    service, binary, sid = binary_project
    def absent():
        raise oracle.OracleToolchainError('private installation path')
    monkeypatch.setattr(oracle, 'detect_toolchain', absent)
    result = service.convert_source(sid, expected_configuration=0, confirmed=True)
    assert result['status'] == 'FAILED'
    assert result['safe_failure']['error_code'] == 'FORMS2XML_UNAVAILABLE'
    assert 'Forms2XML' in result['safe_failure']['remediation']
    assert 'private' not in str(result)
    assert binary.read_bytes() == b'synthetic-form-binary'
    assert service._store.configuration_revision() == 0


def test_explicit_conversion_is_selected_by_real_analysis(binary_project, configured_converter):
    service, binary, sid = binary_project
    result = service.convert_source(sid, expected_configuration=0, confirmed=True)
    assert result['status'] == 'COMPLETED'
    assert result['finished_at'] >= configured_converter['tool_finished_at']
    assert binary.read_bytes() == b'synthetic-form-binary'
    assert not binary.with_name('orders_fmb.xml').exists()
    assert service._store.configuration_revision() == 1
    analyzed = service.analyze(expected_revision=None, expected_configuration=1)
    assert analyzed['status'] == 'COMPLETED'
    saved = service.assessment()
    assert saved['inventory']['forms']['analyzed'] == 1
    assert saved['analysis_options']['intake']['derived_sources']
    assert 'sensitive source' not in str(saved)
    assert service.freshness()['status'] == 'CURRENT'


def test_changed_binary_invalidates_derived_representation(binary_project, configured_converter):
    service, binary, sid = binary_project
    service.convert_source(sid, expected_configuration=0, confirmed=True)
    service.analyze(expected_revision=None, expected_configuration=1)
    binary.write_bytes(b'changed binary')
    assert service.freshness()['status'] != 'CURRENT'
    service.analyze(expected_revision=service.open().analysis_revision, expected_configuration=1)
    saved = service.assessment()
    assert saved['completion_state'] == 'INCOMPLETE'
    assert saved['inventory']['forms']['analyzed'] == 0


@pytest.mark.parametrize('failure', ['escape', 'malformed', 'timeout', 'cancel'])
def test_conversion_failure_never_selects_output(binary_project, configured_converter, monkeypatch, sample_xml, failure):
    service, _, sid = binary_project
    def bad(module, out_dir, toolchain, **kwargs):
        if failure == 'escape':
            return sample_xml, ''
        if failure == 'timeout':
            raise oracle.OracleToolchainError('Forms2XML timeout')
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / 'bad.xml'
        path.write_text('<broken>' if failure == 'malformed' else sample_xml.read_text())
        if failure == 'cancel':
            row = service._store.session.db.execute("SELECT job_id FROM project_job WHERE status='RUNNING'").fetchone()
            service.cancel(row[0])
        return path, ''
    monkeypatch.setattr(oracle, 'convert_module', bad)
    result = service.convert_source(sid, expected_configuration=0, confirmed=True)
    assert result['status'] == ('CANCELLED' if failure == 'cancel' else 'FAILED')
    assert service._store.configuration_revision() == 0


def test_modified_derived_xml_cannot_remain_current(binary_project, configured_converter):
    service, _, sid = binary_project
    service.convert_source(sid, expected_configuration=0, confirmed=True)
    service.analyze(expected_revision=None, expected_configuration=1)
    path = next((service.access.root / '.formslang/derived').glob('*/*/module.xml'))
    path.write_bytes(path.read_bytes() + b'\n')
    assert service.freshness()['status'] == 'UNVERIFIED'


def test_failed_derived_selection_transaction_preserves_configuration(binary_project, configured_converter):
    service, _, sid = binary_project
    db = service._store.session.db
    db.executescript("CREATE TRIGGER fail_selection BEFORE INSERT ON project_derived_source BEGIN SELECT RAISE(ABORT,'test'); END;")
    result = service.convert_source(sid, expected_configuration=0, confirmed=True)
    assert result['status'] == 'FAILED'
    assert service._store.configuration_revision() == 0
    assert db.execute('SELECT COUNT(*) FROM project_derived_source').fetchone()[0] == 0
    db.execute('DROP TRIGGER fail_selection')
    db.commit()
    assert service.convert_source(sid, expected_configuration=0, confirmed=True)['status'] == 'COMPLETED'
