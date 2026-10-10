import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.db import Base
from app import models  # noqa: F401


async def run():
    engine = create_async_engine(settings().database_url)
    async with engine.connect() as connection:

        def migrate(conn):
            context.configure(connection=conn, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()

        await connection.run_sync(migrate)
    await engine.dispose()


asyncio.run(run())
