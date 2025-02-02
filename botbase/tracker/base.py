import asyncio
import datetime
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Event(BaseModel):
    type: str
    text: Optional[str] = None
    payload: Dict[str, Any] = {}
    created_at: datetime.datetime = None


class ConversationTracker(ABC):
    def __init__(self, conv_id: str = None):
        self.conv_id: str = conv_id or str(uuid.uuid4())
        self.events: List[Event] = []
        self.slots: Dict[str, Any] = {}
        self._persisted_count: int = 0  # tracks the number of events already persisted
        self._event_callbacks: List[Callable[[Event], Any]] = []
        logger.debug(f"ConversationTracker initialized for conversation {self.conv_id}")

    def register_callback(self, callback: Callable[[Event], Any]):
        """Register a callback to be called whenever a new event is added."""
        self._event_callbacks.append(callback)
        logger.debug(f"Callback {callback} registered for conversation {self.conv_id}")

    def add_event(self, event: Event):
        """Add an event and invoke registered callbacks."""
        self.events.append(event)
        logger.debug(f"Event added to conversation {self.conv_id}: {event}")
        # Invoke callbacks (if they return a coroutine, schedule it)
        for callback in self._event_callbacks:
            result = callback(event)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)

    def set_slot(self, key: str, value: Any):
        self.slots[key] = value
        slot_event = Event(type="slot", payload={key: value}, created_at=datetime.datetime.utcnow())
        self.add_event(slot_event)
        logger.debug(f"Slot '{key}' set to {value} for conversation {self.conv_id}")

    def send_bot_message(self, text: str, metadata: Dict[str, Any] = None):
        bot_event = Event(type="bot", text=text, payload=metadata or {}, created_at=datetime.datetime.utcnow())
        self.add_event(bot_event)
        logger.info(f"Bot message added for conversation {self.conv_id}: {text}")

    def last_user_message(self) -> Optional[Event]:
        for event in reversed(self.events):
            if event.type == "user":
                return event
        logger.debug(f"No user message found for conversation {self.conv_id}")
        return None

    @abstractmethod
    async def persist(self):
        """
        Persist only new events (since last persist) to the chosen storage.
        """
        pass
