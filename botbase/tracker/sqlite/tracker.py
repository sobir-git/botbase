"""SQLite-based conversation tracker implementation."""

import datetime
import logging

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from botbase.config import SqliteTrackerConfig
from botbase.tracker.base import ConversationTracker, Event
from botbase.tracker.sqlite.database import ConversationEvent, init_database

logger = logging.getLogger(__name__)


# Set aiosqlite logger to WARNING to suppress DEBUG logs.
logging.getLogger("aiosqlite").setLevel(logging.WARNING)


class SQLiteTracker(ConversationTracker):
    """SQLite-based conversation tracker that uses a shared async engine/session."""

    @classmethod
    async def create(cls, config: SqliteTrackerConfig, conv_id: str) -> "SQLiteTracker":
        """
        Create and initialize a new SQLite tracker instance.

        This method ensures the shared session factory is obtained and loads historical events.
        """
        tracker = cls(config, conv_id)
        await tracker.initialize()
        return tracker

    def __init__(self, config: SqliteTrackerConfig, conv_id: str):
        """
        Initialize SQLite tracker.

        Note: Use the create() classmethod instead of calling the constructor directly.
        """
        self.config = config
        # This attribute will hold the shared session factory.
        self._session_factory = None
        super().__init__(conv_id)
        logger.info(f"Initializing SQLiteTracker for conversation {self.conv_id}")
        self._persisted_count = 0
        self._slots = {}

    async def initialize(self) -> None:
        """
        Initialize the tracker by obtaining the shared session factory and loading
        conversation history from SQLite.
        """
        logger.debug("Initializing SQLiteTracker: loading conversation history using shared session")
        # Obtain the shared session factory (and initialize the database if needed).
        self._session_factory = await init_database(self.config.db_path)

        async with self._session_factory() as session:
            result = await session.execute(
                select(ConversationEvent)
                .where(ConversationEvent.conv_id == self.conv_id)
                .order_by(ConversationEvent.created_at)
            )
            events = result.scalars().all()
            for row in events:
                # Rebuild the Event from the stored payload.
                event_obj = Event(**row.payload)
                self.events.append(event_obj)
                # For slot events, update the tracker's slots.
                if row.event_type == "slot":
                    # Instead of expecting a nested key, update directly.
                    self._slots.update(row.payload["payload"])
            self._persisted_count = len(events)
            logger.info(f"Loaded {len(events)} historical events for conversation {self.conv_id}")

    async def persist(self) -> None:
        """
        Persist new events (those not yet stored) to SQLite using the shared session.
        """
        new_events = self.events[self._persisted_count :]
        if not new_events:
            logger.debug("No new events to persist in SQLite")
            return

        logger.info(f"Persisting {len(new_events)} new events to SQLite")
        async with self._session_factory() as session:
            async with session.begin():
                for event in new_events:
                    if event.created_at is None:
                        event.created_at = datetime.datetime.now()
                    payload = jsonable_encoder(event)
                    conv_event = ConversationEvent(
                        conv_id=self.conv_id,
                        event_type=event.type,
                        payload=payload,
                    )
                    session.add(conv_event)
            await session.commit()
        self._persisted_count = len(self.events)
        logger.info("Persistence to SQLite complete")

    def update_slot(self, name: str, value: str) -> None:
        """
        Update a slot value and add a slot event.
        (This method now simply calls set_slot from the base.)
        """
        self.set_slot(name, value)

    # No public slots property – users must call get_slot().
