"""Measure the real project pipeline on an isolated synthetic demo, not customer ROI."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
import tracemalloc
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from formslang import rbac
from formslang.project_intake import ProjectIntake
from formslang.project_service import ProjectService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run = args.output.resolve() / ('run-' + uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    intake = ProjectIntake(run / 'data', run / 'config')
    created = intake.create_demo()
    pid = created['project']['id']
    authorize = lambda: intake.access(pid, rbac.RUN_CONVERSION)
    service = ProjectService(authorize(), authorize=authorize)
    try:
        started = time.perf_counter()
        discovery = service.discover()
        discovery_ms = (time.perf_counter() - started) * 1000
        tracemalloc.start()
        outcome = service.analyze(expected_revision=None, expected_configuration=0)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assessment = service.assessment()
        metadata = json.loads(service._store.session.db.execute(
            'SELECT metadata_json FROM project_analysis_run WHERE job_id=?', (outcome['job_id'],)
        ).fetchone()[0])
        revision = assessment['analysis_revision']
        repeated = service.analyze(expected_revision=revision, expected_configuration=0)
        same = service.assessment()['analysis_revision'] == revision
        report = {
            'fixture': 'bundled synthetic dispatch desk: 2 Forms, 2 tables, 1 package spec/body',
            'platform': platform.platform(), 'python': platform.python_version(),
            'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
            'discovery_ms': round(discovery_ms, 3), 'inventory': discovery['inventory'],
            'analysis': metadata, 'python_tracemalloc_peak_bytes': peak,
            'source_revision': assessment['source_revision'], 'analysis_revision': revision,
            'status': outcome['status'], 'repeat_status': repeated['status'],
            'deterministic_repeat': same,
            'limitations': 'One small synthetic run with tracing overhead; peak is Python allocations, not process RSS. No scale or analyst-time claim.',
        }
        (run / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f'Evidence: {run}')
        print(json.dumps(report, indent=2))
        return 0 if same and outcome['status'] == repeated['status'] == 'COMPLETED' else 1
    finally:
        service.close()


if __name__ == '__main__':
    raise SystemExit(main())
