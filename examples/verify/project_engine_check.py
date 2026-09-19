"""Check a real frozen engine from an isolated directory, without checkout imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import uuid
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
