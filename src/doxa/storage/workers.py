"""OS-held run ownership. A dead process releases its lock, never replays its work."""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID


@contextmanager
def worker_lease(directory: Path, run_id: UUID) -> Iterator[None]:
    root = directory / "worker-locks"
    root.mkdir(parents=True, exist_ok=True)
    # Keep the inode/path after release: deleting it creates split-lock races.
    with (root / f"{run_id}.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError(
                "Another worker owns this run; wait for it to exit before recovery"
            ) from None
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
