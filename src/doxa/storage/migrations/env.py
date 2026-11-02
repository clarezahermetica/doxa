from alembic import context
from sqlalchemy import create_engine


def run() -> None:
    url = context.config.get_main_option("sqlalchemy.url")
    if url is None:
        raise ValueError("Migration database URL is required")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            # sqlite's legacy driver does not begin a transaction for DDL. Take
            # the writer lock before Alembic reads the version or creates tables.
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                context.configure(
                    connection=connection, render_as_batch=True, transactional_ddl=True
                )
                with context.begin_transaction():
                    context.run_migrations()
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
    finally:
        engine.dispose()


run()
