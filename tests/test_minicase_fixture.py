"""minicase: the fixture the demo runs on.

The showcase is a coverage bench -- 5 blocks, 78 items, 55 triggers, 59 review
units -- and is the right module to *test* with. It is the wrong one to
*show*: nobody follows an argument while holding that much on screen. The
minicase exists for the other job, and these tests guard the three properties
that make it usable for it:

1. it stays small enough to walk through by hand;
2. it still covers every element the smallest complete case is required to
   demonstrate (``docs/assessment`` -- query, create/update, required field,
   business rule, failure path, evidence);
3. a rule whose approved code raises *silently* still ships the sentence the
   Forms trigger already showed the user.

The third is the claim the fixture's README makes about message provenance,
and the minicase is the only place a single module proves both origins at
once. The export here is offline: no SQLcl, no database. CI runs the
package through ``apex validate`` separately.
"""

from __future__ import annotations

import json
from pathlib import Path

from formslang.apexlang import export_apexlang
from formslang.convert import Proposal, build_tasks
from formslang.parser import parse_xml
from formslang.rules import AUTO
from formslang.store import APPROVED, Store

MINICASE = Path(__file__).parent / "fixtures" / "minicase" / "module.xml"

# The ceiling the fixture was designed against. It is not a technical limit --
# it is the point past which a viewer stops being able to hold the module in
# mind, which is the only reason this fixture exists instead of the showcase.
MAX_REVIEW_UNITS = 12


def _module():
    return parse_xml(MINICASE)


def _by_name(tasks) -> dict[str, object]:
    """Tasks keyed the way a reviewer names them: ``OWNER.TRIGGER``."""
    return {f"{t.owner}.{t.name}" if t.owner else t.name: t for t in tasks}


def test_minicase_stays_small_enough_to_demo():
    module = _module()
    tasks = build_tasks(module)

    assert len(module.blocks) == 1
    assert len(module.blocks[0].items) == 8
    assert not module.program_units

    # Six triggers, six review units: every trigger in the module has a body
    # worth reviewing, and nothing else does.
    assert len(tasks) == 6
    assert len(tasks) < MAX_REVIEW_UNITS, (
        f"the minicase grew to {len(tasks)} review units; past {MAX_REVIEW_UNITS} "
        "it is a second showcase, not a demo"
    )


def test_minicase_covers_the_six_required_elements():
    module = _module()
    block = module.blocks[0]
    tasks = _by_name(build_tasks(module))

    # 1. Query existing records -- the block restricts what it fetches.
    assert "BK_PRODUTO.PRE-QUERY" in tasks
    # 2. Create a record -- the key and the timestamp are assigned on insert.
    assert "BK_PRODUTO.PRE-INSERT" in tasks

    # 3. Required-field validation, which costs no review unit: it is a
    #    property, not code, and crosses as valueRequired.
    required = {i.name for i in block.items if i.required}
    assert required == {"PK_ID", "DS_NOME", "VL_PRECO"}

    # 4. A business rule that spans two fields, so it can only be a rule.
    rule = tasks["BK_PRODUTO.WHEN-VALIDATE-RECORD"]
    assert rule.verdict == AUTO
    assert "row validation" in rule.apex_hint.lower()

    # 5. A failure path a user can understand: a wrong check digit.
    failure = tasks["BK_PRODUTO.CD_BARRA.WHEN-VALIDATE-ITEM"]
    assert failure.verdict == AUTO
    assert "item validation" in failure.apex_hint.lower()

    # 6. Evidence linking rule to replacement: see the export test below,
    #    which reads the manifest the reviewer's decisions produce.


def test_a_silently_raising_rule_still_ships_the_message_the_form_had(tmp_path):
    """The three approved rules take both routes to an error message.

    Two carry their own sentence in ``raise_application_error``. The third
    raises ``value_error`` and says nothing -- so the only place its message
    can come from is the ``MESSAGE()`` of the Forms trigger it replaces. APEX
    prints the validation's ``errorMessage`` and never the error the code
    raises, so a rule that loses its sentence here loses it on screen.
    """
    module = _module()
    store = Store(tmp_path / "minicase.session.db")
    store.init_session(module.name, str(MINICASE))
    tasks = build_tasks(module)
    store.add_tasks(tasks)

    silent = "BK_PRODUTO.VL_PRECO.WHEN-VALIDATE-ITEM"
    approved = 0
    for task in tasks:
        if task.verdict != AUTO:
            continue
        key = f"{task.owner}.{task.name}"
        code = (
            "begin\n  raise value_error;\nend;"
            if key == silent
            else "begin\n  raise_application_error(-20001, 'aprovado pelo teste');\nend;"
        )
        store.save_proposal(task.id, Proposal(code=code, apex_target="Page validation"))
        store.set_decision(task.id, APPROVED, code=code, reviewer="pytest")
        approved += 1

    assert approved == 3, "the minicase should offer exactly three AUTO rules"

    result = export_apexlang(
        store, module, tmp_path / "out", {"alias": "minicase", "app_id": 19200}
    )
    store.close()

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    sources = [c["message_source"] for c in manifest["approved_components"]]
    assert sorted(sources) == ["Forms trigger", "approved code", "approved code"]

    pages = sorted((result.project / "pages").glob("*.apx"))
    text = "".join(p.read_text(encoding="utf-8") for p in pages)
    assert text.count("\n    validation forms-") == approved
    # The sentence below lives only in the Forms trigger's MESSAGE() call.
    assert 'errorMessage: "Preco deve ser maior que zero."' in text
    assert "Replace this text with the message" not in text
