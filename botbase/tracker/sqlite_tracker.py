"""SQLite-based conversation tracker implementation."""

import datetime
import logging

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from botbase.database import async_session
from botbase.models import ConversationEvent
from botbase.tracker.base import ConversationTracker, Event

logger = logging.getLogger(__name__)


class SQLiteTracker(ConversationTracker):
    """SQLite-based conversation tracker.

    This tracker stores conversation events in a SQLite database using SQLAlchemy ORM.
    It provides the same interface as the base ConversationTracker while persisting
    data to SQLite.
    """

    def __init__(self, conv_id: str = None):
        super().__init__(conv_id)
        logger.info(f"Initializing SQLiteTracker for conversation {self.conv_id}")

    @classmethod
    async def create(cls, conv_id: str = None) -> "SQLiteTracker":
        """Create and initialize a new SQLiteTracker instance."""
        tracker = cls(conv_id)
        await tracker._load_history()
        return tracker

    def update_slot(self, name: str, value: any):
        """Update a slot value and add a slot event."""
        self.slots[name] = value
        self.add_event(Event(type="slot", payload={name: value}))

    async def _load_history(self):
        """Load past events for this conversation from the SQLite database.

        Rebuilds the tracker's event list and slot state.
        """
        logger.debug("Loading conversation history from SQLite")
        async with async_session() as session:
            result = await session.execute(
                select(ConversationEvent)
                .where(ConversationEvent.conv_id == self.conv_id)
                .order_by(ConversationEvent.created_at)
            )
            rows = result.scalars().all()
            for row in rows:
                event = Event.model_validate(row.payload)
                self.events.append(event)
                if event.type == "slot":
                    self.slots.update(event.payload)
            self._persisted_count = len(self.events)
            logger.info(f"Loaded {self._persisted_count} historical events for conversation {self.conv_id}")

    async def persist(self):
        """Persist new events (those not yet stored) to SQLite.

        Uses jsonable_encoder to properly serialize any datetime or non-serializable types.
        """
        new_events = self.events[self._persisted_count :]
        if not new_events:
            logger.debug("No new events to persist in SQLite")
            return

        logger.info(f"Persisting {len(new_events)} new events to SQLite")
        async with async_session() as session:
            async with session.begin():
                for event in new_events:
                    # Ensure created_at is set
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
