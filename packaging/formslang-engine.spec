# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from importlib.metadata import version
import re

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

project_root = Path(SPECPATH).parent
expected = re.search(r'^version\s*=\s*"([^"]+)"',
                     (project_root / 'pyproject.toml').read_text(encoding='utf-8'), re.MULTILINE)[1]
if version('formslang') != expected:
    raise RuntimeError('Stale FormsLang package metadata. Regenerate egg_info and reinstall '
                       'the editable package before building the engine.')

datas = []
datas += collect_data_files('formslang')
datas += copy_metadata('formslang')


a = Analysis(
    ['sidecar_entry.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='formslang-engine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
