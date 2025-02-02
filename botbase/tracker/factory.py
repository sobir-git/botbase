from botbase.config import config

if config.tracker == "jsonl":
    from botbase.tracker.jsonl_tracker import JSONLTracker as TrackerImpl
elif config.tracker == "postgresql":
    from botbase.tracker.postgresql_tracker import PostgreSQLTracker as TrackerImpl
else:
    raise ValueError("Invalid tracker type in configuration.")


def create_tracker(conv_id: str = None):
    if config.tracker == "jsonl":
        return TrackerImpl(config.jsonl.file_path, conv_id)
    else:
        return TrackerImpl(conv_id)
