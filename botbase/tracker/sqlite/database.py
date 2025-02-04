"""SQLite database implementation for conversation tracking."""

from pathlib import Path
from typing import Optional

from sqlalchemy import JSON, TIMESTAMP, Column, Index, Integer, String, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class ConversationEvent(Base):
    """Model for storing conversation events in SQLite."""

    __tablename__ = "conversation_events"

    id = Column(Integer, primary_key=True)
    conv_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_conversation_events_conv_id", "conv_id"),)


def get_sqlite_url(db_path: str) -> str:
    """Get SQLite URL from database path."""
    return f"sqlite+aiosqlite:///{db_path}"


# Global session factory for SQLite.
_global_async_session: Optional[sessionmaker] = None


async def init_database(db_path: str) -> sessionmaker:
    """
    Initialize SQLite database and return a globally shared session factory.
    If already initialized, return the existing session factory.
    """
    global _global_async_session
    if _global_async_session is not None:
        return _global_async_session

    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(
        get_sqlite_url(db_path),
        echo=False,  # Set to False in production
    )

    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    _global_async_session = async_session
    return _global_async_session
