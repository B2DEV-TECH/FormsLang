"""Project v2 routes run through real loopback guards, services and worker jobs."""

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from urllib.parse import quote

import pytest

from formslang import authstore, config, rbac
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


def analyze_demo(client):
    created = client.post('/api/v2/projects/demo', {})
    assert created.status == 201, created.json
    project_id = created.json['project']['id']
    job = client.post(f'/api/v2/projects/{project_id}/analyze', {
        'expected_revision': None, 'expected_configuration': 0,
    })
    assert job.status == 202, job.json
    assert client.wait_job(project_id, job.json['job_id'])['status'] == 'COMPLETED'
    return project_id


def test_onboarding_exposes_backend_target_profile(project_server):
    client, _ = project_server
    response = client.get('/api/v2/source-areas')
    assert response.status == 200
    assert response.json['target_profile'] == {'platform': 'Oracle APEX', 'version': '26.1', 'representation': 'APEXlang'}


def test_review_http_decision_conflict_and_annotation(project_server):
    client, _ = project_server
    pid = analyze_demo(client)
    route = f'/api/v2/projects/{pid}/review'
    page = client.get(route + '?limit=1')
    assert page.status == 200, page.json
    assert len(page.json['rows']) == 1
    finding = page.json['rows'][0]['id']
    detail = client.get(route + '/' + quote(finding, safe=''))
    assert detail.status == 200, detail.json
    request = {**detail.json['binding'], 'action': 'APPROVE'}
    assert client.post(route + '/' + quote(finding, safe=''), request).status == 200
    assert client.post(route + '/' + quote(finding, safe=''), request).status == 409
    current = client.get(route + '/' + quote(finding, safe=''))
    annotation = {**current.json['binding'], 'operation': 'ANNOTATE',
                  'kind': 'CONFIRMED_BUSINESS_RULE', 'note': '<script>private</script>'}
    assert client.post(route + '/' + quote(finding, safe=''), annotation).status == 200
    page = client.get(route)
    assert 'private' not in json.dumps(page.json)
    assert client.get(route + '?limit=201').status == 400
    assert client.get(route + '?review_revision=0').status == 409
    assert client.get(route + '/foreign-finding').status == 404


def test_demo_endpoint_uses_normal_analysis_route(project_server):
    client, _ = project_server
    created = client.post('/api/v2/projects/demo', {})
    assert created.status == 201
    pid = created.json['project']['id']
    job = client.post(f'/api/v2/projects/{pid}/analyze', {'expected_revision': None, 'expected_configuration': 0})
    assert job.status == 202
    assert client.wait_job(pid, job.json['job_id'])['status'] == 'COMPLETED'
    saved = client.get(f'/api/v2/projects/{pid}/assessment').json['assessment']
    assert saved['inventory']['forms']['analyzed'] == 2


def test_cli_and_http_produce_same_revision(project_server, project_sources, capsys):
    from formslang.cli import main

    client, _ = project_server
    _, _, xml = project_sources
    pid, _ = create_project(client, xml.parent)
    response = client.post(f'/api/v2/projects/{pid}/analyze', {
        'expected_revision': None, 'expected_configuration': 0})
    assert response.status == 202
    first = client.wait_job(pid, response.json['job_id'])
    assert first['status'] == 'COMPLETED'
    saved = client.get(f'/api/v2/projects/{pid}/assessment').json['assessment']
    destination = config.data_dir() / 'projects'
    locators = list(destination.glob('*/.formslang/project.json'))
    assert len(locators) == 1
    capsys.readouterr()
    assert main(['project', 'analyze', str(locators[0]), '--json']) == 0
    second = json.loads(capsys.readouterr().out)
    assert second['analysis_revision'] == saved['analysis_revision']
    assert client.get(f'/api/v2/projects/{pid}/assessment').json['assessment']['analyzed_at'] == saved['analyzed_at']


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


def test_a_finished_job_has_released_the_project_before_it_reports_done(project_server, project_sources, monkeypatch):
    # A client that sees the job finish must be able to start the next locked
    # operation; the worker still holds the lock between finish() and return.
    from formslang import project_jobs
    client, _ = project_server
    pid, _ = create_project(client, project_sources[2].parent)
    job = client.post(f'/api/v2/projects/{pid}/analyze', {'expected_revision': None, 'expected_configuration': 0})
    assert client.wait_job(pid, job.json['job_id'])['status'] == 'COMPLETED'
    finished, release = threading.Event(), threading.Event()
    finish = project_jobs.JobLease.finish
    def held(self, status, *a, **k):
        finish(self, status, *a, **k)
        if status == 'COMPLETED':
            finished.set()
            assert release.wait(10)
    monkeypatch.setattr(project_jobs.JobLease, 'finish', held)
    fresh = client.post(f'/api/v2/projects/{pid}/freshness', {})
    assert finished.wait(10)
    seen, done = {}, threading.Event()
    def poll_then_report():
        seen['job'] = client.get(f'/api/v2/projects/{pid}/jobs/{fresh.json["job_id"]}').json['status']
        seen['reports'] = client.get(f'/api/v2/projects/{pid}/reports').status
        done.set()
    poller = threading.Thread(target=poll_then_report)
    poller.start()
    # The status request must not answer while the worker still holds the lock.
    assert not done.wait(1)
    release.set()
    poller.join(10)
    assert seen == {'job': 'COMPLETED', 'reports': 200}


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
    review = client.get(f'/api/v2/projects/{pid}/review?limit=1')
    assert review.status == 200, review.json
    finding_id = quote(review.json['rows'][0]['id'], safe='')
    detail = client.get(f'/api/v2/projects/{pid}/review/{finding_id}')
    assert detail.status == 200 and str(tmp_path) not in json.dumps(detail.json)
    command = {**detail.json['binding'], 'action': 'DEFER'}
    assert client.post(f'/api/v2/projects/{pid}/review/{finding_id}', command,
                       headers={'X-CSRF-Token': ''}).status == 403
    assert client.post(f'/api/v2/projects/{pid}/review/{finding_id}', command).status == 200
    reviewed = client.get(f'/api/v2/projects/{pid}/review/{finding_id}')
    assert owner['user_id'] not in json.dumps(reviewed.json)
    assert client.post(f'/api/v2/projects/{pid}/freshness', {}, headers={'X-CSRF-Token': ''}).status == 403
    registry.db.execute('DELETE FROM membership WHERE user_id=?', (owner['user_id'],))
    assert client.get(f'/api/v2/projects/{pid}').status == 401
    assert client.get(f'/api/v2/projects/{pid}/review').status == 401
    assert client.post(f'/api/v2/projects/{pid}/review/{finding_id}', command).status == 401


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
    assert observer.post(f'/api/v2/projects/{pid}/review/foreign', {}).status == 403
    org = registry.create_organization('foreign', 'Foreign')
    registry.create_membership(org, viewer, authstore.DEVELOPER)
    token, session = registry.create_session(viewer, org)
    foreign = Client(client.base, {'Cookie': f'formslang_session={token}', 'X-CSRF-Token': session['csrf_secret'], 'Origin': client.base})
    assert foreign.get('/api/v2/projects').json['projects'] == []
    assert foreign.get(f'/api/v2/projects/{pid}').status == 404
    assert foreign.get(f'/api/v2/projects/{pid}/review').status == 404
    assert foreign.post(f'/api/v2/projects/{pid}/analyze', {'expected_revision': None, 'expected_configuration': 0}).status == 404


def test_overview_is_empty_before_analysis_and_real_afterward(project_server):
    client, _ = project_server
    created = client.post('/api/v2/projects/demo', {})
    pid = created.json['project']['id']

    empty = client.get(f'/api/v2/projects/{pid}/overview')
    assert empty.status == 200 and empty.json == {'overview': None}

    job = client.post(f'/api/v2/projects/{pid}/analyze', {
        'expected_revision': None, 'expected_configuration': 0,
    })
    assert client.wait_job(pid, job.json['job_id'])['status'] == 'COMPLETED'
    response = client.get(f'/api/v2/projects/{pid}/overview')

    assert response.status == 200
    result = response.json['overview']
    assert result['inventory']['forms_modules'] == 2
    assert result['inventory']['modernization_findings'] == sum(
        result['risk_distribution'].values()
    )
    assert result['assessment']['analysis_revision']
    assert 'source_text' not in json.dumps(response.json)
    assert str(config.data_dir()) not in json.dumps(response.json)


def test_inventory_http_filters_pages_details_and_rejects_revision_mix(project_server):
    client, _ = project_server
    pid = analyze_demo(client)
    overview = client.get(f'/api/v2/projects/{pid}/overview').json['overview']
    revision = overview['assessment']['analysis_revision']

    page = client.get(
        f'/api/v2/projects/{pid}/inventory?category=findings&risk=CRITICAL&limit=50'
        f'&revision={revision}'
    )
    assert page.status == 200, page.json
    assert page.json['category'] == 'findings'
    assert page.json['total'] >= 1
    assert all(row['risk'] == 'CRITICAL' for row in page.json['rows'])
    item_id = page.json['rows'][0]['id']
    detail = client.get(
        f'/api/v2/projects/{pid}/inventory/findings/{item_id}?revision={revision}'
    )
    assert detail.status == 200 and detail.json['item']['id'] == item_id
    assert 'source_text' not in json.dumps(detail.json)
    assert client.get(
        f'/api/v2/projects/{pid}/inventory?category=findings&limit=201'
    ).status == 400
    conflict = client.get(
        f'/api/v2/projects/{pid}/inventory?category=findings&offset=1'
        f'&revision={"0" * 64}'
    )
    assert conflict.status == 409 and conflict.json['code'] == 'PROJECT_CONFLICT'


def test_inventory_detail_accepts_opaque_percent_encoded_engine_identity(project_server):
    client, _ = project_server
    pid = analyze_demo(client)
    overview = client.get(f'/api/v2/projects/{pid}/overview').json['overview']
    revision = overview['assessment']['analysis_revision']
    page = client.get(
        f'/api/v2/projects/{pid}/inventory?category=findings&limit=50&revision={revision}'
    )
    item_id = next(row['id'] for row in page.json['rows'] if ':' in row['id'])

    detail = client.get(
        f'/api/v2/projects/{pid}/inventory/findings/{quote(item_id, safe="")}'
        f'?revision={revision}'
    )

    assert detail.status == 200
    assert detail.json['item']['id'] == item_id


def test_overview_keeps_saved_metrics_and_reports_stale_source(project_server):
    client, workbench = project_server
    pid = analyze_demo(client)
    before = client.get(f'/api/v2/projects/{pid}/overview').json['overview']
    intake = workbench.project_api._intake(None)
    access = intake.access(pid, rbac.VIEW_PROJECT)
    service = ProjectService(access)
    try:
        descriptor = service.open()
        forms_root = next(root for root in descriptor.source_roots if root.kind == 'forms')
        source = next((access.root / forms_root.path).glob('*.xml'))
    finally:
        service.close()
    source.write_bytes(source.read_bytes() + b'\n<!-- stale -->\n')
    job = client.post(f'/api/v2/projects/{pid}/freshness', {})
    assert client.wait_job(pid, job.json['job_id'])['status'] == 'COMPLETED_WITH_WARNINGS'

    after = client.get(f'/api/v2/projects/{pid}/overview').json['overview']

    assert after['assessment']['freshness'] == 'STALE'
    assert after['inventory'] == before['inventory']
    assert after['warnings'][0]['code'] == 'ASSESSMENT_STALE'


def test_cli_summary_and_inventory_reconcile_with_http(project_server, capsys):
    from formslang.cli import main

    client, _ = project_server
    pid = analyze_demo(client)
    descriptor = next((config.data_dir() / 'projects').glob('*/.formslang/project.json'))

    assert main(['project', 'summary', str(descriptor), '--json']) == 0
    cli_summary = json.loads(capsys.readouterr().out)
    http_summary = client.get(f'/api/v2/projects/{pid}/overview').json['overview']
    assert cli_summary == http_summary

    revision = cli_summary['assessment']['analysis_revision']
    assert main([
        'project', 'inventory', str(descriptor), '--category', 'findings',
        '--risk', 'HIGH', '--revision', revision, '--json',
    ]) == 0
    cli_inventory = json.loads(capsys.readouterr().out)
    http_inventory = client.get(
        f'/api/v2/projects/{pid}/inventory?category=findings&risk=HIGH&revision={revision}'
    ).json
    assert cli_inventory == http_inventory


def test_system_map_and_search_http_endpoints(project_server):
    client, _ = project_server
    pid = analyze_demo(client)

    # Test system-map endpoint
    map_res = client.get(f'/api/v2/projects/{pid}/system-map')
    assert map_res.status == 200, map_res.json
    assert 'nodes' in map_res.json
    assert 'edges' in map_res.json
    assert 'available_forms' in map_res.json
    assert map_res.json['total_nodes'] > 0

    # Test system-map with depth and layer filters
    map_filtered = client.get(f'/api/v2/projects/{pid}/system-map?depth=1&layer=FORM')
    assert map_filtered.status == 200
    assert map_filtered.json['depth'] == 1

    # Test system-map invalid parameter
    bad_map = client.get(f'/api/v2/projects/{pid}/system-map?depth=not_an_int')
    assert bad_map.status == 400

    # 2.2: the estate view lays out every lane, and a node has a bounded drawer detail
    estate = client.get(f'/api/v2/projects/{pid}/system-map?view=estate')
    assert estate.status == 200, estate.json
    assert estate.json['view'] == 'ESTATE' and estate.json['layout']['mode'] == 'ESTATE'
    assert set(estate.json['layout']['positions']) == {n['id'] for n in estate.json['nodes']}
    assert client.get(f'/api/v2/projects/{pid}/system-map?view=galaxy').status == 400
    focus = estate.json['nodes'][0]['id']
    detail = client.get(f'/api/v2/projects/{pid}/system-map/node?id={quote(focus, safe="")}')
    assert detail.status == 200, detail.json
    assert detail.json['node']['id'] == focus
    assert client.get(f'/api/v2/projects/{pid}/system-map/node?id=nope').status == 400
    assert client.get(f'/api/v2/projects/{pid}/system-map/node?id=x&extra=1').status == 400
    visual = client.get(f'/api/v2/projects/{pid}/overview/visual')
    assert visual.status == 200, visual.json
    assert [lane['lane'] for lane in visual.json['visual']['estate']] == [
        'APPLICATION', 'SHARED_LOGIC', 'DATA', 'INTEGRATION']

    # Test search endpoint
    search_res = client.get(f'/api/v2/projects/{pid}/search?query=shipments')
    assert search_res.status == 200, search_res.json
    assert 'results' in search_res.json
    assert search_res.json['total'] > 0
    assert any('shipments' in r['title'].casefold() for r in search_res.json['results'])

    # Test search invalid limit
    bad_search = client.get(f'/api/v2/projects/{pid}/search?limit=not_an_int')
    assert bad_search.status == 400
