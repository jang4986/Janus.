import asyncio
import os

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine


def get_database_url() -> URL:
    if os.getenv("APP_ENV") != "e2e":
        raise RuntimeError("Database reset is only allowed in E2E environment.")

    if os.getenv("E2E_ALLOW_DATABASE_RESET") != "YES":
        raise RuntimeError("Set E2E_ALLOW_DATABASE_RESET=YES to allow database reset.")

    raw_url = os.getenv("DATABASE_URL")

    if not raw_url:
        raise RuntimeError("Missing DATABASE_URL.")

    url = make_url(raw_url)

    if url.get_backend_name() != "postgresql":
        raise RuntimeError("Only PostgreSQL is supported.")

    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")

    elif url.drivername != "postgresql+asyncpg":
        raise RuntimeError("Expected PostgreSQL asyncpg driver.")

    # Chuẩn hóa query parameters cho asyncpg.
    query = dict(url.query)

    # asyncpg không nhận channel_binding.
    query.pop("channel_binding", None)

    # asyncpg dùng ssl thay vì sslmode.
    sslmode = query.pop("sslmode", None)

    if sslmode and "ssl" not in query:
        query["ssl"] = sslmode

    return url.set(query=query)


async def reset_database():
    database_url = get_database_url()

    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        async with engine.begin() as connection:
            result = await connection.execute(
                text("""
                    SELECT format('%I.%I', schemaname, tablename)
                    FROM pg_tables
                    WHERE schemaname = 'public'
                      AND tablename <> 'alembic_version'
                    ORDER BY tablename
                """)
            )

            tables = result.scalars().all()

            if not tables:
                print("No application tables found.")
                return

            query = "TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"

            await connection.execute(text(query))

            print(f"Successfully reset {len(tables)} tables.")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset_database())
