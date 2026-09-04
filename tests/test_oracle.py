"""Finding the Oracle Forms home: fixed paths, then whatever the installer was told."""

from __future__ import annotations

import os

import pytest

from formslang import oracle


def _make_home(root, name):
    """A folder that looks enough like a Forms 12c/14c home to be picked."""
    home = root / name
    java = home / "oracle_common" / "jdk" / "bin" / ("java.exe" if os.name == "nt" else "java")
    java.parent.mkdir(parents=True)
    java.write_bytes(b"")
    for jar in oracle._JARS:
        path = home / jar.replace("\\", os.sep)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    return home


@pytest.fixture()
def only_scanned(tmp_path, monkeypatch):
    """No fixed candidates, no ORACLE_HOME: only the scanned root can answer."""
    root = tmp_path / "Oracle"
    root.mkdir()
    monkeypatch.delenv("ORACLE_HOME", raising=False)
    monkeypatch.setattr(oracle, "_CANDIDATE_HOMES", ())
    monkeypatch.setattr(oracle, "_CANDIDATE_ROOTS", (str(root),))
    return root


def test_a_home_named_by_the_installer_is_found_under_the_root(only_scanned):
    home = _make_home(only_scanned, "FR1412")
    (only_scanned / "notes.txt").write_text("not a home", encoding="utf-8")
    (only_scanned / "Empty").mkdir()  # a folder without jlib is never tried

    tc = oracle.detect_toolchain()
    assert tc.oracle_home == home
    assert tc.java_exe.parent == home / "oracle_common" / "jdk" / "bin"
    assert str(home / "jlib" / "frmxmltools.jar") in tc.classpath


def test_scanned_homes_are_tried_in_name_order(only_scanned):
    _make_home(only_scanned, "FR1412")
    first = _make_home(only_scanned, "A_Forms")
    assert oracle.detect_toolchain().oracle_home == first


def test_an_explicit_home_still_wins(only_scanned, tmp_path):
    _make_home(only_scanned, "FR1412")
    chosen = _make_home(tmp_path, "Chosen")
    assert oracle.detect_toolchain(str(chosen)).oracle_home == chosen


def test_an_incomplete_home_is_named_in_the_error(only_scanned):
    home = only_scanned / "FR1412"
    (home / "jlib").mkdir(parents=True)  # looks like a home, has nothing in it
    with pytest.raises(oracle.OracleToolchainError, match="FR1412"):
        oracle.detect_toolchain()


def test_nothing_found_says_so(only_scanned):
    with pytest.raises(oracle.OracleToolchainError, match="no ORACLE_HOME found"):
        oracle.detect_toolchain()
