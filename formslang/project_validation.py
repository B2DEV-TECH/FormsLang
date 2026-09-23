"""Explicit offline Oracle validation, bound to immutable artifact bytes."""

import hashlib
import tempfile
from pathlib import Path

from . import apeximport, rbac
from .project_jobs import now
from .project_lock import project_worker_lock
from .project_model import RevisionConflict, canonical_json


def validate_artifact(generation, artifact_id):
    service = generation.service
    service._job_authority(rbac.EXPORT_PROJECT)
    with project_worker_lock(service.access.root):
        payload = generation.download(artifact_id)
        data = getattr(payload, 'body', payload)
        fingerprint = hashlib.sha256(data).hexdigest()
        if generation._artifact_metadata(artifact_id).get('artifact_kind'):
            # A target-neutral package has no target syntax: check its declared
            # structure, member hashes and references, and say only that.
            from .adapters.generic import PACKAGE_SCHEMA, validate_package
            verdict = validate_package(data)
            result = {
                'artifact_id': artifact_id,
                'artifact_sha256': fingerprint,
                'tool_version': PACKAGE_SCHEMA,
                'mode': 'package-structure',
                'timestamp': now(),
                'status': 'Package Verified' if verdict['valid'] else 'Package Invalid',
                'exit_code': None,
                'message': ('Assessment package structure, member hashes and references verified.'
                            if verdict['valid'] else '; '.join(verdict['diagnostics'])[:4000]),
                'limitation': ('Structure and integrity only; not SQLcl syntax, architecture acceptance '
                               'or runtime testing.'),
            }
        else:
            version = apeximport.sqlcl_version()
            result = {'artifact_id': artifact_id, 'artifact_sha256': fingerprint,
                      'tool_version': version, 'mode': 'offline-syntax', 'timestamp': now(),
                      'status': 'Not Validated', 'exit_code': None,
                      'message': 'Configure a working SQLcl with APEXlang support and validate again.',
                      'limitation': 'Syntax validation is not functional equivalence or runtime testing.'}
            if version:
                # Validate a private snapshot, never a mutable user path. Do not use
                # saved connection settings or credentials; this cannot import.
                with tempfile.TemporaryDirectory(prefix='formslang-validate-') as temporary:
                    package = Path(temporary) / 'application.apex.zip'
                    package.write_bytes(data)
                    try:
                        verdict = apeximport.run_import(package, validate_only=True)
                    except ValueError:
                        result['message'] = 'SQLcl could not complete offline validation. Check its installation and rerun explicitly.'
                    else:
                        positive = 'Validation successful.' in verdict.stdout
                        result.update(status='Validated' if verdict.ok and positive else 'Validation Failed',
                                      exit_code=verdict.exit_code,
                                      message='Oracle offline syntax validation passed.' if verdict.ok and positive else
                                      'Oracle did not confirm valid syntax. Inspect the artifact with SQLcl; no import occurred.')
        service._job_authority(rbac.EXPORT_PROJECT)
        with generation.store._write() as db:
            if hashlib.sha256(generation._artifact_bytes(artifact_id)).hexdigest() != fingerprint:
                raise RevisionConflict('Artifact changed during validation; no verdict was published.')
            db.execute('INSERT INTO project_artifact_validation(artifact_id,artifact_sha256,created_at,payload_json) VALUES (?,?,?,?)',
                       (artifact_id, fingerprint, result['timestamp'], canonical_json(result)))
        return result
