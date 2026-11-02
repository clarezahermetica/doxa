from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection, connect

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL


def require_active_run(db: Connection, run_id: str) -> None:
    import json

    row = db.execute(
        "SELECT body FROM records WHERE run_id=? AND kind='run_state' ORDER BY rowid DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    if row and json.loads(row[0])["status"] in {"cancelled", "failed", "completed"}:
        raise ValueError("Run is terminal; no further inference may be dispatched")


def migrate(path: Path, revision: str = "head") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    url = URL.create("sqlite", database=str(path.resolve())).render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, revision)


@contextmanager
def connection(path: Path) -> Iterator[Connection]:
    db = connect(path, timeout=10)
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        db.close()
