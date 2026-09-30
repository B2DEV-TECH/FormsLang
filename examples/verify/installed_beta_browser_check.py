"""Exercise the saved synthetic A-to-B project through the frozen Workbench."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

from workbench_browser_check import browser_path, stop


def free_port() -> int:
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        return reservation.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--browser')
    args = parser.parse_args()
    engine = args.engine.resolve(strict=True)
    project = args.project.resolve(strict=True)
    run = args.output.resolve()
    run.mkdir(parents=True, exist_ok=False)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    port, debug_port = free_port(), free_port()
    url = f'http://127.0.0.1:{port}'
    environment = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    (run / 'state.json').write_text(json.dumps({'url': url, 'debug_port': debug_port,
        'project': str(project), 'project_id': args.project_id}), encoding='utf-8')
    server = edge = node = None
    print(f'Installed beta browser evidence: {run}', flush=True)
    try:
        with (run / 'engine.log').open('w', encoding='utf-8') as engine_log, \
                (run / 'browser.log').open('w', encoding='utf-8') as browser_log, \
                (run / 'node.log').open('w', encoding='utf-8') as node_log:
            server = subprocess.Popen([str(engine), 'workbench', str(project.parent / 'sources'),
                '-o', str(run / 'work'), '--port', str(port), '--no-browser'],
                cwd=run, env=environment, stdout=engine_log, stderr=engine_log,
                creationflags=hidden)
            deadline = time.monotonic() + 60
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f'Frozen Workbench exited with {server.returncode}; see engine.log')
                try:
                    with urllib.request.urlopen(url + '/api/state', timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError('Frozen Workbench did not answer within 60 seconds')
                time.sleep(.25)
            edge = subprocess.Popen([browser_path(args.browser), '--headless=new', '--disable-gpu',
                '--no-first-run', '--disable-extensions', '--disable-background-networking',
                '--disable-sync', '--remote-debugging-address=127.0.0.1',
                f'--remote-debugging-port={debug_port}', '--window-size=1360,800',
                f'--user-data-dir={run / "browser-profile"}', 'about:blank'],
                creationflags=hidden, stdout=browser_log, stderr=browser_log)
            node = subprocess.Popen(['node', str(Path(__file__).with_suffix('.mjs')), str(run)],
                creationflags=hidden, stdout=node_log, stderr=node_log)
            node.wait(timeout=300)
        print((run / 'node.log').read_text(encoding='utf-8'), flush=True)
        return node.returncode
    finally:
        stop(node)
        stop(edge)
        stop(server)


if __name__ == '__main__':
    raise SystemExit(main())
