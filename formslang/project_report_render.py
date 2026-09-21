"""Pure, escaped delivery rendering. Inputs are projections, never parser/AI calls."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import re

from .project_reports import json_bytes
from .project_review import STATES
from .report import _CSS

LIMITATIONS = [
    'Static candidates are not verified business intent. Dynamic SQL and missing representations limit evidence.',
    'AUTO describes intervention, not generation authorization, effort or project duration.',
    'Review, code approval, generation and validation are separate states.',
    'Generated output is a selected-module scope, not proof of complete migration.',
    'Offline syntax validation is not runtime equivalence, security acceptance or UAT.',
    'Source bodies, credentials and private reviewer identifiers are not part of these reports.',
    'No automatic DDL, import or deployment occurs. Oracle does not endorse this product.',
]
LABELS = {'PRESERVE': 'Preserve', 'CONVERT': 'Convert', 'REFACTOR': 'Refactor',
          'MOVE_TO_PLSQL_API': 'Move to PL/SQL API', 'REPLACE_WITH_APEX_NATIVE': 'Use Native APEX',
          'MANUAL_REVIEW': 'Human Review', 'DROP': 'Drop', 'UNKNOWN': 'Unresolved'}


def public_value(value):
    """Defense in depth for metadata; never a substitute for omitting source bodies."""
    if isinstance(value, str):
        if re.search(r'''(?i)(?<![a-z0-9])[a-z]:[\\/]|\\\\|(?:^|[\s"'(])/(?!/)[^\s]+|\b(?:password|passwd|pwd|secret|token)\s*[:=]''', value):
            return '[Potential host path or credential assignment omitted]'
        return value
    if isinstance(value, (list, tuple)):
        return [public_value(v) for v in value]
    if isinstance(value, dict):
        return {k: public_value(v) for k, v in value.items()}
    return value


def display(value):
    if value is None:
        return 'Not assessed'
    if type(value) is bool:
        return 'Yes' if value else 'No'
    if isinstance(value, (list, tuple)):
        return '; '.join(display(v) for v in value)
    if isinstance(value, dict):
        return '; '.join(f'{k}: {display(v)}' for k, v in value.items())
    return str(value)


def escape(value):
    return html.escape(display(value), quote=True)


def table(rows, columns):
    head = ''.join(f'<th scope="col">{escape(label)}</th>' for _, label in columns)
    body = ''.join('<tr>' + ''.join(f'<td>{escape(row.get(key))}</td>' for key, _ in columns) + '</tr>' for row in rows)
    return f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>' if rows else '<p>No observations in the saved assessment for this section.</p>'


def pairs(values):
    return table([{'name': str(k).replace('_', ' '), 'value': v} for k, v in values.items()], [('name', 'Measure'), ('value', 'Observed value')])


def section(title, body):
    return f'<section><h2>{escape(title)}</h2>{body}</section>'


def page(title, snapshot, sections):
    o = snapshot['overview']
    a = o['assessment']
    meta = {'FormsLang': snapshot['formslang_version'], 'Assessment timestamp': a['assessment_timestamp'],
            'Source revision': a['source_revision'], 'Analysis revision': a['analysis_revision'],
            'Review revision': a['review_revision'], 'Snapshot': snapshot['snapshot_revision'],
            'Engine fingerprint': hashlib.sha256(json_bytes(snapshot['engine_identity'])).hexdigest()}
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        f'<title>{escape(title)} — FormsLang</title><style>{_CSS}'
        'td{overflow-wrap:anywhere}section{break-inside:auto}thead{display:table-header-group}'
        '@media print{body,.card{background:white;color:black}.wrap{padding:0;max-width:none}th,.sub{color:#333}a{color:black}h2{break-after:avoid}}'
        f'</style></head><body><main class="wrap"><h1>{escape(title)}</h1>'
        f'<p class="sub">{escape(o["project"]["name"])} · {escape(o["project"]["target"])}</p>'
        f'<p><strong>Saved assessment: {escape(a["freshness"])} / {escape(a["status"])}</strong></p>'
        '<p>This deliverable records the saved assessment and its human decisions. It is not a migration-complete or runtime-parity claim.</p>'
        + ''.join(sections) + section('Provenance', pairs(meta))
        + '<footer>FormsLang — Oracle Forms to APEX Modernization Workbench. No external resources or scripts are required.</footer></main></body></html>').encode('utf-8')


def csv_bytes(rows, columns):
    stream = io.StringIO(newline='')
    # csv.writer only quotes characters present in the lineterminator: with LF
    # alone Python 3.10 emits an embedded CR raw and the file stops being CSV.
    writer = csv.writer(stream, lineterminator='\r\n')
    writer.writerow(columns)
    for row in rows:
        values = []
        for column in columns:
            value = display(row.get(column, ''))
            # Whitespace/control prefixes do not make spreadsheet formulas safe.
            if value.lstrip().lstrip('\ufeff').lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return ('\ufeff' + stream.getvalue()).encode('utf-8')


def markdown(value):
    return re.sub(r'([\\`*_{}\[\]()!#<>])', r'\\\1', display(value)).replace('\n', ' ')


def build_files(snapshot, *, include_notes, artifact_files):
    snapshot = public_value(snapshot)
    o = snapshot['overview']
    rows = snapshot['inventory']
    # Explicit allowlists prevent stored source/evidence/reviewer fields leaking.
    decisions = snapshot['decisions']
    if not include_notes:
        for decision in decisions:
            for event in decision['history']:
                event.pop('rationale', None)
            for annotation in decision['annotations']:
                annotation.pop('note', None)
    by_id = {d['finding_id']: d for d in decisions}
    provenance = {'formslang_version': snapshot['formslang_version'], **o['assessment'],
                  'snapshot_revision': snapshot['snapshot_revision'], 'human_notes_included': include_notes,
                  'sensitivity': 'Sensitive human notes' if include_notes else 'Technical identifiers; source bodies and notes excluded'}
    csv_provenance = {'FormsLang Version': snapshot['formslang_version'],
        'Snapshot Revision': snapshot['snapshot_revision'], 'Source Revision': o['assessment']['source_revision'],
        'Analysis Revision': o['assessment']['analysis_revision'], 'Review Revision': o['assessment']['review_revision'],
        'Assessment Timestamp': o['assessment']['assessment_timestamp'], 'Assessment Status': o['assessment']['freshness'],
        'Sensitivity': provenance['sensitivity']}
    backlog = []
    for row in rows['findings']:
        decision = by_id[row['id']]
        backlog.append({'ID': row['id'], 'Application': o['project']['name'], 'Module': row['module'],
            'Component': row['name'], 'Source Type': row['source_type'], 'Recommendation': row['recommendation'],
            'Human Decision': decision['human_decision'], 'Risk': row['risk'], 'Intervention': row['intervention'],
            'Review Status': STATES.get(row['review_state'], 'Pending'), 'Target': row['target'],
            'Reason': row['reason'], 'Dependencies': row['dependencies'],
            'Notes': decision['history'][0].get('rationale', '') if include_notes and decision['history'] else '',
            **csv_provenance})
    columns = ['ID', 'Application', 'Module', 'Component', 'Source Type', 'Recommendation', 'Human Decision',
               'Risk', 'Intervention', 'Review Status', 'Target', 'Reason', 'Dependencies', 'Notes', *csv_provenance]
    unresolved = [b for b in backlog if b['Review Status'] not in {'Accepted', 'Changed'}]
    common = [section('Scope', pairs({'Application': o['project']['name'], 'Target': o['project']['target'],
                    'Assessment': o['assessment']['freshness'], 'Completion': o['assessment']['completion_state']})),
              section('Application Inventory', pairs(o['inventory'])),
              section('Source Coverage', pairs(o['source_coverage'])),
              section('Risk Distribution', pairs(o['risk_distribution'])),
              section('Modernization Direction', pairs({LABELS.get(k, k): v for k, v in o['recommendation_distribution'].items()})),
              section('Automation / Intervention Distribution', pairs(o['intervention_distribution']) +
                      '<p>Based on modernization categories, not effort or project-duration estimation. AUTO is not generation-ready.</p>')]
    artifact_rows = []
    validations = {v['artifact_id']: v for v in snapshot['validation_evidence']}
    exclusions = {e['artifact_id']: e['reason'] for e in snapshot['exclusions']}
    for artifact in snapshot['artifacts']:
        validation = validations.get(artifact['artifact_id'], {})
        artifact_rows.append({'artifact_id': artifact['artifact_id'], 'source_id': artifact['source_id'],
            'sha256': artifact['sha256'], 'created_at': artifact['created_at'],
            'validation_status': ('Not Validated' if exclusions.get(artifact['artifact_id']) == 'ARTIFACT_INTEGRITY'
                                  else validation.get('status', 'Not Validated')),
            'validation': validation, 'inclusion': exclusions.get(artifact['artifact_id'], 'Included'),
            'analysis_revision': artifact['analysis_revision'], 'review_revision': artifact['review_revision'],
            'target_revision': artifact['target_revision'], 'code_revision': artifact['code_revision'],
            'excluded_source_ids': artifact.get('excluded_source_ids', [])})
    generation = section('Generation Readiness', '<p>Not assessed by report export. Use Generate for current eligibility. Existing artifacts below are historical byte-bound evidence, not authorization to deploy.</p>' +
        table(artifact_rows, [('source_id', 'Scope'), ('artifact_id', 'Artifact'), ('inclusion', 'Package inclusion')]))
    validation = section('Validation Status', table(artifact_rows, [('artifact_id', 'Artifact'), ('validation_status', 'Recorded syntax status')]) +
                         '<p>Validation applies only to the recorded hash; edited files and runtime behavior are not covered.</p>')
    limitations = section('Known Limitations', '<ul>' + ''.join(f'<li>{escape(v)}</li>' for v in LIMITATIONS) + '</ul>')
    critical = [b for b in backlog if b['Risk'] == 'CRITICAL']
    executive = page('Executive Assessment', snapshot, [
        section('Executive Summary', '<p>FormsLang inventories and triages observed legacy structure so specialists can focus on architectural and business decisions. Counts below describe analyzed evidence, not the completeness of an unknown estate.</p>'),
        *common, section('Critical Findings', table(critical, [('Module', 'Module'), ('Component', 'Component'),
            ('Recommendation', 'Engine recommendation'), ('Review Status', 'Review status')])),
        section('Architecture Summary', '<p>Target: Oracle APEX applications supported by reviewed PL/SQL/database boundaries. Recommendations remain proposals until reviewed; no synthesized runtime equivalence is claimed.</p>'),
        section('Human Decisions Required', pairs(o['review_progress']) + pairs(o['priority'])), generation, validation,
        limitations, section('Recommended Next Steps', '<ol><li>Resolve missing representations and stale source.</li><li>Review critical and manual decisions with business owners.</li><li>Confirm database/security prerequisites and code approvals.</li><li>Generate eligible scope, validate syntax, then test behavior and UAT.</li></ol>'),
        section('Methodology', '<p>Deterministic static analysis, persisted evidence, human review overlays and source fingerprints. No calibrated labor, cost or duration estimate is provided.</p>')])
    inventory_sections = []
    for key, title in [('forms', 'Forms Structure'), ('libraries', 'Library Representations'), ('packages', 'Database Packages'),
                       ('routines', 'Procedures and Functions'), ('tables', 'Tables'), ('views', 'Views')]:
        inventory_sections.append(section(title, table(rows[key], [('name', 'Name'), ('source_type', 'Type'),
            ('findings', 'Findings'), ('highest_risk', 'Highest risk')])))
    technical = page('Technical Assessment', snapshot, [*common, *inventory_sections,
        section('Cross-layer Dependencies', table(rows['dependencies'], [('source', 'Source'), ('target', 'Target'), ('relationship', 'Relationship')])),
        section('Business Rule Candidates', table(rows['business_rules'], [('name', 'Candidate'), ('module', 'Module'), ('candidate_kind', 'Evidence category')])),
        section('Duplicate Logic / API Ownership', table([r for r in rows['findings'] if r['evidence_factors']],
                [('name', 'Component'), ('module', 'Module'), ('evidence_factors', 'Observed factors')])),
        section('Modernization Findings / APEX Target Mapping', table(backlog, [('ID', 'Finding'), ('Module', 'Module'),
            ('Recommendation', 'Engine recommendation'), ('Human Decision', 'Human decision'), ('Risk', 'Risk'),
            ('Review Status', 'Review'), ('Target', 'Suggested target'), ('Reason', 'Reason')])),
        section('Database Prerequisites', '<p>Review observed object identities, supported row keys, APIs, permissions and security behavior in Generate. No database change is applied by this report.</p>'),
        section('Unresolved Decisions', table(unresolved, [('ID', 'Finding'), ('Review Status', 'Status'), ('Recommendation', 'Direction')])),
        generation, validation, limitations])
    risk = page('Risk Report', snapshot, [section('Risk Distribution', pairs(o['risk_distribution'])),
        section('Observed Findings', table(backlog, [('ID', 'Finding'), ('Module', 'Module'), ('Risk', 'Risk'),
                ('Recommendation', 'Direction'), ('Review Status', 'Review')])), limitations])
    inventory = {key: [{k: v for k, v in row.items() if not k.startswith('_')} for row in category] for key, category in rows.items()}
    architecture = '# Proposed target architecture\n\nEngine suggestions, not deployed architecture.\n\n' + '\n'.join(
        f'- {markdown(b["ID"])}: {markdown(b["Target"])} ({markdown(b["Review Status"])})' for b in backlog)
    candidates = '# Refactoring candidates — review required\n\nNo executable SQL is generated by this report.\n\n' + '\n'.join(
        f'- {markdown(b["ID"])}: {markdown(b["Recommendation"])} — {markdown(b["Reason"])}' for b in backlog
        if b['Recommendation'] in {'REFACTOR', 'MOVE_TO_PLSQL_API'})
    files = {
        'README.md': ('# Modernization package\n\nStart with assessment/executive-summary.html.\n'
            'Technical reports, backlog and decision metadata share one saved snapshot.\n'
            'APEXlang is present only when explicitly requested and verified.\n'
            'This is not a complete migration or permission to deploy. See manifest exclusions.\n'
            + ('Sensitive human notes included by explicit request.\n' if include_notes else 'Human notes and source bodies excluded.\n')).encode(),
        'assessment/executive-summary.html': executive, 'assessment/technical-assessment.html': technical,
        'assessment/risk-report.html': risk, 'assessment/application-inventory.json': json_bytes(inventory),
        'architecture/target-architecture.md': architecture.encode(),
        'architecture/dependency-map.json': json_bytes(inventory['dependencies']),
        'architecture/modernization-decisions.json': json_bytes({'metadata': provenance, 'rows': decisions}),
        'database/prerequisites.md': '# Database prerequisites — review required\n\nConfirm observed tables, columns, row keys, APIs, grants and security in Generate. No DDL is executed.\n'.encode(),
        'database/refactoring-candidates.md': candidates.encode(),
        'backlog/modernization-backlog.csv': csv_bytes(backlog, columns),
        'backlog/modernization-backlog.json': json_bytes({'metadata': provenance, 'rows': backlog}),
        'review/decisions.json': json_bytes({'metadata': provenance, 'rows': decisions}), 'review/unresolved-decisions.csv': csv_bytes(unresolved, columns),
        'evidence/analysis.json': json_bytes({'disclosure': 'Structural projection only; source bodies and private identities excluded.',
            'engine_identity': snapshot['engine_identity'], 'source_manifest': snapshot['source_manifest'],
            'assessment': o['assessment'], 'findings': inventory['findings'], 'warnings': o['warnings']}),
        **artifact_files,
    }
    manifest = {'schema': snapshot['schema'], 'formslang_version': snapshot['formslang_version'],
        'project_id': o['project']['id'], **o['assessment'], 'target_profile': o['project']['target'],
        'snapshot_revision': snapshot['snapshot_revision'], 'artifact_revision': hashlib.sha256(json_bytes(artifact_rows)).hexdigest(),
        'generation_timestamp': [a['created_at'] for a in artifact_rows], 'artifacts': artifact_rows,
        'exclusions': snapshot['exclusions'], 'limitations': LIMITATIONS, 'human_notes_included': include_notes,
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['manifest.json'] = json_bytes(manifest)
    return files
