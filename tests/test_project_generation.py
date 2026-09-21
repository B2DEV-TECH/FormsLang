"""Real static project through existing exporter, never mocked generation bytes."""

import hashlib
import json
import zipfile

import pytest

from formslang.project_model import RevisionConflict, SourceRoot
from formslang.project_service import ProjectService
from formslang.projects import local_project_access


@pytest.fixture
def generation_project(tmp_path, monkeypatch):
    monkeypatch.setenv('FORMSLANG_AUTH', '0')
    root = tmp_path / 'project'
    sources = tmp_path / 'forms'
    sources.mkdir()
    (sources / 'notice.xml').write_text('''<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="NOTICE" Title="Public-safe notice">
      <Block Name="INFO" DatabaseBlock="false">
        <Item Name="MESSAGE" ItemType="Display Item" Prompt="Message" Width="100" Height="16"/>
      </Block></FormModule></Module>''', encoding='utf-8')
    service = ProjectService(local_project_access(root, approved_roots=(tmp_path,)))
    service.create('Synthetic generation', roots=(SourceRoot('forms', 'forms', '../forms'),))
    result = service.analyze(expected_revision=None, expected_configuration=0)
    assert result['status'] in {'COMPLETED', 'COMPLETED_WITH_WARNINGS'}, json.dumps(result)
    yield service
    service.close()


def approve_architecture(service):
    for row in service.review_queue(limit=200)['rows']:
        detail = service.review_detail(row['id'])
        service.review_decide(row['id'], {**detail['binding'], 'action': 'APPROVE'})


def prepared(service):
    overview = service.generation_overview()
    sid = overview['modules'][0]['source_id']
    service.generation_prepare(sid, overview['binding'])
    approve_architecture(service)
    detail = service.generation_module(sid)
    service.generation_configure(sid, {**detail['binding'], 'code_revision': detail['code_revision'],
        'target_revision': detail['target_revision'], 'plan': {
            'security_confirmed': True, 'database_confirmed': True, 'mapping_confirmed': True,
            'rationale': 'No data writes; authenticated APEX account access reviewed.', 'keys': {}}})
    return service.generation_module(sid)


def test_prepare_does_not_approve_code_or_architecture(generation_project):
    service = generation_project
    overview = service.generation_overview()
    assert overview['modules']
    sid = overview['modules'][0]['source_id']
    service.generation_prepare(sid, overview['binding'])
    detail = service.generation_module(sid)
    assert detail['tasks'] == []
    assert detail['blockers']
    assert service.overview(freshness=service.freshness())['review_progress']['reviewed'] == 0


@pytest.mark.parametrize('damage', ['missing', 'empty', 'deleted_task', 'source', 'owner'])
def test_lost_prepared_code_cannot_become_zero_task_eligible(generation_project, damage):
    from contextlib import closing

    from formslang.project_model import ProjectError
    from formslang.store import Store
    service = generation_project
    sid, _, _, _ = code_scope(service)
    detail = prepared(service)
    assert not detail['ready'] and detail['tasks']
    record = service._store.module_sessions()[0]
    path = service._store.directory / record['relative_store']
    if damage in {'missing', 'empty'}:
        path.unlink()
    if damage == 'empty':
        with closing(Store(path)):
            pass
    if damage == 'deleted_task':
        with closing(Store(path)) as session:
            session.db.execute('DELETE FROM task')
            session.db.commit()
    if damage in {'source', 'owner'}:
        with closing(Store(path)) as session:
            session.db.execute('UPDATE task SET ' + damage + '=?', ('SYNTHETIC_ALTERATION',))
            session.db.commit()
    with pytest.raises(ProjectError, match='session|tasks'):
        service.generation_module(sid)
    if damage == 'missing':
        assert not path.exists()


def test_generate_is_deterministic_versioned_and_reopenable(generation_project):
    service = generation_project
    detail = prepared(service)
    assert detail['blockers'] == []
    request = {**detail['binding'], 'scopes': [{'source_id': detail['source_id'],
        'target_revision': detail['target_revision'], 'code_revision': detail['code_revision']}]}
    first = service.generate(request)
    assert first['status'] == 'Generated'
    data = service.generation_download(first['artifact_id'])
    assert hashlib.sha256(data).hexdigest() == first['sha256']
    second = service.generate(request)
    assert second['artifact_id'] != first['artifact_id']
    assert service.generation_download(second['artifact_id']) == data
    service.close()
    assert service.generation_download(first['artifact_id']) == data
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        apx = [n for n in archive.namelist() if n.endswith('.apx')]
        assert apx and any(n.endswith('application.apx') for n in apx)


def test_stale_source_rejects_generation_and_keeps_artifacts(generation_project):
    service = generation_project
    detail = prepared(service)
    source = service.access.source_roots[0] / 'forms' / 'notice.xml'
    source.write_text(source.read_text() + '\n<!-- changed -->', encoding='utf-8')
    with pytest.raises(RevisionConflict):
        service.generate({**detail['binding'], 'scopes': [{'source_id': detail['source_id'],
            'target_revision': detail['target_revision'], 'code_revision': detail['code_revision']}]})


def test_human_edited_files_are_preserved_and_invalidate_download(generation_project):
    service = generation_project
    detail = prepared(service)
    request = {**detail['binding'], 'scopes': [{'source_id': detail['source_id'],
        'target_revision': detail['target_revision'], 'code_revision': detail['code_revision']}]}
    first = service.generate(request)
    file = service.access.root / '.formslang/artifacts' / first['artifact_id'] / 'apexlang/application.apx'
    file.write_text('Human edit must remain here.', encoding='utf-8')
    with pytest.raises(RevisionConflict, match='edited'):
        service.generation_download(first['artifact_id'])
    second = service.generate(request)
    assert second['artifact_id'] != first['artifact_id']
    assert file.read_text() == 'Human edit must remain here.'


def test_review_changed_during_export_never_publishes(generation_project, monkeypatch):
    from formslang import apexlang
    service = generation_project
    detail = prepared(service)
    original = apexlang.export_apexlang

    def interleaved(*args, **kwargs):
        result = original(*args, **kwargs)
        # Represents a legacy writer which does not take the project worker lock.
        with service._store._write() as db:
            db.execute('UPDATE modernization_project SET review_revision=review_revision+1')
        return result

    monkeypatch.setattr(apexlang, 'export_apexlang', interleaved)
    with pytest.raises(RevisionConflict):
        service.generate({**detail['binding'], 'scopes': [{'source_id': detail['source_id'],
            'target_revision': detail['target_revision'], 'code_revision': detail['code_revision']}]})
    assert service.generation_overview()['artifacts'] == []


def code_scope(service):
    source = service.access.source_roots[0] / 'forms/notice.xml'
    text = source.read_text().replace('</Block>', '''<Trigger Name="WHEN-VALIDATE-RECORD"
        TriggerText="BEGIN IF :INFO.MESSAGE IS NULL THEN RAISE FORM_TRIGGER_FAILURE; END IF; END;"/></Block>''')
    source.write_text(text, encoding='utf-8')
    service.analyze(expected_revision=service.open().analysis_revision, expected_configuration=0)
    overview = service.generation_overview()
    sid = overview['modules'][0]['source_id']
    service.generation_prepare(sid, overview['binding'])
    detail = service.generation_module(sid)
    task = detail['tasks'][0]
    assert task['state'] == 'pending'
    request = {**detail['binding'], 'code_revision': detail['code_revision'],
        'state': 'approved', 'code': "BEGIN IF :P0_INFO_MESSAGE IS NULL THEN raise_application_error(-20001, 'Required'); END IF; END;",
        'rationale': 'Reviewed source and target validation.', 'code_confirmed': True}
    return sid, task, detail, request


def test_code_approval_uses_existing_session_and_exact_code_revision(generation_project):
    service = generation_project
    sid, task, detail, request = code_scope(service)
    from formslang.project_model import ProjectError
    with pytest.raises(ProjectError):
        service.generation_code(sid, task['id'], {**request, 'code_confirmed': False})
    service.generation_code(sid, task['id'], request)
    current = service.generation_module(sid)
    assert current['tasks'][0]['state'] == 'approved'
    assert current['code_revision'] != detail['code_revision']
    assert service.overview(freshness=service.freshness())['review_progress']['reviewed'] == 0
    with pytest.raises(RevisionConflict):
        service.generation_code(sid, task['id'], request)


def test_source_change_during_code_approval_rolls_back(generation_project, monkeypatch):
    from formslang.store import Store
    service = generation_project
    sid, task, _, request = code_scope(service)
    original = Store.set_decision
    source = service.access.source_roots[0] / 'forms/notice.xml'

    def interleaved(*args, **kwargs):
        original(*args, **kwargs)
        source.write_text(source.read_text() + '\n<!-- concurrent source edit -->', encoding='utf-8')

    monkeypatch.setattr(Store, 'set_decision', interleaved)
    with pytest.raises(RevisionConflict):
        service.generation_code(sid, task['id'], request)
    assert service.generation_task(sid, task['id'])['state'] == 'pending'


def test_added_artifact_file_invalidates_original_snapshot(generation_project):
    service = generation_project
    detail = prepared(service)
    artifact = service.generate({**detail['binding'], 'scopes': [detail]})
    directory = service.access.root / '.formslang/artifacts' / artifact['artifact_id'] / 'apexlang'
    (directory / 'unreviewed.apx').write_text('human addition', encoding='utf-8')
    with pytest.raises(RevisionConflict):
        service.generation_download(artifact['artifact_id'])


def test_code_change_during_artifact_copy_never_publishes(generation_project, monkeypatch):
    import shutil

    from formslang.store import Store
    service = generation_project
    detail = prepared(service)
    original = shutil.copytree

    def interleaved(*args, **kwargs):
        result = original(*args, **kwargs)
        from pathlib import Path
        destination = Path(args[1])
        if destination.name != 'apexlang' or len(destination.parent.name) != 32:
            return result
        record = service._store.module_sessions()[0]
        session = Store(service._store.directory / record['relative_store'], reconcile_jobs=False)
        try:
            session.confirm_block_key('INFO', '', 'MESSAGE', 'concurrent legacy writer')
        finally:
            session.close()
        return result

    monkeypatch.setattr(shutil, 'copytree', interleaved)
    with pytest.raises(RevisionConflict):
        service.generate({**detail['binding'], 'scopes': [detail]})
    assert service.generation_overview()['artifacts'] == []


@pytest.mark.parametrize(('replacement', 'blocker'), [
    ('<Item Name="A-B" ItemType="Text Item"/><Item Name="A_B" ItemType="Text Item"/>', 'TARGET_NAME_COLLISION'),
    ('<Item Name="PICTURE" ItemType="Image"/>', 'UNSUPPORTED_LAYOUT'),
])
def test_unsupported_layout_and_collisions_are_blocked(generation_project, replacement, blocker):
    service = generation_project
    source = service.access.source_roots[0] / 'forms/notice.xml'
    source.write_text(source.read_text().replace('</Block>', replacement + '</Block>'), encoding='utf-8')
    service.analyze(expected_revision=service.open().analysis_revision, expected_configuration=0)
    overview = service.generation_overview()
    sid = overview['modules'][0]['source_id']
    detail = service.generation_prepare(sid, overview['binding'])
    assert blocker in {b['code'] for b in detail['blockers']}


def test_target_plan_and_legacy_key_store_must_agree(generation_project):
    from formslang.store import Store
    service = generation_project
    detail = prepared(service)
    record = service._store.module_sessions()[0]
    session = Store(service._store.directory / record['relative_store'], reconcile_jobs=False)
    try:
        session.confirm_block_key('INFO', '', 'MESSAGE', 'legacy reviewer')
    finally:
        session.close()
    assert 'TARGET_KEYS_CHANGED' in {b['code'] for b in service.generation_module(detail['source_id'])['blockers']}


def test_invalid_later_key_does_not_partially_change_session(generation_project):
    service = generation_project
    detail = prepared(service)
    request = {**detail['binding'], 'target_revision': detail['target_revision'],
               'code_revision': detail['code_revision'], 'plan': {**detail['plan'],
                   'keys': {'INFO': 'MESSAGE', 'MISSING': 'ID'}}}
    with pytest.raises(ValueError):
        service.generation_configure(detail['source_id'], request)
    assert service.generation_module(detail['source_id'])['code_revision'] == detail['code_revision']


def test_source_change_during_key_confirmation_rolls_back(generation_project, monkeypatch):
    from formslang import apexlang
    service = generation_project
    detail = prepared(service)
    original = apexlang.apply_block_keys

    def interleaved(*args, **kwargs):
        original(*args, **kwargs)
        source = service.access.source_roots[0] / 'forms/notice.xml'
        source.write_text(source.read_text() + '\n<!-- edited -->', encoding='utf-8')

    monkeypatch.setattr(apexlang, 'apply_block_keys', interleaved)
    with pytest.raises(RevisionConflict):
        service.generation_configure(detail['source_id'], {**detail['binding'],
            'target_revision': detail['target_revision'], 'code_revision': detail['code_revision'],
            'plan': {**detail['plan'], 'keys': {'INFO': 'MESSAGE'}}})
    assert service.generation_module(detail['source_id'])['code_revision'] == detail['code_revision']


def test_target_change_invalidates_old_code_approval(generation_project):
    service = generation_project
    sid, task, detail, request = code_scope(service)
    service.generation_configure(sid, {**detail['binding'], 'code_revision': detail['code_revision'],
        'target_revision': detail['target_revision'], 'plan': {
            'security_confirmed': True, 'database_confirmed': True, 'mapping_confirmed': True,
            'rationale': 'Revised target prerequisites.', 'keys': {}}})
    with pytest.raises(RevisionConflict):
        service.generation_code(sid, task['id'], request)


@pytest.mark.parametrize('restriction', ['InsertAllowed="false"', 'UpdateAllowed="false"',
                                         'WhereClause="TENANT_ID = :GLOBAL.TENANT"'])
def test_unimplemented_data_controls_never_authorize_save(generation_project, restriction):
    service = generation_project
    source = service.access.source_roots[0] / 'forms/notice.xml'
    source.write_text(source.read_text().replace('DatabaseBlock="false"',
        'DatabaseBlock="true" QueryDataSourceName="ORDERS" ' + restriction), encoding='utf-8')
    service.analyze(expected_revision=service.open().analysis_revision, expected_configuration=0)
    overview = service.generation_overview()
    sid = overview['modules'][0]['source_id']
    detail = service.generation_prepare(sid, overview['binding'])
    assert 'UNSUPPORTED_DATA_CONTROL' in {b['code'] for b in detail['blockers']}


@pytest.mark.parametrize('code', ["BEGIN GO_BLOCK('INFO'); END;", 'BEGIN RAISE FORM_TRIGGER_FAILURE; END;',
                                 'BEGIN :INFO.MESSAGE := NULL; END;', 'BEGIN :P0_MISSING := NULL; END;'])
def test_approved_code_with_unmapped_forms_behavior_is_blocked(generation_project, code):
    service = generation_project
    sid, task, _, request = code_scope(service)
    service.generation_code(sid, task['id'], {**request, 'code': code})
    detail = service.generation_module(sid)
    assert 'UNSUPPORTED_TARGET_CODE' in {b['code'] for b in detail['blockers']}


def test_reviewed_validation_generates_enabled_component(generation_project):
    service = generation_project
    sid, task, _, _ = code_scope(service)
    approve_architecture(service)
    detail = service.generation_module(sid)
    detail = service.generation_configure(sid, {**detail['binding'], 'code_revision': detail['code_revision'],
        'target_revision': detail['target_revision'], 'plan': {
            'security_confirmed': True, 'database_confirmed': True, 'mapping_confirmed': True,
            'rationale': 'Required display field validation reviewed; no data writes.', 'keys': {}}})
    service.generation_code(sid, task['id'], {**detail['binding'], 'code_revision': detail['code_revision'],
        'target_revision': detail['target_revision'], 'state': 'approved', 'code_confirmed': True,
        'rationale': 'Reviewed against the current target plan.',
        'code': "BEGIN IF :P0_MESSAGE IS NULL THEN raise_application_error(-20001, 'Required'); END IF; END;"})
    detail = service.generation_module(sid)
    assert detail['ready'], detail['blockers']
    result = service.generate({**detail['binding'], 'scopes': [detail]})
    import io
    with zipfile.ZipFile(io.BytesIO(service.generation_download(result['artifact_id']))) as archive:
        pages = '\n'.join(archive.read(n).decode() for n in archive.namelist() if n.endswith('.apx'))
    assert 'plsqlCodeRaisingError' in pages
    assert ':P1_MESSAGE' in pages and ':P0_MESSAGE' not in pages


def test_existing_code_approval_is_nonapplicable_after_target_change(generation_project):
    service = generation_project
    sid, task, _, request = code_scope(service)
    service.generation_code(sid, task['id'], request)
    detail = service.generation_module(sid)
    current = service.generation_configure(sid, {**detail['binding'], 'code_revision': detail['code_revision'],
        'target_revision': detail['target_revision'], 'plan': {
            'security_confirmed': True, 'database_confirmed': True, 'mapping_confirmed': True,
            'rationale': 'Changed target assumptions.', 'keys': {}}})
    assert 'CODE_NEEDS_REVALIDATION' in {b['code'] for b in current['blockers']}
    assert service.generation_task(sid, task['id'])['history'][0]['state'] == 'approved'


def test_identical_legacy_reapproval_cannot_hide_lost_provenance(generation_project, monkeypatch):
    from formslang import store
    monkeypatch.setattr(store, '_now', lambda: '2026-09-21T03:00:00')
    service = generation_project
    sid, task, _, request = code_scope(service)
    service.generation_code(sid, task['id'], request)
    before = service.generation_module(sid)['code_revision']
    record = service._store.module_sessions()[0]
    session = store.Store(service._store.directory / record['relative_store'], reconcile_jobs=False)
    try:
        latest = session.latest_decision(task['id'])
        session.set_decision(task['id'], latest['state'], latest['code'], latest['comment'], latest['reviewer'])
    finally:
        session.close()
    assert service.generation_module(sid)['code_revision'] != before


def exercise_database_binding(generation_project, tmp_path, restriction, query_source='ORDERS'):
    source = tmp_path / 'forms/notice.xml'
    source.write_text(source.read_text().replace('DatabaseBlock="false"',
        'DatabaseBlock="true" QueryDataSourceName="ORDERS" QueryDataSourceType="Table"').replace('Name="MESSAGE" ItemType="Display Item"',
        'Name="ID" ItemType="Text Item" DatabaseItem="true"'), encoding='utf-8')
    if query_source != 'ORDERS':
        source.write_text(source.read_text().replace('QueryDataSourceName="ORDERS"',
            'QueryDataSourceName="' + query_source.replace('"', '&quot;') + '"'), encoding='utf-8')
    if restriction:
        source.write_text(source.read_text().replace('</Block>',
            f'<Item Name="LOCKED" ItemType="Text Item" DatabaseItem="true" {restriction}/></Block>'), encoding='utf-8')
        if 'CanvasName=' in restriction:
            source.write_text(source.read_text().replace('Name="ID" ItemType=', 'Name="ID" CanvasName="MAIN" ItemType=').replace(
                '</FormModule>', '<Canvas Name="MAIN" CanvasType="Content" Width="100" Height="100"/></FormModule>'), encoding='utf-8')
    database = tmp_path / 'database'
    database.mkdir()
    columns = 'id number primary key' + (', locked varchar2(30)' if restriction else '')
    (database / 'orders.sql').write_text(f'create table orders ({columns});', encoding='utf-8')
    service = ProjectService(local_project_access(tmp_path / 'db-project', approved_roots=(tmp_path,)))
    try:
        service.create('Synthetic reviewed data binding', roots=(SourceRoot('forms', 'forms', '../forms'),
                                                                SourceRoot('database', 'database', '../database')))
        service.analyze(expected_revision=None, expected_configuration=0)
        overview = service.generation_overview()
        sid = overview['modules'][0]['source_id']
        service.generation_prepare(sid, overview['binding'])
        for row in service.review_queue(limit=200)['rows']:
            detail = service.review_detail(row['id'])
            service.review_decide(row['id'], {**detail['binding'], 'action': 'MODIFY',
                'recommendation': 'PRESERVE', 'rationale': 'Observed synthetic ORDERS.ID table and simple binding reviewed.',
                'critical_confirmed': True})
        detail = service.generation_module(sid)
        detail = service.generation_configure(sid, {**detail['binding'], 'code_revision': detail['code_revision'],
            'target_revision': detail['target_revision'], 'plan': {
                'security_confirmed': True, 'database_confirmed': True, 'mapping_confirmed': True,
                'rationale': 'Observed ORDERS.ID primary key. Both create and update are allowed; no row predicate.',
                'keys': {'INFO': 'ID'}}})
        if query_source != 'ORDERS':
            assert not detail['ready'] and 'UNSUPPORTED_TABLE_IDENTITY' in {b['code'] for b in detail['blockers']}
            return
        if restriction:
            assert not detail['ready'] and 'UNSUPPORTED_ITEM_CONTROL' in {b['code'] for b in detail['blockers']}
            return
        assert detail['ready'], json.dumps({'blockers': detail['blockers'], 'questions': [
            {'id': f['id'], 'questions': f.get('unresolved_questions')} for f in service.assessment()['blueprint']['findings']
            if f['id'] in {b['id'] for b in detail['blockers']}]}, indent=2)
        artifact = service.generate({**detail['binding'], 'scopes': [detail]})
        assert service.generation_download(artifact['artifact_id'])
    finally:
        service.close()


@pytest.mark.parametrize('restriction', [None, 'UpdateAllowed="false"', 'InsertAllowed="false"',
    'QueryOnly="true"', 'Visible="false" Enabled="false"', 'InitializeValue=":GLOBAL.TENANT"',
    'MinimumValue="1"', 'HighestAllowedValue="100"', 'Visible="false" Required="true"',
    'Visible="false" InitializeValue="fixed"', 'Visible="false" MaximumLength="10"',
    'CanvasName="UNMAPPED" Enabled="false"'])
def test_observed_database_binding_requires_reviewed_key_and_dependencies(generation_project, tmp_path, restriction):
    exercise_database_binding(generation_project, tmp_path, restriction)


@pytest.mark.parametrize('query_source', ['"MixedCase"', 'ORDERS@REPORTING', 'UNOBSERVED'])
def test_generation_cannot_sanitize_an_unobserved_table_into_a_target(generation_project, tmp_path, query_source):
    exercise_database_binding(generation_project, tmp_path, None, query_source)
