import asyncio
import datetime
import json
import logging
from pathlib import Path

from botbase.tracker.base import ConversationTracker, Event

logger = logging.getLogger(__name__)


class JSONLTracker(ConversationTracker):
    @classmethod
    async def create(cls, config, conv_id: str = None) -> "JSONLTracker":
        """
        Asynchronously create a new JSONLTracker instance.
        The config parameter is expected to have a `file_path` attribute.
        """
        # When creating a tracker, the caller is expected to supply a valid conv_id
        # or one is generated by the base class.
        return cls(config.file_path, conv_id)

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
        Each record contains a top-level 'conv_id' along with the 'event' payload.
        For slot events, update the tracker's internal _slots dictionary.
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
                            # Validate the event. If created_at is missing, this will error.
                            event = Event.model_validate(event_data)
                            self.events.append(event)
                            if event.type == "slot":
                                self._slots.update(event.payload)
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed JSON line")
                        continue
            self._persisted_count = len(self.events)
            logger.info(f"Loaded {self._persisted_count} events from JSONL file for conversation {self.conv_id}")
        except Exception as e:
            logger.error(f"Error loading history from JSONL: {e}", exc_info=True)

    async def persist(self):
        """
        Persist new events (those not yet written) to the JSONL file.
        Each event is stored as a JSON record containing the conv_id and the event data.
        Before persisting, we enforce that each event has a valid created_at timestamp.
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
