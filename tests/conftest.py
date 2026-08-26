"""Shared fixtures.

The fixture module below is synthetic: it reproduces the shape Forms2XML
emits (namespace, attribute-held code, double-escaped newlines, cp1252
mojibake) without carrying a single line of customer code.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
            ColumnName="ORDER_ID" DatabaseItem="true" Required="true"/>
      <Item Name="CUSTOMER" ItemType="Text Item" DataType="Char"
            ColumnName="CUSTOMER" DatabaseItem="true" Prompt="ConexÃ£o"
            LOVName="LOV_CUSTOMER">
        <Trigger Name="WHEN-VALIDATE-ITEM"
                 TriggerText="BEGIN&amp;#10;  IF :ORDERS.CUSTOMER IS NULL THEN&amp;#10;    MESSAGE('required');&amp;#10;  END IF;&amp;#10;END;"/>
      </Item>
      <Item Name="BTN_PRINT" ItemType="Push Button" DatabaseItem="false">
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
    <Canvas Name="CV_MAIN"/>
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
