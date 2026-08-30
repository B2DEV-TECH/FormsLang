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

from dataclasses import dataclass

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


# ==========================================================================
# Structured compatibility catalog
#
# The tables above are the authoring format: one line per construct, verdict
# plus APEX target. This section layers the rest of the matrix on top --
# category, what Forms actually does, migration classification and a risk
# weight -- without restating the verdict anywhere. There is exactly one
# place where "GO_BLOCK is ASSISTED" is written down, and it is above.
#
# Category is the pivot. A statement true of a whole family (timers have no
# server-side equivalent; OLE has no browser equivalent) is written once on
# the category; only the handful of constructs where the family statement is
# wrong carry an override.
# ==========================================================================

# Migration classification -- how the construct crosses to APEX.
DIRECT_EQUIVALENT = "DIRECT_EQUIVALENT"
SERVER_SIDE_REPLACEMENT = "SERVER_SIDE_REPLACEMENT"
CLIENT_SIDE_REPLACEMENT = "CLIENT_SIDE_REPLACEMENT"
ARCHITECTURAL_REDESIGN = "ARCHITECTURAL_REDESIGN"
MANUAL_REVIEW = "MANUAL_REVIEW"
UNSUPPORTED = "UNSUPPORTED"
# Added to the six classes the matrix normally carries: a DROP verdict is
# neither unsupported nor replaced -- the construct solves a problem APEX
# does not have. Folding it into UNSUPPORTED would inflate every "missing
# feature" count with things that are gains.
NOT_REQUIRED = "NOT_REQUIRED"

MIGRATION_CLASSES = (
    DIRECT_EQUIVALENT,
    SERVER_SIDE_REPLACEMENT,
    CLIENT_SIDE_REPLACEMENT,
    ARCHITECTURAL_REDESIGN,
    MANUAL_REVIEW,
    UNSUPPORTED,
    NOT_REQUIRED,
)


@dataclass(frozen=True)
class Category:
    """A family of Forms constructs that migrate for the same reason."""

    id: str
    label: str
    forms_behavior: str   # what the Forms runtime does with this family
    risk: float           # 0..1 danger weight per occurrence, for risk.py
    risk_reason: str      # the evidence sentence shown to a reviewer
    review_area: str      # what a human has to look at because of it
    assisted: str         # migration class when the verdict is ASSISTED
    manual: str           # migration class when the verdict is MANUAL


def _cat(
    ident: str, label: str, forms_behavior: str, risk: float, risk_reason: str,
    review_area: str, assisted: str = SERVER_SIDE_REPLACEMENT,
    manual: str = ARCHITECTURAL_REDESIGN,
) -> Category:
    return Category(ident, label, forms_behavior, risk, risk_reason, review_area,
                    assisted, manual)


CATEGORIES: dict[str, Category] = {
    "navigation": _cat(
        "navigation", "Block/item navigation",
        "Moves the Forms input focus, which also drives the trigger firing order.",
        0.45,
        "Logic depends on Forms navigation, and APEX has no navigation cycle to depend on.",
        "Navigation-dependent logic and trigger firing order",
        assisted=CLIENT_SIDE_REPLACEMENT,
    ),
    "query": _cat(
        "query", "Query execution",
        "Runs or aborts the block query and switches the block between normal and query mode.",
        0.40,
        "Query execution is explicit in Forms and implicit in an APEX region refresh.",
        "Where the query runs and what triggers it",
    ),
    "form_state": _cat(
        "form_state", "Form and block state",
        "Clears or leaves the form, which can silently discard uncommitted changes.",
        0.60,
        "Clearing or exiting can discard pending changes; APEX has no equivalent prompt.",
        "What happens to unsaved changes",
    ),
    "transaction": _cat(
        "transaction", "Transaction control",
        "Posts or commits the Forms transaction at a point the developer chose.",
        0.90,
        "The transaction boundary moves: APEX commits at the end of page processing.",
        "Transaction boundaries and commit points",
    ),
    "record_dml": _cat(
        "record_dml", "Record-level DML",
        "Creates, deletes, duplicates or locks a record inside the Forms block buffer.",
        0.60,
        "Record buffer operations have no APEX counterpart; the locking model differs.",
        "Row lifecycle and locking model",
    ),
    "block_state": _cat(
        "block_state", "Block properties",
        "Reads or rewrites block properties, including WHERE and ORDER BY, at runtime.",
        0.55,
        "Runtime changes to the block query become a different region source design.",
        "Dynamic query construction",
    ),
    "item_state": _cat(
        "item_state", "Item properties",
        "Reads or sets item properties: value, visibility, enabled state, format.",
        0.20,
        "Item property changes become dynamic actions with a different execution point.",
        "Item state and dynamic actions",
        assisted=CLIENT_SIDE_REPLACEMENT,
    ),
    "indirection": _cat(
        "indirection", "Indirect item access",
        "Reads or writes an item whose name is only known at runtime, as a string.",
        0.85,
        "The target is a runtime string, so no static analysis can name what this touches.",
        "Indirect item access -- resolve the targets by hand",
        manual=MANUAL_REVIEW,
    ),
    "message": _cat(
        "message", "Messages and alerts",
        "Shows a message or a modal alert and, for alerts, blocks until the user answers.",
        0.10,
        "Alerts block the Forms client; APEX cannot block server-side processing on an answer.",
        "User confirmation flow",
        assisted=CLIENT_SIDE_REPLACEMENT,
    ),
    "ui_container": _cat(
        "ui_container", "Windows, canvases and views",
        "Manipulates the thick-client window and canvas geometry.",
        0.10,
        "Window and canvas geometry has no meaning in a browser layout.",
        "Screen layout",
        assisted=CLIENT_SIDE_REPLACEMENT,
    ),
    "module_nav": _cat(
        "module_nav", "Cross-module navigation",
        "Opens, calls or replaces another Forms module, with its own session state.",
        0.70,
        "Another module is invoked: migrating this unit depends on that form too.",
        "Cross-form dependencies and parameter passing",
    ),
    "lov_group": _cat(
        "lov_group", "LOVs, record groups and lists",
        "Builds or reads an in-memory record group, list item or LOV.",
        0.35,
        "In-memory record groups become queries or collections with a different lifetime.",
        "LOV and record group rebuild",
    ),
    "timer": _cat(
        "timer", "Timers",
        "Schedules client-side code to run after a delay, repeatedly or once.",
        0.70,
        "There is no server-side timer in APEX; the scheduling model has to change.",
        "Anything that depended on elapsed time",
        manual=ARCHITECTURAL_REDESIGN,
    ),
    "menu": _cat(
        "menu", "Menu",
        "Reads or rewrites the attached Forms menu at runtime.",
        0.30,
        "Menu state carries authorization decisions that become APEX authorization schemes.",
        "Authorization rules hidden in menu state",
    ),
    "reporting": _cat(
        "reporting", "Reporting integration",
        "Hands off to Oracle Reports or another external product.",
        0.70,
        "An external reporting product is invoked; the target has to be chosen first.",
        "Reporting target",
    ),
    "external": _cat(
        "external", "Operating system and external integration",
        "Reaches outside the database: the client OS, the file system or another product.",
        0.90,
        "The code reaches outside the database; a browser cannot do this at all.",
        "External integration -- redesign, not translation",
        manual=UNSUPPORTED,
    ),
    "client_platform": _cat(
        "client_platform", "Thick-client platform",
        "Uses a Java, OLE, DDE or native capability that only the Forms client has.",
        0.95,
        "Depends on a thick-client capability the browser does not expose.",
        "Client platform capability -- no equivalent exists",
        manual=UNSUPPORTED,
    ),
    "dynamic_sql": _cat(
        "dynamic_sql", "Dynamic SQL and DDL",
        "Builds and runs SQL or DDL assembled at runtime.",
        0.90,
        "SQL is assembled at runtime: neither the effect nor the privileges are static.",
        "Dynamic SQL -- effect and privileges",
        manual=MANUAL_REVIEW,
    ),
    "scheduling": _cat(
        "scheduling", "Background jobs",
        "Submits work to run outside the current session.",
        0.50,
        "Background work outlives the request; ownership and scheduling change.",
        "Background job ownership",
    ),
    "handle": _cat(
        "handle", "Object handles",
        "Looks up an internal handle to a Forms object.",
        0.10,
        "Handles disappear with the Forms runtime, together with the code that uses them.",
        "Handle-based code",
    ),
    "application": _cat(
        "application", "Application properties",
        "Reads or sets a runtime property of the whole application.",
        0.30,
        "Application-level properties map to different APEX concepts case by case.",
        "Application property mapping",
        manual=MANUAL_REVIEW,
    ),
    "system_var": _cat(
        "system_var", "Forms system variables",
        "Exposes runtime state of the Forms cycle: mode, status, cursor position.",
        0.35,
        "Reads Forms runtime state that APEX does not maintain.",
        "Forms runtime state assumptions",
    ),
    "unknown": _cat(
        "unknown", "Outside the catalog",
        "Not classified yet -- FormsLang does not claim to know what this does.",
        0.60,
        "Construct is outside the catalog, so its cost and risk are unproven.",
        "Unclassified construct -- confirm by hand",
        assisted=MANUAL_REVIEW, manual=MANUAL_REVIEW,
    ),
}

# Which family each built-in belongs to. Grouped exactly like the table it
# annotates, so the two stay reviewable side by side.
_CATEGORY_MEMBERS: dict[str, tuple[str, ...]] = {
    "navigation": (
        "GO_BLOCK", "GO_ITEM", "GO_RECORD", "NEXT_ITEM", "PREVIOUS_ITEM",
        "NEXT_RECORD", "PREVIOUS_RECORD", "FIRST_RECORD", "LAST_RECORD",
        "NEXT_BLOCK", "PREVIOUS_BLOCK", "NEXT_SET", "DO_KEY",
    ),
    "query": ("EXECUTE_QUERY", "ENTER_QUERY", "COUNT_QUERY", "ABORT_QUERY"),
    "form_state": ("EXIT_FORM", "CLEAR_FORM", "CLEAR_BLOCK", "CLEAR_RECORD", "CLEAR_ITEM"),
    "transaction": ("COMMIT_FORM", "COMMIT", "ROLLBACK", "POST", "POST_FORM"),
    "record_dml": (
        "CREATE_RECORD", "DELETE_RECORD", "DUPLICATE_RECORD", "DUPLICATE_ITEM",
        "LOCK_RECORD", "SET_RECORD_PROPERTY", "GET_RECORD_PROPERTY",
    ),
    "dynamic_sql": ("FORMS_DDL",),
    "block_state": ("SET_BLOCK_PROPERTY", "GET_BLOCK_PROPERTY"),
    "item_state": (
        "SET_ITEM_PROPERTY", "GET_ITEM_PROPERTY", "SET_ITEM_INSTANCE_PROPERTY",
        "GET_ITEM_INSTANCE_PROPERTY", "DEFAULT_VALUE", "SET_LOV_PROPERTY",
    ),
    "indirection": ("NAME_IN", "COPY"),
    "message": (
        "MESSAGE", "SHOW_ALERT", "SET_ALERT_PROPERTY", "SET_ALERT_BUTTON_PROPERTY",
        "ERROR_CODE", "ERROR_TEXT", "ERROR_TYPE", "DBMS_ERROR_CODE",
        "DBMS_ERROR_TEXT", "FORM_SUCCESS", "FORM_FAILURE", "FORM_FATAL",
    ),
    "ui_container": (
        "SET_WINDOW_PROPERTY", "GET_WINDOW_PROPERTY", "SHOW_WINDOW", "HIDE_WINDOW",
        "SHOW_VIEW", "HIDE_VIEW", "SET_VIEW_PROPERTY", "SET_CANVAS_PROPERTY",
        "REPLACE_CONTENT_VIEW", "SYNCHRONIZE", "PAUSE", "SET_WINDOW_SCROLL_BAR",
    ),
    "module_nav": ("CALL_FORM", "OPEN_FORM", "NEW_FORM", "CLOSE_FORM"),
    "lov_group": (
        "SHOW_LOV", "LIST_VALUES", "CREATE_GROUP_FROM_QUERY", "POPULATE_GROUP",
        "POPULATE_GROUP_WITH_QUERY", "ADD_GROUP_ROW", "ADD_GROUP_COLUMN",
        "DELETE_GROUP", "DELETE_GROUP_ROW", "GET_GROUP_ROW_COUNT",
        "GET_GROUP_NUMBER_CELL", "GET_GROUP_CHAR_CELL", "GET_GROUP_DATE_CELL",
        "SET_GROUP_NUMBER_CELL", "SET_GROUP_CHAR_CELL", "SET_GROUP_DATE_CELL",
        "POPULATE_LIST", "ADD_LIST_ELEMENT", "DELETE_LIST_ELEMENT", "CLEAR_LIST",
        "GET_LIST_ELEMENT_COUNT", "GET_LIST_ELEMENT_VALUE",
        "GET_LIST_ELEMENT_LABEL", "RETRIEVE_LIST",
    ),
    "timer": ("CREATE_TIMER", "SET_TIMER", "DELETE_TIMER", "FIND_TIMER"),
    "menu": (
        "SET_MENU_ITEM_PROPERTY", "GET_MENU_ITEM_PROPERTY", "REPLACE_MENU",
        "SHOW_MENU", "HIDE_MENU",
    ),
    "reporting": (
        "RUN_REPORT_OBJECT", "REPORT_OBJECT_STATUS", "SET_REPORT_OBJECT_PROPERTY",
        "GET_REPORT_OBJECT_PROPERTY", "RUN_PRODUCT",
    ),
    "external": (
        "HOST", "GET_FILE_NAME", "READ_IMAGE_FILE", "WRITE_IMAGE_FILE",
        "READ_SOUND_FILE", "WEB.SHOW_DOCUMENT", "TOOL_ENV.GETVAR", "USER_EXIT",
    ),
    "handle": (
        "ID_NULL", "FIND_ITEM", "FIND_BLOCK", "FIND_CANVAS", "FIND_VIEW",
        "FIND_WINDOW", "FIND_ALERT", "FIND_LOV", "FIND_GROUP", "FIND_RELATION",
        "FIND_FORM", "FIND_MENU_ITEM", "FIND_REPORT_OBJECT", "FIND_TAB_PAGE",
        "SET_TAB_PAGE_PROPERTY", "GET_TAB_PAGE_PROPERTY",
    ),
    "application": ("GET_APPLICATION_PROPERTY", "SET_APPLICATION_PROPERTY"),
}

# Which family each thick-client prefix belongs to.
_PREFIX_CATEGORY: dict[str, str] = {
    "WEBUTIL_": "client_platform",
    "CLIENT_TEXT_IO.": "client_platform",
    "CLIENT_OLE2.": "client_platform",
    "CLIENT_HOST": "client_platform",
    "OLE2.": "client_platform",
    "DDE.": "client_platform",
    "TEXT_IO.": "external",
    "ORA_FFI.": "client_platform",
    "ORA_JAVA.": "client_platform",
    "DBMS_JOB.": "scheduling",
}

# Where the family statement is wrong for one construct.
_CLASS_OVERRIDE: dict[str, str] = {
    "HOST": UNSUPPORTED,
    "USER_EXIT": UNSUPPORTED,
    "READ_SOUND_FILE": UNSUPPORTED,
    "LOCK_RECORD": ARCHITECTURAL_REDESIGN,
    "FORMS_DDL": MANUAL_REVIEW,
}

# Risk the family weight does not capture for one construct: reading a
# property is not the same act as changing it.
_RISK_OVERRIDE: dict[str, float] = {
    "GET_BLOCK_PROPERTY": 0.20,
    "GET_RECORD_PROPERTY": 0.20,
    "GET_ITEM_PROPERTY": 0.10,
    "GET_MENU_ITEM_PROPERTY": 0.15,
    "GET_APPLICATION_PROPERTY": 0.15,
    # Leaving the form is not the same act as clearing unsaved work.
    "EXIT_FORM": 0.45,
    "CLEAR_ITEM": 0.15,
    # A plain redirect, not an OS call.
    "WEB.SHOW_DOCUMENT": 0.15,
    "GET_FILE_NAME": 0.35,
    # Reaches the environment, but through the application server.
    "TOOL_ENV.GETVAR": 0.40,
}


@dataclass(frozen=True)
class BuiltinSpec:
    """One row of the Forms -> APEX compatibility matrix."""

    name: str
    category: str
    verdict: str
    apex: str              # the APEX strategy, taken from the tables above
    migration_class: str
    risk: float
    forms_behavior: str
    known: bool = True

    @property
    def label(self) -> str:
        return CATEGORIES[self.category].label

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "category_label": self.label,
            "verdict": self.verdict,
            "apex": self.apex,
            "migration_class": self.migration_class,
            "risk": round(self.risk, 3),
            "forms_behavior": self.forms_behavior,
            "known": self.known,
        }


def _classify(verdict: str, cat: Category, name: str) -> str:
    override = _CLASS_OVERRIDE.get(name)
    if override:
        return override
    if verdict == DROP:
        return NOT_REQUIRED
    if verdict == AUTO:
        return DIRECT_EQUIVALENT
    if verdict == ASSISTED:
        return cat.assisted
    if verdict == MANUAL:
        return cat.manual
    return MANUAL_REVIEW


def _build_spec(name: str, verdict: str, apex: str, category: str) -> BuiltinSpec:
    cat = CATEGORIES[category]
    return BuiltinSpec(
        name=name,
        category=category,
        verdict=verdict,
        apex=apex,
        migration_class=_classify(verdict, cat, name),
        risk=_RISK_OVERRIDE.get(name, cat.risk),
        forms_behavior=cat.forms_behavior,
        known=category != "unknown",
    )


def _build_catalog() -> dict[str, BuiltinSpec]:
    of_name = {n: c for c, names in _CATEGORY_MEMBERS.items() for n in names}
    out: dict[str, BuiltinSpec] = {}
    for name, (verdict, apex) in BUILTINS.items():
        # An unmapped built-in falls into "unknown": expensive and visible,
        # never silently cheap. test_every_builtin_has_a_category keeps that
        # bucket at zero.
        out[name] = _build_spec(name, verdict, apex, of_name.get(name, "unknown"))
    for name, (verdict, apex) in SYSTEM_VARS.items():
        out[name] = _build_spec(name, verdict, apex, "system_var")
    return out


CATALOG: dict[str, BuiltinSpec] = _build_catalog()


def spec_for(name: str) -> BuiltinSpec:
    """The matrix row for a construct -- always answers, never invents.

    An unrecognised name comes back as an honest UNKNOWN row rather than a
    guess, so the caller can show catalog debt instead of false confidence.
    """
    key = (name or "").strip().upper()
    hit = CATALOG.get(key)
    if hit is not None:
        return hit
    for prefix, category in _PREFIX_CATEGORY.items():
        if key.startswith(prefix.upper()):
            verdict, apex = CLIENT_SIDE_PREFIXES[prefix]
            return _build_spec(key, verdict, apex, category)
    return _build_spec(
        key, UNKNOWN, "Built-in outside the catalog: classify manually", "unknown"
    )


# --------------------------------------------------------------------------
# Trigger risk
#
# A trigger's verdict says what it costs to move. This says what it costs to
# get wrong -- a different question with a different answer: PRE-INSERT is
# ASSISTED (cheap) and dangerous (afterwards it runs at a different moment).
# --------------------------------------------------------------------------
_VERDICT_RISK = {AUTO: 0.10, DROP: 0.05, ASSISTED: 0.30, MANUAL: 0.60, UNKNOWN: 0.55}

TRIGGER_RISK: dict[str, tuple[float, str]] = {
    # Transaction and DML replacement: the semantics live here.
    "ON-COMMIT": (0.90, "Replaces Forms commit processing entirely."),
    "ON-ROLLBACK": (0.90, "Replaces Forms rollback processing entirely."),
    "ON-LOCK": (0.85, "Pessimistic row locking; APEX uses optimistic checksums."),
    "ON-INSERT": (0.85, "Replaces the default INSERT for the block."),
    "ON-UPDATE": (0.85, "Replaces the default UPDATE for the block."),
    "ON-DELETE": (0.85, "Replaces the default DELETE for the block."),
    "ON-SELECT": (0.80, "Replaces the default SELECT for the block."),
    "ON-FETCH": (0.80, "Procedure-based block: the region source has to be redesigned."),
    "PRE-COMMIT": (0.65, "Runs once per transaction, before any DML."),
    "POST-COMMIT": (0.65, "Runs once per transaction, after the DML."),
    "POST-FORMS-COMMIT": (0.65, "Runs inside the Forms commit sequence."),
    # DML hooks: cheap to move, easy to move to the wrong place.
    "PRE-INSERT": (0.55, "Fires per row inside the Forms commit; the APEX equivalent may not."),
    "PRE-UPDATE": (0.55, "Fires per row inside the Forms commit; the APEX equivalent may not."),
    "PRE-DELETE": (0.55, "Fires per row inside the Forms commit; the APEX equivalent may not."),
    "POST-INSERT": (0.50, "Fires per row after the DML, still inside the transaction."),
    "POST-UPDATE": (0.50, "Fires per row after the DML, still inside the transaction."),
    "POST-DELETE": (0.50, "Fires per row after the DML, still inside the transaction."),
    # Navigation cycle: has no APEX counterpart at all.
    "WHEN-NEW-BLOCK-INSTANCE": (0.70, "Depends on block navigation, which APEX does not have."),
    "WHEN-NEW-RECORD-INSTANCE": (0.70, "Depends on record navigation, which APEX does not have."),
    "PRE-BLOCK": (0.65, "Part of the Forms navigation cycle."),
    "POST-BLOCK": (0.65, "Part of the Forms navigation cycle."),
    "PRE-RECORD": (0.65, "Part of the Forms navigation cycle."),
    "POST-RECORD": (0.65, "Part of the Forms navigation cycle."),
    # Query shaping and per-row work.
    "PRE-QUERY": (0.60, "Shapes the query at runtime; becomes a static region source."),
    "POST-QUERY": (0.60, "Runs once per fetched row; usually becomes a join."),
    # Session and timing.
    "WHEN-TIMER-EXPIRED": (0.70, "Depends on a timer APEX does not have."),
    "ON-LOGON": (0.80, "Authentication moves to an APEX authentication scheme."),
    "PRE-LOGON": (0.80, "Authentication moves to an APEX authentication scheme."),
    "POST-LOGON": (0.75, "Becomes an APEX post-authentication procedure."),
    "ON-LOGOUT": (0.70, "Session teardown differs."),
    "ON-ERROR": (0.55, "Central error handling becomes an APEX error handling function."),
    "WHEN-CUSTOM-ITEM-EVENT": (0.85, "Driven by a Java bean or WebUtil the browser does not have."),
}


def trigger_risk(name: str) -> tuple[float, str]:
    """Risk weight and evidence sentence for a trigger point."""
    key = (name or "").strip().upper()
    hit = TRIGGER_RISK.get(key)
    if hit is not None:
        return hit
    verdict = classify_trigger(key)[0]
    if verdict == UNKNOWN:
        return (_VERDICT_RISK[UNKNOWN], "Trigger point is outside the catalog.")
    return (_VERDICT_RISK[verdict], "")


def catalog_coverage() -> dict[str, int]:
    """How the catalog distributes across migration classes."""
    out = {c: 0 for c in MIGRATION_CLASSES}
    for spec in CATALOG.values():
        out[spec.migration_class] += 1
    return out
