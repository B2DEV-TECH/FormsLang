"""Sample warm read latency (p50/p95) on a project saved by project_corporate_scale.py.

The scale script takes one measurement per operation. This script reopens the saved
project, discards the first call of each operation and reports p50/p95 over N warm
samples, the response size and the traced allocation peak of a focused System Map.
It reads only; it never analyses, decides or writes.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from formslang.project_service import ProjectService
from formslang.projects import local_project_access


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('run', type=Path, help='run-* directory written by project_corporate_scale.py')
    parser.add_argument('--samples', type=int, default=10)
    args = parser.parse_args()
    os.environ['FORMSLANG_AUTH'] = '0'
    run = args.run.resolve()
    service = ProjectService(local_project_access(run / 'project', approved_roots=(run,)))
    samples, sizes, first = {}, {}, {}

    def timed(name, action, into):
        start = time.perf_counter()
        value = action()
        into.setdefault(name, []).append((time.perf_counter() - start) * 1000)
        sizes[name] = len(json.dumps(value, default=str).encode())
        return value

    try:
        fresh = timed('freshness', service.freshness, first)
        estate = timed('system_map_estate', lambda: service.system_map(view='ESTATE', freshness=fresh), first)
        # Same focus rule as the scale script: the Form with the most outbound relationships.
        focus = max((n for n in estate['nodes'] if n['type'] == 'FORM'), key=lambda n: (n['fan_out'], n['id']))['id']
        operations = {
            'overview': lambda: service.overview(freshness=fresh),
            'system_map_estate': lambda: service.system_map(view='ESTATE', freshness=fresh),
            'system_map_focus': lambda: service.system_map(focus=focus, freshness=fresh),
            'system_map_node': lambda: service.system_map_node(focus, freshness=fresh),
            'module_360': lambda: service.module_view(node=focus, freshness=fresh),
        }
        for name, action in operations.items():
            if name not in first:
                timed(name, action, first)
        for _ in range(args.samples):
            for name, action in operations.items():
                timed(name, action, samples)
            timed('freshness', service.freshness, samples)
        tracemalloc.start()
        service.system_map(focus=focus, freshness=fresh)
        traced_peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    finally:
        service.close()
    result = {
        'run': run.name, 'samples_per_operation': args.samples, 'focus': focus,
        'first_call_after_reopen_ms': {name: round(values[0], 1) for name, values in first.items()},
        'warm': {name: {'n': len(values), 'p50_ms': round(statistics.median(values), 1),
                        'p95_ms': round(percentile(values, 0.95), 1), 'min_ms': round(min(values), 1),
                        'max_ms': round(max(values), 1), 'response_bytes': sizes[name]}
                 for name, values in samples.items()},
        'traced_peak_focus_bytes': traced_peak,
        'limitations': 'One machine, one synthetic project, sequential calls in one process.',
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
