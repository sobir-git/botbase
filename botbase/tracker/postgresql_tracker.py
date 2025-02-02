import logging

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from botbase.database import async_session
from botbase.models import ConversationEvent
from botbase.tracker.base import ConversationTracker, Event

logger = logging.getLogger(__name__)


class PostgreSQLTracker(ConversationTracker):
    def __init__(self, conv_id: str = None):
        super().__init__(conv_id)
        logger.info(f"Initializing PostgreSQLTracker for conversation {self.conv_id}")
        # Asynchronous history loading can be scheduled if needed.
        # Here we call _load_history synchronously for simplicity.
        self._load_history()

    async def _load_history(self):
        """
        Load past events for this conversation from the PostgreSQL database.
        Rebuilds the tracker's event list and slot state.
        """
        logger.debug("Loading conversation history from PostgreSQL")
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
        """
        Persist new events (those not yet stored) to PostgreSQL.
        Uses jsonable_encoder to properly serialize any datetime or non-serializable types.
        """
        new_events = self.events[self._persisted_count :]
        if not new_events:
            logger.debug("No new events to persist in PostgreSQL")
            return

        logger.info(f"Persisting {len(new_events)} new events to PostgreSQL")
        async with async_session() as session:
            async with session.begin():
                for event in new_events:
                    payload = jsonable_encoder(event)
                    conv_event = ConversationEvent(
                        conv_id=self.conv_id,
                        event_type=event.type,
                        payload=payload,
                    )
                    session.add(conv_event)
            await session.commit()
        self._persisted_count = len(self.events)
        logger.info("Persistence to PostgreSQL complete")
