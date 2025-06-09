"""Tests for SQLite-based conversation tracker."""

import asyncio
import datetime
import os
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

from botbase.config import SqliteTrackerConfig
from botbase.tracker.base import Event
from botbase.tracker.sqlite.database import Base, init_database
from botbase.tracker.sqlite.tracker import SQLiteTracker


@pytest_asyncio.fixture
async def temp_db(tmp_path: Path) -> str:
    """
    Create a temporary SQLite database file, initialize its tables,
    yield the file path as a string, and then remove the file afterwards.
    """
    db_path = tmp_path / "test_conversations.db"
    # Initialize the database; init_database returns a tuple (session_factory, db_file)
    session_factory = await init_database(str(db_path))
    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield str(db_path)
    # Clean up: remove the database file
    try:
        os.remove(str(db_path))
    except FileNotFoundError:
        pass


@pytest_asyncio.fixture
def sqlite_config(temp_db: str) -> SqliteTrackerConfig:
    """
    Return a SqliteTrackerConfig instance using the temporary database file.
    """
    return SqliteTrackerConfig(db_path=temp_db)


@pytest.mark.asyncio
async def test_sqlite_tracker_init(sqlite_config: SqliteTrackerConfig):
    conv_id = str(uuid.uuid4())
    tracker = await SQLiteTracker.create(sqlite_config, conv_id)
    assert tracker.conv_id == conv_id
    assert len(tracker.events) == 0
    assert tracker._persisted_count == 0


@pytest.mark.asyncio
async def test_sqlite_tracker_persist_and_load(sqlite_config: SqliteTrackerConfig):
    conv_id = str(uuid.uuid4())
    tracker = await SQLiteTracker.create(sqlite_config, conv_id)
    test_events = [
        Event(type="message", payload={"text": "Hello"}, created_at=datetime.datetime.now(datetime.timezone.utc)),
        Event(type="slot", payload={"name": "value"}, created_at=datetime.datetime.now(datetime.timezone.utc)),
        Event(type="message", payload={"text": "Goodbye"}, created_at=datetime.datetime.now(datetime.timezone.utc)),
    ]
    for event in test_events:
        tracker.add_event(event)
    await tracker.persist()
    assert tracker._persisted_count == len(test_events)
    new_tracker = await SQLiteTracker.create(sqlite_config, conv_id)
    assert len(new_tracker.events) == len(test_events)
    assert new_tracker._persisted_count == len(test_events)
    for orig_event, loaded_event in zip(test_events, new_tracker.events):
        assert loaded_event.type == orig_event.type
        assert loaded_event.payload == orig_event.payload


@pytest.mark.asyncio
async def test_sqlite_tracker_slot_updates(sqlite_config: SqliteTrackerConfig):
    conv_id = str(uuid.uuid4())
    tracker = await SQLiteTracker.create(sqlite_config, conv_id)
    tracker.set_slot("name", "value")
    tracker.set_slot("count", 42)
    await tracker.persist()
    new_tracker = await SQLiteTracker.create(sqlite_config, conv_id)
    assert new_tracker.get_slot("name") == "value"
    assert new_tracker.get_slot("count") == 42


@pytest.mark.asyncio
async def test_sqlite_tracker_json_serialization(sqlite_config: SqliteTrackerConfig):
    conv_id = str(uuid.uuid4())
    tracker = await SQLiteTracker.create(sqlite_config, conv_id)
    complex_payload = {
        "list": [1, 2, 3],
        "dict": {"a": 1, "b": [4, 5, 6]},
        "null": None,
        "bool": True,
    }
    event = Event(type="complex", payload=complex_payload, created_at=datetime.datetime.now(datetime.timezone.utc))
    tracker.add_event(event)
    await tracker.persist()
    new_tracker = await SQLiteTracker.create(sqlite_config, conv_id)
    loaded_event = new_tracker.events[0]
    assert loaded_event.type == "complex"
    assert loaded_event.payload == complex_payload


@pytest.mark.asyncio
async def test_sqlite_tracker_concurrent_access(sqlite_config: SqliteTrackerConfig):
    conv_id = str(uuid.uuid4())

    async def add_events(count: int):
        tracker = await SQLiteTracker.create(sqlite_config, conv_id)
        for i in range(count):
            tracker.add_event(
                Event(type="message", payload={"count": i}, created_at=datetime.datetime.now(datetime.timezone.utc))
            )
        await tracker.persist()

    await asyncio.gather(
        add_events(5),
        add_events(5),
        add_events(5),
    )
    final_tracker = await SQLiteTracker.create(sqlite_config, conv_id)
    assert len(final_tracker.events) == 15
