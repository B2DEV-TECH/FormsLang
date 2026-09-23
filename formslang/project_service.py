"""Access-aware local project facade. UI/API/CLI adapters share these contracts."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from pathlib import Path

from . import authstore, rbac
from .project_assessment import current_assessment
from .project_manifest import engine_identity
from .project_migration import import_legacy_session
from .project_model import (
    ProjectDescriptor,
    ProjectError,
    SourceRoot,
    TargetProfile,
    descriptor_to_dict,
    validate_descriptor,
)
from .project_projection import (
    ProjectionCache,
    inventory_page,
    prepare_projection,
    projection_key,
    search_project,
)
from .project_projection import (
    inventory_detail as project_inventory_detail,
)
from .project_projection import (
    overview as project_overview,
)
from .project_projection import (
    system_map as project_system_map,
)
from .project_store import ProjectStore
from .projects import ProjectAccess


class ProjectService:
    """One authorized project and one worker-owned connection per instance."""

    def __init__(self, access: ProjectAccess, *, authorize=None, projection_cache=None):
        self.access = access
        self._authorize_callback = authorize
        self._store: ProjectStore | None = None
        self._projection_cache = projection_cache if projection_cache is not None else ProjectionCache()

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
               description: str = "", client_label: str = "", project_id: str | None = None,
               target: TargetProfile | None = None) -> ProjectDescriptor:
        self._require(rbac.CREATE_PROJECT)
        if self.access.org_id is not None and (project_id is None or self._authorize_callback is None):
            raise ProjectError("Authenticated creation requires the project intake adapter")
        descriptor = ProjectDescriptor(id=project_id if project_id is not None else uuid.uuid4().hex, name=name, source_roots=roots,
                                       description=description, client_label=client_label,
                                       target=target if target is not None else TargetProfile())
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

    def _prepared_projection(self, freshness=None):
        assessment = self.assessment(freshness=freshness)
        if assessment is None:
            return None
        descriptor = descriptor_to_dict(self.open())
        storage = str(self._store.session.path.resolve()).casefold().encode("utf-8")
        store_scope = hashlib.sha256(storage).hexdigest()
        key = projection_key(descriptor, assessment, freshness or {}, store_scope=store_scope)
        return self._projection_cache.get_or_build(
            key,
            lambda: prepare_projection(
                descriptor, assessment, freshness or {}, store_scope=store_scope,
            ),
        )

    def overview(self, *, freshness=None) -> dict | None:
        prepared = self._prepared_projection(freshness)
        return project_overview(prepared) if prepared is not None else None

    def inventory(self, category: str, *, query="", filters=None, sort="name",
                  offset=0, limit=50, expected_revision=None, freshness=None) -> dict:
        prepared = self._prepared_projection(freshness)
        if prepared is None:
            raise ProjectError("Analyze the project before opening Inventory")
        return inventory_page(prepared, category, query=query, filters=filters, sort=sort,
                              offset=offset, limit=limit,
                              expected_revision=expected_revision)

    def inventory_detail(self, category: str, item_id: str, *, expected_revision=None,
                         freshness=None) -> dict:
        prepared = self._prepared_projection(freshness)
        if prepared is None:
            raise ProjectError("Analyze the project before opening Inventory")
        return project_inventory_detail(prepared, category, item_id,
                                        expected_revision=expected_revision)

    def system_map(self, *, focus=None, depth=2, layer=None, edge_type=None,
                   limit=100, edge_limit=200, freshness=None) -> dict:
        prepared = self._prepared_projection(freshness)
        if prepared is None:
            raise ProjectError("Analyze the project before opening System Map")
        return project_system_map(prepared, focus=focus, depth=depth, layer=layer,
                                  edge_type=edge_type, limit=limit, edge_limit=edge_limit)

    def search(self, query: str, *, limit: int = 20, freshness=None) -> dict:
        prepared = self._prepared_projection(freshness)
        if prepared is None:
            raise ProjectError("Analyze the project before searching")
        return search_project(prepared, query, limit=limit)

    def _job_authority(self, action=rbac.RUN_CONVERSION):
        self._require(action)
        if self.access.org_id is not None and self._authorize_callback is None:
            raise PermissionError('Project operations require fresh authorization')
        return self._authorize_callback() if self._authorize_callback else self.access

    def _review_service(self):
        from .project_review import ProjectReviewService
        self.open()
        return ProjectReviewService(self)

    def review_queue(self, **query):
        return self._review_service().queue(**query)

    def review_detail(self, finding_id, **query):
        return self._review_service().detail(finding_id, **query)

    def review_decide(self, finding_id, command):
        return self._review_service().mutate(finding_id, command)

    def review_annotate(self, finding_id, command):
        return self._review_service().mutate(finding_id, command, annotation=True)

    def review_bulk_preview(self, command):
        return self._review_service().bulk(command, apply=False)

    def review_bulk_apply(self, command):
        return self._review_service().bulk(command, apply=True)

    def _generation_service(self):
        from .project_generation import ProjectGenerationService
        self.open()
        return ProjectGenerationService(self)

    def generation_overview(self):
        return self._generation_service().overview()

    def generation_module(self, source_id):
        return self._generation_service().module(source_id)

    def generation_prepare(self, source_id, request):
        return self._generation_service().prepare(source_id, request)

    def generation_configure(self, source_id, request):
        return self._generation_service().configure(source_id, request)

    def generation_task(self, source_id, task_id):
        return self._generation_service().task(source_id, task_id)

    def generation_code(self, source_id, task_id, request):
        return self._generation_service().code(source_id, task_id, request)

    def generate(self, request):
        return self._generation_service().generate(request)

    def generation_download(self, artifact_id):
        return self._generation_service().download(artifact_id)

    def generation_validate(self, artifact_id):
        from .project_validation import validate_artifact
        return validate_artifact(self._generation_service(), artifact_id)

    def report_overview(self):
        from .project_reports import ProjectReportService
        self.open()
        return ProjectReportService(self).overview()

    def report_export(self, kind, request, **options):
        from .project_reports import ProjectReportService
        self.open()
        return ProjectReportService(self).export(kind, request, **options)

    def target_adapter(self):
        """Returns the TargetAdapter for this project's target profile."""
        from .target_adapter import get_target_adapter
        descriptor = self.open()
        if descriptor.target.platform == "UNSELECTED":
            raise ProjectError("Target strategy is unselected.")
        return get_target_adapter(descriptor.target)

    def architecture_policy(self) -> dict:
        """Inspect the effective architecture policy, its provenance map, and override state."""
        import json

        from .architecture_policy import (
            default_architecture_policy,
            policy_to_dict,
            resolve_effective_policy,
        )
        self.open()
        policy_file = self.access.root / ".formslang" / "policy.json"
        project_override = None
        if policy_file.is_file():
            try:
                project_override = json.loads(policy_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                project_override = None

        effective, provenance = resolve_effective_policy(
            default_architecture_policy(),
            organization_policy=None,
            project_policy=project_override,
        )
        return {
            "effective": policy_to_dict(effective),
            "provenance": provenance,
            "has_project_override": project_override is not None,
        }

    def update_architecture_policy(self, updates: dict) -> dict:
        """Update and persist project-specific architecture policy overrides."""
        import json

        from .architecture_policy import validate_policy_dict
        self._require(rbac.RUN_CONVERSION)
        self.open()
        validate_policy_dict(updates)
        policy_file = self.access.root / ".formslang" / "policy.json"
        policy_file.write_text(json.dumps(updates, indent=2), encoding="utf-8")
        return self.architecture_policy()

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
