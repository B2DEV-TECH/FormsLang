"""Credentials, kept where the operating system keeps secrets.

The settings file records what provider to use and which model; it must not
record the credential. This module is the credential half, and it talks to
the platform's own store:

===========  ==========================================================
Windows      Credential Manager, through ``advapi32`` (``CredReadW`` /
             ``CredWriteW`` / ``CredDeleteW``)
macOS        Keychain, through the ``security`` tool that ships with the
             system
Linux/BSD    Secret Service, through ``secret-tool`` (libsecret)
===========  ==========================================================

Two rules shape the code below.

**Zero third-party dependencies.** FormsLang runs on locked-down machines
where installing a package is a change request, so no ``keyring``, no
``pywin32``: ``ctypes`` on Windows, and on the others the binary the
platform already ships. That is also why the Unix backends exist at all --
they are a subprocess call, not a dependency.

**No silent fallback to plaintext.** If no backend answers, storing a key
fails with :class:`SecureStorageUnavailable` and the caller tells the user
to set ``FORMSLANG_AI_KEY`` instead. A credential is never quietly written
somewhere less safe than the user was promised.

The secret never travels on a command line: ``secret-tool`` reads it from
stdin, and ``security`` is driven in interactive mode so the value goes
through a pipe as well. The same reasoning the CLI providers use for source
code applies to a key -- a process listing is not a private place.

``FORMSLANG_SECRET_BACKEND`` forces a backend by name; ``memory`` is a
process-local store with no persistence, which is how the test suite keeps
its hands off a real keychain.

**Two callers, two APIs.** ``get_key``/``set_key``/``delete_key`` are the
original, single-slot API for the AI provider key (``FormsLang:ai-api-key``)
and are unchanged in behavior, including ``get_key()``'s choice to swallow
every failure into ``""`` -- reasonable there, since worst case the user
retypes a key. ``get_secret``/``set_secret``/``delete_secret`` are the
general, multi-slot API (design doc section 2.3, D6): any ``(service,
account)`` pair gets its own entry, used for one MFA TOTP secret per user
(``FormsLang:mfa-totp:<user_id>``). ``get_secret`` deliberately does not
swallow a store failure into ``""`` the way ``get_key`` does -- MFA
correctness depends on telling "not enrolled" apart from "the vault could
not be reached," and collapsing those would let a transient store failure
either look like a bypass or an unexplained lockout.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

# One well-known identity in whatever store answers. Changing either string
# orphans every key already saved, so they are constants on purpose.
SERVICE = "FormsLang"
ACCOUNT = "ai-api-key"
TARGET = f"{SERVICE}:{ACCOUNT}"

#: What the user is told when the platform offers nowhere safe to put a key.
UNAVAILABLE_MESSAGE = (
    "Secure credential storage is not available. "
    "Use an environment variable instead."
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")


class SecureStorageUnavailable(RuntimeError):
    """No OS credential store answered, so nothing was saved or read."""

    def __init__(self, message: str = UNAVAILABLE_MESSAGE) -> None:
        super().__init__(message)


def _clean(value: str) -> str:
    """A secret must be one line of printable text, or we cannot pass it safely."""
    value = str(value or "").strip()
    if any(ch.isspace() for ch in value):
        raise ValueError("a secret cannot contain whitespace")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("a secret cannot contain control characters")
    return value


def _clean_identifier(kind: str, value: str) -> str:
    """``service``/``account`` are interpolated into a command line for the
    macOS backend's interactive ``security -i`` mode, so they get the same
    scrutiny an argument would -- this is what keeps a caller-supplied
    account name (e.g. built from a user id) from ever being able to inject
    an extra command into that stream."""
    value = str(value or "")
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"invalid {kind}: {value!r}")
    return value


# -- Windows: Credential Manager -------------------------------------------


class _WindowsBackend:
    """Generic credentials in the Windows Credential Manager, via ctypes."""

    name = "credential-manager"
    label = "Windows Credential Manager"

    _CRED_TYPE_GENERIC = 1
    _CRED_PERSIST_LOCAL_MACHINE = 2
    _ERROR_NOT_FOUND = 1168

    def __init__(self) -> None:
        import ctypes
        import ctypes.wintypes as wt

        self._ctypes = ctypes
        self._advapi = ctypes.WinDLL("advapi32", use_last_error=True)

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", wt.DWORD),
                ("dwHighDateTime", wt.DWORD),
            ]

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", wt.DWORD),
                ("Type", wt.DWORD),
                ("TargetName", wt.LPWSTR),
                ("Comment", wt.LPWSTR),
                ("LastWritten", FILETIME),
                ("CredentialBlobSize", wt.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
                ("Persist", wt.DWORD),
                ("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wt.LPWSTR),
                ("UserName", wt.LPWSTR),
            ]

        self._CREDENTIAL = CREDENTIAL
        self._advapi.CredReadW.argtypes = [
            wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIAL))
        ]
        self._advapi.CredReadW.restype = wt.BOOL
        self._advapi.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wt.DWORD]
        self._advapi.CredWriteW.restype = wt.BOOL
        self._advapi.CredDeleteW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD]
        self._advapi.CredDeleteW.restype = wt.BOOL
        self._advapi.CredFree.argtypes = [ctypes.c_void_p]
        self._advapi.CredFree.restype = None

    def available(self) -> bool:
        return True

    def get(self, service: str, account: str) -> str:
        ctypes = self._ctypes
        target = f"{service}:{account}"
        ptr = ctypes.POINTER(self._CREDENTIAL)()
        ok = self._advapi.CredReadW(target, self._CRED_TYPE_GENERIC, 0, ctypes.byref(ptr))
        if not ok:
            err = ctypes.get_last_error()
            if err not in (0, self._ERROR_NOT_FOUND):
                # Something other than "no such entry" -- do not let the
                # caller read this as "not enrolled".
                raise SecureStorageUnavailable(
                    f"Windows Credential Manager could not be read (error {err}). "
                    f"{UNAVAILABLE_MESSAGE}"
                )
            return ""  # not found is the ordinary case, not an error
        try:
            cred = ptr.contents
            blob = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
        finally:
            self._advapi.CredFree(ptr)
        for encoding in ("utf-16-le", "utf-8"):
            try:
                return blob.decode(encoding).strip("\x00").strip()
            except UnicodeDecodeError:
                continue
        return ""

    def set(self, service: str, account: str, value: str, *, comment: str = "") -> None:
        ctypes = self._ctypes
        target = f"{service}:{account}"
        blob = value.encode("utf-16-le")
        buf = ctypes.create_string_buffer(blob, len(blob))
        cred = self._CREDENTIAL()
        cred.Flags = 0
        cred.Type = self._CRED_TYPE_GENERIC
        cred.TargetName = target
        cred.Comment = comment or "FormsLang credential"
        cred.CredentialBlobSize = len(blob)
        cred.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))
        cred.Persist = self._CRED_PERSIST_LOCAL_MACHINE
        cred.AttributeCount = 0
        cred.Attributes = None
        cred.TargetAlias = None
        cred.UserName = account
        if not self._advapi.CredWriteW(ctypes.byref(cred), 0):
            raise SecureStorageUnavailable(
                "Windows Credential Manager refused to store the credential "
                f"(error {ctypes.get_last_error()}). {UNAVAILABLE_MESSAGE}"
            )

    def delete(self, service: str, account: str) -> None:
        # Deleting what is not there is a success, not a failure.
        target = f"{service}:{account}"
        self._advapi.CredDeleteW(target, self._CRED_TYPE_GENERIC, 0)


# -- macOS: Keychain --------------------------------------------------------


class _MacBackend:
    """Generic keychain items through ``/usr/bin/security``."""

    name = "keychain"
    label = "macOS Keychain"
    binary = "/usr/bin/security"

    def available(self) -> bool:
        return os.path.exists(self.binary)

    def get(self, service: str, account: str) -> str:
        out = _run(
            [self.binary, "find-generic-password", "-a", account, "-s", service, "-w"]
        )
        return out.strip() if out is not None else ""

    def set(self, service: str, account: str, value: str, *, comment: str = "") -> None:
        # Interactive mode reads commands from stdin, so the key is never an
        # argument of a process anyone can list. ``-w`` takes the rest of the
        # token, and _clean() has already ruled out whitespace; service and
        # account have already passed _clean_identifier().
        label = comment or service
        command = (
            f"add-generic-password -U -a {account} -s {service} "
            f"-l {label} -D 'application password' -w {value}\n"
        )
        if _run([self.binary, "-i"], stdin=command) is None:
            raise SecureStorageUnavailable(
                f"the macOS Keychain refused to store the credential. {UNAVAILABLE_MESSAGE}"
            )

    def delete(self, service: str, account: str) -> None:
        _run([self.binary, "delete-generic-password", "-a", account, "-s", service])


# -- Linux and the BSDs: Secret Service -------------------------------------


class _SecretToolBackend:
    """The freedesktop Secret Service, through libsecret's ``secret-tool``."""

    name = "secret-service"
    label = "Secret Service (libsecret)"

    def __init__(self) -> None:
        self._binary = shutil.which("secret-tool") or ""

    def available(self) -> bool:
        return bool(self._binary)

    def get(self, service: str, account: str) -> str:
        out = _run(
            [self._binary, "lookup", "service", service, "account", account]
        )
        return out.strip() if out is not None else ""

    def set(self, service: str, account: str, value: str, *, comment: str = "") -> None:
        # ``store`` reads the secret from stdin by design.
        label = comment or service
        ok = _run(
            [
                self._binary, "store",
                "--label", label,
                "service", service, "account", account,
            ],
            stdin=value + "\n",
        )
        if ok is None:
            raise SecureStorageUnavailable(
                "the Secret Service refused to store the credential (is a keyring "
                f"daemon running?). {UNAVAILABLE_MESSAGE}"
            )

    def delete(self, service: str, account: str) -> None:
        _run([self._binary, "clear", "service", service, "account", account])


# -- tests only -------------------------------------------------------------


class _MemoryBackend:
    """A process-local store. Never persisted, never a production choice."""

    name = "memory"
    label = "in-memory (testing)"
    _store: dict[tuple[str, str], str] = {}

    def available(self) -> bool:
        return True

    def get(self, service: str, account: str) -> str:
        return _MemoryBackend._store.get((service, account), "")

    def set(self, service: str, account: str, value: str, *, comment: str = "") -> None:
        _MemoryBackend._store[(service, account)] = value

    def delete(self, service: str, account: str) -> None:
        _MemoryBackend._store.pop((service, account), None)


def reset_memory_backend() -> None:
    """Empty the test backend, so one test cannot see another's secret."""
    _MemoryBackend._store.clear()


# -- picking one ------------------------------------------------------------


def _run(argv: list[str], stdin: str | None = None) -> str | None:
    """Run a helper; ``None`` means it failed, a string means it answered."""
    try:
        proc = subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


_CACHE: dict = {}


def _build(forced: str):
    if forced == "memory":
        return _MemoryBackend()
    if forced == "none":
        return None
    candidates = []
    if os.name == "nt":
        candidates.append(_WindowsBackend)
    elif sys.platform == "darwin":
        candidates.append(_MacBackend)
    else:
        candidates.append(_SecretToolBackend)
    for cls in candidates:
        if forced and cls.name != forced:
            continue
        try:
            backend = cls()
        except Exception:  # a missing DLL, a broken install: try the next one
            continue
        if backend.available():
            return backend
    return None


def backend():
    """The credential store for this machine, or ``None`` if there is none."""
    forced = os.environ.get("FORMSLANG_SECRET_BACKEND", "").strip().lower()
    if _CACHE.get("forced") != forced or "backend" not in _CACHE:
        _CACHE.clear()
        _CACHE["forced"] = forced
        _CACHE["backend"] = _build(forced)
    return _CACHE["backend"]


def available() -> bool:
    return backend() is not None


def backend_name() -> str:
    b = backend()
    return b.name if b else ""


def backend_label() -> str:
    b = backend()
    return b.label if b else ""


# -- the AI provider key API (unchanged behavior) ---------------------------


def get_key() -> str:
    """The stored key, or ``""`` -- an unreadable store is not an error here."""
    b = backend()
    if b is None:
        return ""
    try:
        return b.get(SERVICE, ACCOUNT)
    except Exception:
        return ""


def set_key(value: str) -> None:
    """Store the key. Raises if the platform has nowhere safe to put it."""
    value = _clean(value)
    if not value:
        delete_key()
        return
    b = backend()
    if b is None:
        raise SecureStorageUnavailable()
    b.set(SERVICE, ACCOUNT, value, comment="FormsLang AI provider API key")


def delete_key() -> None:
    """Forget the stored key. Silent when there is nothing to forget."""
    b = backend()
    if b is None:
        return
    try:
        b.delete(SERVICE, ACCOUNT)
    except Exception:
        pass


# -- the general (service, account) API, e.g. one MFA secret per user -------


def get_secret(service: str, account: str) -> str:
    """The stored secret for ``(service, account)``, or ``""`` if unset.

    Deliberately does not swallow a store failure the way :func:`get_key`
    does: raises :class:`SecureStorageUnavailable` if there is no backend at
    all, or if the backend answered with something other than "not found".
    A caller that needs to know whether a user has enrolled MFA must not
    have that question silently collapsed into "no".
    """
    service = _clean_identifier("service", service)
    account = _clean_identifier("account", account)
    b = backend()
    if b is None:
        raise SecureStorageUnavailable()
    try:
        return b.get(service, account)
    except SecureStorageUnavailable:
        raise
    except Exception as e:
        raise SecureStorageUnavailable(
            f"the credential store could not be read. {UNAVAILABLE_MESSAGE}"
        ) from e


def set_secret(service: str, account: str, value: str, *, comment: str = "") -> None:
    """Store a secret under ``(service, account)``. Raises if there is
    nowhere safe to put it -- there is no lower-security fallback."""
    service = _clean_identifier("service", service)
    account = _clean_identifier("account", account)
    value = _clean(value)
    if not value:
        delete_secret(service, account)
        return
    b = backend()
    if b is None:
        raise SecureStorageUnavailable()
    b.set(service, account, value, comment=comment)


def delete_secret(service: str, account: str) -> None:
    """Forget a stored secret. Silent when there is nothing to forget or no
    backend to ask -- deleting is the terminal state either way, and
    ``auth.db`` (not this module) is the source of truth for whether a user
    is enrolled, so an orphaned vault entry left behind by an unreachable
    backend is inert, never re-read once the caller has moved on."""
    service = _clean_identifier("service", service)
    account = _clean_identifier("account", account)
    b = backend()
    if b is None:
        return
    try:
        b.delete(service, account)
    except Exception:
        pass
