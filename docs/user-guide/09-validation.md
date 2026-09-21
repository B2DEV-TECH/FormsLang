# 9. Validation

After generation, explicitly choose **Validate offline with SQLcl**. Install supported Oracle SQLcl separately. Set its executable path in Settings or the `FORMSLANG_SQLCL_PATH` environment variable before launching FormsLang if it is not discoverable. FormsLang does not redistribute Oracle binaries.

States distinguish Generated, Not Validated, Validated and Validation Failed. Evidence records artifact hash, tool/version, mode, timestamp and safe diagnostics. A changed artifact cannot retain a current validation claim.

Offline validation checks supported APEXlang syntax/structure. It does not prove runtime behavior, security, database availability or Forms equivalence. Unavailable tooling is Not Validated, not success; process exit zero alone is insufficient.

Live Oracle/APEX validation is separate, requires explicit authorization and should use a disposable schema/workspace. Never use a customer production schema for acceptance. Developers must inspect output, test behavior and complete UAT before deployment.
