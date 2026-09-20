"""Access-aware local project facade. UI/API/CLI adapters share these contracts."""

from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path

from . import authstore, rbac
from .project_assessment import current_assessment
from .project_manifest import engine_identity
from .project_migration import import_legacy_session
from .project_model import ProjectDescriptor, ProjectError, SourceRoot, validate_descriptor
from .project_store import ProjectStore
from .projects import ProjectAccess


class ProjectService:
    """One authorized project and one worker-owned connection per instance."""

    def __init__(self, access: ProjectAccess, *, authorize=None):
        self.access = access
        self._authorize_callback = authorize
        self._store: ProjectStore | None = None

    def _require(self, action: str) -> None:
        fresh = self._authorize_callback() if self._authorize_callback else self.access
        if (fresh.root != self.access.root or fresh.org_id != self.access.org_id
                or fresh.actor != self.access.actor or fresh.source_roots != self.access.source_roots):
            raise PermissionError('Project authorization changed; reopen the project')
        if action not in fresh.actions:
            raise PermissionError("Project action is not permitted")
        if self.access.org_id is None and authstore.auth_enabled():
            raise PermissionError("Authenticated mode requires project membership")
        if self.access.root.resolve() != self.access.root:
            raise ProjectError("Project root was redirected; reopen through authorized intake")
        directory = self.access.root / ".formslang"
        if directory.resolve() != directory:
            raise ProjectError("Project storage was redirected")

    def _source(self, path: Path) -> Path:
        resolved = path.resolve()
        if not any(root.resolve() == root and resolved.is_relative_to(root)
                   for root in self.access.source_roots):
            raise PermissionError("Source lies outside host-approved roots")
        return resolved

    def create(self, name: str, *, roots: tuple[SourceRoot, ...] = (),
               description: str = "", client_label: str = "", project_id: str | None = None) -> ProjectDescriptor:
        self._require(rbac.CREATE_PROJECT)
        if self.access.org_id is not None and (project_id is None or self._authorize_callback is None):
            raise ProjectError("Authenticated creation requires the project intake adapter")
        descriptor = ProjectDescriptor(id=project_id if project_id is not None else uuid.uuid4().hex, name=name, source_roots=roots,
                                       description=description, client_label=client_label)
        validate_descriptor(descriptor)
        for root in roots:
            self._source(self.access.root / root.path)
        if self._store is not None:
            raise ProjectError("Project service is already open")
        self._store = ProjectStore.create(self.access.root, descriptor)
        return self._store.descriptor()

    def open(self) -> ProjectDescriptor:
        self._require(rbac.VIEW_PROJECT)
        if self._store is None:
            self._store = ProjectStore.open(self.access.root)
            if self.access.org_id is None or self._authorize_callback is not None:
                from .project_jobs import ProjectJobManager
                authorize = lambda: self._job_authority(rbac.VIEW_PROJECT)
                ProjectJobManager(authorize(), authorize).recover()
        return self._store.descriptor()

    def assessment(self, *, freshness=None) -> dict | None:
        self.open()
        return current_assessment(self._store, expected_engines=engine_identity(), freshness=freshness)

    def _job_authority(self, action=rbac.RUN_CONVERSION):
        self._require(action)
        if self.access.org_id is not None and self._authorize_callback is None:
            raise PermissionError('Project operations require fresh authorization')
        return self._authorize_callback() if self._authorize_callback else self.access

    def analyze(self, *, expected_revision, expected_configuration, progress=None, cancellation=None, started=None):
        from .project_analysis import analyze_project

        self.open()
        return analyze_project(self._job_authority(), expected_revision=expected_revision,
            expected_configuration=expected_configuration, authorize=self._job_authority,
            progress=progress, cancellation=cancellation, started=started)

    def discover(self, *, expected_revision=..., expected_configuration=...):
        from .project_conversion import discover_project_sources
        from .project_jobs import ProjectJobManager

        descriptor = self.open()
        manager = ProjectJobManager(self._job_authority(), self._job_authority)
        with manager.claim('DISCOVER', expected_revision=descriptor.analysis_revision if expected_revision is ... else expected_revision,
                           expected_configuration=self._store.configuration_revision() if expected_configuration is ... else expected_configuration) as lease:
            result = discover_project_sources(self.access, descriptor, lease.store,
                                               checkpoint=lease.checkpoint, progress=lease.progress, preview=True)
            lease.store.record_discovery(result, run_id=lease.job_id)
            lease.finish('COMPLETED_WITH_WARNINGS' if result.diagnostics else 'COMPLETED')
            return lease.store.discovery(lease.job_id)

    def job(self, job_id):
        from .project_jobs import ProjectJobManager
        authorize = lambda: self._job_authority(rbac.VIEW_PROJECT)
        return ProjectJobManager(authorize(), authorize).get(job_id)

    def cancel(self, job_id):
        from .project_jobs import ProjectJobManager
        return ProjectJobManager(self._job_authority(), self._job_authority).cancel(job_id)

    def convert_source(self, source_id, *, expected_configuration, confirmed=False):
        from .project_conversion import convert_selected
        self.open()
        return convert_selected(self._job_authority(), source_id, expected_configuration=expected_configuration,
                                confirmed=confirmed, authorize=self._job_authority)

    def freshness(self, *, started=None):
        from .project_freshness import check_freshness
        from .project_jobs import ProjectJobManager

        descriptor = self.open()
        authorize = lambda: self._job_authority(rbac.VIEW_PROJECT)
        manager = ProjectJobManager(authorize(), authorize)
        with manager.claim('FRESHNESS', expected_revision=descriptor.analysis_revision,
                           expected_configuration=self._store.configuration_revision(), started=started) as lease:
            lease.progress({'phase': 'FRESHNESS', 'processed': 0, 'total': None})
            result = check_freshness(self.access, lease.store.descriptor(), lease.store.load_assessment(),
                                     checkpoint=lease.checkpoint)
            lease.finish('COMPLETED' if result['status'] == 'CURRENT' else 'COMPLETED_WITH_WARNINGS', outcome=result)
            return result

    def relink(self, root_id, path, *, expected_configuration):
        from .project_discovery import authorized_roots
        from .project_jobs import ProjectJobManager
        from .project_lock import project_worker_lock

        self._job_authority()
        self.open()
        with project_worker_lock(self.access.root):
            self._job_authority()
            descriptor = self._store.descriptor()
            if root_id not in {root.id for root in descriptor.source_roots}:
                raise ProjectError('Unknown source root')
            raw = self.access.root / Path(path)
            resolved = self._source(raw)
            if raw.absolute() != resolved or not resolved.is_dir():
                raise ProjectError('Select an available source folder without redirects')
            spelling = resolved.relative_to(self.access.root).as_posix() if resolved.is_relative_to(self.access.root) else str(resolved)
            roots = tuple(replace(root, path=spelling) if root.id == root_id else root for root in descriptor.source_roots)
            authorized_roots(self.access, replace(descriptor, source_roots=roots))
            ProjectJobManager._recover_locked(self._store)
            self._store.replace_roots(roots, expected_configuration=expected_configuration)
        return {'descriptor': self.open(), 'freshness': self.freshness()}

    def import_session(self, source: Path, *, source_key: str) -> dict:
        self._require(rbac.ADOPT_PROJECT)
        approved_source = self._source(Path(source))
        self.open()
        return import_legacy_session(self._store, approved_source, source_key=source_key)

    def close(self) -> None:
        if self._store is not None:
            self._store.close()
            self._store = None
