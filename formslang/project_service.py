"""Access-aware local project facade. UI/API/CLI adapters share these contracts."""

from __future__ import annotations

import uuid
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
               description: str = "", client_label: str = "") -> ProjectDescriptor:
        self._require(rbac.CREATE_PROJECT)
        if self.access.org_id is not None:
            raise ProjectError("Authenticated creation requires the project intake adapter")
        descriptor = ProjectDescriptor(id=uuid.uuid4().hex, name=name, source_roots=roots,
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
        return self._store.descriptor()

    def assessment(self) -> dict | None:
        self.open()
        return current_assessment(self._store, expected_engines=engine_identity())

    def _job_authority(self, action=rbac.RUN_CONVERSION):
        self._require(action)
        if self.access.org_id is not None and self._authorize_callback is None:
            raise PermissionError('Project operations require fresh authorization')
        return self._authorize_callback() if self._authorize_callback else self.access

    def analyze(self, *, expected_revision, expected_configuration, progress=None, cancellation=None):
        from .project_analysis import analyze_project

        self.open()
        return analyze_project(self._job_authority(), expected_revision=expected_revision,
            expected_configuration=expected_configuration, authorize=self._job_authority,
            progress=progress, cancellation=cancellation)

    def discover(self):
        from .project_discovery import discover_sources
        from .project_jobs import ProjectJobManager

        descriptor = self.open()
        manager = ProjectJobManager(self._job_authority(), self._job_authority)
        with manager.claim('DISCOVER', expected_revision=descriptor.analysis_revision,
                           expected_configuration=self._store.configuration_revision()) as lease:
            result = discover_sources(self.access, descriptor, checkpoint=lease.checkpoint, progress=lease.progress)
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

    def import_session(self, source: Path, *, source_key: str) -> dict:
        self._require(rbac.ADOPT_PROJECT)
        approved_source = self._source(Path(source))
        self.open()
        return import_legacy_session(self._store, approved_source, source_key=source_key)

    def close(self) -> None:
        if self._store is not None:
            self._store.close()
            self._store = None
