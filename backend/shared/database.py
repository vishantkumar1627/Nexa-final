from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from shared.config import settings

# 1. Declarative Base
Base = declarative_base()

# 2. Async Engine and Session (For FastAPI)
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

async_engine_args = {
    "echo": False,
    "future": True,
}
if is_sqlite:
    async_engine_args["connect_args"] = connect_args
else:
    async_engine_args["pool_size"] = 10
    async_engine_args["max_overflow"] = 20

async_engine = create_async_engine(
    settings.DATABASE_URL,
    **async_engine_args
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 3. Sync Engine and Session (For Celery Tasks, Migrations)
is_sync_sqlite = settings.SYNC_DATABASE_URL.startswith("sqlite")
sync_connect_args = {"check_same_thread": False} if is_sync_sqlite else {}

sync_engine_args = {
    "echo": False,
}
if is_sync_sqlite:
    sync_engine_args["connect_args"] = sync_connect_args
else:
    sync_engine_args["pool_size"] = 5
    sync_engine_args["max_overflow"] = 10

sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    **sync_engine_args
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# 4. FastAPI Dependency Injectors
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions in FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_sync_db() -> Generator[Session, None, None]:
    """Helper for getting sync database sessions in workers or synchronous scripts."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
