"""Local OS-held locks: opening a project cannot revoke another live worker."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path

from .project_model import ProjectBusy, ProjectError

_registry_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


@contextmanager
def project_worker_lock(root: Path):
    root = Path(root).absolute()
    directory = root / '.formslang'
    path = directory / 'project.worker.lock'
    if root.resolve() != root or directory.resolve() != directory or path.resolve() != path:
        raise ProjectError('Project worker lock path was redirected')
    key = os.path.normcase(str(path))
    with _registry_guard:
        lock = _locks.setdefault(key, threading.Lock())
    if not lock.acquire(blocking=False):
        raise ProjectBusy('Another project operation is active')
    stream = None
    acquired = False
    try:
        stream = path.open('a+b')
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b'\0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise ProjectBusy('Another project operation is active') from exc
        yield
    finally:
        if stream is not None:
            try:
                if acquired:
                    stream.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            finally:
                stream.close()
        lock.release()
