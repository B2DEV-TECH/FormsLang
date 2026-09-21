"""Conservative authorization of scope; never a second modernization classifier."""

import re
from dataclasses import asdict

from . import plsql
from .project_model import TargetProfile

POLICY_VERSION = 'project-generation/1'
SUPPORTED_DIRECTIONS = frozenset({'PRESERVE', 'CONVERT', 'REFACTOR',
                                 'MOVE_TO_PLSQL_API', 'REPLACE_WITH_APEX_NATIVE'})


def target_code_supported(code, emitted_items):
    """Reject known unconverted runtime dependencies using existing lexical evidence."""
    evidence = plsql.evidence(code)
    analysis = plsql.analyze_evidence(code, evidence)
    if analysis.builtins or any(t.kind == 'incomplete' or t.value == 'FORM_TRIGGER_FAILURE'
                               for t in evidence['tokens']):
        return False
    system = {'APP_USER', 'APP_ID', 'APP_SESSION', 'APP_PAGE_ID', 'REQUEST'}
    for event in evidence['events']:
        if event['kind'] != 'BIND':
            continue
        name = event['name']
        if name.startswith('P0_'):
            name = 'P1_' + name[3:]
        if name not in emitted_items and (name not in system or event.get('access') == 'WRITE'):
            return False
    return True


def table_mapping_blockers(module, blueprint):
    """A sanitizer must never choose a different writable database object."""
    identifier = r'[A-Za-z][A-Za-z0-9_$#]{0,127}'
    tables = {n['name'].upper(): n for n in blueprint['entities'] if n['type'] == 'TABLE'}
    blockers = []
    for block in module.blocks:
        if not block.database_block:
            continue
        name = block.query_data_source_name.strip()
        observed = tables.get(name.upper())
        if (block.query_data_source_type.upper() != 'TABLE'
                or not re.fullmatch(identifier + r'(?:\.' + identifier + r')?', name)
                or observed is None):
            blockers.append({'code': 'UNSUPPORTED_TABLE_IDENTITY', 'id': block.name,
                             'message': 'Data-bound generation requires an explicit bare table identity matching observed DDL; quoted, remote and unknown targets remain blocked.'})
            continue
        columns = {c['name'].upper() for c in observed.get('attributes', {}).get('columns', [])}
        for item in block.items:
            if not item.database_item:
                continue
            column = item.column_name.strip() or item.name
            if not re.fullmatch(identifier, column) or column.upper() not in columns:
                blockers.append({'code': 'UNSUPPORTED_COLUMN_IDENTITY', 'id': f'{block.name}.{item.name}',
                                 'message': 'A data-bound item does not map unchanged to an observed table column.'})
    return blockers


def related_scope(blueprint, module):
    """Follow observed dependencies, retaining shared API/control findings."""
    included = {n['id'] for n in blueprint['entities'] if n.get('module') == module}
    outgoing = {}
    for edge in blueprint.get('edges', []):
        outgoing.setdefault(edge['source'], []).append(edge['target'])
    for node in blueprint['entities']:
        if node.get('resolved_target'):
            outgoing.setdefault(node['id'], []).append(node['resolved_target'])
    pending = list(included)
    while pending:
        for target in outgoing.get(pending.pop(), []):
            if target not in included:
                included.add(target)
                pending.append(target)
    return included


def module_blockers(assessment, module, plan, *, freshness, code_blockers):
    """Explicit blockers, from persisted evidence and independent approvals only."""
    blockers = []

    def add(code, identity, message):
        blockers.append({'code': code, 'id': identity, 'message': message})

    if freshness != 'CURRENT' or assessment.get('status') != 'Current':
        add('SOURCE_NOT_CURRENT', module, 'Refresh and complete the assessment before generation.')
    if assessment.get('target') != asdict(TargetProfile()):
        add('UNSUPPORTED_TARGET', module, 'Select a supported APEXlang target profile.')
    for field in ('security_confirmed', 'database_confirmed'):
        if plan.get(field) is not True or not str(plan.get('rationale', '')).strip():
            add('PREREQUISITE_NOT_CONFIRMED', field,
                'An architect must confirm the target security and database prerequisites with rationale.')
    bp = assessment['blueprint']
    included = related_scope(bp, module)
    if not any(n.get('module') == module and n.get('type') == 'FORM' for n in bp['entities']):
        add('MODULE_NOT_OBSERVED', module, 'Select an analyzed Forms representation.')
    nodes = {n['id']: n for n in bp['entities']}
    for identity in sorted(included):
        node = nodes.get(identity)
        if node is None or node.get('attributes', {}).get('missing'):
            add('UNRESOLVED_DEPENDENCY', identity, 'A required dependency has no observed representation.')
    for finding in sorted(bp['findings'], key=lambda f: f['id']):
        if finding['entity'] not in included:
            continue
        identity = finding['id']
        if finding.get('review_state') not in {'APPROVE', 'MODIFY'}:
            add('UNRESOLVED_REVIEW', identity, 'Resolve the current modernization decision before generation.')
        decision = finding.get('human_decision') or {}
        if decision.get('recommendation') not in SUPPORTED_DIRECTIONS:
            add('UNSUPPORTED_TARGET_DECISION', identity,
                'No supported reviewed target mapping authorizes this finding.')
        questions = set(finding.get('unresolved_questions', []))
        node = nodes.get(finding['entity'], {})
        observed_table = ((node.get('type') == 'TABLE' or
                           (node.get('type') == 'TABLE_OR_VIEW_REFERENCE'
                            and nodes.get(node.get('resolved_target'), {}).get('type') == 'TABLE'))
                          and plan.get('database_confirmed') is True
                          and decision.get('recommendation') == 'PRESERVE')
        structural = node.get('type') in {'FORM', 'BLOCK', 'ITEM', 'LOV', 'RECORD_GROUP', 'CANVAS', 'WINDOW'}
        if plan.get('mapping_confirmed') is True and (structural or observed_table):
            questions.discard('Confirm target behavior and ownership.')
        if questions:
            add('UNRESOLVED_ARCHITECTURE', identity,
                'Required architectural questions remain unresolved; acceptance alone does not answer them.')
    blockers.extend(code_blockers)
    return blockers
