"""Where a provider's traffic actually goes: nowhere, this machine, or the network.

``formslang.ai.provider_catalog()`` classifies a provider as ``cli`` or
``http`` -- a statement about how a *credential* is supplied, not about
where the *source code* ends up. ``claude_cli`` and ``codex_cli`` are "cli"
and still send the source to Anthropic/OpenAI over the network; ``ollama``
is "http" and, pointed at itself, never leaves the machine. For an
enterprise customer who must prove the source never left the building, the
credential axis is exactly the wrong axis to gate on. This module adds the
right one: egress.

Enforcement point is ``formslang.ai.build_provider`` -- the one chokepoint
every production call path passes through, ``workbench.py`` included, since
it calls ``build_provider`` directly rather than ``provider_from_env``. A
provider that ``check()`` refuses must also not be offered as available in
the catalog or accepted by the settings save -- see ``ai.provider_catalog``
and ``workbench.save_settings``/``start_job``, which apply this module at
those three points.

Known limitation, stated honestly rather than implied away: this module
looks at the *address* a provider would call -- loopback and private
ranges are LOCAL, everything else is CLOUD -- not at what a gateway behind
that address does with the traffic afterwards. An on-premise proxy at a
private IP that forwards to a public model is invisible to this check by
design (the README documents that pattern); it is a policy about where a
direct connection goes, not a network audit.
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

VERSION = "policy/1"

NONE, LOCAL, CLOUD = "NONE", "LOCAL", "CLOUD"
EGRESS_LEVELS = (NONE, LOCAL, CLOUD)

ENTERPRISE_ENV = "FORMSLANG_ENTERPRISE_MODE"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

# Providers with no ``base_url`` to inspect -- their egress is fixed, not a
# function of an endpoint. The CLI providers are subprocesses that call out
# to their own hosted backend; Echo makes no network call at all.
_FIXED_EGRESS = {
    "echo": NONE,
    "claude_cli": CLOUD,
    "codex_cli": CLOUD,
}


class PolicyViolation(ValueError):
    """A provider was refused because enterprise mode forbids its egress."""


def enterprise_mode() -> bool:
    """Whether enterprise mode is active for this process.

    Mirrors ``FORMSLANG_SECRET_BACKEND``'s reading convention in
    ``secrets.py``: empty or unset is off, and off is the only default that
    keeps every existing local install behaving exactly as it did before
    this module existed.
    """
    value = os.environ.get(ENTERPRISE_ENV, "").strip().lower()
    return value in {"1", "true", "on", "yes"}


def _is_local_host(host: str) -> bool:
    host = (host or "").strip().lower()
    if not host:
        return False
    if host in _LOCAL_HOSTS:
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_private


def egress_for(type_id: str, base_url: str = "") -> str:
    """Where this provider's traffic goes, given the endpoint it would use.

    A provider this module cannot prove is local -- an unknown type id, a
    blank or unparseable ``base_url``, a hostname instead of a loopback or
    private address -- is classed CLOUD. That is a deliberate fail-closed
    default, the same instinct as MFA verification failing closed when the
    credential vault is unreachable: an egress class we cannot establish is
    treated as leaving the building, never as staying inside it.
    """
    type_id = (type_id or "").strip().lower()
    if type_id in _FIXED_EGRESS:
        return _FIXED_EGRESS[type_id]
    host = urlparse(base_url or "").hostname or ""
    return LOCAL if _is_local_host(host) else CLOUD


def check(type_id: str, base_url: str = "") -> None:
    """Raise :class:`PolicyViolation` when enterprise mode forbids this egress.

    A no-op whenever ``enterprise_mode()`` is off -- the default, and the
    only behaviour every existing local install ever sees.
    """
    if not enterprise_mode():
        return
    egress = egress_for(type_id, base_url)
    if egress == CLOUD:
        raise PolicyViolation(
            f"Enterprise mode is on ({ENTERPRISE_ENV}=1): this provider would "
            "send source code off this machine, and enterprise mode blocks "
            "that outright. Pick a local provider instead -- Ollama pointed "
            "at a loopback or private address, or Echo."
        )
