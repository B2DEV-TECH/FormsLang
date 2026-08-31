"""Project registry orchestration: resolve, authorize, adopt (§3, §8, §9).

``formslang/authstore.py`` owns the ``project`` table's raw CRUD. This
module is the layer above it that the HTTP handlers actually call --
every place that turns a ``project_id`` into a filesystem path, or a
(user, project) pair into a yes/no, goes through here, and only here, so
there is exactly one chokepoint to audit for the IDOR and path-traversal
concerns in the design doc's threat model (§3).

Nothing here trusts a client-supplied path. ``resolve_project_path`` only
ever accepts a ``project`` row already fetched from :class:`~formslang.authstore.AuthStore`
-- there is no code path that lets a caller hand in an arbitrary string
and have it opened.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from . import authstore, rbac
from .store import Store


class AdoptionError(authstore.AuthStoreError):
    pass


class ProjectPathEscape(ValueError):
    """An adopted project's on-disk path resolved outside ``data_dir``.

    Should never happen -- FormsLang itself constructs every adopted
    project's path -- but the containment check runs on every resolution
    anyway (§8: "resolve symlinks first, then verify containment"), not
    only at adoption time, in case the on-disk layout was tampered with
    after the fact.
    """


def resolve_project_path(project: dict, *, data_dir: Path | str) -> Path:
    """The one place a project's session-database path is derived (§8).

    ``EXTERNAL_LEGACY`` points at wherever the operator's original file
    lives, outside FormsLang's control. ``ADOPTED`` always lives under
    ``data_dir`` -- symlinks are resolved and containment is re-verified
    here, every call, before the path is handed to anything that will
    open or serve it.
    """
    if project["storage_mode"] == authstore.EXTERNAL_LEGACY:
        return Path(project["external_path"])

    root = Path(data_dir).resolve()
    candidate = Path(project["session_db_path"]).resolve()
    try:
        common = os.path.commonpath([str(candidate), str(root)])
    except ValueError:
        common = None  # different drives on Windows -- definitely not contained
    if common != str(root):
        raise ProjectPathEscape(f"adopted project path escapes data_dir: {candidate}")
    return candidate


def authorize_project_access(
    store: authstore.AuthStore, user_id: str, active_org_id: str, project_id: str, action: str,
) -> dict:
    """The IDOR chokepoint (§3): every route re-derives access here, every request.

    A project belonging to another organization -- or one that never
    existed at all -- is refused identically, via
    :class:`~formslang.authstore.ProjectNotFound`: existence is not leaked
    to a caller who is not a member of the owning organization. A caller
    who *is* a member but whose role lacks ``action`` gets a distinct
    ``PermissionError`` instead, since membership already proves the
    project is visible to them -- that is an ordinary RBAC denial, not an
    existence leak.
    """
    project = store.get_project(project_id)
    if project is None or project["org_id"] != active_org_id or project["deleted_at"]:
        raise authstore.ProjectNotFound(project_id)

    membership = store.get_membership(active_org_id, user_id)
    if membership is None:
        raise authstore.ProjectNotFound(project_id)

    role = membership["role"]
    if action == rbac.EXPORT_PROJECT:
        has_export = store.has_project_permission(project_id, user_id, "EXPORT")
        allowed = rbac.can_export(role, has_project_permission=has_export)
    else:
        allowed = rbac.has_permission(role, action)
    if not allowed:
        raise PermissionError(f"role {role} may not {action}")
    return project


def adopt_project(
    store: authstore.AuthStore, project_id: str, *, data_dir: Path | str, actor_user_id: str,
) -> dict:
    """Copy an EXTERNAL_LEGACY project's file into ``data_dir`` and flip it to ADOPTED.

    Copy, validate, atomically install, flip the database row, audit --
    in that order, and any failure before the atomic install leaves the
    original file and the project row untouched (§8's "non-destructive
    rollback"). The validation step re-opens the copy as a
    :class:`~formslang.store.Store` and checks it actually looks like a
    FormsLang session, not just a well-formed SQLite file -- ``Store``'s
    own ``CREATE TABLE IF NOT EXISTS`` schema would otherwise happily
    "adopt" an empty or unrelated database.
    """
    project = store.get_project(project_id)
    if project is None:
        raise authstore.ProjectNotFound(project_id)
    if project["storage_mode"] != authstore.EXTERNAL_LEGACY:
        raise AdoptionError(f"project {project_id} is not EXTERNAL_LEGACY (already adopted?)")

    source = Path(project["external_path"])
    if not source.is_file():
        raise AdoptionError(f"original file no longer exists: {source}")

    target_dir = Path(data_dir).resolve() / "orgs" / project["org_id"] / "projects" / project_id
    target_dir.mkdir(parents=True, exist_ok=True)
    final_path = target_dir / "main.session.db"
    tmp_path = target_dir / f".adopt-{uuid.uuid4().hex}.tmp"

    try:
        shutil.copy2(source, tmp_path)
        validated = Store(tmp_path)
        try:
            if not validated.session().get("title"):
                raise AdoptionError(f"not a FormsLang session file: {source}")
        finally:
            validated.close()
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        if isinstance(e, AdoptionError):
            raise
        raise AdoptionError(f"adoption validation failed: {e}") from e

    os.replace(tmp_path, final_path)  # atomic install -- the original is never touched
    store.mark_project_adopted(project_id, str(final_path))
    store.record_audit(
        org_id=project["org_id"],
        user_id=actor_user_id,
        event_type="PROJECT_ADOPTED",
        target_type="project",
        target_id=project_id,
    )
    return store.get_project(project_id)
