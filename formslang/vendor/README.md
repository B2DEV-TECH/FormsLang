# Vendored third-party code

## qrcode-generator 1.4.4

| | |
|---|---|
| File | `qrcode-generator-1.4.4.js` |
| Project | QR Code Generator for JavaScript, by Kazuhiko Arase |
| Upstream | https://github.com/kazuhikoarase/qrcode-generator |
| Version | 1.4.4 (npm `qrcode-generator@1.4.4`, file `qrcode.js`) |
| License | MIT (`qrcode-generator-LICENSE`) -- compatible with Apache-2.0 |
| SHA-256 | `18ae399f81182bc9de916e9c77b195df20cc58d6f2d55a62b085a299f1bf1780` |

Retrieved 2026-08-31 from
`https://cdnjs.cloudflare.com/ajax/libs/qrcode-generator/1.4.4/qrcode.js` and
byte-for-byte verified against a second, independent distribution channel
(`https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.js`) -- both
yield the SHA-256 above. `tests/test_workbench_mfa.py` re-hashes the file on
every run, so any local modification fails the suite.

Why vendored: the MFA enrollment page renders the `otpauth://` provisioning
URI as a QR code **locally**. Loading an encoder from a CDN would leak the
page's existence to a third party and violate the workbench's
no-external-request rule (see `SECURITY.md`). The library uses no `eval`,
no `Function` constructor, and performs no network or DOM I/O of its own,
so it runs under the workbench's CSP (which has no `unsafe-eval`).

"QR Code" is a registered trademark of DENSO WAVE INCORPORATED.
