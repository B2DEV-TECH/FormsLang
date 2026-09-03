"""Shared fixtures.

The fixture module below is synthetic: it reproduces the shape Forms2XML
emits (namespace, attribute-held code, double-escaped newlines, cp1252
mojibake) without carrying a single line of third-party code.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every test gets an empty settings directory.

    Without this, a real ``config.json`` on the developer's machine would
    leak into the suite -- the offline default, for one, would stop being
    the default. The same goes for the credential store: the suite must
    never touch the developer's real keychain.
    """
    config_home = tmp_path / "formslang-config"
    monkeypatch.setenv("FORMSLANG_CONFIG_DIR", str(config_home))
    # The API key lives in the OS credential store, which a test suite has
    # no business writing to: a process-local backend, emptied per test.
    monkeypatch.setenv("FORMSLANG_SECRET_BACKEND", "memory")
    from formslang import secrets  # after the sys.path line above

    secrets.reset_memory_backend()
    return config_home


@pytest.fixture()
def auth_store(tmp_path: Path):
    """A fresh, isolated ``AuthStore`` -- never the developer's real ``auth.db``."""
    from formslang import authstore

    store = authstore.AuthStore(tmp_path / "auth.db")
    yield store
    store.close()


def setup_confirmed_mfa(auth_store, user_id: str) -> dict:
    """Enroll and confirm TOTP for a user, the way tests need it done.

    Confirmation uses the real two-consecutive-codes flow (current step,
    then the next step's code -- verify_code's +-1 window accepts the
    second one early). Afterwards the replay watermark is rewound far below
    the current window: production code never does this, but a test that
    logs the same user in more than once inside a single 30-second TOTP
    window needs earlier steps to be spendable again.

    Returns ``{"secret", "recovery_codes"}``.
    """
    from formslang import totp

    enrollment = auth_store.mfa_enroll(user_id)
    secret = enrollment["secret"]
    now = time.time()
    code1 = totp.generate_code(secret, at=now)
    code2 = totp.generate_code(secret, at=now + totp.PERIOD_SECONDS)
    recovery_codes = auth_store.mfa_confirm(user_id, code1, code2)
    auth_store.db.execute(
        "UPDATE mfa_secret SET last_accepted_step = last_accepted_step - 1000 "
        "WHERE user_id = ?",
        (user_id,),
    )
    return {"secret": secret, "recovery_codes": recovery_codes}


def next_mfa_code(auth_store, user_id: str, secret: str) -> str:
    """A TOTP code that is inside the verification window AND above the
    user's current replay watermark -- i.e. one that will actually be
    accepted right now. Starts at the earliest spendable step, so up to
    three same-user logins fit in one 30-second window."""
    from formslang import totp

    row = auth_store.db.execute(
        "SELECT last_accepted_step FROM mfa_secret WHERE user_id = ?", (user_id,)
    ).fetchone()
    last = row["last_accepted_step"] if row else None
    step = totp.current_step() - totp.DEFAULT_WINDOW
    if last is not None and last >= step:
        step = last + 1
    if step > totp.current_step() + totp.DEFAULT_WINDOW:
        raise RuntimeError(
            "too many MFA logins for this user inside one TOTP window -- "
            "spread the logins across users or wait a step"
        )
    return totp.generate_code(secret, at=step * totp.PERIOD_SECONDS)


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Module xmlns="http://xmlns.oracle.com/Forms" version="12.2.1.4.0">
  <FormModule Name="DEMO_ORDER" Title="Order entry" FirstNavigationBlockName="ORDERS">
    <Trigger Name="WHEN-NEW-FORM-INSTANCE"
             TriggerText="BEGIN&amp;#10;&amp;#9;GO_BLOCK('ORDERS');&amp;#10;&amp;#9;-- HOST('notepad.exe');&amp;#10;END;"/>
    <Trigger Name="KEY-CLRFRM" TriggerText="CLEAR_FORM;"/>
    <Trigger Name="WHEN-BANANA-SPLIT" TriggerText="NULL;"/>
    <Trigger Name="WHEN-CUSTOM-ITEM-EVENT"
             TriggerText="BEGIN&amp;#10;  WEBUTIL_CORE.CUSTOMEVENTHANDLER;&amp;#10;END;"/>
    <Block Name="ORDERS" DatabaseBlock="true" QueryDataSourceName="ORDERS"
           RecordsDisplayCount="1">
      <Trigger Name="PRE-INSERT"
               TriggerText="BEGIN&amp;#10;  :ORDERS.CREATED := SYSDATE;&amp;#10;END;"/>
      <Item Name="ORDER_ID" ItemType="Text Item" DataType="Number"
            ColumnName="ORDER_ID" DatabaseItem="true" Required="true"
            CanvasName="CV_MAIN" XPosition="20" YPosition="20" Width="100" Height="17"/>
      <Item Name="CUSTOMER" ItemType="Text Item" DataType="Char"
            ColumnName="CUSTOMER" DatabaseItem="true" Prompt="ConexÃ£o"
            LovName="LOV_CUSTOMER"
            CanvasName="CV_MAIN" XPosition="20" YPosition="50" Width="200" Height="17">
        <Trigger Name="WHEN-VALIDATE-ITEM"
                 TriggerText="BEGIN&amp;#10;  IF :ORDERS.CUSTOMER IS NULL THEN&amp;#10;    MESSAGE('required');&amp;#10;  END IF;&amp;#10;END;"/>
      </Item>
      <Item Name="BTN_PRINT" ItemType="Push Button" DatabaseItem="false"
            CanvasName="CV_MAIN" XPosition="20" YPosition="90" Width="80" Height="24">
        <Trigger Name="WHEN-BUTTON-PRESSED"
                 TriggerText="BEGIN&amp;#10;  WEBUTIL_FILE.FILE_SELECTION_DIALOG(:GLOBAL.DIR);&amp;#10;  HOST('print.bat');&amp;#10;END;"/>
      </Item>
    </Block>
    <ProgramUnit Name="P_TOTAL" ProgramUnitType="Procedure"
                 ProgramUnitText="PROCEDURE P_TOTAL IS&amp;#10;BEGIN&amp;#10;  SELECT 1 INTO :ORDERS.ORDER_ID FROM DUAL;&amp;#10;END;"/>
    <RecordGroup Name="RG_CUSTOMER" RecordGroupType="Query"
                 RecordGroupQuery="SELECT NAME, ID FROM CUSTOMERS"/>
    <LOV Name="LOV_CUSTOMER" RecordGroupName="RG_CUSTOMER" Title="Customers">
      <LOVColumnMapping Name="NAME"/>
      <LOVColumnMapping Name="ID"/>
    </LOV>
    <Canvas Name="CV_MAIN" CanvasType="Content" WindowName="WIN_MAIN"
            Width="640" Height="480" ViewportWidth="600" ViewportHeight="400"/>
    <Window Name="WIN_MAIN"/>
    <Alert Name="AL_CONFIRM"/>
    <AttachedLibrary Name="DEMO_LIB"/>
  </FormModule>
</Module>
"""


@pytest.fixture()
def sample_xml(tmp_path: Path) -> Path:
    path = tmp_path / "DEMO_ORDER_fmb.xml"
    path.write_text(SAMPLE_XML, encoding="utf-8")
    return path
