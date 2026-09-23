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
from .project_model import TARGET_CHOICES, ProjectError, TargetProfile, target_from_choice
from .project_projection import CATEGORIES, INTERVENTIONS, RECOMMENDATIONS, RISK_LEVELS, SORTS
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
    if operation == 'demo':
        return intake.create_demo(destination=args.project), 0
    if operation == 'create':
        sources = [intake.select_source(path, kind) for kind in ('forms', 'database', 'supporting')
                   for path in getattr(args, kind)]
        target_profile = target_from_choice(getattr(args, 'target', 'apex'))
        return intake.create(args.name, sources, description=args.description,
                             client_label=args.client, destination=args.project,
                             target=target_profile), 0
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
    action = rbac.VIEW_PROJECT if operation in {'status', 'summary', 'inventory', 'search'} else rbac.RUN_CONVERSION
    authorize = lambda: intake.access(pid, action)
    service = ProjectService(authorize(), authorize=authorize)
    try:
        descriptor = service.open()
        preconditions = {'expected_revision': descriptor.analysis_revision,
                         'expected_configuration': summary['configuration_revision']}
        if operation == 'search':
            return service.search(args.query, limit=args.limit), 0
        if operation == 'report':
            state = service.report_overview()
            if args.format == 'status':
                return state, 0
            if not args.output:
                raise ProjectError('Choose --output for this report download.')
            download = service.report_export(args.format, state['binding'],
                include_notes=args.include_notes, include_artifacts=args.include_artifacts)
            with Path(args.output).open('xb') as output:
                output.write(download.body)
            return {'saved': True, 'size_bytes': len(download.body), 'binding': state['binding']}, 0
        if operation == 'generation':
            command = args.generation_command
            if command == 'status':
                return service.generation_overview(), 0
            if command == 'module':
                return service.generation_module(args.source), 0
            if command == 'task':
                return service.generation_task(args.source, args.task), 0
            if command == 'validate':
                result = service.generation_validate(args.artifact)
                return result, 0 if result['status'] in {'Validated', 'Package Verified'} else 1
            if command == 'download':
                payload = service.generation_download(args.artifact)
                data = getattr(payload, 'body', payload)
                with Path(args.output).open('xb') as output:
                    output.write(data)
                return {'artifact_id': args.artifact, 'size_bytes': len(data), 'saved': True}, 0
            path = Path(args.request)
            if path.stat().st_size > 256000:
                raise ProjectError('Generation request exceeds 256 KB')
            request = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(request, dict):
                raise ProjectError('Generation request must be a JSON object with exact revisions')
            if command == 'generate':
                return service.generate(request), 0
            if command == 'code':
                return service.generation_code(args.source, args.task, request), 0
            method = service.generation_prepare if command == 'prepare' else service.generation_configure
            return method(args.source, request), 0
        if operation == 'review':
            if args.review_command == 'list':
                filters = {key: getattr(args, key) for key in ('risk', 'recommendation',
                    'intervention', 'module', 'source_type', 'review') if getattr(args, key)}
                return service.review_queue(query=args.query, filters=filters, limit=args.limit,
                    offset=args.offset, sort=args.sort, expected_revision=args.revision,
                    expected_review=args.review_revision), 0
            if args.review_command == 'show':
                return service.review_detail(args.finding), 0
            binding = json.loads(args.binding)
            if not isinstance(binding, dict):
                raise ProjectError('Binding must be the JSON revision object from review show')
            if args.review_command == 'annotate':
                return service.review_annotate(args.finding, {**binding, 'kind': args.kind, 'note': args.note}), 0
            return service.review_decide(args.finding, {**binding, 'action': args.action,
                'recommendation': args.recommendation, 'rationale': args.rationale,
                'reason_code': args.reason, 'critical_confirmed': args.confirm_critical}), 0
        if operation == 'status':
            freshness = service.freshness()
            row = service._store.session.db.execute('SELECT job_id FROM project_job ORDER BY rowid DESC LIMIT 1').fetchone()
            return {**summary, 'freshness': freshness, 'assessment': service.assessment(freshness=freshness),
                    'last_job': service.job(row[0]) if row else None}, 0
        if operation == 'summary':
            result = service.overview(freshness=service.freshness())
            if result is None:
                raise ProjectError('Analyze the project before requesting its summary')
            return result, 0
        if operation == 'inventory':
            filters = {key: value for key, value in {
                'risk': args.risk, 'recommendation': args.recommendation,
                'intervention': args.intervention, 'module': args.module,
                'source_type': args.source_type, 'review': args.review,
            }.items() if value}
            return service.inventory(
                args.category, query=args.query, filters=filters, sort=args.sort,
                offset=args.offset, limit=args.limit, expected_revision=args.revision,
                freshness=service.freshness(),
            ), 0
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
    from .project_reports import FORMATS
    report = commands.add_parser('report', help='snapshot HTML, backlog and modernization package')
    report.add_argument('project')
    report.add_argument('--format', choices=['status', *FORMATS], default='status')
    report.add_argument('--output')
    report.add_argument('--include-notes', action='store_true', help='explicit sensitive human-note disclosure')
    report.add_argument('--include-artifacts', action='store_true', help='include verified generated code in package')
    report.add_argument('--json', action='store_true')
    report.set_defaults(func=run_project)
    generation = commands.add_parser('generation', help='reviewed module artifacts and explicit offline validation')
    generation_commands = generation.add_subparsers(dest='generation_command', required=True)
    for operation in ('status', 'module', 'prepare', 'plan', 'task', 'code', 'generate', 'validate', 'download'):
        command = generation_commands.add_parser(operation)
        command.add_argument('project')
        command.add_argument('--json', action='store_true')
        command.set_defaults(func=run_project)
        if operation in {'module', 'prepare', 'plan', 'task', 'code'}:
            command.add_argument('--source', required=True)
        if operation in {'task', 'code'}:
            command.add_argument('--task', required=True)
        if operation in {'prepare', 'plan', 'code', 'generate'}:
            command.add_argument('--request', required=True, help='JSON file with exact binding and operation fields')
        if operation in {'validate', 'download'}:
            command.add_argument('--artifact', required=True)
        if operation == 'download':
            command.add_argument('--output', required=True, help='new ZIP path; existing files are never overwritten')
    review = commands.add_parser('review', help='revision-bound modernization decisions')
    review_commands = review.add_subparsers(dest='review_command', required=True)
    for operation in ('list', 'show', 'decide', 'annotate'):
        command = review_commands.add_parser(operation)
        command.add_argument('project')
        command.add_argument('--json', action='store_true')
        command.set_defaults(func=run_project)
        if operation == 'list':
            command.add_argument('--query', default='')
            for key in ('risk', 'recommendation', 'intervention', 'module', 'source-type', 'review'):
                command.add_argument('--' + key)
            command.add_argument('--limit', type=int, default=50)
            command.add_argument('--offset', type=int, default=0)
            command.add_argument('--sort', choices=SORTS, default='priority')
            command.add_argument('--revision')
            command.add_argument('--review-revision', type=int)
        else:
            command.add_argument('--finding', required=True)
        if operation in {'decide', 'annotate'}:
            command.add_argument('--binding', required=True, help='exact JSON binding from review show')
        if operation == 'decide':
            command.add_argument('--action', choices=['APPROVE', 'MODIFY', 'REJECT', 'DEFER'], required=True)
            command.add_argument('--recommendation', default='')
            command.add_argument('--rationale', default='')
            command.add_argument('--reason', default='')
            command.add_argument('--confirm-critical', action='store_true')
        if operation == 'annotate':
            command.add_argument('--kind', required=True)
            command.add_argument('--note', default='')
    for name in ('create', 'demo', 'discover', 'analyze', 'status', 'summary',
                 'inventory', 'info', 'open', 'relink'):
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
            command.add_argument('--target', choices=list(TARGET_CHOICES), default='apex',
                                 help='target modernization strategy (default: apex)')
            command.add_argument('--target-apex', choices=[TargetProfile().version], default=TargetProfile().version)
        elif name == 'relink':
            command.add_argument('--root', required=True, help='stable source root ID from project info')
            command.add_argument('--path', required=True, help='explicitly authorize the replacement source folder')
        elif name == 'inventory':
            command.add_argument('--category', choices=CATEGORIES, default='forms')
            command.add_argument('--query', default='')
            command.add_argument('--risk', choices=RISK_LEVELS)
            command.add_argument('--recommendation', choices=RECOMMENDATIONS)
            command.add_argument('--intervention', choices=INTERVENTIONS)
            command.add_argument('--module')
            command.add_argument('--source-type')
            command.add_argument('--review')
            command.add_argument('--sort', choices=SORTS, default='name')
            command.add_argument('--offset', type=int, default=0)
            command.add_argument('--limit', type=int, choices=range(1, 201), default=50)
            command.add_argument('--revision')

    search_cmd = commands.add_parser('search', help='search project estate, system map, business rules, and findings')
    search_cmd.add_argument('project', help='project directory or .formslang/project.json descriptor')
    search_cmd.add_argument('--query', required=True, help='search query string')
    search_cmd.add_argument('--limit', type=int, choices=range(1, 51), default=20, metavar='1-50',
                            help='maximum results to return (1-50)')
    search_cmd.add_argument('--json', action='store_true', help='machine-readable stdout')
    search_cmd.set_defaults(func=run_project)
