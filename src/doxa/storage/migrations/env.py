from alembic import context
from sqlalchemy import create_engine


def run() -> None:
    url = context.config.get_main_option("sqlalchemy.url")
    if url is None:
        raise ValueError("Migration database URL is required")
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run()
