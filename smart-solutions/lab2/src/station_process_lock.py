"""Local, cooperative process lock for one canonical station SQLite path.

Keep the sidecar file: unlinking it could let another process lock a new inode
while the original owner is still running. This is not a global MG400 lock.
"""

from __future__ import annotations

import os
from pathlib import Path


class StationLockError(RuntimeError):
    """The station must not open its database or USB port."""


class StationProcessLock:
    def __init__(self, database: str | Path) -> None:
        try:
            self.database_path = Path(os.path.normcase(str(Path(database).expanduser().resolve())))
        except (OSError, RuntimeError) as error:
            raise StationLockError("cannot resolve station database path") from error
        self.lock_path = self.database_path.with_name(self.database_path.name + ".station.lock")
        self._fd: int | None = None

    def __enter__(self) -> "StationProcessLock":
        if self._fd is not None:
            raise StationLockError("station process lock is already held by this instance")
        descriptor = None
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            # Never truncate the file. Python's os.open descriptors are non-inheritable.
            descriptor = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            if os.name == "nt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                # Windows permits locking a region beyond EOF, including an empty file.
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            elif os.name == "posix":
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                raise OSError("unsupported process lock platform")
        except (OSError, ImportError) as error:
            if descriptor is not None:
                os.close(descriptor)
            raise StationLockError("cannot acquire station database process lock") from error
        self._fd = descriptor
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        descriptor, self._fd = self._fd, None
        if descriptor is not None:
            # Closing releases the OS lock on both platforms, also on exceptional exit.
            # The OS closes it if the owning process crashes or is terminated.
            os.close(descriptor)
