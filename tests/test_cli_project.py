"""Project commands exercise the same persisted local service as the Workbench."""

import json
import signal

import pytest

from formslang.cli import main


def run_json(capsys, arguments, expected=0):
    assert main(['project', *map(str, arguments), '--json']) == expected
    captured = capsys.readouterr()
    return json.loads(captured.out), captured.err


def create(capsys, tmp_path, sample_xml):
    destination = tmp_path / 'project'
    result, _ = run_json(capsys, ['create', destination, '--name', 'Orders', '--forms', sample_xml.parent])
    assert result['project']['target_version'] == '26.1'
    return destination, result


def test_create_analyze_status_json(tmp_path, sample_xml, capsys):
    destination, _ = create(capsys, tmp_path, sample_xml)
    first, progress = run_json(capsys, ['analyze', destination])
    assert first['analysis_revision']
    assert 'FORMS_PARSING' in progress
    status, _ = run_json(capsys, ['status', destination / '.formslang/project.json'])
    assert status['assessment']['analysis_revision'] == first['analysis_revision']
    assert status['freshness']['status'] == 'CURRENT'
    assert status['last_job']['status'] == 'COMPLETED'
    again, _ = run_json(capsys, ['analyze', destination])
    assert again['analysis_revision'] == first['analysis_revision']


def test_discover_open_and_relink(tmp_path, sample_xml, capsys):
    destination, created = create(capsys, tmp_path, sample_xml)
    found, _ = run_json(capsys, ['discover', destination])
    assert found['inventory']['forms']['parseable'] >= 1
    opened, _ = run_json(capsys, ['open', destination])
    assert opened['project']['id'] == created['project']['id']
    result, _ = run_json(capsys, ['relink', destination, '--root', created['project']['source_roots'][0]['id'],
                                '--path', sample_xml.parent])
    assert result['configuration_revision'] == 1


def test_auth_mode_refuses_local_authority(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('FORMSLANG_AUTH', '1')
    result, _ = run_json(capsys, ['create', tmp_path / 'project', '--name', 'Orders'], expected=2)
    assert 'API' in result['error']
    assert not (tmp_path / 'project').exists()


def test_missing_source_and_blank_name_are_safe_errors(tmp_path, capsys):
    result, _ = run_json(capsys, ['create', tmp_path / 'project', '--name', 'Orders',
                                '--forms', tmp_path / 'absent'], expected=2)
    assert result['error']
    result, _ = run_json(capsys, ['create', tmp_path / 'project', '--name', ' '], expected=2)
    assert result['error']


def test_unsupported_target_is_argument_error(tmp_path):
    with pytest.raises(SystemExit) as failure:
        main(['project', 'create', str(tmp_path), '--name', 'Orders', '--target-apex', '0'])
    assert failure.value.code == 2


def test_sigint_cooperatively_cancels_and_restores_handler(tmp_path, sample_xml, capsys, monkeypatch):
    from formslang import project_cli

    destination, _ = create(capsys, tmp_path, sample_xml)
    saved, _ = run_json(capsys, ['analyze', destination])
    previous = signal.getsignal(signal.SIGINT)
    original_progress = project_cli._progress

    def interrupt_at_parsing(event):
        original_progress(event)
        if event['phase'] == 'FORMS_PARSING':
            signal.raise_signal(signal.SIGINT)

    monkeypatch.setattr(project_cli, '_progress', interrupt_at_parsing)
    cancelled, _ = run_json(capsys, ['analyze', destination], expected=130)
    assert cancelled['status'] == 'CANCELLED'
    assert signal.getsignal(signal.SIGINT) == previous
    status, _ = run_json(capsys, ['status', destination])
    assert status['assessment']['analysis_revision'] == saved['analysis_revision']


def test_open_does_not_grant_descriptor_source_authority(tmp_path, sample_xml, capsys, monkeypatch):
    destination, _ = create(capsys, tmp_path, sample_xml)
    run_json(capsys, ['analyze', destination])
    monkeypatch.setenv('FORMSLANG_CONFIG_DIR', str(tmp_path / 'other-local-settings'))
    opened, _ = run_json(capsys, ['open', destination])
    assert opened['project']['analysis_revision']
    result, _ = run_json(capsys, ['analyze', destination], expected=1)
    assert result['status'] == 'FAILED'


def test_failed_analysis_returns_one_without_traceback(tmp_path, capsys):
    sources = tmp_path / 'sources'
    sources.mkdir()
    (sources / 'bad.xml').write_text('<broken', encoding='utf-8')
    destination = tmp_path / 'project'
    run_json(capsys, ['create', destination, '--name', 'Broken', '--forms', sources])
    result, progress = run_json(capsys, ['analyze', destination], expected=1)
    assert result['status'] == 'FAILED'
    assert 'Traceback' not in progress


def test_unexpected_failure_does_not_expose_source_or_credentials(tmp_path, sample_xml, capsys, monkeypatch):
    from formslang.project_service import ProjectService

    destination, _ = create(capsys, tmp_path, sample_xml)

    def broken(*args, **kwargs):
        raise RuntimeError('secret-password customer-source-body')

    monkeypatch.setattr(ProjectService, 'analyze', broken)
    result, output = run_json(capsys, ['analyze', destination], expected=1)
    assert 'retry' in result['error'].lower()
    assert 'secret-password' not in json.dumps(result) + output


def test_demo_cli_creates_normal_offline_project(tmp_path, capsys):
    destination = tmp_path / 'demo-project'
    created, _ = run_json(capsys, ['demo', destination])
    assert created['project']['name'] == 'Synthetic dispatch desk'
    analyzed, _ = run_json(capsys, ['analyze', destination])
    assert analyzed['status'] == 'COMPLETED'


def test_summary_and_inventory_read_saved_projection(tmp_path, capsys):
    destination = tmp_path / 'demo-project'
    run_json(capsys, ['demo', destination])
    analyzed, _ = run_json(capsys, ['analyze', destination])

    summary, progress = run_json(capsys, ['summary', destination])
    inventory, inventory_progress = run_json(capsys, [
        'inventory', destination, '--category', 'findings', '--risk', 'CRITICAL',
        '--limit', '50', '--revision', analyzed['analysis_revision'],
    ])

    assert progress == inventory_progress == ''
    assert summary['assessment']['analysis_revision'] == analyzed['analysis_revision']
    assert summary['inventory']['modernization_findings'] > 0
    assert inventory['analysis_revision'] == analyzed['analysis_revision']
    assert inventory['total'] >= 1
    assert all(row['risk'] == 'CRITICAL' for row in inventory['rows'])


def test_inventory_cli_rejects_invalid_category_and_limit(tmp_path, capsys):
    destination = tmp_path / 'demo-project'
    run_json(capsys, ['demo', destination])
    run_json(capsys, ['analyze', destination])

    with pytest.raises(SystemExit) as category:
        main(['project', 'inventory', str(destination), '--category', 'unknown', '--json'])
    with pytest.raises(SystemExit) as limit:
        main(['project', 'inventory', str(destination), '--limit', '201', '--json'])

    assert category.value.code == limit.value.code == 2
