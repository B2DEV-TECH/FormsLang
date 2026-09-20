"""Local OS-held locks: opening a project cannot revoke another live worker."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path

from .project_model import ProjectBusy, ProjectError

_registry_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}
_thread_state = threading.local()


@contextmanager
def project_worker_lock(root: Path, *, blocking: bool = False):
    root = Path(root).absolute()
    directory = root / '.formslang'
    path = directory / 'project.worker.lock'
    if root.resolve() != root or directory.resolve() != directory or path.resolve() != path:
        raise ProjectError('Project worker lock path was redirected')
    key = os.path.normcase(str(path))
    owned = getattr(_thread_state, 'blocking_keys', None)
    if blocking and owned is not None and key in owned:
        yield
        return
    with _registry_guard:
        lock = _locks.setdefault(key, threading.Lock())
    if not lock.acquire(blocking=blocking):
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
                mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
                msvcrt.locking(stream.fileno(), mode, 1)
            else:
                import fcntl
                mode = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
                fcntl.flock(stream.fileno(), mode)
            acquired = True
        except OSError as exc:
            raise ProjectBusy('Another project operation is active') from exc
        if blocking:
            if owned is None:
                owned = set()
                _thread_state.blocking_keys = owned
            owned.add(key)
        yield
    finally:
        if blocking and acquired:
            owned.remove(key)
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
