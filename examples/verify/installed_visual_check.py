"""Walk the 2.2 Visual Modernization Intelligence journey on an installed engine.

The engine is started the way the desktop starts it (``workbench <folder> -o
<work> --port <port> --no-browser``) and headless Edge drives its own UI with the
lab showcase: Overview -> Start Here -> Hotspot -> System Map -> Review ->
Module 360 -> Reports. Nothing from the checkout is imported or served; the
checkout only supplies the synthetic lab sources and the browser script.

    python examples/verify/installed_visual_check.py --engine <formslang-engine.exe> --version 2.2.0 --output <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path

from workbench_browser_check import REPO, browser_path, stop


def free_port() -> int:
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        return reservation.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--browser')
    parser.add_argument('--node', default='node')
    args = parser.parse_args()
    engine = args.engine.resolve(strict=True)
    run = args.output.resolve() / ('run-' + uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    reported = subprocess.run([str(engine), '--version'], capture_output=True, text=True, timeout=60,
                              creationflags=hidden, check=False).stdout.strip()
    if reported != f'FormsLang {args.version}':
        raise SystemExit(f'Installed engine reports {reported!r}, expected FormsLang {args.version}')
    # Schema source only, as in the walkthrough: the lab's seed scripts load rows
    # into a live database and are not part of the estate being assessed.
    lab = run / 'sources/lab'
    shutil.copytree(REPO / 'examples/modernization-lab/forms/xml', lab / 'forms')
    shutil.copytree(REPO / 'examples/modernization-lab/database', lab / 'database', ignore=shutil.ignore_patterns('seed'))
    environment = {k: v for k, v in os.environ.items() if not k.startswith('FORMSLANG_') and k != 'PYTHONPATH'}
    environment.update(FORMSLANG_CONFIG_DIR=str(run / 'config'), FORMSLANG_DATA_DIR=str(run / 'data'),
                       FORMSLANG_AUTH='0', FORMSLANG_SECRET_BACKEND='memory')
    port, debug_port = free_port(), free_port()
    url = f'http://127.0.0.1:{port}'
    (run / 'state.json').write_text(json.dumps({'url': url, 'debug_port': debug_port, 'version': args.version,
        'lab_forms': str(lab / 'forms'), 'lab_database': str(lab / 'database')}), encoding='utf-8')
    server = edge = node = None
    print(f'Installed visual evidence: {run}', flush=True)
    try:
        with (run / 'engine.log').open('w', encoding='utf-8') as engine_log, \
                (run / 'browser.log').open('w', encoding='utf-8') as log, \
                (run / 'node.log').open('w', encoding='utf-8') as node_log:
            server = subprocess.Popen([str(engine), 'workbench', str(run / 'sources'), '-o', str(run / 'work'),
                                       '--port', str(port), '--no-browser'],
                                      cwd=run, env=environment, stdout=engine_log, stderr=engine_log, creationflags=hidden)
            deadline = time.monotonic() + 60
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f'Installed engine exited with {server.returncode}; inspect engine.log')
                try:
                    with urllib.request.urlopen(url + '/api/state', timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError('Installed engine did not answer within 60 seconds')
                time.sleep(.25)
            edge = subprocess.Popen([browser_path(args.browser), '--headless=new', '--disable-gpu', '--no-first-run',
                '--disable-extensions', '--disable-background-networking', '--disable-sync',
                '--remote-debugging-address=127.0.0.1', f'--remote-debugging-port={debug_port}',
                '--window-size=1360,800', f'--user-data-dir={run / "browser-profile"}', 'about:blank'],
                creationflags=hidden, stdout=log, stderr=log)
            node = subprocess.Popen([args.node, str(Path(__file__).with_suffix('.mjs')), str(run)],
                                    creationflags=hidden, stdout=node_log, stderr=node_log)
            try:
                node.wait(timeout=600)
            except subprocess.TimeoutExpired:
                raise TimeoutError('Installed visual journey exceeded ten minutes') from None
        print((run / 'node.log').read_text(encoding='utf-8'), flush=True)
        return node.returncode
    finally:
        stop(node)
        stop(edge)
        stop(server)


if __name__ == '__main__':
    raise SystemExit(main())
