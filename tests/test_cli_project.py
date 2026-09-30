"""Project commands exercise the same persisted local service as the Workbench."""

import json
import signal
import sqlite3

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
    assert status['freshness']['status'] == 'UNVERIFIED'
    assert status['last_job']['status'] == 'COMPLETED'
    checked, _ = run_json(capsys, ['freshness', destination])
    assert checked['status'] == 'CURRENT'
    status, _ = run_json(capsys, ['status', destination])
    assert status['freshness']['status'] == 'CURRENT'
    assert status['last_job']['operation'] == 'FRESHNESS'
    again, _ = run_json(capsys, ['analyze', destination])
    assert again['analysis_revision'] == first['analysis_revision']


def test_project_reads_use_saved_freshness_until_explicit_check(tmp_path, sample_xml, capsys):
    destination, _ = create(capsys, tmp_path, sample_xml)
    analyzed, _ = run_json(capsys, ['analyze', destination])
    database = destination / '.formslang' / 'project.session.db'

    def jobs():
        with sqlite3.connect(database) as db:
            return db.execute('SELECT COUNT(*) FROM project_job').fetchone()[0]

    before = jobs()
    status, _ = run_json(capsys, ['status', destination])
    summary, _ = run_json(capsys, ['summary', destination])
    inventory, _ = run_json(capsys, ['inventory', destination, '--category', 'forms'])
    assert status['freshness']['status'] == 'UNVERIFIED'
    assert status['freshness']['analysis_revision'] == analyzed['analysis_revision']
    assert summary['assessment']['analysis_revision'] == analyzed['analysis_revision']
    assert inventory['analysis_revision'] == analyzed['analysis_revision']
    assert jobs() == before

    checked, _ = run_json(capsys, ['freshness', destination])
    assert checked['status'] == 'CURRENT'
    assert jobs() == before + 1
    status, _ = run_json(capsys, ['status', destination])
    assert status['freshness']['status'] == 'CURRENT'
    assert jobs() == before + 1

    # Saved CURRENT describes the check at checked_at; it is not a live scan.
    checked_at = status['freshness']['checked_at']
    sample_xml.write_text(sample_xml.read_text(encoding='utf-8') + '\n<!-- changed after check -->\n',
                          encoding='utf-8')
    cached, _ = run_json(capsys, ['status', destination])
    summary, _ = run_json(capsys, ['summary', destination])
    assert cached['freshness']['status'] == 'CURRENT'
    assert cached['freshness']['checked_at'] == checked_at
    assert summary['assessment']['freshness'] == 'CURRENT'
    assert jobs() == before + 1
    refreshed, _ = run_json(capsys, ['freshness', destination])
    assert refreshed['status'] == 'STALE'
    assert refreshed['reasons'] == ['SOURCE_CHANGED']
    assert jobs() == before + 2


def test_analysis_history_lists_saved_revisions_without_repair_or_scan(tmp_path, sample_xml, capsys):
    destination, _ = create(capsys, tmp_path, sample_xml)
    first, _ = run_json(capsys, ['analyze', destination])
    sample_xml.write_text(sample_xml.read_text(encoding='utf-8') + '\n<!-- second source revision -->\n',
                          encoding='utf-8')
    second, _ = run_json(capsys, ['analyze', destination])
    assert first['analysis_revision'] != second['analysis_revision']
    database = destination / '.formslang' / 'project.session.db'
    mirror = destination / '.formslang' / 'project.json'
    mirror.unlink()
    with sqlite3.connect(database) as db:
        jobs_before = db.execute('SELECT COUNT(*) FROM project_job').fetchone()[0]

    history, _ = run_json(capsys, ['analysis-history', destination])

    assert history['scope'] == 'SAVED_ANALYSES_ONLY'
    assert history['current_analysis_revision'] == second['analysis_revision']
    assert history['total'] == 2
    assert [row['analysis_revision'] for row in history['rows']] == [
        second['analysis_revision'], first['analysis_revision']]
    assert [row['current'] for row in history['rows']] == [True, False]
    assert all(len(row['source_revision']) == 64 and row['analyzed_at'] for row in history['rows'])
    assert history['rows'][0]['source_revision'] != history['rows'][1]['source_revision']
    assert not mirror.exists()
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT COUNT(*) FROM project_job').fetchone()[0] == jobs_before


@pytest.mark.parametrize('arguments', [['--limit', '0'], ['--limit', '201'], ['--offset', '-1'],
                                         ['--offset', '9223372036854775808']])
def test_analysis_history_rejects_unbounded_or_negative_pagination(tmp_path, sample_xml, capsys, arguments):
    destination, _ = create(capsys, tmp_path, sample_xml)
    result, _ = run_json(capsys, ['analysis-history', destination, *arguments], expected=2)
    assert 'limit' in result['error'].lower() or 'offset' in result['error'].lower()


def test_analysis_history_direct_service_requires_read_only_open(tmp_path, sample_xml, capsys):
    from formslang.project_model import ProjectError
    from formslang.project_service import ProjectService
    from formslang.projects import local_project_access

    destination, _ = create(capsys, tmp_path, sample_xml)
    run_json(capsys, ['analyze', destination])
    mirror = destination / '.formslang' / 'project.json'
    mirror.unlink()
    service = ProjectService(local_project_access(destination, approved_roots=()))
    try:
        with pytest.raises(ProjectError, match='read-only'):
            service.analysis_history()
    finally:
        service.close()
    assert not mirror.exists()


def test_analysis_history_reads_one_sqlite_snapshot_during_publication(tmp_path, sample_xml, capsys):
    from formslang.project_service import ProjectService
    from formslang.projects import local_project_access

    destination, _ = create(capsys, tmp_path, sample_xml)
    first, _ = run_json(capsys, ['analyze', destination])
    database = destination / '.formslang' / 'project.session.db'
    service = ProjectService(local_project_access(destination, approved_roots=()), read_only=True)
    service.open()
    db = service._store.session.db
    attempts = []

    def concurrent_publication(statement):
        if 'SELECT COUNT(*) FROM project_assessment' not in statement or attempts:
            return
        writer = sqlite3.connect(database, timeout=0)
        try:
            writer.execute('INSERT INTO project_assessment VALUES (?,?,?,?)',
                           ('f' * 64, 'e' * 64, '2099-01-01T00:00:00+00:00', '{}'))
            writer.commit()
            attempts.append('published')
        except sqlite3.OperationalError:
            attempts.append('blocked')
        finally:
            writer.close()

    db.set_trace_callback(concurrent_publication)
    try:
        history = service.analysis_history()
    finally:
        db.set_trace_callback(None)
        service.close()
    assert attempts == ['blocked']
    assert history['current_analysis_revision'] == first['analysis_revision']
    assert history['total'] == len(history['rows']) == 1


def test_analysis_history_distinguishes_empty_project_from_missing_current_assessment(
        tmp_path, sample_xml, capsys):
    destination, _ = create(capsys, tmp_path, sample_xml)
    empty, _ = run_json(capsys, ['analysis-history', destination])
    assert empty['total'] == 0 and empty['rows'] == []
    assert empty['current_analysis_revision'] is None
    analyzed, _ = run_json(capsys, ['analyze', destination])
    database = destination / '.formslang' / 'project.session.db'
    with sqlite3.connect(database) as db:
        db.execute('DELETE FROM project_assessment WHERE revision=?', (analyzed['analysis_revision'],))

    result, _ = run_json(capsys, ['analysis-history', destination], expected=2)
    assert 'integrity' in result['error'].lower()


def test_analysis_history_tied_timestamps_have_stable_revision_order(tmp_path, sample_xml, capsys):
    destination, _ = create(capsys, tmp_path, sample_xml)
    run_json(capsys, ['analyze', destination])
    sample_xml.write_text(sample_xml.read_text(encoding='utf-8') + '\n<!-- next -->\n',
                          encoding='utf-8')
    run_json(capsys, ['analyze', destination])
    database = destination / '.formslang' / 'project.session.db'
    with sqlite3.connect(database) as db:
        rows = db.execute('SELECT * FROM project_assessment').fetchall()
        assert len(rows) == 2
        db.execute('DELETE FROM project_assessment')
        for revision, source_revision, _, payload in sorted(rows, reverse=True):
            db.execute('INSERT INTO project_assessment VALUES (?,?,?,?)',
                       (revision, source_revision, '2026-09-30T00:00:00+00:00', payload))

    first, _ = run_json(capsys, ['analysis-history', destination])
    second, _ = run_json(capsys, ['analysis-history', destination])
    assert first == second
    assert [row['analysis_revision'] for row in first['rows']] == sorted(row[0] for row in rows)


def test_status_does_not_republish_missing_descriptor_mirror(tmp_path, sample_xml, capsys):
    destination, _ = create(capsys, tmp_path, sample_xml)
    run_json(capsys, ['analyze', destination])
    mirror = destination / '.formslang' / 'project.json'
    mirror.unlink()

    status, _ = run_json(capsys, ['status', destination])

    assert status['assessment']['analysis_revision']
    assert not mirror.exists()


def test_status_requires_explicit_storage_upgrade_without_writing(tmp_path, sample_xml, capsys):
    destination, _ = create(capsys, tmp_path, sample_xml)
    database = destination / '.formslang' / 'project.session.db'
    mirror = destination / '.formslang' / 'project.json'
    with sqlite3.connect(database) as db:
        db.execute('DROP TABLE project_job')
    mirror.unlink()

    error, _ = run_json(capsys, ['status', destination], expected=2)

    assert 'migration' in error['error'].lower()
    assert 'formslang project open' in error['error']
    assert not mirror.exists()
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='project_job'").fetchone() is None

    opened, _ = run_json(capsys, ['open', destination])
    assert opened['project']['id']
    assert mirror.exists()
    status, _ = run_json(capsys, ['status', destination])
    assert status['project']['id'] == opened['project']['id']


def test_project_reports_use_snapshot_and_exclusive_download(tmp_path, sample_xml, capsys):
    destination, _ = create(capsys, tmp_path, sample_xml)
    run_json(capsys, ['analyze', destination])
    state, _ = run_json(capsys, ['report', destination, '--format', 'status'])
    assert state['binding']['snapshot_revision']
    output = tmp_path / 'executive.html'
    first, _ = run_json(capsys, ['report', destination, '--format', 'executive', '--output', output])
    assert first['saved'] and first['size_bytes'] == output.stat().st_size
    assert 'Executive Summary' in output.read_text(encoding='utf-8')
    before = output.read_bytes()
    run_json(capsys, ['report', destination, '--format', 'executive', '--output', output], expected=2)
    assert output.read_bytes() == before


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


def test_generation_cli_uses_project_service(tmp_path, sample_xml, capsys):
    destination, _ = create(capsys, tmp_path, sample_xml)
    run_json(capsys, ['analyze', destination])
    overview, _ = run_json(capsys, ['generation', 'status', destination])
    sid = overview['modules'][0]['source_id']
    request = tmp_path / 'request.json'
    request.write_text(json.dumps(overview['binding']), encoding='utf-8')
    prepared, _ = run_json(capsys, ['generation', 'prepare', destination, '--source', sid, '--request', request])
    detail, _ = run_json(capsys, ['generation', 'module', destination, '--source', sid])
    assert detail['code_revision'] == prepared['code_revision']
    assert detail['blockers'] and not detail['ready']


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


def test_review_cli_uses_shared_history_and_explicit_revision(tmp_path, capsys):
    destination = tmp_path / 'review-demo'
    run_json(capsys, ['demo', destination])
    run_json(capsys, ['analyze', destination])
    page, _ = run_json(capsys, ['review', 'list', destination, '--limit', '1'])
    finding_id = page['rows'][0]['id']
    detail, _ = run_json(capsys, ['review', 'show', destination, '--finding', finding_id])
    binding = detail['binding']
    args = ['review', 'decide', destination, '--finding', finding_id,
            '--action', 'APPROVE', '--binding', json.dumps(binding)]
    run_json(capsys, args)
    conflict, _ = run_json(capsys, args, expected=2)
    assert 'changed' in conflict['error']
    after, _ = run_json(capsys, ['review', 'show', destination, '--finding', finding_id])
    assert after['item']['review_state'] == 'APPROVE'
    assert len(after['history']) == 1
