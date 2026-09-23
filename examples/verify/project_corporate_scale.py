"""Real synthetic source pipeline and persisted operations; no customer benchmark."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from formslang.project_model import SourceRoot
from formslang.project_service import ProjectService
from formslang.projects import local_project_access


def peak_memory():
    if os.name != 'nt':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    class Counters(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
            'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    value = Counters()
    value.cb = ctypes.sizeof(value)
    current = ctypes.windll.kernel32.GetCurrentProcess
    current.restype = ctypes.c_void_p
    getter = ctypes.windll.psapi.GetProcessMemoryInfo
    getter.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    if not getter(current(), ctypes.byref(value), value.cb):
        raise OSError('Could not measure process peak working set')
    return value.PeakWorkingSetSize


def write_fixture(run, count):
    forms, database = run / 'sources/forms', run / 'sources/database'
    forms.mkdir(parents=True)
    database.mkdir()
    for index in range(count):
        items = '<Item Name="MESSAGE" ItemType="Display Item" Prompt="Message"/>' if index == 0 else ''.join(
            f'<Item Name="VALUE_{item}" ItemType="Text Item" Prompt="Value {item}">'
            f'<Trigger Name="WHEN-VALIDATE-ITEM" TriggerText="BEGIN SCALE_API.check_value(:INFO.VALUE_{item}); END;"/>'
            '</Item>' for item in range(12))
        (forms / f'module_{index:04d}.xml').write_text(
            f'<Module xmlns="http://xmlns.oracle.com/Forms"><FormModule Name="SCALE_{index:04d}"><Block Name="INFO" DatabaseBlock="false">'
            + items + '</Block></FormModule></Module>', encoding='utf-8')
    (database / 'scale.sql').write_text('''CREATE TABLE SCALE_VALUES (ID NUMBER PRIMARY KEY, VALUE NUMBER);
CREATE OR REPLACE PACKAGE SCALE_API AS PROCEDURE check_value(p_value NUMBER); END SCALE_API;
/
CREATE OR REPLACE PACKAGE BODY SCALE_API AS
PROCEDURE check_value(p_value NUMBER) IS v_count NUMBER; BEGIN
SELECT COUNT(*) INTO v_count FROM SCALE_VALUES WHERE VALUE = p_value;
IF v_count = 0 THEN raise_application_error(-20001, 'Synthetic value not found'); END IF;
END check_value; END SCALE_API;
/
''', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forms', type=int, choices=(100, 500), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run = args.output.resolve() / ('run-' + uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    os.environ['FORMSLANG_AUTH'] = '0'
    write_fixture(run, args.forms)
    service = ProjectService(local_project_access(run / 'project', approved_roots=(run,)))
    metrics = {}
    result = {'forms_requested': args.forms, 'platform': platform.platform(), 'python': platform.python_version(),
        'processor': platform.processor(), 'commit': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(), 'timings_ms': metrics,
        'fixture': 'One display-only generation control; remaining modules each have 12 validation triggers calling a shared synthetic package.',
        'limitations': 'Single local synthetic run; no customer/analyst claim. Generation measures one eligible independent display module, not full-estate conversion.'}
    def measure(name, action):
        start = time.perf_counter()
        value = action()
        metrics[name] = round((time.perf_counter() - start) * 1000, 3)
        print(name + ': ' + str(metrics[name]) + ' ms', flush=True)
        return value
    try:
        service.create('Corporate scale synthetic', roots=(SourceRoot('forms', 'forms', '../sources/forms'),
                       SourceRoot('database', 'database', '../sources/database')))
        measure('discovery', service.discover)
        outcome = measure('analysis', lambda: service.analyze(expected_revision=None, expected_configuration=0))
        if outcome['status'] != 'COMPLETED':
            raise AssertionError(outcome)
        assessment = service.assessment()
        result['analysis_stages'] = json.loads(service._store.session.db.execute(
            'SELECT metadata_json FROM project_analysis_run WHERE job_id=?', (outcome['job_id'],)).fetchone()[0])
        fresh = service.freshness()
        summary = measure('cold_overview', lambda: service.overview(freshness=fresh))
        measure('warm_overview', lambda: service.overview(freshness=fresh))
        # 2.2 visual projections over the same saved assessment.
        measure('visual_overview', lambda: service.visual_overview(freshness=fresh))
        estate = measure('system_map_estate', lambda: service.system_map(view='ESTATE', freshness=fresh))
        # Focus the Form with the most outbound relationships, not the display-only control module.
        focus = max((n for n in estate['nodes'] if n['type'] == 'FORM'), key=lambda n: (n['fan_out'], n['id']))['id']
        focused = measure('system_map_focus', lambda: service.system_map(focus=focus, freshness=fresh))
        measure('system_map_node', lambda: service.system_map_node(focus, freshness=fresh))
        hotspots = measure('hotspot_explorer', lambda: service.hotspot_explorer(freshness=fresh))
        measure('module_360', lambda: service.module_view(node=focus, freshness=fresh))
        result['visual'] = {'estate_nodes_shown': len(estate['nodes']), 'estate_edges_shown': len(estate['edges']),
                            'estate_nodes_total': estate['total_estate_nodes'], 'estate_edges_total': estate['total_estate_edges'],
                            'focus_nodes_shown': len(focused['nodes']), 'focus_edges_shown': len(focused['edges']),
                            'hotspots_total': hotspots['total']}
        if not estate['edges'] or len(focused['nodes']) < 2:
            raise AssertionError('System Map measurement did not exercise relationships: ' + json.dumps(result['visual']))
        result['inventory'] = summary['inventory']
        if summary['inventory']['forms_modules'] != args.forms:
            raise AssertionError('Module count mismatch')
        measure('inventory_first_page', lambda: service.inventory('forms', freshness=fresh))
        measure('inventory_filter', lambda: service.inventory('findings', filters={'risk': 'HIGH'}, freshness=fresh))
        measure('inventory_search', lambda: service.inventory('findings', query='module_0099', freshness=fresh))
        page = measure('review_queue', service.review_queue)
        detail = measure('review_detail', lambda: service.review_detail(page['rows'][0]['id']))
        command = {**detail['binding'], 'action': 'DEFER', 'findings': [
            {'id': row['id'], 'revision': row['finding_revision']} for row in page['rows']]}
        preview = measure('bulk_preview', lambda: service.review_bulk_preview(command))
        measure('bulk_apply', lambda: service.review_bulk_apply({**command, 'preview_token': preview['preview_token']}))
        scopes = service.generation_overview()
        module = next(m for m in scopes['modules'] if m['module'].endswith('module_0000.xml'))
        sid = module['source_id']
        measure('generation_prepare', lambda: service.generation_prepare(sid, scopes['binding']))
        for finding in service.review_queue(filters={'module': module['module']})['rows']:
            detail = service.review_detail(finding['id'])
            service.review_decide(finding['id'], {**detail['binding'], 'action': 'APPROVE'})
        detail = service.generation_module(sid)
        detail = service.generation_configure(sid, {**detail['binding'], 'code_revision': detail['code_revision'],
            'target_revision': detail['target_revision'], 'plan': {'security_confirmed': True,
            'database_confirmed': True, 'mapping_confirmed': True, 'keys': {},
            'rationale': 'Synthetic display-only control, no data writes; authentication reviewed for fixture.'}})
        artifact = measure('generation_one_display_module', lambda: service.generate({**detail['binding'], 'scopes': [detail]}))
        report = service.report_overview()
        executive = measure('report_executive', lambda: service.report_export('executive', report['binding']))
        result['executive_report_bytes'] = len(executive.body)
        delivery = measure('report_package', lambda: service.report_export('package', report['binding'], include_artifacts=True))
        result.update(package_bytes=len(delivery.body), artifact_bytes=artifact['size_bytes'],
                      analysis_revision=assessment['analysis_revision'], process_peak_bytes=peak_memory())
        service.close()
        reopened = measure('reopen_summary', lambda: service.overview(freshness=service.freshness()))
        if reopened['assessment']['analysis_revision'] != assessment['analysis_revision']:
            raise AssertionError('Reopen changed assessment')
        result['passed'] = True
    except Exception as exc:
        result.update(passed=False, error=repr(exc))
        raise
    finally:
        service.close()
        (run / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('Evidence: ' + str(run), flush=True)


if __name__ == '__main__':
    main()
