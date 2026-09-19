"""Authorized source inventory; discovery is not a claim of semantic support."""

from __future__ import annotations

import os
import stat
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from . import database, parser
from .project_manifest import SourceCandidate, relative_source_path, source_id
from .project_model import ProjectDescriptor, ProjectError, validate_descriptor
from .projects import ProjectAccess

DISCOVERY_VERSION = 'project-discovery/1'
FORM_EXTENSIONS = frozenset({'.xml', '.fmb', '.pll', '.mmb', '.olb'})
DB_EXTENSIONS = frozenset({'.sql', '.pks', '.pkb', '.prc', '.fnc', '.trg', '.vw'})
IGNORED_DIRECTORIES = frozenset({'.git', '.formslang', '.worktrees', '.superpowers',
    '__pycache__', '.pytest_cache', '.ruff_cache', '.venv', 'venv', 'node_modules',
    'build', 'dist', 'target', 'artifacts', 'reports', 'scratch_tmp'})
MAX_SOURCE_BYTES = 268435456
MAX_FILES = 100000
MAX_DEPTH = 64
DB_FAMILIES = ('tables', 'views', 'package_specs', 'package_bodies', 'sequences')


@dataclass(frozen=True)
class SourceDiagnostic:
    source_id: str
    relative_path: str
    stage: str
    error_code: str
    safe_message: str
    remediation: str


@dataclass(frozen=True)
class DiscoveredSource:
    candidate: SourceCandidate
    lifecycle: str
    support: str
    original_binary_id: str | None = None
    freshness_verified: bool = False


@dataclass(frozen=True)
class DiscoveryResult:
    entries: tuple[DiscoveredSource, ...]
    diagnostics: tuple[SourceDiagnostic, ...]
    inventory: dict


def _redirected(path: Path) -> bool:
    info = path.lstat()
    return (stat.S_ISLNK(info.st_mode) or
            bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024)))


def authorized_roots(access: ProjectAccess, descriptor: ProjectDescriptor) -> dict[str, Path]:
    """Configuration is not permission. Check lexical spelling before resolution."""
    validate_descriptor(descriptor)
    if access.root.resolve() != access.root:
        raise ProjectError('Project root was redirected')
    result = {}
    for root in descriptor.source_roots:
        raw = Path(os.path.abspath(access.root / root.path))
        resolved = raw.resolve()
        if raw != resolved:
            raise ProjectError('Source root was redirected; select the original folder')
        if not any(base.resolve() == base and resolved.is_relative_to(base) for base in access.source_roots):
            raise PermissionError('Source lies outside host-approved roots')
        if '.formslang' in (p.lower() for p in raw.parts):
            raise ProjectError('Project storage cannot be a source root')
        if any(resolved.is_relative_to(access.root / name) for name in ('artifacts', 'reports')):
            raise ProjectError('Project output cannot be a source root')
        if any(resolved.is_relative_to(other) or other.is_relative_to(resolved) for other in result.values()):
            raise ProjectError('Duplicate or overlapping source roots')
        result[root.id] = resolved
    return result


def diagnostic(root_id: str, relative: str, code: str, message: str,
               remediation: str, stage: str = 'DISCOVERY') -> SourceDiagnostic:
    return SourceDiagnostic(source_id(root_id, relative), relative, stage, code, message, remediation)


def _inspect(path: Path) -> tuple[str, dict]:
    """Bound the read and inspect a local snapshot, not an unbounded parser read."""
    with path.open('rb') as stream:
        data = stream.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        return 'SOURCE_TOO_LARGE', {}
    with tempfile.TemporaryDirectory(prefix='formslang-preview-') as directory:
        staged = Path(directory) / ('source' + path.suffix.lower())
        staged.write_bytes(data)
        if path.suffix.lower() == '.xml':
            try:
                parser.parse_xml(staged)
                return 'SUPPORTED', {}
            except ValueError as exc:
                return ('UNSUPPORTED_XML' if 'no <FormModule>' in str(exc) else 'INVALID_XML'), {}
        parsed = database.parse_database_file(staged)
        counts = {family: len(getattr(parsed, family)) for family in DB_FAMILIES}
        supported = any(counts.values())
        counts['_package_names'] = sorted(set(parsed.package_specs) | set(parsed.package_bodies))
        return ('SUPPORTED' if supported else 'UNSUPPORTED_SQL'), counts


def discover_sources(access: ProjectAccess, descriptor: ProjectDescriptor, *,
                     checkpoint: Callable[[], None], progress: Callable[[dict], None],
                     preview: bool = True) -> DiscoveryResult:
    locations = authorized_roots(access, descriptor)
    entries, diagnostics = [], []
    physical_files, visited = set(), set()
    db_counts = Counter({family: 0 for family in DB_FAMILIES})
    package_names = set()
    traversed = 0

    def warn(root_id, relative, code, message, action='Select a supported representation or correct the source.'):
        diagnostics.append(diagnostic(root_id, relative, code, message, action))

    for root in descriptor.source_roots:
        checkpoint()
        location = locations[root.id]
        if not location.is_dir():
            warn(root.id, '__root__', 'MISSING_ROOT', 'Source folder is unavailable.', 'Relink the source folder.')
            continue
        stack = [(location, 0)]
        while stack:
            checkpoint()
            directory, depth = stack.pop()
            relative_dir = directory.relative_to(location).as_posix()
            relative_dir = '__root__' if relative_dir == '.' else relative_dir
            try:
                if _redirected(directory) or not directory.resolve().is_relative_to(location):
                    warn(root.id, relative_dir, 'REDIRECTED_PATH', 'Redirected directory was excluded.')
                    continue
                info = directory.stat()
                key = (info.st_dev, info.st_ino)
                if key in visited:
                    warn(root.id, relative_dir, 'DUPLICATE_DIRECTORY', 'Directory was already visited.')
                    continue
                visited.add(key)
                children = []
                with os.scandir(directory) as iterator:
                    for child in iterator:
                        checkpoint()
                        if traversed >= MAX_FILES:
                            warn(root.id, relative_dir, 'FILE_LIMIT', 'Source traversal entry limit reached.',
                                 'Select a smaller source scope.')
                            break
                        traversed += 1
                        children.append(child)
                children.sort(key=lambda e: (e.name.casefold(), e.name))
            except InterruptedError:
                raise
            except OSError:
                warn(root.id, relative_dir, 'UNREADABLE_DIRECTORY', 'Source directory could not be read.',
                     'Check folder permissions and retry discovery.')
                continue
            for child in children:
                checkpoint()
                path = Path(child.path)
                relative = path.relative_to(location).as_posix()
                candidate = None
                try:
                    relative_source_path(relative)
                    if _redirected(path) or not path.resolve().is_relative_to(location):
                        warn(root.id, relative, 'REDIRECTED_PATH', 'Redirected source was excluded.')
                        continue
                    if child.is_dir(follow_symlinks=False):
                        parts = [part.lower() for part in path.relative_to(location).parts]
                        benchmark_output = 'benchmark' in parts and child.name.lower() in {'outputs', 'output', 'baselines'}
                        if child.name.lower() in IGNORED_DIRECTORIES or benchmark_output:
                            continue
                        if depth >= MAX_DEPTH:
                            warn(root.id, relative, 'DEPTH_LIMIT', 'Source traversal depth limit reached.', 'Select a narrower source folder.')
                            continue
                        stack.append((path, depth + 1))
                        continue
                    suffix = path.suffix.lower()
                    if suffix not in FORM_EXTENSIONS | DB_EXTENSIONS:
                        continue
                    # DirEntry.stat on Windows can report st_ino=0 for every file.
                    info = path.stat(follow_symlinks=False)
                    representation = 'xml' if suffix == '.xml' else 'database' if suffix in DB_EXTENSIONS else 'binary'
                    selected = representation != 'binary'
                    candidate = SourceCandidate(root.id, relative, representation, selected)
                    support, lifecycle = 'DISCOVERED', 'DISCOVERED'
                    identity = (info.st_dev, info.st_ino)
                    if not stat.S_ISREG(info.st_mode):
                        selected, support, lifecycle = False, 'UNSUPPORTED_REPRESENTATION', 'EXCLUDED'
                        warn(root.id, relative, 'NOT_REGULAR_FILE', 'Non-regular source was excluded.')
                    elif identity in physical_files:
                        selected, support, lifecycle = False, 'DUPLICATE', 'EXCLUDED'
                        warn(root.id, relative, 'DUPLICATE_FILE', 'Physical source was already inventoried.')
                    elif info.st_size > MAX_SOURCE_BYTES:
                        support, lifecycle = 'UNSUPPORTED_REPRESENTATION', 'FAILED'
                        warn(root.id, relative, 'SOURCE_TOO_LARGE', 'Source exceeds the static input size limit.', 'Split the source or select a bounded export.')
                    elif representation == 'binary':
                        support = 'UNSUPPORTED_REPRESENTATION'
                    elif preview:
                        code, counts = _inspect(path)
                        package_names.update(counts.pop('_package_names', []))
                        db_counts.update(counts)
                        support = 'SUPPORTED' if code == 'SUPPORTED' else 'UNSUPPORTED_REPRESENTATION'
                        lifecycle = 'SUPPORTED' if code == 'SUPPORTED' else 'FAILED' if code == 'INVALID_XML' else 'DISCOVERED'
                        if code != 'SUPPORTED':
                            warn(root.id, relative, code, 'This source has no supported parseable representation.'
                                 if code != 'INVALID_XML' else 'XML could not be parsed.',
                                 'Check the XML export and retry.' if representation == 'xml' else
                                 'Supply supported table/view/package source; unsupported SQL needs human review.')
                    physical_files.add(identity)
                    entries.append(DiscoveredSource(replace(candidate, selected=selected), lifecycle, support))
                except (OSError, RuntimeError):
                    if candidate is not None:
                        entries.append(DiscoveredSource(candidate, 'FAILED', 'UNSUPPORTED_REPRESENTATION'))
                    warn(root.id, relative, 'UNREADABLE_SOURCE', 'Source could not be read.', 'Check permissions and retry.')
                progress({'phase': 'DISCOVERY', 'processed': len(entries), 'total': None,
                          'warnings_count': len(diagnostics)})

    # Pair independently of semantic preview: manifest selection must stay stable.
    xmls = {}
    for index, entry in enumerate(entries):
        candidate = entry.candidate
        if candidate.representation == 'xml' and entry.lifecycle != 'EXCLUDED':
            xmls.setdefault((candidate.root_id, candidate.relative_path.casefold()), []).append(index)
    for index, entry in enumerate(entries):
        candidate = entry.candidate
        if candidate.representation != 'binary' or entry.lifecycle == 'EXCLUDED':
            continue
        path = Path(candidate.relative_path)
        matches = []
        if path.suffix.lower() == '.fmb':
            for name in (path.stem + '_fmb.xml', path.stem + '.xml'):
                matches.extend(xmls.get((candidate.root_id, (path.parent / name).as_posix().casefold()), []))
        if len(matches) == 1:
            chosen = matches[0]
            entries[chosen] = replace(entries[chosen], original_binary_id=source_id(candidate.root_id, candidate.relative_path))
        else:
            code = 'AMBIGUOUS_XML_PAIR' if matches else 'FORMS2XML_REQUIRED' if path.suffix.lower() == '.fmb' else 'UNSUPPORTED_BINARY'
            warn(candidate.root_id, candidate.relative_path, code, 'Binary source requires a supported representation.',
                 'Select an unambiguous Forms2XML export, explicitly convert with configured Oracle tooling, or continue with available sources.')

    entries.sort(key=lambda e: (e.candidate.root_id, e.candidate.relative_path))
    diagnostics.sort(key=lambda d: (d.source_id, d.stage, d.error_code))
    fmbs = [e for e in entries if e.candidate.relative_path.lower().endswith('.fmb')]
    paired = {e.original_binary_id for e in entries if e.original_binary_id}
    db_counts['packages'] = len(package_names)
    inventory = {'candidates': len(entries), 'forms': {
        'discovered': sum(e.candidate.representation in {'xml', 'binary'} for e in entries),
        'parseable': sum(e.candidate.representation == 'xml' and e.support == 'SUPPORTED' for e in entries),
        'fmb_without_xml': sum(source_id(e.candidate.root_id, e.candidate.relative_path) not in paired for e in fmbs),
    }, 'database': dict(db_counts), 'warnings': len(diagnostics),
        'excluded': sum(e.lifecycle == 'EXCLUDED' for e in entries)}
    return DiscoveryResult(tuple(entries), tuple(diagnostics), inventory)
