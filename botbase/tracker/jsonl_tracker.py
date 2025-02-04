import asyncio
import datetime
import json
import logging
from pathlib import Path

from botbase.tracker.base import ConversationTracker, Event

logger = logging.getLogger(__name__)


class JSONLTracker(ConversationTracker):
    def __init__(self, file_path: str, conv_id: str = None):
        super().__init__(conv_id)
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            self.file_path.touch()
            logger.info(f"Created new JSONL file at {self.file_path}")
        self._load_history()

    def _load_history(self):
        """
        Load past events for this conversation from the JSONL file.
        The file now stores a top-level 'conv_id' along with the event data,
        ensuring that we load all events for the current conversation.
        Also, for slot events, update the tracker's slots.
        """
        logger.debug("Loading conversation history from JSONL file")
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if record.get("conv_id") != self.conv_id:
                            continue
                        event_data = record.get("event")
                        if event_data:
                            event = Event.model_validate(event_data)
                            self.events.append(event)
                            if event.type == "slot":
                                self.slots.update(event.payload)
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed JSON line")
                        continue
            self._persisted_count = len(self.events)
            logger.info(f"Loaded {self._persisted_count} events from JSONL file " f"for conversation {self.conv_id}")
        except Exception as e:
            logger.error(f"Error loading history from JSONL: {e}", exc_info=True)

    async def persist(self):
        """
        Persist new events (those that haven't yet been written) to the JSONL file.
        Each event is stored as a JSON record containing both the conv_id and the event data.
        """
        new_events = self.events[self._persisted_count :]
        if not new_events:
            logger.debug("No new events to persist in JSONL")
            return

        logger.info(f"Persisting {len(new_events)} new events to JSONL")
        loop = asyncio.get_event_loop()

        def write_events():
            with self.file_path.open("a", encoding="utf-8") as f:
                for event in new_events:
                    record = {"conv_id": self.conv_id, "event": event.model_dump()}
                    # Use a default function to serialize datetime objects.
                    f.write(
                        json.dumps(
                            record,
                            default=lambda o: o.isoformat() if isinstance(o, datetime.datetime) else str(o),
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

        await loop.run_in_executor(None, write_events)
        self._persisted_count = len(self.events)
        logger.info("Persistence to JSONL file complete")
