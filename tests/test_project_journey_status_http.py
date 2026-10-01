"""WP-39a journey over HTTP and the CLI: same service, same payload."""

# ruff: noqa: F811 -- imported pytest fixtures are injected by name

import json

from formslang import config
from formslang.cli import main
from tests.test_project_http import analyze_demo, project_server  # noqa: F401


def test_http_journey_without_a_saved_source_check_asks_for_one(project_server):
    client, _ = project_server
    pid = analyze_demo(client)
    response = client.get(f'/api/v2/projects/{pid}/journey')
    assert response.status == 200, response.json
    body = response.json
    assert body['schema'] == 'formslang-journey/1'
    assert body['freshness']['status'] == 'UNVERIFIED'
    assert body['focus'] == 'UNDERSTAND'
    assert body['steps'][0]['project']['reasons'] == [
        {'code': 'SOURCE_CHECK_REQUIRED', 'resolved_in': 'UNDERSTAND'}]
    assert [f['name'] for f in body['forms']] == ['CUSTOMERS', 'SHIPMENTS']


def test_http_journey_filters_and_rejects(project_server):
    client, _ = project_server
    pid = analyze_demo(client)
    everything = client.get(f'/api/v2/projects/{pid}/journey').json
    customers = everything['forms'][0]
    by_id = client.get(f"/api/v2/projects/{pid}/journey?form={customers['entity_id']}")
    assert by_id.status == 200 and [f['name'] for f in by_id.json['forms']] == ['CUSTOMERS']
    by_name = client.get(f'/api/v2/projects/{pid}/journey?form=customers')
    assert [f['name'] for f in by_name.json['forms']] == ['CUSTOMERS']
    assert client.get(f'/api/v2/projects/{pid}/journey?form=GHOST').status == 404
    assert client.get(f'/api/v2/projects/{pid}/journey?view=all').status == 400


def test_cli_journey_matches_http(project_server, capsys):
    client, _ = project_server
    pid = analyze_demo(client)
    descriptor = next((config.data_dir() / 'projects').glob('*/.formslang/project.json'))
    capsys.readouterr()
    assert main(['project', 'journey', str(descriptor), '--json']) == 0
    cli_journey = json.loads(capsys.readouterr().out)
    http_journey = client.get(f'/api/v2/projects/{pid}/journey').json
    assert cli_journey == http_journey
    assert cli_journey['freshness']['status'] == 'CURRENT'
    assert main(['project', 'journey', str(descriptor), '--form', 'SHIPMENTS', '--json']) == 0
    assert [f['name'] for f in json.loads(capsys.readouterr().out)['forms']] == ['SHIPMENTS']
    assert main(['project', 'journey', str(descriptor), '--form', 'GHOST', '--json']) == 2
    assert json.loads(capsys.readouterr().out)['error'].startswith('Form not found')
