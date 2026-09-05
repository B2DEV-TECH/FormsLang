"""Render an imported page through ORDS and inspect the HTML, without making it public.

``formslang apex validate`` proves the package compiles and ``formslang apex
import`` proves APEX accepts it; neither sees a defect that only shows when
the page is rendered. This script does that last mile the way a person
would, and leaves nothing behind:

1. creates a temporary *end user* in the workspace (``apex_util.create_user``
   with no developer privileges and a random password that never leaves this
   process);
2. logs in over HTTP exactly as the browser does (login page 9999,
   ``wwv_flow.accept``) and fetches the page with the session cookie;
3. saves the HTML and prints a small inspection: regions, Interactive Grids
   with their headings, item types, textareas, region titles, and the signs of a
   broken page (error banner, ``LABEL_COLUMN_SPAN``, ``ORA-`` errors,
   absolute positioning, layout scripts);
4. removes the temporary user, even when a fetch fails.

The database connection, SQLcl path and password come from the saved
FormsLang connection (``formslang apex`` settings, credential store or
``FORMSLANG_APEX_PASSWORD``). No password is ever an argument or logged.

Usage:
    python examples/verify/apex_render_check.py OUT_DIR APP:PAGE [APP:PAGE ...]
        [--ords http://localhost:8080/ords] [--workspace FORMSLANG]
        [--schema FORMSLANG] [--login-page 9999]
"""

from __future__ import annotations

import argparse
import html as htmlmod
import json
import os
import re
import secrets as pysecrets
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter
from http.cookiejar import CookieJar
from pathlib import Path

from formslang import apeximport, secrets
from formslang import config as cfg

TEMP_USER = "FL_VERIFY_TMP"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("targets", nargs="+", metavar="APP:PAGE")
    parser.add_argument("--ords", default="http://localhost:8080/ords")
    parser.add_argument("--workspace", default="FORMSLANG")
    parser.add_argument("--schema", default="FORMSLANG")
    parser.add_argument("--login-page", type=int, default=9999)
    return parser.parse_args()


class SqlRunner:
    """Runs a SQLcl script on the saved connection; the password stays on stdin."""

    def __init__(self) -> None:
        conf = cfg.load_config()
        self.sqlcl = conf.get("sqlcl_path") or apeximport.sqlcl_binary()
        self.connect = conf["apex_connect_string"]
        self.user = conf["apex_username"]
        self.password = os.environ.get("FORMSLANG_APEX_PASSWORD") or secrets.get_secret(
            apeximport.SERVICE, apeximport.account_key(self.user, self.connect)
        )
        if not self.password:
            sys.exit(
                "no saved password for the APEX connection (run `formslang apex` once, or set FORMSLANG_APEX_PASSWORD)"
            )

    def run(self, script: str, *hide: str) -> str:
        stdin = (
            f"connect {self.user}/{self.password}@{self.connect}\n"
            "set serveroutput on size unlimited feedback off\n"
            f"{script}\nexit\n"
        )
        env = dict(os.environ, MSYS_NO_PATHCONV="1")
        result = subprocess.run(
            [self.sqlcl, "-S", "-thin", "/nolog"],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
            check=False,
        )
        out = result.stdout + result.stderr
        for secret in (self.password, *hide):
            out = out.replace(secret, "***")
        return out.strip()


def create_user(sql: SqlRunner, workspace: str, schema: str, pwd: str) -> str:
    return sql.run(
        "begin\n"
        f"  apex_util.set_security_group_id(apex_util.find_security_group_id(p_workspace => '{workspace}'));\n"
        f"  apex_util.create_user(p_user_name => '{TEMP_USER}', p_web_password => '{pwd}',\n"
        "    p_email_address => 'fl_verify@example.invalid', p_developer_privs => null,\n"
        f"    p_default_schema => '{schema}', p_change_password_on_first_use => 'N');\n"
        "  commit;\n"
        "  dbms_output.put_line('temporary user created');\n"
        "end;\n/\n",
        pwd,
    )


def remove_user(sql: SqlRunner, workspace: str) -> str:
    return sql.run(
        "begin\n"
        f"  apex_util.set_security_group_id(apex_util.find_security_group_id(p_workspace => '{workspace}'));\n"
        f"  apex_util.remove_user(p_user_name => '{TEMP_USER}');\n"
        "  commit;\n"
        "  dbms_output.put_line('temporary user removed');\n"
        "end;\n/\n"
    )


def hidden_value(page: str, id_: str) -> str:
    """The value of a hidden input, with HTML entities decoded (APEX escapes '/')."""
    m = re.search(r'<input[^>]*\bid="' + re.escape(id_) + r'"[^>]*\bvalue="([^"]*)"', page)
    if not m:
        m = re.search(r'<input[^>]*\bvalue="([^"]*)"[^>]*\bid="' + re.escape(id_) + r'"', page)
    return htmlmod.unescape(m.group(1)) if m else ""


def login(opener, ords: str, app: int, login_page: int, pwd: str) -> str | None:
    """Logs in as the temporary user; returns the APEX session id, or None."""
    login_url = f"{ords}/f?p={app}:{login_page}"
    with opener.open(login_url, timeout=60) as r:
        login_html = r.read().decode("utf-8", "replace")
    fields = {
        k: hidden_value(login_html, k)
        for k in (
            "pFlowId",
            "pFlowStepId",
            "pInstance",
            "pPageSubmissionId",
            "pSalt",
            "pPageItemsProtected",
            "pPageItemsRowVersion",
        )
    }
    m = re.search(r"request:\s*['\"](\w+)['\"]", login_html)
    request = m.group(1) if m else "LOGIN"
    p_json = json.dumps(
        {
            "pageItems": {
                "itemsToSubmit": [
                    {"n": f"P{login_page}_USERNAME", "v": TEMP_USER},
                    {"n": f"P{login_page}_PASSWORD", "v": pwd},
                ],
                "protected": fields["pPageItemsProtected"],
                "rowVersion": fields["pPageItemsRowVersion"],
                "formRegionChecksums": [],
            },
            "salt": fields["pSalt"],
        }
    )
    body = urllib.parse.urlencode(
        {
            "p_flow_id": fields["pFlowId"] or str(app),
            "p_flow_step_id": fields["pFlowStepId"] or str(login_page),
            "p_instance": fields["pInstance"],
            "p_page_submission_id": fields["pPageSubmissionId"],
            "p_request": request,
            "p_reload_on_submit": "S",
            "p_json": p_json,
        }
    ).encode()
    req = urllib.request.Request(
        f"{ords}/wwv_flow.accept",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": login_url},
    )
    with opener.open(req, timeout=60) as r:
        after_login = r.read().decode("utf-8", "replace")
    if f"P{login_page}_USERNAME" in after_login:
        return None
    return fields["pInstance"]


def interactive_grids(page: str) -> list[dict]:
    """Headings of every Interactive Grid the page initialises (hidden columns are not
    sent to the client: check them in the APEX dictionary, see the runbook)."""
    grids = []
    for m in re.finditer(r"#(\w+)_ig['\"]\);[\w$]*\.interactiveGrid\(", page):
        start, depth, i = m.end(), 0, m.end()
        while i < len(page):
            if page[i] == "{":
                depth += 1
            elif page[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        blob = page[start : i + 1]
        headings = re.findall(
            r'"heading"\s*:\s*\{[^}]*"heading"\s*:\s*"([^"]*)"', blob
        ) or re.findall(r'"heading":"([^"]*)"', blob)
        grids.append(
            {
                "region": m.group(1),
                "headings": headings,
                "editable": '"editable":true' in blob.replace(" ", ""),
            }
        )
    return grids


def inspect(page: str) -> dict:
    region_classes = re.findall(r'class="(t-Region|t-IRR-region|t-TabsRegion)[ "]', page)
    return {
        "title": (re.search(r"<title>(.*?)</title>", page, re.DOTALL) or [None, ""])[
            1
        ].strip(),
        "regions": Counter(region_classes).most_common(),
        "interactive_grids": interactive_grids(page),
        "form_fields": len(re.findall(r'class="t-Form-fieldContainer', page)),
        "date_pickers": len(re.findall(r"<a-date-picker", page)),
        "number_fields": len(re.findall(r'inputmode="decimal"', page)),
        "textareas": re.findall(r'<textarea[^>]*\brows="(\d+)"[^>]*\bcols="(\d+)"', page),
        "region_titles": [
            t.strip()
            for t in re.findall(
                r'<h2[^>]*class="[^"]*t-Region-title[^"]*"[^>]*>([^<]*)<', page
            )
        ],
        "buttons": len(re.findall(r'class="t-Button', page)),
        "error_banner": bool(re.search(r"t-Alert--danger|t-Alert--warning", page)),
        "label_column_span_error": "LABEL_COLUMN_SPAN" in page,
        "ora_errors": re.findall(r"ORA-\d{5}[^<]{0,80}", page)[:5],
        "absolute_positioning": len(re.findall(r"position:\s*absolute", page)),
        "layout_script": bool(re.search(r"\.css\(\s*['\"](top|left|position)", page)),
    }


def render(args, app: int, page: int, pwd: str) -> dict:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (FormsLang verification)")]
    session = login(opener, args.ords, app, args.login_page, pwd)
    if not session:
        return {"app": app, "page": page, "ok": False, "why": "login not accepted"}
    with opener.open(f"{args.ords}/f?p={app}:{page}:{session}", timeout=120) as r:
        html_text = r.read().decode("utf-8", "replace")
        status = r.status
    out = args.out_dir / f"render{app}_p{page}.html"
    out.write_text(html_text, encoding="utf-8")
    return {
        "app": app,
        "page": page,
        "ok": True,
        "status": status,
        "file": str(out),
        "bytes": len(html_text),
        **inspect(html_text),
    }


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    targets = [tuple(int(x) for x in t.split(":")) for t in args.targets]
    sql = SqlRunner()
    pwd = "Fl" + pysecrets.token_urlsafe(18) + "9!"
    print(create_user(sql, args.workspace, args.schema, pwd))
    results = []
    try:
        for app, page in targets:
            try:
                results.append(render(args, app, page, pwd))
            except Exception as exc:  # noqa: BLE001 - report and keep going, the user is removed below
                results.append({"app": app, "page": page, "ok": False, "why": repr(exc)})
    finally:
        print(remove_user(sql, args.workspace))
    print(json.dumps(results, indent=1, ensure_ascii=False))
    if not all(r.get("ok") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
