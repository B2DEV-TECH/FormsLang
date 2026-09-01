"""Doc/diff buttons: open the technical documentation report for the module
on screen, or pick another version and open a structural diff against it --
split out of formslang/ui.py.

Both reports are their own self-contained HTML page (own CSS, no SPA chrome),
generated server-side by formdoc.py/formdiff.py, so they are opened in a new
tab rather than fetched as JSON through api().
"""

from __future__ import annotations

FORMDOC_JS = r"""function openDoc() {
  if (!state.can_export_apex) { toast("Open a Forms module first", true); return; }
  window.open("/api/doc", "_blank");
}
function diffWith(path) {
  closeModal();
  window.open("/api/diff?other=" + encodeURIComponent(path), "_blank");
}
function pickDiffTarget() {
  if (!state.can_export_apex) { toast("Open a Forms module first", true); return; }
  browse("", {
    onPick: diffWith,
    title: "Compare against another module",
    hint: "Pick the other version of this module to compare against — the module open now is the baseline.",
    buttonLabel: "Compare",
    allowUpload: false,
  });
}
"""
