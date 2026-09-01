"""Auth/login/MFA UI is not part of the workbench single-page app.

It is served separately by formslang/authui.py (its own HTML document
and inline script, including the vendored QR encoder for TOTP enrolment).
This module exists only for parity with the other named workbench UI
concerns; it currently has nothing to contribute to INDEX_HTML.
"""

from __future__ import annotations
