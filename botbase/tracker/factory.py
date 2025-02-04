from botbase.config import config

if config.tracker == "jsonl":
    from botbase.tracker.jsonl_tracker import JSONLTracker as TrackerImpl
elif config.tracker == "postgresql":
    from botbase.tracker.postgresql_tracker import PostgreSQLTracker as TrackerImpl
elif config.tracker == "sqlite":
    from botbase.tracker.sqlite.tracker import SQLiteTracker as TrackerImpl
else:
    raise ValueError("Invalid tracker type in configuration.")


async def create_tracker(conv_id: str = None):
    if config.tracker == "jsonl":
        return await TrackerImpl.create(config.jsonl, conv_id)
    elif config.tracker == "sqlite":
        return await TrackerImpl.create(config.sqlite, conv_id)
    else:
        return await TrackerImpl.create(conv_id)
