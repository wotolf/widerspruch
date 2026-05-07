"""
Async-Datenbankanbindung via SQLAlchemy 2.0 + asyncpg.

Exports:
    engine        — AsyncEngine (für Lifetime-Management)
    async_session — async_sessionmaker, direkt verwendbar
    get_session   — async context manager für einzelne Sessions
    init_db       — Verbindungsprüfung beim Start
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import settings

log = structlog.get_logger()

# URL: "postgresql://..." → "postgresql+asyncpg://..."
# Zweistufig damit auch "postgresql+psycopg2://..." korrekt behandelt wird.
_async_url: str = (
    settings.database_url
    .replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    .replace("postgresql://", "postgresql+asyncpg://", 1)
)

engine: AsyncEngine = create_async_engine(
    _async_url,
    echo=settings.environment == "development",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager für eine einzelne DB-Session.
    Commit on success, Rollback on exception.

        async with get_session() as session:
            player = await session.get(Player, player_id)
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Prüft beim App-Start ob die Datenbank erreichbar ist.
    Wirft bei Fehler — Bot soll nicht starten wenn DB down ist.
    """
    log.info("db_connecting", host=_async_url.split("@")[-1])
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("db_connected")
    except OperationalError as exc:
        log.error("db_connection_failed", error=str(exc))
        raise


__all__ = ["engine", "async_session", "get_session", "init_db"]
