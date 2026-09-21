"""Authenticated attachment routes share the project snapshot service."""

# ruff: noqa: F811 -- imported pytest fixtures

import json
import urllib.request
from urllib.parse import urlencode

from tests.test_project_http import authenticated_server, project_server  # noqa: F401


def test_report_attachment_authorization_and_revision(authenticated_server):
    from formslang import authstore
    from tests.test_project_http import Client
    client, registry, owner, selected, _ = authenticated_server
    created = client.post('/api/v2/projects', {'name': 'Report <script>hostile()</script>', 'sources': [selected]})
    pid = created.json['project']['id']
    root = f'/api/v2/projects/{pid}'
    assert client.get(root + '/reports').status == 400
    job = client.post(root + '/analyze', {'expected_revision': None, 'expected_configuration': 0})
    client.wait_job(pid, job.json['job_id'])
    state = client.get(root + '/reports')
    assert state.status == 200, state.json
    route = root + '/reports/executive?' + urlencode(state.json['binding'])
    with urllib.request.urlopen(urllib.request.Request(client.base + route, headers=client.headers)) as response:
        assert response.headers['Content-Type'].startswith('text/html')
        assert response.headers['Content-Disposition'] == 'attachment; filename="executive-summary.html"'
        content = response.read().decode()
        assert '<script>hostile()' not in content and '&lt;script&gt;' in content
    viewer = registry.create_user('reports-viewer@example.test', 'correct horse battery staple')
    registry.create_membership(owner['organization_id'], viewer, authstore.VIEWER)
    token, session = registry.create_session(viewer, owner['organization_id'])
    observer = Client(client.base, {'Cookie': f'formslang_session={token}', 'X-CSRF-Token': session['csrf_secret']})
    assert observer.get(root + '/reports').status == 200
    assert observer.get(route).status == 403
    registry.grant_project_permission(pid, viewer, 'EXPORT', granted_by=owner['user_id'])
    # JSON attachment is parseable through the normal test client.
    json_route = root + '/reports/decisions?' + urlencode(state.json['binding'])
    assert observer.get(json_route).status == 200
    assert 'user_id' not in json.dumps(observer.get(json_route).json)
    bad = {**state.json['binding'], 'review_revision': -1}
    assert client.get(root + '/reports/decisions?' + urlencode(bad)).status in {400, 409}
    assert client.get(json_route + '&include_notes=maybe').status == 400
    registry.db.execute('DELETE FROM membership WHERE user_id=?', (viewer,))
    assert observer.get(json_route).status == 401
