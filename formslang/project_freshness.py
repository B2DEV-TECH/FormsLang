"""Source freshness is a read projection, never a rewrite of saved evidence."""

from .project_discovery import discover_sources
from .project_jobs import AnalysisCancelled, now
from .project_manifest import engine_identity, fingerprint_sources, source_revision
from .project_model import ProjectError


def check_freshness(access, descriptor, assessment, *, checkpoint):
    result = {'status': 'UNVERIFIED', 'reasons': [], 'source_revision': None,
              'analysis_revision': assessment['analysis_revision'] if assessment else None,
              'checked_at': now()}
    if assessment is None:
        return {**result, 'status': 'INCOMPLETE', 'reasons': ['NOT_ANALYZED']}
    try:
        checkpoint()
        discovery = discover_sources(access, descriptor, checkpoint=checkpoint,
                                     progress=lambda event: None, preview=False)
        entries = []
        for entry in discovery.entries:
            checkpoint()
            entries.extend(fingerprint_sources(access.root, descriptor.source_roots, (entry.candidate,)))
        checkpoint()
        revision = source_revision(tuple(entries), assessment['analysis_options'].get('intake', {}))
        result['source_revision'] = revision
        missing = {e['source_id'] for e in assessment['source_manifest']} - {e.source_id for e in entries}
        if missing or any(d.error_code == 'MISSING_ROOT' for d in discovery.diagnostics) or any(e.status == 'missing' for e in entries):
            result.update(status='MISSING_SOURCE', reasons=['SOURCE_MISSING'])
        elif any(e.status != 'available' for e in entries):
            result['reasons'] = ['SOURCE_UNREADABLE']
        elif any(d.error_code in {'FILE_LIMIT', 'UNREADABLE_SOURCE', 'UNREADABLE_DIRECTORY',
                                 'DEPTH_LIMIT', 'REDIRECTED_PATH', 'NOT_REGULAR_FILE'}
                 for d in discovery.diagnostics):
            result['reasons'] = ['DISCOVERY_INCOMPLETE']
        elif revision != assessment['source_revision']:
            result.update(status='STALE', reasons=['SOURCE_CHANGED'])
        elif assessment['engine_identity'] != engine_identity():
            result.update(status='STALE', reasons=['ENGINE_CHANGED'])
        elif assessment['status'] == 'Incomplete':
            result.update(status='INCOMPLETE', reasons=['ASSESSMENT_INCOMPLETE'])
        else:
            result['status'] = 'CURRENT'
        return result
    except AnalysisCancelled:
        raise
    except (PermissionError, ProjectError, OSError):
        return {**result, 'status': 'UNVERIFIED', 'reasons': ['SOURCE_CHECK_UNAVAILABLE']}
