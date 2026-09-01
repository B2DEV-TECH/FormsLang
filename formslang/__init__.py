"""FormsLang -- Oracle Forms analysis and conversion to Oracle APEX.

Reads .fmb modules through the Oracle Forms XML toolchain, classifies every
trigger and built-in against a Forms->APEX catalog, and reports measured
effort instead of guessed effort.

Not affiliated with, nor endorsed by, Oracle Corporation. Oracle, Oracle
Forms and Oracle APEX are trademarks of Oracle Corporation.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("formslang")
except PackageNotFoundError:
    # Running from source with no installed distribution (e.g. a fresh
    # editable checkout before `pip install -e .`) -- pyproject.toml is
    # the source of truth; this is a fallback only, kept in sync by hand.
    __version__ = "0.1.6"

__all__ = ["__version__"]
