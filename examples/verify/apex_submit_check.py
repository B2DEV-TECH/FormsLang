"""Submit an imported page the way the browser does, and read what came back.

``apex_render_check.py`` proves the page renders. This proves the last thing
the chain never showed: that APEX's page-processing engine runs the
validations FormsLang exported from Forms triggers, and where the message
lands on the screen.

It logs in as the same disposable end user, GETs the page, and POSTs
``wwv_flow.accept`` twice:

1. with the item under test empty -- the rule must reject the submit;
2. with a valid value in it -- that same rule must not appear.

Both responses are saved. Nothing is written to the application.
"""

from __future__ import annotations

import argparse
import base64
import html as htmlmod
import json
import re
import secrets as pysecrets
import urllib.parse
import urllib.request
from collections import OrderedDict
from http.cookiejar import CookieJar
from pathlib import Path

# Same directory, same disposable user, same login: this is the second half of
# the render check, not a separate harness.
import apex_render_check as rc

ITEM_RE = re.compile(
    r'<(input|select|textarea)\b(?P<attrs>[^>]*)>', re.IGNORECASE
)
ATTR_RE = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')


def form_items(page: str, page_no: int) -> OrderedDict[str, str]:
    """Every named page item on the form, with the value the page rendered."""
    items: OrderedDict[str, str] = OrderedDict()
    prefix = f"P{page_no}_"
    for m in ITEM_RE.finditer(page):
        attrs = dict(ATTR_RE.findall(m.group("attrs")))
        name = attrs.get("name", "")
        if not name.startswith(prefix):
            continue
        # A checkbox or radio that is not checked submits nothing.
        kind = attrs.get("type", "").lower()
        if kind in {"checkbox", "radio"} and "checked" not in m.group("attrs").lower():
            items.setdefault(name, "")
            continue
        items[name] = htmlmod.unescape(attrs.get("value", ""))
    return items


def item_checksums(page: str) -> dict[str, str]:
    """item -> checksum, from the companion ``<input data-for="ITEM">``."""
    out: dict[str, str] = {}
    for m in ITEM_RE.finditer(page):
        attrs = dict(ATTR_RE.findall(m.group("attrs")))
        target = attrs.get("data-for")
        if target and "value" in attrs:
            out[target] = htmlmod.unescape(attrs["value"])
    return out


def protected_names(protected: str) -> set[str]:
    """The item names APEX packed into pPageItemsProtected, for exclusion."""
    # APEX breaks the base64 into ".,"-separated chunks that continue each
    # other: decoding them one by one truncates the name on every boundary
    # (P1_TOKEN_SESS + AO). Join first, then decode once.
    blob = protected.split("/")[0].replace(".,", "")
    pad = "=" * (-len(blob) % 4)
    try:
        text = base64.b64decode(blob + pad).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - an undecodable blob tells us nothing
        return set()
    return {n for n in text.split(":") if n}


def inline_errors(page: str) -> list[dict]:
    """Field-level messages, as APEX renders them beside the item."""
    # Universal Theme renders the field-level message as
    # <div class="t-Form-error"><div id="ITEM_error">text</div></div>, inside
    # the item's own container -- a <span> only in older templates.
    out = []
    for m in re.finditer(
        r'<(?:div|span)[^>]*\bid="(P\d+_[A-Z0-9_]+)_error"[^>]*>(.*?)</(?:div|span)>',
        page,
        re.DOTALL,
    ):
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if text:
            out.append({"item": m.group(1), "message": htmlmod.unescape(text)})
    return out


def notification_errors(page: str) -> list[str]:
    """Messages in the page-level notification region."""
    out = []
    for m in re.finditer(
        r'<li[^>]*class="[^"]*a-Notification-item[^"]*"[^>]*>(.*?)</li>',
        page,
        re.DOTALL,
    ):
        text = re.sub(r"<[^>]+>", " ", m.group(1))
        text = htmlmod.unescape(re.sub(r"\s+", " ", text)).strip()
        if text:
            out.append(text)
    if not out:
        banner = r'<div[^>]*t-Alert--danger.*?</div>\s*</div>\s*</div>'
        for m in re.finditer(banner, page, re.DOTALL):
            text = re.sub(r"<[^>]+>", " ", m.group(0))
            text = htmlmod.unescape(re.sub(r"\s+", " ", text)).strip()
            if text:
                out.append(text[:400])
    return out


def submit(opener, ords: str, app: int, page_no: int, page_html: str,
           overrides: dict[str, str], request: str) -> str:
    """POST the page exactly as the browser's own submit does."""
    fields = {
        k: rc.hidden_value(page_html, k)
        for k in ("pFlowId", "pFlowStepId", "pInstance", "pPageSubmissionId",
                  "pSalt", "pPageItemsProtected", "pPageItemsRowVersion")
    }
    items = form_items(page_html, page_no)
    items.update(overrides)
    # A protected item travels with its own checksum -- the browser reads it
    # from the companion <input data-for="ITEM" value="CK">. Submitting the
    # item without its ck is a page protection violation.
    checksums = item_checksums(page_html)
    to_submit = []
    for name, value in items.items():
        entry = {"n": name, "v": value}
        if name in checksums:
            entry["ck"] = checksums[name]
        to_submit.append(entry)
    p_json = json.dumps({
        "pageItems": {
            "itemsToSubmit": to_submit,
            "protected": fields["pPageItemsProtected"],
            "rowVersion": fields["pPageItemsRowVersion"],
            "formRegionChecksums": [],
        },
        "salt": fields["pSalt"],
    })
    body = urllib.parse.urlencode({
        "p_flow_id": fields["pFlowId"] or str(app),
        "p_flow_step_id": fields["pFlowStepId"] or str(page_no),
        "p_instance": fields["pInstance"],
        "p_page_submission_id": fields["pPageSubmissionId"],
        "p_request": request,
        "p_reload_on_submit": "S",
        "p_json": p_json,
    }).encode()
    req = urllib.request.Request(
        f"{ords}/wwv_flow.accept",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Referer": f"{ords}/f?p={app}:{page_no}"},
    )
    with opener.open(req, timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def run(args, pwd: str) -> list[dict]:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (FormsLang verification)")]
    session = rc.login(opener, args.ords, args.app, args.login_page, pwd)
    if not session:
        return [{"ok": False, "why": "login not accepted"}]

    results = []
    for label, overrides in (
        ("empty", {args.item: ""}),
        ("valid", {args.item: args.good}),
    ):
        with opener.open(f"{args.ords}/f?p={args.app}:{args.page}:{session}", timeout=120) as r:
            page_html = r.read().decode("utf-8", "replace")
        answer = submit(opener, args.ords, args.app, args.page, page_html,
                        overrides, args.request)
        out = args.out_dir / f"submit{args.app}_p{args.page}_{label}.html"
        out.write_text(answer, encoding="utf-8")
        results.append({
            "case": label,
            f"{args.item}": overrides[args.item],
            "file": str(out),
            "bytes": len(answer),
            "inline_errors": inline_errors(answer),
            "notification_errors": notification_errors(answer),
            "ora_20001": sorted(set(re.findall(r"ORA-20001[^<\"\\n]{0,120}", answer))),
            "error_banner": "t-Alert--danger" in answer,
        })
    return results


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out_dir", type=Path)
    p.add_argument("--app", type=int, default=190122)
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--item", default="P1_VL_PRECO")
    p.add_argument("--good", default="19.90")
    p.add_argument("--request", default="SAVE")
    p.add_argument("--ords", default="http://localhost:8080/ords")
    p.add_argument("--workspace", default="FORMSLANG")
    p.add_argument("--schema", default="FORMSLANG")
    p.add_argument("--login-page", type=int, default=9999)
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    sql = rc.SqlRunner()
    pwd = "Fl" + pysecrets.token_urlsafe(18) + "9!"
    print(rc.create_user(sql, args.workspace, args.schema, pwd))
    try:
        results = run(args, pwd)
    finally:
        print(rc.remove_user(sql, args.workspace))
    print(json.dumps(results, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
