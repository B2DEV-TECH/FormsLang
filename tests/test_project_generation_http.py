"""Real v2 generation routes use the same source-bound service."""

# ruff: noqa: F811 -- imported pytest fixtures are injected by name

import json
import urllib.request
from pathlib import Path
from urllib.parse import quote

from tests.test_project_generation import generation_project  # noqa: F401
from tests.test_project_http import (  # noqa: F401
    Client,
    authenticated_server,
    create_project,
    project_server,
)


def test_http_generation_workflow_and_foreign_artifact(project_server, generation_project):
    client, _ = project_server
    source = generation_project.access.source_roots[0] / 'forms'
    pid, _ = create_project(client, source)
    root = f'/api/v2/projects/{pid}'
    job = client.post(root + '/analyze', {'expected_revision': None, 'expected_configuration': 0})
    assert client.wait_job(pid, job.json['job_id'])['status'] == 'COMPLETED'
    first = client.get(root + '/generation')
    assert first.status == 200, first.json
    sid = first.json['modules'][0]['source_id']
    module = root + '/generation/modules/' + sid
    assert client.post(module + '/prepare', first.json['binding']).status == 200
    assert client.post(root + '/generation', {**first.json['binding'], 'scopes': []}).status == 400
    page = client.get(root + '/review').json
    from urllib.parse import quote
    for row in page['rows']:
        route = root + '/review/' + quote(row['id'], safe='')
        detail = client.get(route).json
        assert client.post(route, {**detail['binding'], 'action': 'APPROVE'}).status == 200
    detail = client.get(module).json
    request = {**detail['binding'], 'target_revision': detail['target_revision'],
               'code_revision': detail['code_revision'], 'plan': {
                   'security_confirmed': True, 'database_confirmed': True, 'mapping_confirmed': True,
                   'rationale': 'Synthetic display page; no writes.', 'keys': {}}}
    configured = client.post(module + '/plan', request)
    assert configured.status == 200, configured.json
    detail = configured.json
    generated = client.post(root + '/generation', {**detail['binding'], 'scopes': [detail]})
    assert generated.status == 201, generated.json
    artifact = generated.json
    with urllib.request.urlopen(client.base + root + '/artifacts/' + artifact['artifact_id'] + '/download') as response:
        assert response.headers['Content-Type'] == 'application/zip'
        assert response.read().startswith(b'PK')
    other, _ = create_project(client, source)
    assert client.get(f"/api/v2/projects/{other}/artifacts/{artifact['artifact_id']}/download").status == 404
    assert client.post(root + '/generation', {**detail['binding'], 'scopes': [detail]},
                       headers={'Origin': 'https://foreign.invalid'}).status == 403
    assert 'source_excerpt' not in json.dumps(first.json)


def test_authenticated_generation_rechecks_roles_csrf_and_revocation(authenticated_server, tmp_path):
    from formslang import authstore
    client, registry, owner, selected, _ = authenticated_server
    created = client.post('/api/v2/projects', {'name': 'Private generation', 'sources': [selected]})
    pid = created.json['project']['id']
    root = f'/api/v2/projects/{pid}'
    job = client.post(root + '/analyze', {'expected_revision': None, 'expected_configuration': 0})
    assert client.wait_job(pid, job.json['job_id'])['status'] == 'COMPLETED'
    overview = client.get(root + '/generation')
    assert overview.status == 200 and str(tmp_path) not in json.dumps(overview.json)
    sid = overview.json['modules'][0]['source_id']
    module = root + '/generation/modules/' + sid
    assert client.post(module + '/prepare', overview.json['binding'], headers={'X-CSRF-Token': ''}).status == 403
    assert client.post(module + '/prepare', overview.json['binding']).status == 200
    assert client.post(root + '/generation', {**overview.json['binding'], 'scopes': []}).status == 400
    assert client.post(module + '/code/unknown', overview.json['binding']).status == 409  # code fence required
    viewer = registry.create_user('generation-viewer@example.test', 'correct horse battery staple')
    registry.create_membership(owner['organization_id'], viewer, authstore.VIEWER)
    token, session = registry.create_session(viewer, owner['organization_id'])
    observer = Client(client.base, {'Cookie': f'formslang_session={token}',
        'X-CSRF-Token': session['csrf_secret'], 'Origin': client.base})
    artifact = root + '/artifacts/' + 'a' * 32 + '/download'
    assert observer.get(root + '/generation').status == 200
    assert observer.get(artifact).status == 403
    assert observer.post(module + '/code/unknown', {}).status == 403
    registry.grant_project_permission(pid, viewer, 'EXPORT', granted_by=owner['user_id'])
    assert observer.get(artifact).status == 404  # authorized, but never existed
    foreign_org = registry.create_organization('generation-foreign', 'Foreign')
    registry.create_membership(foreign_org, viewer, authstore.DEVELOPER)
    foreign_token, foreign_session = registry.create_session(viewer, foreign_org)
    foreign = Client(client.base, {'Cookie': f'formslang_session={foreign_token}',
        'X-CSRF-Token': foreign_session['csrf_secret'], 'Origin': client.base})
    assert foreign.get(root + '/generation').status == 404
    assert foreign.get(artifact).status == 404
    registry.db.execute('DELETE FROM membership WHERE user_id=? AND org_id=?',
                        (viewer, owner['organization_id']))
    assert observer.get(artifact).status == 401
    assert observer.post(module + '/code/unknown', {}).status == 401


def test_authenticated_generation_code_and_download_roundtrip(authenticated_server, project_sources):
    client, _, _, selected, _ = authenticated_server
    xml = Path('tests/fixtures/project-generation/notice.xml').read_text(encoding='utf-8')
    project_sources[2].write_text(xml, encoding='utf-8')
    created = client.post('/api/v2/projects', {'name': 'Authenticated generation', 'sources': [selected]})
    pid = created.json['project']['id']
    root = f'/api/v2/projects/{pid}'
    job = client.post(root + '/analyze', {'expected_revision': None, 'expected_configuration': 0})
    assert client.wait_job(pid, job.json['job_id'])['status'] == 'COMPLETED'
    initial = client.get(root + '/generation').json
    module = root + '/generation/modules/' + initial['modules'][0]['source_id']
    assert client.post(module + '/prepare', initial['binding']).status == 200
    for row in client.get(root + '/review').json['rows']:
        route = root + '/review/' + quote(row['id'], safe='')
        finding = client.get(route).json
        assert client.post(route, {**finding['binding'], 'action': 'APPROVE'}).status == 200
    detail = client.get(module).json
    configured = client.post(module + '/plan', {**detail['binding'],
        'code_revision': detail['code_revision'], 'target_revision': detail['target_revision'],
        'plan': {'security_confirmed': True, 'database_confirmed': True, 'mapping_confirmed': True,
                 'rationale': 'Synthetic validation, no database writes.', 'keys': {}}})
    assert configured.status == 200, configured.json
    detail = configured.json
    task = detail['tasks'][0]
    approved = client.post(module + '/code/' + quote(task['id'], safe=''), {**detail['binding'],
        'code_revision': detail['code_revision'], 'target_revision': detail['target_revision'],
        'state': 'approved', 'code_confirmed': True, 'rationale': 'Reviewed current validation.',
        'code': "BEGIN IF :P0_MESSAGE IS NULL THEN raise_application_error(-20001, 'Required'); END IF; END;"})
    assert approved.status == 200, approved.json
    detail = client.get(module).json
    generated = client.post(root + '/generation', {**detail['binding'], 'scopes': [detail]})
    assert generated.status == 201, generated.json
    request = urllib.request.Request(client.base + root + '/artifacts/' + generated.json['artifact_id'] + '/download',
                                     headers=client.headers)
    with urllib.request.urlopen(request) as response:
        assert response.read().startswith(b'PK')
