"""Observed window/canvas declarations; never infer a runtime layout."""

from collections import defaultdict


def project_window_canvas(builder, mod, key):
    """Keep property evidence independent from resolution of its local target.

    Empty parsed values mean no declared target value. The model cannot distinguish
    an absent XML attribute from an explicitly empty one. Legacy model objects
    without the property remain UNAVAILABLE instead of acquiring a default.
    """
    nodes = {(e['type'], e['name']): e for e in builder.entities.values()
             if e['module'] == key}
    candidates = defaultdict(list)
    for typ, objects in (('CANVAS', mod.canvases), ('WINDOW', mod.windows)):
        for obj in objects:
            name = obj if isinstance(obj, str) else obj.name
            candidates[typ, name.upper()].append(nodes[typ, name]['id'])

    def declaration(node, value, prop, attr, state_attr, target_type, relation):
        status = {'resolution': 'UNAVAILABLE' if value is None else 'NOT_DECLARED',
                  'conflict': False, 'conflicting_evidence': []}
        node['attributes'][state_attr] = status
        count = len(candidates[node['type'], node['name'].upper()])
        if count > 1:
            status.update(resolution='AMBIGUOUS', reason='SOURCE_DECLARATION_AMBIGUOUS',
                          source_declaration_count=count)
            return None
        if value is None:
            return None
        node['attributes'][attr] = value
        if not value:
            return None
        proof = builder.proof(key, node['name'], f'{prop}: {value}', source=key)
        node['evidence'] = sorted(set(node['evidence']) | {proof})
        matches = candidates[target_type, value.upper()]
        status['resolution'] = ('RESOLVED' if len(matches) == 1 else
                                'AMBIGUOUS' if matches else 'UNRESOLVED')
        if len(matches) == 1:
            target = matches[0]
        else:
            target = builder.node(target_type + '_REFERENCE', value, key,
                                  evidence=[proof], resolution=status['resolution'],
                                  candidates=sorted(set(matches)))
        edge_id = builder.edge(node['id'], target, relation, proof)
        edge = builder.edges[edge_id]
        edge['placement'] = status
        return edge

    canvas_edges = {}
    for canvas in mod.canvases:
        name = canvas if isinstance(canvas, str) else canvas.name
        node = nodes['CANVAS', name]
        edge = declaration(node, getattr(canvas, 'window_name', None), 'WindowName',
                           'window_name', 'window_placement', 'WINDOW', 'CANVAS_IN_WINDOW')
        if edge:
            canvas_edges[node['id']] = edge
    for name in mod.windows:
        node = nodes['WINDOW', name]
        details = getattr(mod, 'window_details', {}).get(name)
        primary = declaration(node, getattr(details, 'primary_canvas', None),
                              'PrimaryCanvas', 'primary_canvas', 'primary_canvas_placement', 'CANVAS',
                              'WINDOW_PRIMARY_CANVAS')
        if not primary or primary['placement']['resolution'] != 'RESOLVED':
            continue
        canvas = canvas_edges.get(primary['target'])
        declared_window = builder.entities[primary['target']]['attributes'].get('window_name', '')
        if canvas and declared_window.upper() != name.upper():
            for edge, other in ((primary, canvas), (canvas, primary)):
                state = edge['placement']
                state['conflict'] = True
                state['conflicting_evidence'] = sorted(
                    set(state['conflicting_evidence']) | set(other['evidence']))
