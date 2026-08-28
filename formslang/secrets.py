"""The API key, kept where the operating system keeps secrets.

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
"""

from __future__ import annotations

import os
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


class SecureStorageUnavailable(RuntimeError):
    """No OS credential store answered, so nothing was saved."""

    def __init__(self, message: str = UNAVAILABLE_MESSAGE) -> None:
        super().__init__(message)


def _clean(value: str) -> str:
    """A key must be one line of printable text, or we cannot pass it safely."""
    value = str(value or "").strip()
    if any(ch.isspace() for ch in value):
        raise ValueError("an API key cannot contain whitespace")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("an API key cannot contain control characters")
    return value


# -- Windows: Credential Manager -------------------------------------------


class _WindowsBackend:
    """Generic credentials in the Windows Credential Manager, via ctypes."""

    name = "credential-manager"
    label = "Windows Credential Manager"

    _CRED_TYPE_GENERIC = 1
    _CRED_PERSIST_LOCAL_MACHINE = 2

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

    def get(self) -> str:
        ctypes = self._ctypes
        ptr = ctypes.POINTER(self._CREDENTIAL)()
        ok = self._advapi.CredReadW(TARGET, self._CRED_TYPE_GENERIC, 0, ctypes.byref(ptr))
        if not ok:
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

    def set(self, value: str) -> None:
        ctypes = self._ctypes
        blob = value.encode("utf-16-le")
        buf = ctypes.create_string_buffer(blob, len(blob))
        cred = self._CREDENTIAL()
        cred.Flags = 0
        cred.Type = self._CRED_TYPE_GENERIC
        cred.TargetName = TARGET
        cred.Comment = "FormsLang AI provider API key"
        cred.CredentialBlobSize = len(blob)
        cred.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))
        cred.Persist = self._CRED_PERSIST_LOCAL_MACHINE
        cred.AttributeCount = 0
        cred.Attributes = None
        cred.TargetAlias = None
        cred.UserName = ACCOUNT
        if not self._advapi.CredWriteW(ctypes.byref(cred), 0):
            raise SecureStorageUnavailable(
                "Windows Credential Manager refused to store the key "
                f"(error {ctypes.get_last_error()}). {UNAVAILABLE_MESSAGE}"
            )

    def delete(self) -> None:
        # Deleting what is not there is a success, not a failure.
        self._advapi.CredDeleteW(TARGET, self._CRED_TYPE_GENERIC, 0)


# -- macOS: Keychain --------------------------------------------------------


class _MacBackend:
    """Generic keychain items through ``/usr/bin/security``."""

    name = "keychain"
    label = "macOS Keychain"
    binary = "/usr/bin/security"

    def available(self) -> bool:
        return os.path.exists(self.binary)

    def get(self) -> str:
        out = _run(
            [self.binary, "find-generic-password", "-a", ACCOUNT, "-s", SERVICE, "-w"]
        )
        return out.strip() if out is not None else ""

    def set(self, value: str) -> None:
        # Interactive mode reads commands from stdin, so the key is never an
        # argument of a process anyone can list. ``-w`` takes the rest of the
        # token, and _clean() has already ruled out whitespace.
        command = (
            f"add-generic-password -U -a {ACCOUNT} -s {SERVICE} "
            f"-l {SERVICE} -D 'application password' -w {value}\n"
        )
        if _run([self.binary, "-i"], stdin=command) is None:
            raise SecureStorageUnavailable(
                f"the macOS Keychain refused to store the key. {UNAVAILABLE_MESSAGE}"
            )

    def delete(self) -> None:
        _run([self.binary, "delete-generic-password", "-a", ACCOUNT, "-s", SERVICE])


# -- Linux and the BSDs: Secret Service -------------------------------------


class _SecretToolBackend:
    """The freedesktop Secret Service, through libsecret's ``secret-tool``."""

    name = "secret-service"
    label = "Secret Service (libsecret)"

    def __init__(self) -> None:
        self._binary = shutil.which("secret-tool") or ""

    def available(self) -> bool:
        return bool(self._binary)

    def get(self) -> str:
        out = _run(
            [self._binary, "lookup", "service", SERVICE, "account", ACCOUNT]
        )
        return out.strip() if out is not None else ""

    def set(self, value: str) -> None:
        # ``store`` reads the secret from stdin by design.
        ok = _run(
            [
                self._binary, "store",
                "--label", "FormsLang AI provider API key",
                "service", SERVICE, "account", ACCOUNT,
            ],
            stdin=value + "\n",
        )
        if ok is None:
            raise SecureStorageUnavailable(
                "the Secret Service refused to store the key (is a keyring "
                f"daemon running?). {UNAVAILABLE_MESSAGE}"
            )

    def delete(self) -> None:
        _run([self._binary, "clear", "service", SERVICE, "account", ACCOUNT])


# -- tests only -------------------------------------------------------------


class _MemoryBackend:
    """A process-local store. Never persisted, never a production choice."""

    name = "memory"
    label = "in-memory (testing)"
    _value = ""

    def available(self) -> bool:
        return True

    def get(self) -> str:
        return _MemoryBackend._value

    def set(self, value: str) -> None:
        _MemoryBackend._value = value

    def delete(self) -> None:
        _MemoryBackend._value = ""


def reset_memory_backend() -> None:
    """Empty the test backend, so one test cannot see another's key."""
    _MemoryBackend._value = ""


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


# -- the API the rest of FormsLang uses -------------------------------------


def get_key() -> str:
    """The stored key, or ``""`` -- an unreadable store is not an error here."""
    b = backend()
    if b is None:
        return ""
    try:
        return b.get()
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
    b.set(value)


def delete_key() -> None:
    """Forget the stored key. Silent when there is nothing to forget."""
    b = backend()
    if b is None:
        return
    try:
        b.delete()
    except Exception:
        pass
