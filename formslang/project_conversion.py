"""Explicit Oracle conversion and allowlisted, immutable derived representations."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from dataclasses import replace
from pathlib import Path

from . import oracle, parser
from .project_discovery import (
    DISCOVERY_VERSION,
    MAX_SOURCE_BYTES,
    DiscoveredSource,
    authorized_roots,
    discover_sources,
)
from .project_jobs import AnalysisCancelled, ProjectJobManager, now
from .project_manifest import SourceCandidate, fingerprint_sources, source_id
from .project_model import ProjectError, RevisionConflict, SourceRoot, canonical_json


def intake_options(discovery):
    options = {'discovery': DISCOVERY_VERSION}
    if discovery.derived_provenance:
        options['derived_sources'] = list(discovery.derived_provenance)
    return options


def derived_directory(access, sid, digest):
    if any(not isinstance(v, str) or not re.fullmatch('[a-f0-9]{64}', v) for v in (sid, digest)):
        raise ProjectError('Invalid derived-source provenance')
    path = access.root / '.formslang/derived' / sid / digest
    if path.resolve() != path:
        raise ProjectError('Derived-source storage was redirected')
    return path


def discover_project_sources(access, descriptor, store, *, checkpoint, progress, preview=False):
    result = discover_sources(access, descriptor, checkpoint=checkpoint, progress=progress, preview=preview)
    entries, roots, provenance = list(result.entries), [], []
    diagnostics = list(result.diagnostics)
    candidates = {source_id(e.candidate.root_id, e.candidate.relative_path): e.candidate for e in entries}
    for row in store.session.db.execute('SELECT * FROM project_derived_source ORDER BY source_id').fetchall():
        checkpoint()
        candidate = candidates.get(row['source_id'])
        if candidate is None:
            continue
        original = fingerprint_sources(access.root, descriptor.source_roots, (candidate,))[0]
        if original.status != 'available' or original.sha256 != row['source_sha256']:
            continue  # Never apply an old conversion to a changed binary.
        # A supplied XML already wins; never silently select two representations.
        if any(e.original_binary_id == row['source_id'] for e in result.entries):
            continue
        directory = derived_directory(access, row['source_id'], row['xml_sha256'])
        expected = (directory / 'module.xml').relative_to(access.root / '.formslang').as_posix()
        if row['relative_path'] != expected:
            raise ProjectError('Derived-source registry path mismatch')
        root = SourceRoot('converted_' + row['source_id'], 'forms', str(directory))
        xml = SourceCandidate(root.id, 'module.xml', 'xml')
        actual = fingerprint_sources(access.root, (root,), (xml,))[0]
        if actual.status == 'available' and actual.sha256 != row['xml_sha256']:
            raise ProjectError('Derived representation changed; explicitly reconvert the original')
        roots.append(root)
        entries.append(DiscoveredSource(xml, 'SELECTED', 'SUPPORTED', row['source_id'], True))
        diagnostics = [d for d in diagnostics if not (d.source_id == row['source_id'] and d.error_code == 'FORMS2XML_REQUIRED')]
        provenance.append({'source_id': row['source_id'], 'source_sha256': row['source_sha256'],
                           'xml_sha256': row['xml_sha256'], 'tool_identity': json.loads(row['tool_identity_json'])})
    inventory = copy.deepcopy(result.inventory)
    inventory['candidates'] += len(roots)
    inventory['forms']['parseable'] += len(roots)
    inventory['forms']['fmb_without_xml'] = max(0, inventory['forms']['fmb_without_xml'] - len(roots))
    inventory['warnings'] = len(diagnostics)
    return replace(result, entries=tuple(entries), diagnostics=tuple(diagnostics), inventory=inventory,
                   derived_roots=tuple(roots), derived_provenance=tuple(provenance))


def convert_selected(access, sid, *, expected_configuration, confirmed, authorize):
    if confirmed is not True:
        raise ProjectError('Confirm explicit Forms2XML conversion before invoking Oracle tools')
    manager = ProjectJobManager(access, authorize)
    from .project_store import ProjectStore
    store = ProjectStore.open(access.root)
    try:
        revision = store.descriptor().analysis_revision
    finally:
        store.close()
    with manager.claim('CONVERT', expected_revision=revision, expected_configuration=expected_configuration) as lease:
        try:
            descriptor = lease.store.descriptor()
            discovery = discover_sources(access, descriptor, checkpoint=lease.checkpoint,
                                         progress=lease.progress, preview=False)
            selected = next((e.candidate for e in discovery.entries
                             if source_id(e.candidate.root_id, e.candidate.relative_path) == sid), None)
            if selected is None or Path(selected.relative_path).suffix.lower() != '.fmb':
                raise ProjectError('Select an FMB source from this project')
            source = authorized_roots(access, descriptor)[selected.root_id] / selected.relative_path
            original = fingerprint_sources(access.root, descriptor.source_roots, (selected,))[0]
            if original.status != 'available':
                raise ProjectError('Binary source is unavailable')
            lease.progress({'phase': 'CONVERSION', 'processed': 0, 'total': 1})
            try:
                tool = oracle.detect_toolchain()
            except oracle.OracleToolchainError:
                lease.finish('FAILED', {'error_code': 'FORMS2XML_UNAVAILABLE', 'safe_message': 'Oracle Forms tooling is unavailable.',
                    'remediation': 'Install/configure your licensed Oracle Forms tools, or export Forms2XML and select the XML folder.'})
            else:
                staging = access.root / '.formslang/runs'
                if staging.resolve() != staging:
                    raise ProjectError('Conversion staging was redirected')
                staging.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix='conversion-', dir=staging) as temporary:
                    work = Path(temporary)
                    with source.open('rb') as stream:
                        data = stream.read(MAX_SOURCE_BYTES + 1)
                    if len(data) > MAX_SOURCE_BYTES or hashlib.sha256(data).hexdigest() != original.sha256:
                        raise ProjectError('Binary source changed before conversion')
                    local = work / 'module.fmb'
                    local.write_bytes(data)
                    lease.checkpoint()
                    output = work / 'output'
                    xml, _log = oracle.convert_module(local, output, tool, timeout=180)
                    lease.checkpoint()
                    xml = Path(xml).absolute()
                    if xml.resolve() != xml or not xml.is_relative_to(output) or not xml.is_file() or xml.stat().st_size > MAX_SOURCE_BYTES:
                        raise ProjectError('Converter output is not a bounded staged XML file')
                    parser.parse_xml(xml)
                    if fingerprint_sources(access.root, descriptor.source_roots, (selected,))[0] != original:
                        raise ProjectError('Binary source changed during conversion')
                    content = xml.read_bytes()
                    digest = hashlib.sha256(content).hexdigest()
                    directory = derived_directory(access, sid, digest)
                    directory.mkdir(parents=True, exist_ok=True)
                    destination = directory / 'module.xml'
                    if destination.resolve() != destination:
                        raise ProjectError('Derived output was redirected')
                    if destination.exists():
                        if destination.read_bytes() != content:
                            raise ProjectError('Existing derived output has different content')
                    else:
                        os.replace(xml, destination)
                    lease.checkpoint()
                    tool_identity = {'adapter': 'oracle.convert_module', 'tool_version': 'unverified',
                        'configuration_sha256': hashlib.sha256(canonical_json([str(tool.oracle_home), str(tool.java_exe), tool.classpath]).encode()).hexdigest()}
                    with lease.store._write() as db:
                        lease.checkpoint()
                        if lease.store.configuration_revision() != expected_configuration:
                            raise RevisionConflict('Project configuration changed')
                        db.execute('INSERT OR REPLACE INTO project_derived_source VALUES (?,?,?,?,?)',
                            (sid, original.sha256, digest, destination.relative_to(access.root / '.formslang').as_posix(), canonical_json(tool_identity)))
                        db.execute('UPDATE project_configuration SET revision=revision+1 WHERE id=1')
                        finished = now()
                        db.execute("UPDATE project_job SET status='COMPLETED',finished_at=?,heartbeat=? WHERE job_id=?",
                                   (finished, finished, lease.job_id))
        except AnalysisCancelled:
            lease.finish('CANCELLED')
        except (ProjectError, OSError, ValueError, oracle.OracleToolchainError):
            lease.finish('FAILED', {'error_code': 'CONVERSION_FAILED', 'safe_message': 'Forms2XML conversion could not complete safely.',
                'remediation': 'Check Oracle Forms tooling and the XML export; original sources and previous selection are unchanged.'})
        job_id = lease.job_id
    return manager.get(job_id)
