"""One project operation composing discovery, existing reasoning and atomic publish."""

from __future__ import annotations

import time
from dataclasses import asdict

from . import blueprint
from .project_assessment import bind_assessment
from .project_conversion import discover_project_sources, intake_options
from .project_discovery import DB_FAMILIES
from .project_jobs import AnalysisCancelled, ProjectJobManager, now
from .project_manifest import engine_identity, source_revision
from .project_model import ProjectError, canonical_json
from .project_sources import fingerprint_inputs, parse_staged, stage_sources

PROJECT_ANALYSIS_VERSION = 'project-analysis/2'
INFORMATIONAL_CODES = {'IDENTICAL_CONTENT', 'DUPLICATE_FILE', 'DUPLICATE_DIRECTORY'}


class SourceChanged(ProjectError):
    pass


def _failure(code, message, remediation):
    return {'error_code': code, 'safe_message': message, 'remediation': remediation}


def analyze_project(access, *, expected_revision, expected_configuration, authorize,
                    progress=None, cancellation=None, started=None):
    manager = ProjectJobManager(access, authorize)
    analysis_started = time.perf_counter()
    durations = {}
    current_phase, phase_started = None, analysis_started
    job_id = None
    denied = None
    counts = {'warnings_count': 0, 'errors_count': 0}
    diagnostics = []
    inventory = {}
    with manager.claim('ANALYZE', expected_revision=expected_revision,
                       expected_configuration=expected_configuration, started=started) as lease:
        job_id = lease.job_id

        def checkpoint():
            if cancellation is not None and cancellation():
                with lease.store._write() as db:
                    db.execute('UPDATE project_job SET cancellation_requested=1 WHERE job_id=?', (job_id,))
                raise AnalysisCancelled('Analysis cancellation requested')
            lease.checkpoint()

        def emit(event):
            nonlocal current_phase, phase_started
            checkpoint()
            clock = time.perf_counter()
            if event['phase'] != current_phase:
                if current_phase:
                    durations[current_phase] = durations.get(current_phase, 0) + (clock - phase_started) * 1000
                current_phase, phase_started = event['phase'], clock
            counts.update({key: event[key] for key in counts if key in event})
            event = {**counts, **event}
            lease.progress(event)
            if progress:
                progress({**event, 'job_id': job_id, 'elapsed_ms': int((clock - analysis_started) * 1000)})
            checkpoint()

        def phase(name):
            emit({'phase': name, 'processed': 0, 'total': None})

        try:
            descriptor = lease.store.descriptor()
            engines = engine_identity()
            phase('DISCOVERY')
            discovery = discover_project_sources(access, descriptor, lease.store, checkpoint=checkpoint, progress=emit, preview=False)
            options = {'intake': intake_options(discovery), 'enterprise': False}
            lease.store.record_discovery(discovery, run_id=job_id)
            with stage_sources(access, descriptor, discovery, checkpoint=checkpoint) as staged:
                parsed = parse_staged(descriptor, discovery, staged, checkpoint=checkpoint, progress=emit)
                diagnostics = [asdict(d) for d in parsed.diagnostics]
                inventory = parsed.inventory
                material = [d for d in parsed.diagnostics if d.error_code not in INFORMATIONAL_CODES]
                counts.update(warnings_count=len(parsed.diagnostics), errors_count=len(material))
                lease.progress({'phase': current_phase, 'processed': 0, 'total': None, **counts})
                if not parsed.modules and not any(getattr(parsed.database, family) for family in DB_FAMILIES):
                    lease.finish('FAILED', _failure('NO_SUPPORTED_SOURCES', 'No usable supported sources were analyzed.',
                        'Select Forms2XML and supported database source, then retry.'))
                else:
                    phase('BLUEPRINT')
                    payload = blueprint.build(parsed.modules, title=descriptor.name,
                        source_keys=parsed.source_keys, database_sources=parsed.database,
                        failures=[asdict(d) for d in material])
                    checkpoint()
                    phase('ASSESSMENT')
                    incomplete = bool(material) or any(e.selected and e.status != 'available' for e in staged.manifest)
                    assessment = bind_assessment(descriptor, staged.manifest, payload, engines=engines,
                        options=options, analyzed_at=now(), status='Incomplete' if incomplete else 'Current')
                    assessment.update(inventory=parsed.inventory, diagnostics=[asdict(d) for d in parsed.diagnostics],
                        completion_state='INCOMPLETE' if incomplete else 'COMPLETE_WITH_WARNINGS' if parsed.diagnostics else 'COMPLETE')
                    phase('PERSISTING')
                    latest = discover_project_sources(access, descriptor, lease.store, checkpoint=checkpoint, progress=lambda e: None, preview=False)
                    current_manifest = fingerprint_inputs(access, descriptor, latest, checkpoint=checkpoint)
                    if (source_revision(current_manifest, intake_options(latest)) != assessment['source_revision']
                            or latest.diagnostics != discovery.diagnostics):
                        raise SourceChanged('Sources changed during analysis')
                    checkpoint()
                    lease.publish(assessment)
        except AnalysisCancelled:
            lease.finish('CANCELLED')
        except SourceChanged:
            lease.finish('FAILED', _failure('INCOMPLETE_SOURCE_CHANGED', 'Sources changed while analysis was running.',
                'Keep the saved assessment and retry after source edits finish.'))
        except PermissionError:
            denied = _failure('ACCESS_REVOKED', 'Project access is no longer authorized.', 'Sign in again or ask the project owner for access.')
            lease.finish('FAILED', denied)
        except (ProjectError, OSError, ValueError):
            lease.finish('FAILED', _failure('ANALYSIS_FAILED', 'Project analysis could not complete safely.',
                'Check source diagnostics and retry; the previous assessment is preserved.'))
        finally:
            if current_phase:
                durations[current_phase] = durations.get(current_phase, 0) + (time.perf_counter() - phase_started) * 1000
            metadata = {'phase_duration_ms': {k: round(v, 3) for k, v in durations.items()},
                        'diagnostics': diagnostics, 'inventory': inventory,
                        'total_duration_ms': round((time.perf_counter() - analysis_started) * 1000, 3)}
            with lease.store._write() as db:
                db.execute('INSERT INTO project_analysis_run VALUES (?,?)', (job_id, canonical_json(metadata)))
    if denied:
        return {'job_id': job_id, 'status': 'FAILED', 'safe_failure': denied}
    result = manager.get(job_id)
    result.update(result.pop('outcome'))
    return result
