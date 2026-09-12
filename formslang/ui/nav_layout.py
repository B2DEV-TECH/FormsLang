"""Remember the navigation width without storing any review or project data."""

NAV_LAYOUT_JS = r"""
const navigationLayoutKey = "formslang.navigation";
const navigationTablet = window.matchMedia("(max-width: 1180px)");
const navigationMobile = window.matchMedia("(max-width: 720px)");
let navigationPreference = null;
try {
  const saved = localStorage.getItem(navigationLayoutKey);
  if (saved === "collapsed" || saved === "expanded") navigationPreference = saved;
} catch (_) { /* A blocked preference store must not affect navigation. */ }

function applyNavigationLayout() {
  const collapsed = navigationPreference === "collapsed" ||
    (navigationPreference === null && navigationTablet.matches);
  document.body.classList.toggle("nav-collapsed", collapsed);
  document.body.classList.toggle("nav-expanded", !collapsed);
  const button = $("nav-collapse");
  button.setAttribute("aria-expanded", String(!collapsed));
  button.setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
  button.title = collapsed ? "Expand navigation" : "Collapse navigation";
  window.dispatchEvent(new Event("formslang:layoutchange"));
}

$("nav-collapse").onclick = () => {
  if (navigationMobile.matches) return;
  navigationPreference = document.body.classList.contains("nav-collapsed") ? "expanded" : "collapsed";
  try { localStorage.setItem(navigationLayoutKey, navigationPreference); }
  catch (_) { /* Keep this session's layout even if persistence is unavailable. */ }
  applyNavigationLayout();
};
function resetNavigationLayout() {
  navigationPreference = null;
  try { localStorage.removeItem(navigationLayoutKey); }
  catch (_) { /* Reset the current window even when storage is unavailable. */ }
  applyNavigationLayout();
}
navigationTablet.addEventListener("change", applyNavigationLayout);
navigationMobile.addEventListener("change", applyNavigationLayout);
applyNavigationLayout();
"""
