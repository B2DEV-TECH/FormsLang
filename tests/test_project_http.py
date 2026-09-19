"""Project v2 routes run through real loopback guards, services and worker jobs."""

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import ThreadingHTTPServer

import pytest

from formslang import authstore, config
from formslang.ai import EchoProvider
from formslang.project_service import ProjectService
from formslang.store import Store
from formslang.workbench import Handler, Workbench


@dataclass
class Response:
    status: int
    json: dict


class Client:
    def __init__(self, base, headers=None):
        self.base, self.headers = base, headers or {}

    def request(self, method, path, body=None, headers=None, raw=None):
        data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method,
            headers={'Content-Type': 'application/json', **self.headers, **(headers or {})})
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return Response(response.status, json.loads(response.read()))

    def get(self, path, **kwargs):
        return self.request('GET', path, **kwargs)

    def post(self, path, body, **kwargs):
        return self.request('POST', path, body, **kwargs)

    def wait_job(self, pid, job_id):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            response = self.get(f'/api/v2/projects/{pid}/jobs/{job_id}')
            assert response.status == 200, response.json
            if response.json['status'] not in {'QUEUED', 'RUNNING'}:
                return response.json
            time.sleep(.02)
        pytest.fail('project job did not finish')


@pytest.fixture
def project_server(tmp_path, monkeypatch):
    monkeypatch.setenv('FORMSLANG_DATA_DIR', str(tmp_path / 'data'))
    store = Store(tmp_path / 'shell.db')
    wb = Workbench(store, EchoProvider(), tmp_path / 'export', browse_root=tmp_path)
    handler = type('ProjectHandler', (Handler,), {'workbench': wb})
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    client = Client(f'http://127.0.0.1:{httpd.server_port}')
    try:
        yield client, wb
    finally:
        httpd.shutdown()
        httpd.server_close()
        if hasattr(wb, 'project_api'):
            wb.project_api.close()
        store.close()


def create_project(client, source):
    selection = client.post('/api/v2/source-selections', {'path': str(source), 'kind': 'forms'})
    assert selection.status == 200, selection.json
    selected = selection.json['selection']
    preview = client.post('/api/v2/discovery-preview', {'sources': [selected]})
    assert preview.status == 200 and preview.json['inventory']['forms']['parseable'] == 1
    created = client.post('/api/v2/projects', {'name': 'Orders', 'sources': [selected]})
    assert created.status == 201, created.json
    return created.json['project']['id'], selected


def test_analysis_is_accepted_then_persisted(project_server, project_sources):
    client, _ = project_server
    pid, _ = create_project(client, project_sources[2].parent)
    job = client.post(f'/api/v2/projects/{pid}/analyze', {'expected_revision': None, 'expected_configuration': 0})
    assert job.status == 202, job.json
    result = client.wait_job(pid, job.json['job_id'])
    assert result['status'] == 'COMPLETED'
    assessment = client.get(f'/api/v2/projects/{pid}/assessment')
    assert assessment.status == 200 and assessment.json['assessment']['inventory']['forms']['analyzed'] == 1
    recent = client.get('/api/v2/projects')
    assert recent.json['projects'][0]['project']['id'] == pid


def test_preview_pagination_browse_and_source_authority(project_server, project_sources):
    client, _ = project_server
    pid, selected = create_project(client, project_sources[2].parent)
    area = selected['area_id']
    assert client.get(f'/api/v2/source-areas/{area}/browse').status == 200
    assert client.get(f'/api/v2/source-areas/{area}/browse?relative=../private').status == 400
    assert client.get('/api/v2/source-areas').status == 200
    assert client.post('/api/v2/discovery-preview', {'sources': [selected], 'limit': 201}).status == 400
    discovered = client.post(f'/api/v2/projects/{pid}/discover', {'expected_revision': None, 'expected_configuration': 0})
    assert discovered.status == 200
    assert client.get(f'/api/v2/projects/{pid}/discovery?limit=1').json['total'] == 1
    assert client.get(f'/api/v2/projects/{pid}/discovery?limit=0').status == 400


@pytest.mark.parametrize('value', [True, 1.5, 10**100])
def test_preview_rejects_noninteger_or_unbounded_pagination(project_server, project_sources, value):
    client, _ = project_server
    selected = client.post('/api/v2/source-selections', {'path': str(project_sources[2].parent), 'kind': 'forms'}).json['selection']
    response = client.post('/api/v2/discovery-preview', {'sources': [selected], 'offset': value})
    assert response.status == 400


def test_local_v2_rejects_foreign_origin_host_and_bad_json(project_server):
    client, _ = project_server
    path = '/api/v2/projects'
    assert client.post(path, {}, headers={'Origin': 'https://evil.example'}).status == 403
    assert client.post(path, {}, headers={'Host': 'evil.example'}).status == 403
    assert client.request('POST', path, raw=b'{broken').status == 400


def test_malformed_origin_is_rejected_without_dropping_connection(project_server):
    client, _ = project_server
    assert client.post('/api/v2/projects', {}, headers={'Origin': 'http://[invalid'}).status == 403


def test_revision_conflict_and_foreign_jobs(project_server, project_sources):
    client, _ = project_server
    pid, _ = create_project(client, project_sources[2].parent)
    wrong = client.post(f'/api/v2/projects/{pid}/analyze', {'expected_revision': None, 'expected_configuration': 9})
    assert wrong.status == 409, wrong.json
    assert client.get(f'/api/v2/projects/{pid}/jobs/' + 'b' * 32).status == 404
    assert client.get('/api/v2/projects/' + 'c' * 32).status == 404


def test_saved_assessment_freshness_and_relink_routes(project_server, project_sources):
    client, _ = project_server
    pid, selected = create_project(client, project_sources[2].parent)
    job = client.post(f'/api/v2/projects/{pid}/analyze', {'expected_revision': None, 'expected_configuration': 0})
    assert client.wait_job(pid, job.json['job_id'])['status'] == 'COMPLETED'
    saved = client.get(f'/api/v2/projects/{pid}/assessment').json['assessment']
    fresh = client.post(f'/api/v2/projects/{pid}/freshness', {})
    assert fresh.status == 202
    client.wait_job(pid, fresh.json['job_id'])
    assert client.get(f'/api/v2/projects/{pid}/freshness').json['status'] == 'CURRENT'
    summary = client.get(f'/api/v2/projects/{pid}')
    assert summary.json['freshness']['status'] == 'CURRENT'
    source = project_sources[2]
    source.write_bytes(source.read_bytes() + b'\n')
    check = client.post(f'/api/v2/projects/{pid}/freshness', {})
    client.wait_job(pid, check.json['job_id'])
    assert client.get(f'/api/v2/projects/{pid}/freshness').json['status'] == 'STALE'
    assert client.get(f'/api/v2/projects/{pid}/assessment').json['assessment']['analyzed_at'] == saved['analyzed_at']
    relink = client.post(f'/api/v2/projects/{pid}/relink', {'root_id': selected['root_id'],
        'selection': selected, 'expected_configuration': 0})
    assert relink.status == 200
    assert client.post(f'/api/v2/projects/{pid}/relink', {'root_id': selected['root_id'],
        'selection': selected, 'expected_configuration': 0}).status == 409


def test_running_job_progress_cancel_and_project_switch_are_scoped(project_server, project_sources, monkeypatch):
    from formslang import project_analysis
    client, _ = project_server
    first, _ = create_project(client, project_sources[2].parent)
    second, _ = create_project(client, project_sources[2].parent)
    entered, release = threading.Event(), threading.Event()
    build = project_analysis.blueprint.build
    def blocked(*a, **k):
        entered.set()
        assert release.wait(10)
        return build(*a, **k)
    monkeypatch.setattr(project_analysis.blueprint, 'build', blocked)
    job = client.post(f'/api/v2/projects/{first}/analyze', {'expected_revision': None, 'expected_configuration': 0})
    assert job.status == 202
    try:
        assert entered.wait(10)
        state = client.get(f'/api/v2/projects/{first}/jobs/{job.json["job_id"]}')
        assert state.json['status'] == 'RUNNING' and state.json['phase'] == 'BLUEPRINT'
        assert client.get(f'/api/v2/projects/{second}/jobs/{job.json["job_id"]}').status == 404
        assert client.post(f'/api/v2/projects/{second}/jobs/{job.json["job_id"]}/cancel', {}).status == 404
        assert client.post(f'/api/v2/projects/{first}/analyze', {'expected_revision': None, 'expected_configuration': 0}).status == 409
        assert client.post(f'/api/v2/projects/{first}/jobs/{job.json["job_id"]}/cancel', {}).status == 200
    finally:
        release.set()
    assert client.wait_job(first, job.json['job_id'])['status'] == 'CANCELLED'
    assert client.get(f'/api/v2/projects/{first}/assessment').json['assessment'] is None
    assert client.get(f'/api/v2/projects/{second}/assessment').json['assessment'] is None


def test_unknown_server_error_is_sanitized(project_server, project_sources, monkeypatch):
    client, _ = project_server
    pid, _ = create_project(client, project_sources[2].parent)
    def fail(*a, **k):
        raise RuntimeError('secret source and private credentials')
    monkeypatch.setattr(ProjectService, 'assessment', fail)
    result = client.get(f'/api/v2/projects/{pid}/assessment')
    assert result.status == 500 and result.json['correlation_id']
    assert 'secret' not in str(result.json) and 'credentials' not in str(result.json)


@pytest.fixture
def authenticated_server(project_server, project_sources, tmp_path, monkeypatch):
    client, wb = project_server
    registry = authstore.AuthStore(tmp_path / 'separate-auth.db')
    owner = registry.bootstrap_owner('owner@example.test', 'correct horse battery staple')
    token, session = registry.create_session(owner['user_id'], owner['organization_id'])
    wb.auth_store, wb.auth_data_dir = registry, tmp_path / 'managed-data'
    monkeypatch.setenv('FORMSLANG_AUTH', '1')
    directory = config.config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'project-source-areas.json').write_text(json.dumps({'organizations': {
        owner['organization_id']: {'approved': str(project_sources[2].parent)}}}))
    client.headers = {'Cookie': f'formslang_session={token}', 'X-CSRF-Token': session['csrf_secret'], 'Origin': client.base}
    selected = {'root_id': 'forms', 'kind': 'forms', 'area_id': 'approved', 'relative_path': ''}
    try:
        yield client, registry, owner, selected, token
    finally:
        registry.close()


def test_authenticated_project_routes_preserve_boundaries(authenticated_server, tmp_path):
    client, registry, owner, selected, _ = authenticated_server
    assert client.get('/api/v2/source-areas').json['areas'] == [{'id': 'approved', 'name': 'approved'}]
    assert client.post('/api/v2/source-selections', {'path': str(tmp_path), 'kind': 'forms'}).status == 403
    assert client.post('/api/v2/discovery-preview', {'sources': [selected]}).status == 200
    created = client.post('/api/v2/projects', {'name': 'Tenant', 'sources': [selected]})
    assert created.status == 201, created.json
    assert str(tmp_path) not in json.dumps(created.json)
    pid = created.json['project']['id']
    job = client.post(f'/api/v2/projects/{pid}/analyze', {'expected_revision': None, 'expected_configuration': 0})
    assert job.status == 202
    assert client.wait_job(pid, job.json['job_id'])['status'] == 'COMPLETED'
    assert str(tmp_path) not in json.dumps(client.get(f'/api/v2/projects/{pid}/assessment').json)
    assert client.post(f'/api/v2/projects/{pid}/freshness', {}, headers={'X-CSRF-Token': ''}).status == 403
    registry.db.execute('DELETE FROM membership WHERE user_id=?', (owner['user_id'],))
    assert client.get(f'/api/v2/projects/{pid}').status == 401


def test_mfa_scoped_session_cannot_reach_v2(authenticated_server):
    client, registry, owner, selected, _ = authenticated_server
    registry.db.execute("UPDATE session_token SET scope='MFA_PENDING' WHERE user_id=?", (owner['user_id'],))
    assert client.get('/api/v2/projects').status == 403
    assert client.post('/api/v2/projects', {'name': 'Forbidden', 'sources': [selected]}).status == 403


def test_empty_source_path_is_not_implicit_cwd_authority(project_server):
    client, _ = project_server
    assert client.post('/api/v2/source-selections', {'path': '', 'kind': 'forms'}).status == 400
    assert client.get('/api/v2/source-areas').json['areas'] == []


def test_open_locator_and_explicit_conversion_route(project_server, project_sources, monkeypatch):
    from formslang import oracle, rbac
    from formslang.project_manifest import source_id
    client, wb = project_server
    pid, selected = create_project(client, project_sources[2].parent)
    root = wb.project_api._intake(None).access(pid, rbac.VIEW_PROJECT).root
    opened = client.post('/api/v2/projects/open', {'locator': str(root / '.formslang/project.json')})
    assert opened.status == 200 and opened.json['project']['id'] == pid
    (project_sources[2].parent / 'extra.fmb').write_bytes(b'synthetic binary')
    sid = source_id(selected['root_id'], 'extra.fmb')
    def absent():
        raise oracle.OracleToolchainError('not installed')
    monkeypatch.setattr(oracle, 'detect_toolchain', absent)
    assert client.post(f'/api/v2/projects/{pid}/convert', {'source_id': sid, 'expected_configuration': 0}).status == 400
    result = client.post(f'/api/v2/projects/{pid}/convert', {'source_id': sid, 'expected_configuration': 0, 'confirmed': True})
    assert result.status == 200 and result.json['safe_failure']['error_code'] == 'FORMS2XML_UNAVAILABLE'


def test_http_foreign_project_hidden_and_viewer_mutation_denied(authenticated_server):
    client, registry, owner, selected, _ = authenticated_server
    pid = client.post('/api/v2/projects', {'name': 'Private', 'sources': [selected]}).json['project']['id']
    viewer = registry.create_user('viewer@example.test', 'correct horse battery staple')
    registry.create_membership(owner['organization_id'], viewer, authstore.VIEWER)
    token, session = registry.create_session(viewer, owner['organization_id'])
    observer = Client(client.base, {'Cookie': f'formslang_session={token}', 'X-CSRF-Token': session['csrf_secret'], 'Origin': client.base})
    assert observer.get(f'/api/v2/projects/{pid}').status == 200
    assert observer.post(f'/api/v2/projects/{pid}/analyze', {'expected_revision': None, 'expected_configuration': 0}).status == 403
    org = registry.create_organization('foreign', 'Foreign')
    registry.create_membership(org, viewer, authstore.DEVELOPER)
    token, session = registry.create_session(viewer, org)
    foreign = Client(client.base, {'Cookie': f'formslang_session={token}', 'X-CSRF-Token': session['csrf_secret'], 'Origin': client.base})
    assert foreign.get('/api/v2/projects').json['projects'] == []
    assert foreign.get(f'/api/v2/projects/{pid}').status == 404
    assert foreign.post(f'/api/v2/projects/{pid}/analyze', {'expected_revision': None, 'expected_configuration': 0}).status == 404
