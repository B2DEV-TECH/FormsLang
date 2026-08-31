# -*- mode: python ; coding: utf-8 -*-
#
# Before running this spec, reinstall the package non-editably from the repo
# root: `pip install --no-deps --force-reinstall .`. PyInstaller resolves
# `formslang` from whatever is on sys.path, not from this file's location --
# an editable install (`pip install -e .`) breaks static analysis here
# (ModuleNotFoundError: formslang.cli in the frozen exe), and a stale
# non-editable install silently freezes an old release's code with no error
# at build time.
from PyInstaller.utils.hooks import collect_data_files

datas = []
datas += collect_data_files('formslang')


a = Analysis(
    ['sidecar_entry.py'],
    pathex=['.'],
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
