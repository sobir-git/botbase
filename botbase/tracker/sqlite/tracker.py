"""SQLite-based conversation tracker implementation."""

import datetime
import logging
from typing import List, Tuple

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from botbase.config import SqliteTrackerConfig
from botbase.tracker.base import ConversationTracker, Event
from botbase.tracker.sqlite.database import ConversationEvent, init_database

logger = logging.getLogger(__name__)


# Set aiosqlite logger to WARNING to suppress DEBUG logs.
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


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

        This method loads all events from the database, finds the most recent session event,
        and then rebuilds the in-memory state (events and slots) using only events from the
        current session.
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
            rows = result.scalars().all()

            loaded_events: List[Tuple[Event, str]] = []
            # Build a list of tuples: (parsed event, stored event type)
            for row in rows:
                try:
                    # Parse the stored payload into an Event instance.
                    event_obj = Event(**row.payload)
                    loaded_events.append((event_obj, row.event_type))
                except Exception as e:
                    logger.error("Error parsing event from payload", exc_info=e)

            # Find the index of the last session event (if any).
            last_session_index = self._get_last_session_index([e for (e, _) in loaded_events])
            if last_session_index >= 0:
                # Only keep events from the last session event onward.
                loaded_events = loaded_events[last_session_index:]
            # Else, if no session event was found, all events are part of the current session.

            # Rebuild in-memory events and slots from the filtered list.
            for event_obj, _ in loaded_events:
                self.events.append(event_obj)
                if event_obj.type == "slot":
                    # Update slots with the data from slot events.
                    self._slots.update(event_obj.payload)
            self._persisted_count = len(self.events)
            logger.info(f"Loaded {len(self.events)} historical events for conversation {self.conv_id}")

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
