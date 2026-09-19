"""Real local-project onboarding browser acceptance on disposable synthetic sources."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

from workbench_browser_check import REPO, browser_path, stop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--browser')
    parser.add_argument('--node', default='node')
    args = parser.parse_args()
    run = args.output.resolve() / ('run-' + uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    os.environ.update(FORMSLANG_CONFIG_DIR=str(run / 'config'), FORMSLANG_DATA_DIR=str(run / 'data'),
                      FORMSLANG_SECRET_BACKEND='memory', FORMSLANG_AUTH='0')
    sys.path.insert(0, str(REPO))
    from formslang.ai import EchoProvider
    from formslang.store import Store
    from formslang.workbench import Handler, Workbench

    forms, database = run / 'sources/forms', run / 'sources/database'
    forms.mkdir(parents=True)
    database.mkdir()
    shutil.copyfile(REPO / 'tests/fixtures/showcase/module.xml', forms / 'orders.xml')
    (database / 'orders.sql').write_text('create table orders (id number primary key);', encoding='utf-8')
    store = Store(run / 'shell.db')
    wb = Workbench(store, EchoProvider(), run / 'exports', browse_root=run / 'sources')
    handler = type('ProjectBrowserHandler', (Handler,), {'workbench': wb})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        debug_port = reservation.getsockname()[1]
    (run / 'state.json').write_text(json.dumps({'url': f'http://127.0.0.1:{server.server_port}',
        'debug_port': debug_port, 'forms': str(forms), 'database': str(database)}), encoding='utf-8')
    hidden = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    edge = node = None
    print(f'Project browser evidence: {run}', flush=True)
    try:
        with (run / 'browser.log').open('w', encoding='utf-8') as log, (run / 'node.log').open('w', encoding='utf-8') as node_log:
            edge = subprocess.Popen([browser_path(args.browser), '--headless=new', '--disable-gpu', '--no-first-run',
                '--disable-extensions', '--disable-background-networking', '--disable-sync',
                '--remote-debugging-address=127.0.0.1', f'--remote-debugging-port={debug_port}',
                '--window-size=1360,800', f'--user-data-dir={run / "browser-profile"}', 'about:blank'],
                creationflags=hidden, stdout=log, stderr=log)
            node = subprocess.Popen([args.node, str(Path(__file__).with_suffix('.mjs')), str(run)],
                                    creationflags=hidden, stdout=node_log, stderr=node_log)
            deadline = time.monotonic() + 180
            while node.poll() is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Project browser acceptance exceeded three minutes')
                time.sleep(.2)
            print((run / 'node.log').read_text(encoding='utf-8'), flush=True)
            return node.returncode
    finally:
        stop(node)
        stop(edge)
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        wb.project_api.close()
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
