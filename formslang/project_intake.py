"""Host-owned source capabilities and recent locators, not another project store."""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import tempfile
import uuid
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from . import authstore, rbac
from .project_discovery import _redirected, authorized_roots, discover_sources
from .project_lock import project_worker_lock
from .project_manifest import relative_source_path
from .project_model import (
    ProjectDescriptor,
    ProjectError,
    SourceRoot,
    canonical_json,
    descriptor_to_dict,
)
from .project_service import ProjectService
from .project_store import ProjectStore, replace_mirror
from .projects import ProjectAccess, authorized_project_access, local_project_access


@dataclass(frozen=True)
class ProjectIdentity:
    """Trusted request identity; session token stays in memory, never locators."""
    token: str = field(repr=False)
    user_id: str
    org_id: str


def _path_spelling(path):
    # Windows realpath may retain its extended prefix during concurrent mkdir.
    # Normalize only DOS/UNC aliases, never GLOBALROOT or a different target.
    value = str(path)
    if os.name == 'nt':
        if value.startswith('\\\\?\\UNC\\'):
            return Path('\\\\' + value[8:])
        if (value.startswith('\\\\?\\') and len(value) > 6 and value[4].isascii()
                and value[4].isalpha() and value[5:7] == ':\\'):
            return Path(value[4:])
    return path


def _plain_path(value):
    path = _path_spelling(Path(os.path.abspath(value)))
    if _path_spelling(path.resolve()) != path:
        raise ProjectError('Redirected path is not an authorized location')
    return path


def _atomic_json(path, payload):
    path = _plain_path(path)
    fd, temporary = tempfile.mkstemp(prefix='.intake-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(canonical_json(payload))
            stream.flush()
            os.fsync(stream.fileno())
        replace_mirror(Path(temporary), path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class ProjectIntake:
    def __init__(self, data_dir, config_dir, *, identity=None, auth_db_path=None):
        self.data_dir = _plain_path(data_dir)
        self.config_dir = _plain_path(config_dir)
        self.identity = identity
        self.auth_db_path = _plain_path(auth_db_path or self.data_dir / 'auth.db')
        self.metadata_root = self.config_dir / 'project-intake'

    def _local(self):
        if self.identity is not None or authstore.auth_enabled():
            raise PermissionError('Use authorized organization source areas in authenticated mode')
        return getpass.getuser()

    @contextmanager
    def _auth(self, action=rbac.VIEW_PROJECT):
        if not isinstance(self.identity, ProjectIdentity):
            raise PermissionError('An authenticated session is required')
        store = authstore.AuthStore(_plain_path(self.auth_db_path))
        try:
            session = store.get_session(self.identity.token)
            if (session is None or session['scope'] != authstore.NORMAL or
                    session['user_id'] != self.identity.user_id or session['active_org_id'] != self.identity.org_id):
                raise PermissionError('Sign in again with a fully authorized session')
            member = store.get_membership(self.identity.org_id, self.identity.user_id)
            user = store.get_user(self.identity.user_id)
            if member is None or user is None or user['disabled_at'] is not None:
                raise PermissionError('Organization membership is no longer available')
            if action != rbac.VIEW_PROJECT and not rbac.has_permission(member['role'], action):
                raise PermissionError('This project action is not permitted')
            yield store
        finally:
            store.close()

    def _host_areas(self):
        with self._auth():
            path = _plain_path(self.config_dir / 'project-source-areas.json')
            if not path.is_file():
                return {}  # Saved evidence is still readable; no source access is granted.
            if path.stat().st_size > 1024 * 1024:
                raise ProjectError('Host source-area configuration is too large')
            try:
                configured = json.loads(path.read_text(encoding='utf-8'))['organizations'].get(self.identity.org_id, {})
                if not isinstance(configured, dict):
                    raise TypeError('invalid areas')
                result = {key: _plain_path(value) for key, value in configured.items()
                          if isinstance(key, str) and isinstance(value, str) and Path(value).is_absolute()}
                if len(result) != len(configured):
                    raise ValueError('invalid area path')
                return result
            except (ValueError, KeyError, TypeError) as exc:
                raise ProjectError('Host source-area configuration is invalid') from exc

    @contextmanager
    def _metadata(self, *, write=False):
        directory = _plain_path(self.metadata_root / '.formslang')
        directory.mkdir(parents=True, exist_ok=True)
        with project_worker_lock(self.metadata_root) if write else nullcontext():
            path = _plain_path(directory / 'locators.json')
            try:
                if path.exists():
                    if path.stat().st_size > 4 * 1024 * 1024:
                        raise ProjectError('Project locator index is too large')
                    payload = json.loads(path.read_text(encoding='utf-8'))
                else:
                    payload = {'areas': {}, 'projects': {}}
                if not isinstance(payload, dict) or set(payload) != {'areas', 'projects'}:
                    raise ProjectError('Invalid project locator index; restore its backup')
                if any(not isinstance(payload[key], dict) for key in payload):
                    raise ProjectError('Invalid project locator index')
            except (ValueError, OSError) as exc:
                raise ProjectError('Project locators could not be read safely') from exc
            yield payload
            if write:
                _atomic_json(path, payload)

    def select_source(self, path, kind):
        actor = self._local()
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise ProjectError('Select a source folder explicitly')
        if kind not in {'forms', 'database', 'supporting'}:
            raise ProjectError('Unknown source type')
        selected = _plain_path(path)
        if not selected.is_dir():
            raise ProjectError('Source folder is unavailable; select an existing folder')
        with self._metadata(write=True) as metadata:
            area_id = next((key for key, value in metadata['areas'].items()
                            if value['actor'] == actor and Path(value['path']) == selected), None)
            if area_id is None:
                area_id = uuid.uuid4().hex
                metadata['areas'][area_id] = {'actor': actor, 'path': str(selected)}
        return {'root_id': area_id, 'kind': kind, 'area_id': area_id, 'relative_path': ''}

    def _area(self, area_id):
        if self.identity is not None:
            area = self._host_areas().get(area_id)
            if area is None:
                raise PermissionError('Ask the host administrator to configure an authorized source area for this organization')
            return area
        actor = self._local()
        with self._metadata() as metadata:
            area = metadata['areas'].get(area_id)
            if area is None or area.get('actor') != actor:
                raise PermissionError('Select this source folder before using it')
            return _plain_path(area['path'])

    def _selection_path(self, area_id, relative=''):
        area = self._area(area_id)
        relative = relative_source_path(relative) if relative else ''
        selected = _plain_path(area / relative)
        if not selected.is_relative_to(area):
            raise PermissionError('Source selection escapes the authorized area')
        return selected

    def browse(self, area_id, relative=''):
        selected = self._selection_path(area_id, relative)
        if not selected.is_dir():
            raise ProjectError('Source folder is unavailable')
        directories = []
        truncated = False
        with os.scandir(selected) as entries:
            for index, entry in enumerate(entries):
                if index >= 100000 or len(directories) >= 200:
                    truncated = True
                    break
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False) and path.resolve() == path and not _redirected(path):
                    directories.append(entry.name)
        return {'area_id': area_id, 'relative_path': relative, 'directories': sorted(directories),
                'truncated': truncated}

    def _selections(self, selections):
        if not isinstance(selections, list) or not 1 <= len(selections) <= 128:
            raise ProjectError('Select at least one source folder (maximum 128)')
        roots = []
        for selection in selections:
            if not isinstance(selection, dict) or set(selection) != {'root_id', 'kind', 'area_id', 'relative_path'}:
                raise ProjectError('Invalid source selection')
            path = self._selection_path(selection['area_id'], selection['relative_path'])
            roots.append(SourceRoot(selection['root_id'], selection['kind'], str(path)))
        return tuple(roots)

    def preview(self, selections):
        roots = self._selections(selections)
        if self.identity is not None:
            with self._auth(rbac.CREATE_PROJECT):
                access = ProjectAccess(self.data_dir / '_preview', self.identity.user_id, self.identity.org_id,
                                       frozenset({rbac.CREATE_PROJECT}), tuple(Path(r.path) for r in roots))
            def checkpoint():
                with self._auth(rbac.CREATE_PROJECT):
                    pass
        else:
            self._local()
            access = local_project_access(self.data_dir / '_preview', approved_roots=tuple(Path(r.path) for r in roots))
            checkpoint = self._local
        descriptor = ProjectDescriptor(uuid.uuid4().hex, 'Source preview', source_roots=roots)
        return discover_sources(access, descriptor, checkpoint=checkpoint, progress=lambda event: None)

    def create(self, name, selections, *, description='', client_label='', destination=None):
        if self.identity is not None:
            if destination is not None:
                raise PermissionError('Authenticated projects use host-managed storage')
            return self._create_managed(name, selections, description, client_label)
        actor = self._local()
        roots = self._selections(selections)
        destination = _plain_path(destination if destination is not None else self.data_dir / 'projects' / uuid.uuid4().hex)
        access = local_project_access(destination, approved_roots=tuple(Path(r.path) for r in roots))
        authorized_roots(access, ProjectDescriptor(uuid.uuid4().hex, name, source_roots=roots))
        service = ProjectService(access)
        try:
            descriptor = service.create(name, roots=roots, description=description, client_label=client_label)
        finally:
            service.close()
        self._remember(descriptor.id, destination / '.formslang/project.json', actor, selections)
        return self._summary(descriptor.id)

    def _create_managed(self, name, selections, description, client_label):
        with self._auth(rbac.CREATE_PROJECT):
            roots = self._selections(selections)
        owner = self.identity
        pending_key = hashlib.sha256(canonical_json([owner.org_id, owner.user_id, name,
            selections, description, client_label]).encode()).hexdigest()
        # Locator reservation only. Project evidence remains solely in ProjectStore.
        with self._metadata(write=True) as metadata:
            pid = next((pid for pid, row in metadata['projects'].items() if row.get('pending_key') == pending_key), None)
            if pid is None:
                pid = uuid.uuid4().hex
                root = self.data_dir / 'orgs' / owner.org_id / 'projects' / pid
                metadata['projects'][pid] = {'locator': str(root / '.formslang/project.json'),
                    'actor': owner.user_id, 'org_id': owner.org_id, 'selections': selections, 'pending_key': pending_key}
        root = _plain_path(self.data_dir / 'orgs' / owner.org_id / 'projects' / pid)
        descriptor = ProjectDescriptor(pid, name, source_roots=roots, description=description, client_label=client_label)
        access = ProjectAccess(root, owner.user_id, owner.org_id, frozenset({rbac.CREATE_PROJECT}), tuple(Path(r.path) for r in roots))
        authorized_roots(access, descriptor)
        root.mkdir(parents=True, exist_ok=True)
        # Separate initialization lock: no database ownership crosses threads/processes.
        lock_root = _plain_path(root / '.initialization')
        (lock_root / '.formslang').mkdir(parents=True, exist_ok=True)
        with project_worker_lock(lock_root):
            marker_path = _plain_path(root / '.initialization/owner.json')
            marker = {'project_id': pid, 'org_id': owner.org_id, 'actor': owner.user_id, 'request': pending_key}
            if marker_path.exists():
                if json.loads(marker_path.read_text(encoding='utf-8')) != marker:
                    raise PermissionError('Project initialization belongs to another request')
            else:
                if (root / '.formslang').exists():
                    raise PermissionError('Existing project cannot be adopted by initialization')
                _atomic_json(marker_path, marker)
            with self._auth(rbac.CREATE_PROJECT) as registry:
                if (root / '.formslang/project.session.db').exists():
                    store = ProjectStore.open(root)
                    try:
                        if store.descriptor() != descriptor:
                            raise ProjectError('Initialized project differs from the creation request')
                    finally:
                        store.close()
                else:
                    def authorize_initialization():
                        with self._auth(rbac.CREATE_PROJECT):
                            if self._selections(selections) != roots:
                                raise PermissionError('Source authority changed during project initialization')
                            return access
                    service = ProjectService(access, authorize=authorize_initialization)
                    try:
                        service.create(name, roots=roots, description=description,
                                       client_label=client_label, project_id=pid)
                    finally:
                        service.close()
                registry.register_modernization_project(owner.org_id, pid, data_dir=self.data_dir, created_by=owner.user_id)
            with self._metadata(write=True) as metadata:
                metadata['projects'][pid].pop('pending_key', None)
        return self._summary(pid)

    def _remember(self, project_id, locator, actor, selections):
        with self._metadata(write=True) as metadata:
            previous = metadata['projects'].get(project_id)
            if previous and (previous['actor'] != actor or Path(previous['locator']) != locator):
                raise ProjectError('Project identity already belongs to another locator')
            metadata['projects'][project_id] = {'locator': str(locator), 'actor': actor,
                'selections': selections if selections else (previous['selections'] if previous else [])}

    def open_locator(self, locator):
        actor = self._local()
        path = _plain_path(locator)
        if path.name != 'project.json' or path.parent.name != '.formslang':
            raise ProjectError('Select a .formslang/project.json descriptor')
        service = ProjectService(local_project_access(path.parent.parent, approved_roots=()))
        try:
            descriptor = service.open()
        finally:
            service.close()
        self._remember(descriptor.id, path, actor, [])
        return self._summary(descriptor.id)

    def access(self, project_id, action):
        if self.identity is not None:
            with self._auth() as registry:
                return authorized_project_access(registry, project_id, active_org_id=self.identity.org_id,
                    user_id=self.identity.user_id, action=action, data_dir=self.data_dir,
                    approved_roots=tuple(self._host_areas().values()))
        actor = self._local()
        if action not in rbac.ACTIONS:
            raise PermissionError('Project action is not permitted')
        with self._metadata() as metadata:
            row = metadata['projects'].get(project_id)
            if row is None or row['actor'] != actor:
                raise PermissionError('Project is not available to this user')
        path = _plain_path(row['locator'])
        roots = self._selections(row['selections']) if row['selections'] else ()
        access = local_project_access(path.parent.parent, approved_roots=tuple(Path(r.path) for r in roots))
        service = ProjectService(access)
        try:
            if service.open().id != project_id:
                raise ProjectError('Project locator identity changed; open the descriptor explicitly')
        finally:
            service.close()
        return access

    def _summary(self, project_id):
        service = ProjectService(self.access(project_id, rbac.VIEW_PROJECT))
        try:
            project = descriptor_to_dict(service.open())
            if self.identity is not None:
                project['source_roots'] = [{'id': r['id'], 'kind': r['kind']} for r in project['source_roots']]
            assessment = service.assessment()
            return {'project': project, 'configuration_revision': service._store.configuration_revision(),
                'analyzed_at': assessment['analyzed_at'] if assessment else None,
                'inventory': assessment.get('inventory', {}) if assessment else {},
                'source_status': 'UNVERIFIED' if assessment else 'INCOMPLETE'}
        finally:
            service.close()

    def _audit(self, project_id, event_type, outcome='ok'):
        if self.identity is not None:
            with self._auth() as registry:
                registry.record_audit(event_type=event_type, org_id=self.identity.org_id,
                    user_id=self.identity.user_id, target_type='project', target_id=project_id, outcome=outcome)

    def relink(self, project_id, root_id, selection, *, expected_configuration):
        self.access(project_id, rbac.RUN_CONVERSION)
        replacement = self._selections([selection])[0]
        if self.identity is None:
            # Keep already granted capabilities if the subsequent CAS fails.
            # The descriptor remains the sole selection/configuration authority.
            with self._metadata(write=True) as metadata:
                grants = metadata['projects'][project_id]['selections']
                if selection not in grants:
                    grants.append(selection)
        authorize = lambda: self.access(project_id, rbac.RUN_CONVERSION)
        service = ProjectService(authorize(), authorize=authorize)
        try:
            result = service.relink(root_id, replacement.path, expected_configuration=expected_configuration)
        finally:
            service.close()
        self._audit(project_id, 'PROJECT_SOURCES_RELINKED')
        return {**self._summary(project_id), 'freshness': result['freshness']}

    def convert(self, project_id, source_id, *, expected_configuration, confirmed=False):
        authorize = lambda: self.access(project_id, rbac.RUN_CONVERSION)
        service = ProjectService(authorize(), authorize=authorize)
        try:
            result = service.convert_source(source_id, expected_configuration=expected_configuration, confirmed=confirmed)
        finally:
            service.close()
        self._audit(project_id, 'PROJECT_SOURCE_CONVERTED', result['status'].lower())
        return result

    def list_recent(self):
        if self.identity is not None:
            with self._auth() as registry:
                rows = registry.list_projects_for_org(self.identity.org_id)
            results = []
            for row in rows:
                try:
                    results.append(self._summary(row['id']))
                except (ProjectError, OSError):
                    continue  # 1.x sessions stay in their existing list until migrated.
            return results
        actor = self._local()
        with self._metadata() as metadata:
            ids = [pid for pid, row in metadata['projects'].items() if row['actor'] == actor]
        results = []
        for pid in ids:
            try:
                results.append(self._summary(pid))
            except (OSError, ProjectError, PermissionError):
                results.append({'project': {'id': pid}, 'source_status': 'UNVERIFIED',
                    'warning': 'Project is unavailable. Open its descriptor or restore its location.'})
        return results
