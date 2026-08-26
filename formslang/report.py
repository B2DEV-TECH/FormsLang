"""Self-contained HTML report for the assessment.

No CDN, no remote fonts, no build step: a single file that opens on any
machine and can be emailed to a manager. FormsLang palette (gold on black).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from . import rules
from .assess import TIERS, PortfolioAssessment

_CSS = """
:root{--bg:#07090C;--surface:#12151A;--line:#242832;--fg:#F2F4F7;--mut:#8A9099;--gold:#F5A640}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:15px/1.6 "Segoe UI",Inter,system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:30px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:19px;margin:44px 0 14px;letter-spacing:-.01em;
 border-bottom:1px solid var(--line);padding-bottom:8px}
.sub{color:var(--mut);margin:0 0 28px;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.card .n{font-size:27px;font-weight:600;color:var(--gold);letter-spacing:-.02em}
.card .l{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.07em;margin-top:2px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:500;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tbody tr:hover{background:#0E1116}
code,.mono{font-family:"JetBrains Mono",Consolas,monospace;font-size:12.5px}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;
 letter-spacing:.03em}
.AUTO{background:#123021;color:#5BD98A}.DROP{background:#1B2430;color:#7FA8D9}
.ASSISTED{background:#3A2E10;color:var(--gold)}.MANUAL{background:#3A1618;color:#F0736F}
.UNKNOWN{background:#2A2430;color:#B98FE0}
.SIMPLE{background:#123021;color:#5BD98A}.MODERATE{background:#1B2430;color:#7FA8D9}
.COMPLEX{background:#3A2E10;color:var(--gold)}.REWRITE{background:#3A1618;color:#F0736F}
.bar{height:7px;border-radius:4px;background:#1B1F27;overflow:hidden;min-width:60px}
.bar i{display:block;height:100%;background:var(--gold)}
.note{background:#12151A;border-left:3px solid var(--gold);padding:13px 16px;border-radius:0 8px 8px 0;
 color:#C8CDD6;font-size:13.5px;margin:16px 0}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
footer{margin-top:56px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:16px}
"""


def _e(v: object) -> str:
    return html.escape(str(v))


def _tag(v: str) -> str:
    return f'<span class="tag {_e(v)}">{_e(v)}</span>'


def _cards(pairs: list[tuple[str, object]]) -> str:
    return '<div class="grid">' + "".join(
        f'<div class="card"><div class="n">{_e(n)}</div><div class="l">{_e(l)}</div></div>'
        for l, n in pairs
    ) + "</div>"


def _verdict_table(title: str, counts: dict[str, int]) -> str:
    total = sum(counts.values()) or 1
    rows = ""
    for v in rules.VERDICT_ORDER:
        n = counts.get(v, 0)
        if not n:
            continue
        pct = 100.0 * n / total
        rows += (
            f"<tr><td>{_tag(v)}</td><td class='n'>{n:,}</td><td class='n'>{pct:.1f}%</td>"
            f"<td><div class='bar'><i style='width:{pct:.1f}%'></i></div></td></tr>"
        )
    return (
        f"<h2>{_e(title)}</h2><div class='scroll'><table><thead><tr>"
        f"<th>Verdict</th><th class='n'>Occurrences</th><th class='n'>%</th><th>&nbsp;</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def render_html(pf: PortfolioAssessment, *, title: str, generated_at: str) -> str:
    d = pf.to_dict()
    summary, totals = d["summary"], d["totals"]

    top = sorted(pf.modules, key=lambda m: -m.net_points)[:40]
    rows_top = "".join(
        f"<tr><td class='mono'>{_e(m.name)}</td><td>{_tag(m.tier)}</td>"
        f"<td class='n'>{m.net_points:,.0f}</td><td class='n'>{m.blocks}</td>"
        f"<td class='n'>{m.items}</td><td class='n'>{m.triggers}</td>"
        f"<td class='n'>{m.plsql_lines:,}</td><td class='n'>{m.automatable_pct:.0f}%</td>"
        f"<td class='n'>{len(m.blockers)}</td></tr>"
        for m in top
    )

    rows_builtins = "".join(
        f"<tr><td class='mono'>{_e(name)}</td><td>{_tag(rules.classify_builtin(name)[0])}</td>"
        f"<td class='n'>{n:,}</td><td>{_e(rules.classify_builtin(name)[1])}</td></tr>"
        for name, n in d["top_builtins"]
    )

    rows_blockers = "".join(
        f"<tr><td class='mono'>{_e(name)}</td><td class='n'>{n}</td>"
        f"<td class='n'>{100.0 * n / max(1, len(pf.modules)):.0f}%</td>"
        f"<td>{_e(rules.classify_builtin(name)[1])}</td></tr>"
        for name, n in d["blockers_by_module"]
    )

    dup = d["duplication"]
    rows_dup = "".join(
        f"<tr><td class='mono'>{_e(s['name'])}</td><td>{_e(s['kind'])}</td>"
        f"<td class='n'>{s['lines']}</td><td class='n'>{s['modules']}</td>"
        f"<td class='n'>{s['instances']}</td>"
        f"<td class='n'>{s['redundant_points']:,.0f}</td></tr>"
        for s in dup["top"]
    )

    tiers = summary["by_tier"]
    rows_tier = ""
    for _lo, _hi, name, note in TIERS:
        n = tiers.get(name, 0)
        pct = 100.0 * n / max(1, len(pf.modules))
        rows_tier += (
            f"<tr><td>{_tag(name)}</td><td class='n'>{n}</td><td class='n'>{pct:.1f}%</td>"
            f"<td><div class='bar'><i style='width:{pct:.1f}%'></i></div></td>"
            f"<td>{_e(note)}</td></tr>"
        )

    trig_debt = d["catalog_debt"]["unknown_triggers"]
    call_debt = d["catalog_debt"]["uncatalogued_calls"]
    rows_debt = "".join(
        f"<tr><td class='mono'>{_e(n)}</td><td class='n'>{c:,}</td><td>uncatalogued call</td></tr>"
        for n, c in call_debt[:25]
    ) + "".join(
        f"<tr><td class='mono'>{_e(n)}</td><td class='n'>{c:,}</td><td>trigger outside the catalog</td></tr>"
        for n, c in trig_debt[:15]
    )

    failures = d["failures"]
    failures_block = ""
    if failures:
        rows_f = "".join(
            f"<tr><td class='mono'>{_e(f['file'])}</td><td>{_e(f['error'][:200])}</td></tr>"
            for f in failures[:40]
        )
        failures_block = (
            f"<h2>Modules that failed to convert ({len(failures)})</h2><div class='scroll'>"
            f"<table><thead><tr><th>File</th><th>Error</th></tr></thead>"
            f"<tbody>{rows_f}</tbody></table></div>"
        )

    cat = summary["catalog"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)} &mdash; FormsLang</title><style>{_CSS}</style></head>
<body><div class="wrap">
<h1>{_e(title)}</h1>
<p class="sub">Oracle Forms &rarr; Oracle APEX migration assessment &middot;
generated by <strong style="color:var(--gold)">FormsLang</strong> on {_e(generated_at)}</p>

{_cards([
    ("Modules analyzed", f"{summary['modules_analyzed']:,}"),
    ("Blocks", f"{totals['blocks']:,}"),
    ("Items", f"{totals['items']:,}"),
    ("Triggers", f"{totals['triggers']:,}"),
    ("Program units", f"{totals['program_units']:,}"),
    ("PL/SQL lines", f"{totals['plsql_lines']:,}"),
    ("Effort points", f"{summary['total_points']:,.0f}"),
    ("Automation-friendly", f"{summary['automatable_pct']:.0f}%"),
])}

<div class="note">
<strong>How to read these numbers.</strong> "Effort points" is a measure derived
from what was counted in each module's XML (structure, triggers, built-ins and
PL/SQL volume), weighted by migration difficulty. <strong>A point is not an
hour.</strong> The conversion to hours uses a factor of
<code>{summary['hours_per_point']}</code> h/point, which is a
<strong>calibration assumption, not a measurement</strong> &mdash; it only becomes a
trustworthy number after real modules have been converted and timed.
With the current factor: <strong>{summary['estimated_hours']:,.0f} h</strong>.
<br><br>
"Automation-friendly" is the share of triggers and built-ins the catalog
classifies as <span class="tag AUTO">AUTO</span> (direct APEX equivalent) or
<span class="tag DROP">DROP</span> (solves a problem APEX does not have). It is
not a promise of automatic screen conversion: it is the theoretical ceiling of
work a machine can take on by itself.
<br><br>
Effort points are <strong>deduplicated</strong>. Counting every copy of the same
boilerplate in full would report
<strong>{summary['raw_points']:,.0f}</strong> points; the code fingerprints show
{summary['duplication_savings']:,.0f} of those belong to blocks that exist in
more than one module and only have to be solved once. Copies keep a review cost
of {summary['duplicate_review_factor'] * 100:.0f}% &mdash; also an assumption.
</div>

<h2>Shared code: what is solved once, not once per form</h2>
<p class="sub">{dup['shared_blocks']:,} distinct code blocks appear byte for byte
in more than one module, in {dup['shared_instances']:,} copies out of
{dup['code_units']:,} code units in the portfolio. This is the signature of a
system built by cloning a template form &mdash; and it is the cheapest work in
the migration, because one conversion serves every copy.</p>
<div class="scroll"><table><thead><tr><th>Block</th><th>Kind</th>
<th class="n">Lines</th><th class="n">Modules</th><th class="n">Copies</th>
<th class="n">Points saved</th></tr></thead>
<tbody>{rows_dup}</tbody></table></div>

<h2>Distribution by complexity tier</h2>
<div class="scroll"><table><thead><tr><th>Tier</th><th class="n">Modules</th>
<th class="n">%</th><th>&nbsp;</th><th>What it means</th></tr></thead>
<tbody>{rows_tier}</tbody></table></div>

{_verdict_table("Triggers by verdict", d["triggers_by_verdict"])}
{_verdict_table("Built-ins by verdict (occurrences)", d["builtins_by_verdict"])}

<h2>Blockers: built-ins with no APEX equivalent</h2>
<p class="sub">Ordered by how many modules in the portfolio depend on each one.
These define the work no tool converts on its own.</p>
<div class="scroll"><table><thead><tr><th>Built-in</th><th class="n">Modules</th>
<th class="n">% of portfolio</th><th>What to do in APEX</th></tr></thead>
<tbody>{rows_blockers}</tbody></table></div>

<h2>Most used built-ins in the portfolio</h2>
<div class="scroll"><table><thead><tr><th>Built-in</th><th>Verdict</th>
<th class="n">Occurrences</th><th>APEX target</th></tr></thead>
<tbody>{rows_builtins}</tbody></table></div>

<h2>Highest-effort modules (top {len(top)})</h2>
<div class="scroll"><table><thead><tr><th>Module</th><th>Tier</th>
<th class="n">Points</th><th class="n">Blocks</th><th class="n">Items</th>
<th class="n">Triggers</th><th class="n">PL/SQL lines</th>
<th class="n">Friendly</th><th class="n">Blockers</th></tr></thead>
<tbody>{rows_top}</tbody></table></div>

<h2>Catalog debt</h2>
<p class="sub">What FormsLang found and cannot classify yet. None of it was
counted as easy &mdash; <span class="tag UNKNOWN">UNKNOWN</span> is weighted as
expensive precisely so the unknown is not hidden.
Current catalog: {cat['builtins']} built-ins, {cat['triggers']} triggers,
{cat['system_vars']} system variables, {cat['client_prefixes']} client-side prefixes.</p>
<div class="scroll"><table><thead><tr><th>Symbol</th><th class="n">Occurrences</th>
<th>Type</th></tr></thead><tbody>{rows_debt}</tbody></table></div>

{failures_block}

<footer>FormsLang &middot; B2DEV TECH &middot; report generated locally; no data leaves this machine.
Oracle, Oracle Forms and Oracle APEX are trademarks of Oracle Corporation; this
product is neither affiliated with nor endorsed by Oracle.</footer>
</div></body></html>"""


def write_reports(
    pf: PortfolioAssessment, out_dir: Path, *, title: str, generated_at: str
) -> tuple[Path, Path]:
    """Write the HTML + JSON reports and return both paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "assessment.html"
    json_path = out_dir / "assessment.json"
    html_path.write_text(
        render_html(pf, title=title, generated_at=generated_at), encoding="utf-8"
    )
    json_path.write_text(
        json.dumps(pf.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return html_path, json_path
