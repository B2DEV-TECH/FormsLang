"""Local project CLI adapter; all analysis belongs to ProjectService."""

from __future__ import annotations

import json
import signal
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from . import authstore, config, rbac
from .project_intake import ProjectIntake
from .project_model import ProjectError, TargetProfile
from .project_service import ProjectService


@contextmanager
def _cancellation():
    cancelled = threading.Event()
    previous = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *_: cancelled.set())
    try:
        yield cancelled.is_set
    finally:
        signal.signal(signal.SIGINT, previous)


def _progress(event):
    total = event.get('total')
    count = str(event.get('processed', 0)) + (f' / {total}' if total is not None else '')
    print(f"{event['phase']}: {count}; warnings: {event.get('warnings_count', 0)}", file=sys.stderr)


def _operation(args):
    if authstore.auth_enabled():
        raise PermissionError('Authenticated mode requires the Workbench API and a normal authorized session; local project CLI is disabled')
    intake = ProjectIntake(config.data_dir(), config.config_dir())
    operation = args.project_command
    if operation == 'create':
        sources = [intake.select_source(path, kind) for kind in ('forms', 'database', 'supporting')
                   for path in getattr(args, kind)]
        return intake.create(args.name, sources, description=args.description,
                             client_label=args.client, destination=args.project), 0
    path = Path(args.project)
    locator = path if path.name == 'project.json' else path / '.formslang/project.json'
    summary = intake.open_locator(locator)
    pid = summary['project']['id']
    if operation in {'open', 'info'}:
        return summary, 0
    if operation == 'relink':
        root = next((r for r in summary['project']['source_roots'] if r['id'] == args.root), None)
        if root is None:
            raise ProjectError('Unknown source root; use project info to list root IDs')
        selection = intake.select_source(args.path, root['kind'])
        return intake.relink(pid, args.root, selection, expected_configuration=summary['configuration_revision']), 0
    action = rbac.VIEW_PROJECT if operation == 'status' else rbac.RUN_CONVERSION
    authorize = lambda: intake.access(pid, action)
    service = ProjectService(authorize(), authorize=authorize)
    try:
        descriptor = service.open()
        preconditions = {'expected_revision': descriptor.analysis_revision,
                         'expected_configuration': summary['configuration_revision']}
        if operation == 'status':
            freshness = service.freshness()
            row = service._store.session.db.execute('SELECT job_id FROM project_job ORDER BY rowid DESC LIMIT 1').fetchone()
            return {**summary, 'freshness': freshness, 'assessment': service.assessment(freshness=freshness),
                    'last_job': service.job(row[0]) if row else None}, 0
        if operation == 'discover':
            return service.discover(**preconditions), 0
        with _cancellation() as cancellation:
            result = service.analyze(**preconditions, progress=_progress, cancellation=cancellation)
        status = result['status']
        return result, (130 if status == 'CANCELLED' else 0 if status in {'COMPLETED', 'COMPLETED_WITH_WARNINGS'} else 1)
    finally:
        service.close()


def run_project(args):
    try:
        result, exit_code = _operation(args)
    except (ProjectError, PermissionError) as exc:
        result, exit_code = {'error': str(exc)}, 2
    except (OSError, LookupError, ValueError):
        result, exit_code = {'error': 'Project could not be opened. Check its descriptor and source folders, then retry.'}, 2
    except KeyboardInterrupt:
        result, exit_code = {'error': 'Operation interrupted; the last saved assessment is preserved.'}, 130
    except Exception:  # noqa: BLE001 - do not print arbitrary exception source/secrets
        result, exit_code = {'error': 'Project operation failed. View saved evidence and retry.'}, 1
    if args.json:
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    elif 'error' in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
    else:
        project = result.get('project', {})
        print(project.get('name', 'Project operation'))
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return exit_code


def add_project_parser(subparsers):
    parser = subparsers.add_parser('project', help='local modernization projects: create, analyze and reopen')
    commands = parser.add_subparsers(dest='project_command', required=True)
    for name in ('create', 'discover', 'analyze', 'status', 'info', 'open', 'relink'):
        command = commands.add_parser(name)
        command.add_argument('project', help='project directory or .formslang/project.json descriptor')
        command.add_argument('--json', action='store_true', help='machine-readable stdout; progress goes to stderr')
        command.set_defaults(func=run_project)
        if name == 'create':
            command.add_argument('--name', required=True)
            command.add_argument('--description', default='')
            command.add_argument('--client', default='')
            for kind in ('forms', 'database', 'supporting'):
                command.add_argument('--' + kind, action='append', default=[], help='source folder; repeat for additional roots')
            command.add_argument('--target-apex', choices=[TargetProfile().version], default=TargetProfile().version)
        elif name == 'relink':
            command.add_argument('--root', required=True, help='stable source root ID from project info')
            command.add_argument('--path', required=True, help='explicitly authorize the replacement source folder')
