"""The workbench UI: one self-contained HTML document, assembled from
the ui/ subpackage.

No build step, no framework, no CDN. The page ships inside the Python
package and is served from localhost, because the data on screen is the
source code under review and it has no business travelling to a CDN to fetch
a font.

Everything the page shows comes from ``/api/state``; the page itself holds
no data and no secrets.

Split into one module per workbench concern so no single file holds the
whole page; INDEX_HTML below reassembles them in the original document
order -- HTML head, then body, then script, top to bottom.
"""

from __future__ import annotations

from .conversion import EXPORT_JS, JOB_PROGRESS_JS, PROPOSE_AND_POLL_JS
from .projects import DASHBOARD_JS, PICKER_JS
from .review import (
    DECIDE_JS,
    DETAIL_SECTION_HTML,
    LIST_AND_DETAIL_JS,
    LIST_PANE_HTML,
    MAIN_OPEN_HTML,
    NAVIGATION_JS,
    SYNTAX_HIGHLIGHT_JS,
)
from .settings import SETTINGS_JS
from .shared import HEAD_HTML, MODAL_HTML, MODAL_JS, SCRIPT_CORE, STYLE_BLOCK, TOAST_HTML
from .shell import (
    BODY_OPEN_HTML,
    DATA_REFRESH_JS,
    HEADER_HTML,
    PROGRESS_BAR_HTML,
    SETUP_BANNER_HTML,
    WELCOME_HTML,
    WIRING_JS,
    WORKING_BANNER_HTML,
)
from .validation import DEPENDENCIES_JS, TEST_CASES_JS

INDEX_HTML = (
    HEAD_HTML
    + STYLE_BLOCK
    + BODY_OPEN_HTML
    + HEADER_HTML
    + PROGRESS_BAR_HTML
    + WORKING_BANNER_HTML
    + SETUP_BANNER_HTML
    + MAIN_OPEN_HTML
    + LIST_PANE_HTML
    + DETAIL_SECTION_HTML
    + WELCOME_HTML
    + MODAL_HTML
    + TOAST_HTML
    + SCRIPT_CORE
    + SYNTAX_HIGHLIGHT_JS
    + LIST_AND_DETAIL_JS
    + DEPENDENCIES_JS
    + TEST_CASES_JS
    + NAVIGATION_JS
    + DATA_REFRESH_JS
    + DECIDE_JS
    + JOB_PROGRESS_JS
    + PROPOSE_AND_POLL_JS
    + MODAL_JS
    + PICKER_JS
    + SETTINGS_JS
    + EXPORT_JS
    + DASHBOARD_JS
    + WIRING_JS
)
