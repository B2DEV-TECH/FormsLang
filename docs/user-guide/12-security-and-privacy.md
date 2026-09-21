# 12. Security and privacy

**Source stays local in the default static workflow.** Discovery, analysis, Overview, review, deterministic generation and reports need no external AI or database connection. No telemetry is sent by default.

Optional external AI is an explicit existing capability, not a prerequisite. Provider/context/policy choices govern egress. Treat any approved external call as disclosure; context reduction/redaction is not proof that arbitrary business logic is anonymous. AI cannot approve decisions or bypass generation policy.

Secrets use the OS credential store: Windows Credential Manager, macOS Keychain or Secret Service. Failure does not silently fall back to plaintext project/config storage. Never place credentials in source files, rationale, request JSON, logs or exports.

Local mode trusts the current OS user and requires no account. Authenticated mode additionally enforces current session/MFA scope, organization membership, project grants and action permissions. The server remains loopback-bound; reverse-proxy operation requires deliberate administrator configuration.

Descriptors are not filesystem permission grants. Authorized roots, containment, project IDs, revision fencing and bounded evidence apply to project APIs. Host/Origin/CSRF protections remain in force. A compromised OS account is outside this application's isolation guarantee.

Reports are not anonymous by default. Share the minimum needed, keep project folders on access-controlled storage and back up auth data together with required OS-secret material using your organization's procedures.
