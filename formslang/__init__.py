"""FormsLang -- Oracle Forms analysis and conversion to Oracle APEX.

Reads .fmb modules through the Oracle Forms XML toolchain, classifies every
trigger and built-in against a Forms->APEX catalog, and reports measured
effort instead of guessed effort.

Not affiliated with, nor endorsed by, Oracle Corporation. Oracle, Oracle
Forms and Oracle APEX are trademarks of Oracle Corporation.
"""

import re
from importlib.metadata import PackageNotFoundError, version


def _display_version(metadata_version: str) -> str:
    """Keep SemVer beta spelling across Python's PEP 440 normalization."""
    return re.sub(r"^(\d+\.\d+\.\d+)b([1-9]\d*)$", r"\1-beta.\2", metadata_version)

try:
    __version__ = _display_version(version("formslang"))
except PackageNotFoundError:
    # Running from source with no installed distribution (e.g. a fresh
    # editable checkout before `pip install -e .`) -- pyproject.toml is
    # the source of truth; this is a fallback only, kept in sync by hand.
    __version__ = "3.0.0-beta.1"

__all__ = ["__version__"]
