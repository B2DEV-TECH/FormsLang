# 2. Installation

Use the Windows EXE or MSI from the [published GitHub release](https://github.com/B2DEV-TECH/FormsLang/releases/latest). Desktop users do not need Python. Check the release version and acceptance notes: unreleased branch features are not present in an older stable installer.

For a source checkout, install Python 3.10+ and run:

```console
python -m pip install -e .
formslang workbench
```

The browser Workbench binds to loopback. Keep its process running while working; jobs do not continue after it exits. Desktop packages the same engine with a Tauri shell.

On Windows, settings default to `%APPDATA%\FormsLang\config.json`; application data defaults to that directory. Project evidence lives in the selected project's `.formslang` directory. `FORMSLANG_CONFIG_DIR` and `FORMSLANG_DATA_DIR` are administrative overrides, not onboarding requirements.

Back up project folders and original 1.x sessions before upgrading. Uninstalling the program is not a request to erase source or project data. Never manually delete a project directory merely to resolve an installer error. Exact EXE/MSI upgrade evidence belongs in [quality acceptance](../quality-acceptance.md).
