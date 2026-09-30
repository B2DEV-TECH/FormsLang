"""Package occurrence projection within an explicitly bound Blueprint analysis."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from . import database, database_identity


class _PackageProjection:
    def __init__(self, project, scope):
        self.project = project
        self.scope = scope if scope is not None and scope.identity is not None else None
        if self.scope and any(d.source_file not in scope.sources for d in project.package_declarations):
            self.scope = None
        self.symbols = database_identity.package_symbols(project) if self.scope else []
        self._occurrences = {(s.source_file, s.ordinal): s for s in self.symbols}
        self.ids = {}
        self._local = defaultdict(list)

    def rows(self, kind):
        if self.scope:
            return [(d.qualified_name, d.parsed, d) for d in self.project.package_declarations
                    if d.kind == kind]
        family = self.project.package_specs if kind == 'PACKAGE' else self.project.package_bodies
        return [(name, parsed, None) for name, parsed in family.items()]

    def occurrence(self, declaration, member=0):
        if declaration is None:
            return None
        if member == -1:
            parent = self.occurrence(declaration)
            return replace(parent, key=('CONSTANT_DECLARATION', *parent.key[1:]),
                           ordinal=(declaration.order, -1))
        return self._occurrences[(declaration.source_file, (declaration.order, member))]

    def attributes(self, declaration, member=0):
        occurrence = self.occurrence(declaration, member)
        if occurrence is None:
            return {}
        return {'identity': database_identity._entity_id(self.scope, occurrence),
                'owner': declaration.owner, 'symbol_key': list(occurrence.key),
                'source_line': occurrence.line, 'declaration_order': list(occurrence.ordinal),
                'analysis_identity': self.scope.identity}

    def register(self, builder, family, name, nid, declaration, member=0):
        occurrence = self.occurrence(declaration, member)
        if occurrence:
            self.ids[occurrence] = nid
        key = ('database', family, name)
        self._local[key].append(nid)
        if len(self._local[key]) == 1:
            builder.local[key] = nid
        else:
            builder.local.pop(key, None)

    def implementation(self, declaration, member):
        occurrence = self.occurrence(declaration, member)
        if occurrence is None or occurrence.key[1] is None:
            return None
        expected = ('PACKAGE_SUBPROGRAM', *occurrence.key[1:])
        matches = [s for s in self.symbols if s.key == expected]
        bodies = [s for s in self.symbols if s.key == occurrence.key]
        return self.ids.get(matches[0]) if len(matches) == len(bodies) == 1 else None

    def resolve(self, reference, *, package=False):
        if not package:
            return database_identity.resolve_package_reference(reference, self.symbols)
        parts = database_identity._reference_parts(reference)
        if parts is None or len(parts) not in {1, 2}:
            return database_identity.Resolution('UNRESOLVED', 'UNSUPPORTED_REFERENCE', ())
        owner, name = (None, parts[0]) if len(parts) == 1 else parts
        matches = [s for s in self.symbols if s.key[0] in {'PACKAGE', 'PACKAGE BODY'}
                   and s.key[2] == name and (owner is None or s.key[1] == owner)]
        spec_owners = {s.key[1] for s in matches if s.key[0] == 'PACKAGE'}
        matches = tuple(s for s in matches if s.key[0] == 'PACKAGE' or s.key[1] not in spec_owners)
        status, reason = ('UNRESOLVED', 'NO_COMPATIBLE_DECLARATION')
        if len(matches) > 1:
            status, reason = 'AMBIGUOUS', 'MULTIPLE_DECLARATIONS'
        elif matches:
            status, reason = (('UNRESOLVED', 'MISSING_SCHEMA_CONTEXT') if owner is None
                              else ('RESOLVED', 'UNIQUE_STATIC_DECLARATION'))
        return database_identity.Resolution(status, reason, matches)

    @staticmethod
    def member_name(package, member, declaration):
        if declaration is None:
            return f'{package}.{member}'.upper()
        # Decoded names are quoted for display only; typed keys carry identity.
        return package + '.' + database._qualified_part('"' + member + '"')
