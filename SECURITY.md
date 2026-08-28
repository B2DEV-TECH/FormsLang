# Security Policy

FormsLang runs against source code that is often confidential — Oracle
Forms modules from real systems. Security reports are taken seriously.

## Reporting a vulnerability

**Do not open a public GitHub issue for a vulnerability.**

Use GitHub's private vulnerability reporting instead:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Describe the issue, how to reproduce it and its impact.

Reports go privately to the maintainer ([@gevianajr](https://github.com/gevianajr)).
You can expect an acknowledgement within a few days and a fix or a
mitigation plan before any public disclosure.

## Scope

Especially relevant areas:

- The local workbench server (`formslang/workbench.py`) — it binds loopback
  only, checks the `Host` header on every request and enforces a strict
  `Content-Type` on every POST. Anything that lets a remote page read or
  write session data is a vulnerability.
- API key handling (`formslang/config.py`, `formslang/ai.py`) — keys are
  write-only over HTTP and must never appear in a response, a log line or
  an error message.
- The exported ZIP and the upload path — path traversal, symlink tricks,
  zip-slip.

## Supported versions

Only the latest release receives fixes.
