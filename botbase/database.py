import logging

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from botbase.config import config

logger = logging.getLogger(__name__)

if config.tracker == "postgresql":
    logger.info("Configuring PostgreSQL engine for conversation persistence")
    engine = create_async_engine(config.postgres.url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
else:
    logger.info("Using JSONL persistence, no SQL engine will be configured")
    engine = None
    async_session = None
