"""Check a real frozen engine from an isolated directory, without checkout imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import uuid
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    engine = args.engine.resolve(strict=True)
    run = args.output.resolve() / ('run-' + uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    environment = {k: v for k, v in os.environ.items() if not k.startswith('FORMSLANG_') and k != 'PYTHONPATH'}
    environment.update(FORMSLANG_CONFIG_DIR=str(run / 'config'), FORMSLANG_DATA_DIR=str(run / 'data'),
                       FORMSLANG_AUTH='0', FORMSLANG_SECRET_BACKEND='memory')
    result = {'engine': str(engine), 'sha256': hashlib.sha256(engine.read_bytes()).hexdigest(), 'checks': []}
    destination = run / 'project'

    def command(name, *arguments, structured=True):
        executed = subprocess.run([str(engine), *map(str, arguments)], cwd=run, env=environment,
                                  capture_output=True, text=True, timeout=180, check=False,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        (run / (name + '.stdout')).write_text(executed.stdout, encoding='utf-8')
        (run / (name + '.stderr')).write_text(executed.stderr, encoding='utf-8')
        if executed.returncode:
            raise RuntimeError(f'{name} failed with exit {executed.returncode}; inspect {name}.stdout/stderr')
        return json.loads(executed.stdout) if structured else executed.stdout.strip()

    def check(name, passed):
        result['checks'].append({'name': name, 'passed': bool(passed)})
        if not passed:
            raise AssertionError(name)

    try:
        result['version'] = command('version', '--version', structured=False)
        created = command('demo', 'project', 'demo', destination, '--json')
        check('bundled demo creates ordinary project', len(created['project']['source_roots']) == 2)
        first = command('analyze', 'project', 'analyze', destination, '--json')
        check('frozen project analysis completes', first['status'] == 'COMPLETED')
        reopened = command('status', 'project', 'status', destination, '--json')
        assessment = reopened['assessment']
        check('saved assessment reopens current', reopened['freshness']['status'] == 'CURRENT')
        check('bundled forms and package parsed', assessment['inventory']['forms']['analyzed'] == 2 and
              assessment['inventory']['database']['package_bodies'] == 1)
        check('engine identity resources present', all(key in assessment['engine_identity'] for key in
              ('parser.sha256', 'project_discovery.sha256', 'project_analysis.sha256', 'project_conversion.sha256')))
        repeated = command('repeat', 'project', 'analyze', destination, '--json')
        check('frozen analysis deterministic', repeated['analysis_revision'] == first['analysis_revision'])
        queue = command('review-list', 'project', 'review', 'list', destination, '--json')
        finding = queue['rows'][0]['id']
        detail = command('review-show', 'project', 'review', 'show', destination, '--finding', finding, '--json')
        command('review-defer', 'project', 'review', 'decide', destination, '--finding', finding,
                '--binding', json.dumps(detail['binding']), '--action', 'DEFER',
                '--rationale', 'Synthetic installed-engine review milestone.', '--json')
        reviewed = command('review-reopen', 'project', 'review', 'show', destination, '--finding', finding, '--json')
        check('frozen review history survives process reopen', reviewed['item']['review_state'] == 'DEFER' and reviewed['history_total'] > 0)
        delivery = run / 'delivery.zip'
        command('report', 'project', 'report', destination, '--format', 'package', '--output', delivery, '--json')
        with zipfile.ZipFile(delivery) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            check('frozen manifest covers the exact archive', bool(manifest['files']) and
                  set(archive.namelist()) == {'manifest.json', *manifest['files']})
            check('frozen report manifest hashes match', all(hashlib.sha256(archive.read(name)).hexdigest() == digest
                  for name, digest in manifest['files'].items()))
            html = archive.read('assessment/executive-summary.html')
            check('frozen executive report has expected heading and no active external content',
                  b'Executive Summary' in html and b'<script' not in html.lower() and
                  b'src="http' not in html.lower() and b'href="http' not in html.lower())
        sources = run / 'eligible-sources'
        sources.mkdir()
        (sources / 'notice.xml').write_text('<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="NOTICE">'
            '<Block Name="INFO" DatabaseBlock="false"><Item Name="MESSAGE" ItemType="Display Item" Prompt="Message"/>'
            '</Block></FormModule></Module>', encoding='utf-8')
        eligible = run / 'eligible-project'
        command('eligible-create', 'project', 'create', eligible, '--name', 'Synthetic installed generation', '--forms', sources, '--json')
        command('eligible-analyze', 'project', 'analyze', eligible, '--json')
        scopes = command('generation-status', 'project', 'generation', 'status', eligible, '--json')
        sid = scopes['modules'][0]['source_id']
        def generation_request(name, operation, payload, *extra):
            request = run / (name + '.request.json')
            request.write_text(json.dumps(payload), encoding='utf-8')
            return command(name, 'project', 'generation', operation, eligible, '--request', request, *extra, '--json')
        generation_request('prepare', 'prepare', scopes['binding'], '--source', sid)
        queue = command('eligible-review', 'project', 'review', 'list', eligible, '--json')
        for index, row in enumerate(queue['rows']):
            detail = command(f'eligible-detail-{index}', 'project', 'review', 'show', eligible, '--finding', row['id'], '--json')
            command(f'eligible-accept-{index}', 'project', 'review', 'decide', eligible, '--finding', row['id'],
                    '--binding', json.dumps(detail['binding']), '--action', 'APPROVE', '--json')
        detail = command('eligible-module', 'project', 'generation', 'module', eligible, '--source', sid, '--json')
        detail = generation_request('target-plan', 'plan', {**detail['binding'], 'code_revision': detail['code_revision'],
            'target_revision': detail['target_revision'], 'plan': {'security_confirmed': True, 'database_confirmed': True,
            'mapping_confirmed': True, 'keys': {}, 'rationale': 'Synthetic display-only scope; no writes; target access reviewed.'}}, '--source', sid)
        artifact = generation_request('generate', 'generate', {**detail['binding'], 'scopes': [detail]})
        exported = run / 'generated.apex.zip'
        command('download', 'project', 'generation', 'download', eligible, '--artifact', artifact['artifact_id'], '--output', exported, '--json')
        check('frozen generation produces exact recorded artifact', hashlib.sha256(exported.read_bytes()).hexdigest() == artifact['sha256'])
        result['analysis_revision'] = first['analysis_revision']
        result['source_revision'] = assessment['source_revision']
        result['engine_identity'] = assessment['engine_identity']
        result['passed'] = True
    except Exception as exc:  # noqa: BLE001 - acceptance artifact records failure, never pretends pass
        result.update(passed=False, failure=str(exc))
    (run / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'evidence': str(run), 'failure': result.get('failure')}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
