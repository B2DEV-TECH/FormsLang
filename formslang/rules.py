"""Forms -> APEX knowledge base.

This is FormsLang's core asset: a classification of every Oracle Forms
built-in and trigger type by what happens to it in an APEX migration.
Everything else (score, estimate, generation) derives from here.

Four verdicts. The difference between them is economic, not technical:

``AUTO``      has a direct, deterministic APEX equivalent. The machine
              converts it; a human only reviews.
``ASSISTED``  the intent translates, the form does not. Needs an AI proposal
              and human approval per hunk.
``MANUAL``    does not exist in APEX. Requires product redesign, an
              architecture decision, or an external integration.
``DROP``      solves a problem APEX simply does not have. It disappears in
              conversion, and that is a gain, not a loss.

Honesty about scope: this catalog covers the built-ins that show up in real
ERP-grade Forms systems. It is not the complete Forms built-in list. Anything
missing is counted as ``UNKNOWN`` and surfaced in the report as catalog debt
-- it is never silently treated as easy.
"""

from __future__ import annotations

AUTO = "AUTO"
ASSISTED = "ASSISTED"
MANUAL = "MANUAL"
DROP = "DROP"
UNKNOWN = "UNKNOWN"

VERDICT_ORDER = (AUTO, DROP, ASSISTED, MANUAL, UNKNOWN)

# Relative effort weight per verdict, used by the complexity score.
# AUTO is not zero: even automatic output gets reviewed by someone.
VERDICT_WEIGHT = {AUTO: 1.0, DROP: 0.2, ASSISTED: 4.0, MANUAL: 12.0, UNKNOWN: 6.0}


# --------------------------------------------------------------------------
# Forms built-ins
# Format: name -> (verdict, APEX target / rationale)
# --------------------------------------------------------------------------
BUILTINS: dict[str, tuple[str, str]] = {
    # -- Navigation across blocks/items/records -----------------------------
    "GO_BLOCK": (ASSISTED, "Navigation between regions or pages; depends on page design"),
    "GO_ITEM": (AUTO, "$('#ITEM').focus() via Execute JavaScript dynamic action"),
    "GO_RECORD": (ASSISTED, "No direct equivalent; becomes row selection in an IG"),
    "NEXT_ITEM": (DROP, "Tab order is native to HTML"),
    "PREVIOUS_ITEM": (DROP, "Tab order is native to HTML"),
    "NEXT_RECORD": (ASSISTED, "Row navigation inside an Interactive Grid"),
    "PREVIOUS_RECORD": (ASSISTED, "Row navigation inside an Interactive Grid"),
    "FIRST_RECORD": (ASSISTED, "Row navigation inside an Interactive Grid"),
    "LAST_RECORD": (ASSISTED, "Row navigation inside an Interactive Grid"),
    "NEXT_BLOCK": (ASSISTED, "Navigation between regions"),
    "PREVIOUS_BLOCK": (ASSISTED, "Navigation between regions"),
    "NEXT_SET": (ASSISTED, "Native APEX report pagination"),
    "DO_KEY": (ASSISTED, "Depends on the key: EXIT_FORM, EXECUTE_QUERY, COMMIT_FORM, etc."),
    # -- Query --------------------------------------------------------------
    "EXECUTE_QUERY": (AUTO, "Region refresh (Refresh dynamic action)"),
    "ENTER_QUERY": (AUTO, "Native Interactive Report filtering"),
    "COUNT_QUERY": (AUTO, "SELECT COUNT(*) in a process or computed item"),
    "ABORT_QUERY": (DROP, "Forms query mode does not exist in APEX"),
    "EXIT_FORM": (AUTO, "Branch/redirect to another page"),
    # -- DML / transaction --------------------------------------------------
    "COMMIT_FORM": (AUTO, "Page DML process plus APEX implicit commit"),
    "COMMIT": (AUTO, "Implicit commit at the end of the APEX request"),
    "ROLLBACK": (ASSISTED, "APEX rolls back on error; explicit rollback changes the design"),
    "POST": (ASSISTED, "No separate post stage; review process ordering"),
    "CLEAR_FORM": (AUTO, "Page cache clear (Clear Cache)"),
    "CLEAR_BLOCK": (AUTO, "Clear cache for the region's items"),
    "CLEAR_RECORD": (ASSISTED, "Client-side row removal in an IG"),
    "CLEAR_ITEM": (AUTO, "Set Value to empty via dynamic action"),
    "CREATE_RECORD": (ASSISTED, "Interactive Grid Add Row"),
    "DELETE_RECORD": (ASSISTED, "Interactive Grid Delete Row or DML process"),
    "DUPLICATE_RECORD": (ASSISTED, "Row duplication needs a custom process"),
    "DUPLICATE_ITEM": (ASSISTED, "Value copy via dynamic action"),
    "LOCK_RECORD": (MANUAL, "Pessimistic locking; APEX uses optimistic checksums"),
    "FORMS_DDL": (MANUAL, "Runtime dynamic DDL: review security and necessity"),
    "SET_BLOCK_PROPERTY": (ASSISTED, "Depends on the property (WHERE/ORDER BY -> region source)"),
    "GET_BLOCK_PROPERTY": (ASSISTED, "Depends on the property"),
    "SET_RECORD_PROPERTY": (ASSISTED, "Row state is not exposed this way in APEX"),
    "GET_RECORD_PROPERTY": (ASSISTED, "Row state is not exposed this way in APEX"),
    # -- Items and properties -----------------------------------------------
    "SET_ITEM_PROPERTY": (AUTO, "Dynamic action (Show/Hide/Enable/Disable/Set Value)"),
    "GET_ITEM_PROPERTY": (ASSISTED, "Depends on the property being read"),
    "SET_ITEM_INSTANCE_PROPERTY": (ASSISTED, "Per-row property; becomes a conditional IG column"),
    "GET_ITEM_INSTANCE_PROPERTY": (ASSISTED, "Per-row property"),
    "NAME_IN": (ASSISTED, "Indirect read; becomes V() or explicit logic"),
    "COPY": (ASSISTED, "Indirect write; becomes APEX_UTIL.SET_SESSION_STATE"),
    "DEFAULT_VALUE": (AUTO, "APEX item default value"),
    "SET_LOV_PROPERTY": (ASSISTED, "Dynamic APEX LOVs are query-based, not property-based"),
    # -- Messages and alerts ------------------------------------------------
    "MESSAGE": (AUTO, "APEX_ERROR.ADD_ERROR or inline notification"),
    "SHOW_ALERT": (ASSISTED, "Confirmation becomes a modal dialog or a DA confirm"),
    "SET_ALERT_PROPERTY": (AUTO, "Message text becomes a dialog parameter"),
    "SET_ALERT_BUTTON_PROPERTY": (ASSISTED, "Dialog button labels"),
    "ERROR_CODE": (AUTO, "SQLCODE / APEX_ERROR"),
    "ERROR_TEXT": (AUTO, "SQLERRM / APEX_ERROR"),
    "ERROR_TYPE": (AUTO, "APEX error handling"),
    "DBMS_ERROR_CODE": (AUTO, "SQLCODE"),
    "DBMS_ERROR_TEXT": (AUTO, "SQLERRM"),
    "FORM_SUCCESS": (AUTO, "Flow control via PL/SQL exceptions"),
    "FORM_FAILURE": (AUTO, "Flow control via PL/SQL exceptions"),
    "FORM_FATAL": (AUTO, "Flow control via PL/SQL exceptions"),
    # -- Windows, canvases, views (the world APEX does not have) ------------
    "SET_WINDOW_PROPERTY": (DROP, "MDI windows do not exist in APEX"),
    "GET_WINDOW_PROPERTY": (DROP, "MDI windows do not exist in APEX"),
    "SHOW_WINDOW": (ASSISTED, "Becomes a modal dialog or a separate page"),
    "HIDE_WINDOW": (ASSISTED, "Becomes closing a dialog"),
    "SHOW_VIEW": (ASSISTED, "Becomes showing a region or switching a tab"),
    "HIDE_VIEW": (ASSISTED, "Becomes hiding a region"),
    "SET_VIEW_PROPERTY": (DROP, "Canvas geometry does not exist in APEX"),
    "SET_CANVAS_PROPERTY": (DROP, "Canvas geometry does not exist in APEX"),
    "REPLACE_CONTENT_VIEW": (ASSISTED, "Content swap becomes navigation or a conditional region"),
    "SYNCHRONIZE": (DROP, "Screen redraw: irrelevant in a browser"),
    "PAUSE": (DROP, "Desktop UI blocking: no equivalent and no need"),
    "SET_WINDOW_SCROLL_BAR": (DROP, "Scrolling is native to the browser"),
    # -- Navigation across modules ------------------------------------------
    "CALL_FORM": (ASSISTED, "Becomes a modal page or a branch with return"),
    "OPEN_FORM": (ASSISTED, "Becomes a new page/tab; the APEX session is single"),
    "NEW_FORM": (ASSISTED, "Becomes a redirect with no return"),
    "CLOSE_FORM": (AUTO, "Close dialog or branch back"),
    "POST_FORM": (ASSISTED, "No separate post stage"),
    # -- LOVs, record groups and lists --------------------------------------
    "SHOW_LOV": (AUTO, "Native APEX popup LOV"),
    "LIST_VALUES": (AUTO, "Native APEX popup LOV"),
    "CREATE_GROUP_FROM_QUERY": (ASSISTED, "Record group becomes a dynamic LOV or a collection"),
    "POPULATE_GROUP": (ASSISTED, "Record group becomes a dynamic LOV or a collection"),
    "POPULATE_GROUP_WITH_QUERY": (ASSISTED, "Record group becomes a dynamic LOV"),
    "ADD_GROUP_ROW": (ASSISTED, "Becomes APEX_COLLECTION"),
    "ADD_GROUP_COLUMN": (ASSISTED, "Becomes APEX_COLLECTION"),
    "DELETE_GROUP": (ASSISTED, "Becomes APEX_COLLECTION.DELETE_COLLECTION"),
    "DELETE_GROUP_ROW": (ASSISTED, "Becomes APEX_COLLECTION"),
    "GET_GROUP_ROW_COUNT": (ASSISTED, "Becomes a COUNT over the collection"),
    "GET_GROUP_NUMBER_CELL": (ASSISTED, "Becomes a collection read"),
    "GET_GROUP_CHAR_CELL": (ASSISTED, "Becomes a collection read"),
    "GET_GROUP_DATE_CELL": (ASSISTED, "Becomes a collection read"),
    "SET_GROUP_NUMBER_CELL": (ASSISTED, "Becomes a collection write"),
    "SET_GROUP_CHAR_CELL": (ASSISTED, "Becomes a collection write"),
    "SET_GROUP_DATE_CELL": (ASSISTED, "Becomes a collection write"),
    "POPULATE_LIST": (AUTO, "Dynamic LOV on the select item"),
    "ADD_LIST_ELEMENT": (AUTO, "Dynamic LOV on the select item"),
    "DELETE_LIST_ELEMENT": (AUTO, "Dynamic LOV on the select item"),
    "CLEAR_LIST": (AUTO, "Dynamic LOV on the select item"),
    "GET_LIST_ELEMENT_COUNT": (AUTO, "COUNT over the LOV query"),
    "GET_LIST_ELEMENT_VALUE": (AUTO, "LOV query"),
    "GET_LIST_ELEMENT_LABEL": (AUTO, "LOV query"),
    "RETRIEVE_LIST": (ASSISTED, "Rebuild as a dynamic LOV"),
    # -- Timers -------------------------------------------------------------
    "CREATE_TIMER": (MANUAL, "No server-side timer; consider periodic region refresh"),
    "SET_TIMER": (MANUAL, "No server-side timer"),
    "DELETE_TIMER": (MANUAL, "No server-side timer"),
    "FIND_TIMER": (MANUAL, "No server-side timer"),
    # -- Menu ---------------------------------------------------------------
    "SET_MENU_ITEM_PROPERTY": (ASSISTED, "Becomes navigation plus APEX authorization"),
    "GET_MENU_ITEM_PROPERTY": (ASSISTED, "Becomes APEX authorization"),
    "REPLACE_MENU": (ASSISTED, "Becomes an APEX navigation list"),
    "SHOW_MENU": (DROP, "The menu is the theme's navigation menu"),
    "HIDE_MENU": (DROP, "The menu is the theme's navigation menu"),
    # -- Reports ------------------------------------------------------------
    "RUN_REPORT_OBJECT": (MANUAL, "Oracle Reports: choose a target (BI Publisher, APEX print, ORDS)"),
    "REPORT_OBJECT_STATUS": (MANUAL, "Depends on the chosen reporting target"),
    "SET_REPORT_OBJECT_PROPERTY": (MANUAL, "Depends on the chosen reporting target"),
    "GET_REPORT_OBJECT_PROPERTY": (MANUAL, "Depends on the chosen reporting target"),
    "RUN_PRODUCT": (MANUAL, "Legacy integration with Reports/Graphics"),
    # -- Client, OS and external integration --------------------------------
    "HOST": (MANUAL, "OS command on the client: no browser equivalent"),
    "GET_FILE_NAME": (ASSISTED, "Becomes an APEX File Browse item"),
    "READ_IMAGE_FILE": (ASSISTED, "Becomes BLOB plus Display Image"),
    "WRITE_IMAGE_FILE": (ASSISTED, "Becomes a BLOB download"),
    "READ_SOUND_FILE": (MANUAL, "Embedded media: redesign"),
    "WEB.SHOW_DOCUMENT": (AUTO, "APEX redirect or link"),
    "TOOL_ENV.GETVAR": (ASSISTED, "Application-server environment variable"),
    # -- Handle utilities ---------------------------------------------------
    "ID_NULL": (AUTO, "Handle check disappears together with the handle"),
    "FIND_ITEM": (AUTO, "Direct reference to the APEX item"),
    "FIND_BLOCK": (AUTO, "Direct reference to the region"),
    "FIND_CANVAS": (DROP, "Canvases do not exist in APEX"),
    "FIND_VIEW": (DROP, "Canvas views do not exist in APEX"),
    "FIND_WINDOW": (DROP, "Windows do not exist in APEX"),
    "FIND_ALERT": (AUTO, "Alert becomes a dialog"),
    "FIND_LOV": (AUTO, "Named APEX LOV"),
    "FIND_GROUP": (ASSISTED, "Record group becomes an LOV or a collection"),
    "FIND_RELATION": (ASSISTED, "Master-detail becomes a relationship between regions"),
    "FIND_FORM": (AUTO, "Page reference"),
    "FIND_MENU_ITEM": (ASSISTED, "Becomes a navigation entry"),
    "FIND_REPORT_OBJECT": (MANUAL, "Depends on the reporting target"),
    "FIND_TAB_PAGE": (AUTO, "APEX tabs region"),
    "SET_TAB_PAGE_PROPERTY": (AUTO, "APEX tabs region"),
    "GET_TAB_PAGE_PROPERTY": (AUTO, "APEX tabs region"),
    # -- Application --------------------------------------------------------
    "GET_APPLICATION_PROPERTY": (ASSISTED, "Depends on the property (USER, DATASOURCE, etc.)"),
    "SET_APPLICATION_PROPERTY": (ASSISTED, "Depends on the property"),
    "USER_EXIT": (MANUAL, "External 3GL code: rewrite"),
}

# Packages/prefixes that are always manual work: they depend on thick-client
# capabilities (OLE, DDE, WebUtil, Java beans) the browser does not expose.
CLIENT_SIDE_PREFIXES: dict[str, tuple[str, str]] = {
    "WEBUTIL_": (MANUAL, "WebUtil: Java client capability; redesign for APEX"),
    "CLIENT_TEXT_IO.": (MANUAL, "IO on the client disk: becomes APEX upload/download"),
    "CLIENT_OLE2.": (MANUAL, "Client-side OLE: no browser equivalent"),
    "CLIENT_HOST": (MANUAL, "OS command on the client: no equivalent"),
    "OLE2.": (MANUAL, "OLE automation: no browser equivalent"),
    "DDE.": (MANUAL, "DDE: no browser equivalent"),
    "TEXT_IO.": (ASSISTED, "File IO: becomes server-side UTL_FILE or APEX upload"),
    "ORA_FFI.": (MANUAL, "Native DLL call: rewrite"),
    "ORA_JAVA.": (MANUAL, "Imported Java bean: rewrite"),
    "DBMS_JOB.": (ASSISTED, "Migrate to DBMS_SCHEDULER"),
}

# The most common Forms system variables and what to do with them.
SYSTEM_VARS: dict[str, tuple[str, str]] = {
    "SYSTEM.CURRENT_FORM": (AUTO, ":APP_PAGE_ID / :APP_ID"),
    "SYSTEM.CURRENT_BLOCK": (ASSISTED, "No equivalent; depends on the design"),
    "SYSTEM.CURRENT_ITEM": (ASSISTED, "No direct equivalent"),
    "SYSTEM.CURSOR_ITEM": (ASSISTED, "No direct equivalent"),
    "SYSTEM.CURSOR_VALUE": (ASSISTED, "Current item value"),
    "SYSTEM.CURSOR_RECORD": (ASSISTED, "IG row index"),
    "SYSTEM.BLOCK_STATUS": (ASSISTED, "Block state does not exist in APEX"),
    "SYSTEM.FORM_STATUS": (ASSISTED, "Form state does not exist in APEX"),
    "SYSTEM.RECORD_STATUS": (ASSISTED, "APEX$ROW_STATUS in an Interactive Grid"),
    "SYSTEM.MODE": (ASSISTED, "Forms query mode does not exist"),
    "SYSTEM.MESSAGE_LEVEL": (DROP, "Forms message level does not exist"),
    "SYSTEM.LAST_QUERY": (ASSISTED, "No direct equivalent"),
    "SYSTEM.TRIGGER_ITEM": (ASSISTED, "No direct equivalent"),
    "SYSTEM.TRIGGER_BLOCK": (ASSISTED, "No direct equivalent"),
    "SYSTEM.DATE": (AUTO, "SYSDATE"),
    "SYSTEM.EFFECTIVE_DATE": (AUTO, "SYSDATE"),
    "SYSTEM.MOUSE_ITEM": (DROP, "Thick-client mouse events"),
}


# --------------------------------------------------------------------------
# Triggers
# --------------------------------------------------------------------------
TRIGGERS: dict[str, tuple[str, str]] = {
    # Lifecycle
    "WHEN-NEW-FORM-INSTANCE": (ASSISTED, "Before Header process / page On Load"),
    "WHEN-NEW-BLOCK-INSTANCE": (MANUAL, "Depends on block navigation, which APEX has no notion of"),
    "WHEN-NEW-RECORD-INSTANCE": (MANUAL, "Depends on record navigation"),
    "WHEN-NEW-ITEM-INSTANCE": (ASSISTED, "Approximated by a focus dynamic action"),
    "WHEN-CREATE-RECORD": (ASSISTED, "Defaults for a new IG row"),
    "PRE-FORM": (ASSISTED, "Before Header process"),
    "POST-FORM": (ASSISTED, "Exit process / branch"),
    "PRE-BLOCK": (MANUAL, "No block navigation cycle in APEX"),
    "POST-BLOCK": (MANUAL, "No block navigation cycle in APEX"),
    "PRE-RECORD": (MANUAL, "No record navigation cycle in APEX"),
    "POST-RECORD": (MANUAL, "No record navigation cycle in APEX"),
    "PRE-TEXT-ITEM": (DROP, "Thick-client item cycle"),
    "POST-TEXT-ITEM": (ASSISTED, "Dynamic action on Change/Blur"),
    "POST-CHANGE": (ASSISTED, "Dynamic action on Change"),
    # Query
    "PRE-QUERY": (ASSISTED, "Filter moves into the region source WHERE clause"),
    "POST-QUERY": (ASSISTED, "Derived columns move into the query itself"),
    "ON-FETCH": (MANUAL, "Procedure-based block: redesign the region source"),
    "ON-COUNT": (ASSISTED, "Native report counting"),
    "ON-SELECT": (MANUAL, "Replaces the default SELECT"),
    # Validation
    "WHEN-VALIDATE-ITEM": (AUTO, "APEX item validation"),
    "WHEN-VALIDATE-RECORD": (AUTO, "APEX row validation"),
    # DML
    "PRE-INSERT": (ASSISTED, "Pre-DML process or table trigger"),
    "PRE-UPDATE": (ASSISTED, "Pre-DML process or table trigger"),
    "PRE-DELETE": (ASSISTED, "Pre-DML process or table trigger"),
    "POST-INSERT": (ASSISTED, "Post-DML process"),
    "POST-UPDATE": (ASSISTED, "Post-DML process"),
    "POST-DELETE": (ASSISTED, "Post-DML process"),
    "ON-INSERT": (MANUAL, "Replaces default DML: becomes a custom DML process"),
    "ON-UPDATE": (MANUAL, "Replaces default DML: becomes a custom DML process"),
    "ON-DELETE": (MANUAL, "Replaces default DML: becomes a custom DML process"),
    "ON-LOCK": (MANUAL, "Pessimistic locking; APEX uses optimistic checksums"),
    "ON-COMMIT": (MANUAL, "Custom transaction control"),
    "ON-ROLLBACK": (MANUAL, "Custom transaction control"),
    "ON-SAVEPOINT": (DROP, "Forms-cycle savepoint"),
    "PRE-COMMIT": (ASSISTED, "Process before the page DML"),
    "POST-COMMIT": (ASSISTED, "Process after the page DML"),
    "POST-FORMS-COMMIT": (ASSISTED, "Process after the page DML"),
    "PRE-SELECT": (ASSISTED, "Region source adjustment"),
    # UI interaction
    "WHEN-BUTTON-PRESSED": (ASSISTED, "Dynamic action or page process"),
    "WHEN-CHECKBOX-CHANGED": (AUTO, "Dynamic action on Change"),
    "WHEN-RADIO-CHANGED": (AUTO, "Dynamic action on Change"),
    "WHEN-LIST-CHANGED": (AUTO, "Dynamic action on Change"),
    "WHEN-LIST-ACTIVATED": (AUTO, "Dynamic action on Change"),
    "WHEN-IMAGE-PRESSED": (AUTO, "Dynamic action on Click"),
    "WHEN-IMAGE-ACTIVATED": (AUTO, "Dynamic action on Double Click"),
    "WHEN-TREE-NODE-SELECTED": (ASSISTED, "APEX Tree region"),
    "WHEN-TREE-NODE-EXPANDED": (ASSISTED, "APEX Tree region"),
    "WHEN-TREE-NODE-ACTIVATED": (ASSISTED, "APEX Tree region"),
    "WHEN-CUSTOM-ITEM-EVENT": (MANUAL, "Java bean / WebUtil event: redesign"),
    "WHEN-MOUSE-CLICK": (AUTO, "Dynamic action on Click"),
    "WHEN-MOUSE-DOUBLECLICK": (AUTO, "Dynamic action on Double Click"),
    "WHEN-MOUSE-ENTER": (DROP, "Hover: CSS"),
    "WHEN-MOUSE-LEAVE": (DROP, "Hover: CSS"),
    "WHEN-MOUSE-MOVE": (DROP, "No use in a business web application"),
    "WHEN-MOUSE-DOWN": (DROP, "No use in a business web application"),
    "WHEN-MOUSE-UP": (DROP, "No use in a business web application"),
    "WHEN-WINDOW-ACTIVATED": (DROP, "MDI windows do not exist in APEX"),
    "WHEN-WINDOW-DEACTIVATED": (DROP, "MDI windows do not exist in APEX"),
    "WHEN-WINDOW-RESIZED": (DROP, "Responsive theme layout"),
    "WHEN-WINDOW-CLOSED": (ASSISTED, "Close dialog"),
    "WHEN-TIMER-EXPIRED": (MANUAL, "No timer; evaluate periodic region refresh"),
    "WHEN-FORM-NAVIGATE": (DROP, "Thick-client window navigation"),
    # LOV, master-detail, errors, session
    "WHEN-NEW-ITEM-INSTANCE-LOV": (ASSISTED, "APEX LOV"),
    "ON-POPULATE-DETAILS": (ASSISTED, "Master-detail: detail region filter"),
    "ON-CHECK-DELETE-MASTER": (ASSISTED, "Referential integrity validation"),
    "ON-CLEAR-DETAILS": (AUTO, "Detail region refresh"),
    "ON-ERROR": (ASSISTED, "APEX error handling function"),
    "ON-MESSAGE": (ASSISTED, "APEX message handling"),
    "ON-LOGON": (MANUAL, "Authentication becomes an APEX authentication scheme"),
    "ON-LOGOUT": (MANUAL, "APEX logout"),
    "PRE-LOGON": (MANUAL, "Authentication becomes an APEX authentication scheme"),
    "POST-LOGON": (MANUAL, "APEX post-authentication procedure"),
    "PRE-LOGOUT": (MANUAL, "APEX logout"),
    "POST-LOGOUT": (MANUAL, "APEX logout"),
}

# KEY-* triggers are thick-client function keys. Few of them make sense on
# the web; most are replaced by an explicit button.
KEY_TRIGGER_PREFIX = "KEY-"
KEY_TRIGGER_DEFAULT = (ASSISTED, "Forms function key: becomes an explicit page button")
KEY_TRIGGER_DROP = {
    "KEY-CLRFRM", "KEY-CLRBLK", "KEY-CLRREC", "KEY-NXTBLK", "KEY-PRVBLK",
    "KEY-NXTITM", "KEY-PRVITM", "KEY-NXTREC", "KEY-PRVREC", "KEY-SCRUP",
    "KEY-SCRDOWN", "KEY-MENU", "KEY-HELP", "KEY-PRINT", "KEY-EDIT",
}


def classify_trigger(name: str) -> tuple[str, str]:
    """Verdict and APEX target for a trigger, by name."""
    key = (name or "").strip().upper()
    if key in TRIGGERS:
        return TRIGGERS[key]
    if key.startswith(KEY_TRIGGER_PREFIX):
        if key in KEY_TRIGGER_DROP:
            return (DROP, "Key-based navigation: replaced by browser navigation")
        return KEY_TRIGGER_DEFAULT
    return (UNKNOWN, "Trigger outside the catalog: classify manually")


def classify_builtin(name: str) -> tuple[str, str]:
    """Verdict and APEX target for a built-in, by name."""
    key = (name or "").strip().upper()
    if key in BUILTINS:
        return BUILTINS[key]
    if key in SYSTEM_VARS:
        return SYSTEM_VARS[key]
    for prefix, verdict in CLIENT_SIDE_PREFIXES.items():
        if key.startswith(prefix.upper()):
            return verdict
    return (UNKNOWN, "Built-in outside the catalog: classify manually")


def worst(verdicts: list[str]) -> str:
    """The most expensive verdict in the list (sets the automation ceiling)."""
    rank = {v: i for i, v in enumerate((AUTO, DROP, ASSISTED, UNKNOWN, MANUAL))}
    return max(verdicts, key=lambda v: rank.get(v, 0)) if verdicts else AUTO


def catalog_size() -> dict[str, int]:
    """Catalog size -- reported so coverage is stated, not implied."""
    return {
        "builtins": len(BUILTINS),
        "system_vars": len(SYSTEM_VARS),
        "client_prefixes": len(CLIENT_SIDE_PREFIXES),
        "triggers": len(TRIGGERS),
    }
