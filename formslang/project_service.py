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

    def __init__(self, access: ProjectAccess):
        self.access = access
        self._store: ProjectStore | None = None

    def _require(self, action: str) -> None:
        if action not in self.access.actions:
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

    def import_session(self, source: Path, *, source_key: str) -> dict:
        self._require(rbac.ADOPT_PROJECT)
        approved_source = self._source(Path(source))
        self.open()
        return import_legacy_session(self._store, approved_source, source_key=source_key)

    def close(self) -> None:
        if self._store is not None:
            self._store.close()
            self._store = None
