"""Tests for JSONL-based conversation tracker."""

import asyncio
import datetime
import os
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

from botbase.config import JSONLConfig
from botbase.tracker.base import Event
from botbase.tracker.jsonl_tracker import JSONLTracker


@pytest_asyncio.fixture
def temp_jsonl(tmp_path: Path) -> str:
    file_path = tmp_path / "test_events.jsonl"
    file_path.touch()
    yield str(file_path)
    try:
        os.remove(str(file_path))
    except FileNotFoundError:
        pass


@pytest.fixture
def jsonl_config(temp_jsonl: str) -> JSONLConfig:
    return JSONLConfig(file_path=temp_jsonl)


@pytest.mark.asyncio
async def test_jsonl_tracker_init(jsonl_config: JSONLConfig):
    conv_id = str(uuid.uuid4())
    tracker = await JSONLTracker.create(jsonl_config, conv_id)
    assert tracker.conv_id == conv_id
    assert len(tracker.events) == 0
    assert tracker._persisted_count == 0


@pytest.mark.asyncio
async def test_jsonl_tracker_persist_and_load(jsonl_config: JSONLConfig):
    conv_id = str(uuid.uuid4())
    tracker = await JSONLTracker.create(jsonl_config, conv_id)
    test_events = [
        Event(type="message", payload={"text": "Hello"}, created_at=datetime.datetime.utcnow()),
        Event(type="slot", payload={"greeted": True}, created_at=datetime.datetime.utcnow()),
        Event(type="message", payload={"text": "Goodbye"}, created_at=datetime.datetime.utcnow()),
    ]
    for event in test_events:
        tracker.add_event(event)
    await tracker.persist()
    assert tracker._persisted_count == len(test_events)
    new_tracker = await JSONLTracker.create(jsonl_config, conv_id)
    assert len(new_tracker.events) == len(test_events)
    assert new_tracker._persisted_count == len(test_events)
    for orig_event, loaded_event in zip(test_events, new_tracker.events):
        assert loaded_event.type == orig_event.type
        assert loaded_event.payload == orig_event.payload


@pytest.mark.asyncio
async def test_jsonl_tracker_slot_updates(jsonl_config: JSONLConfig):
    conv_id = str(uuid.uuid4())
    tracker = await JSONLTracker.create(jsonl_config, conv_id)
    tracker.set_slot("name", "value")
    tracker.set_slot("count", 42)
    await tracker.persist()
    new_tracker = await JSONLTracker.create(jsonl_config, conv_id)
    assert new_tracker.get_slot("name") == "value"
    assert new_tracker.get_slot("count") == 42


@pytest.mark.asyncio
async def test_jsonl_tracker_json_serialization(jsonl_config: JSONLConfig):
    conv_id = str(uuid.uuid4())
    tracker = await JSONLTracker.create(jsonl_config, conv_id)
    complex_payload = {
        "list": [1, 2, 3],
        "dict": {"a": 1, "b": [4, 5, 6]},
        "null": None,
        "bool": True,
    }
    # Ensure created_at is provided (strict mode)
    event = Event(type="complex", payload=complex_payload, created_at=datetime.datetime.utcnow())
    tracker.add_event(event)
    await tracker.persist()
    new_tracker = await JSONLTracker.create(jsonl_config, conv_id)
    assert len(new_tracker.events) >= 1
    loaded_event = new_tracker.events[0]
    assert loaded_event.type == "complex"
    assert loaded_event.payload == complex_payload


@pytest.mark.asyncio
async def test_jsonl_tracker_concurrent_access(jsonl_config: JSONLConfig):
    conv_id = str(uuid.uuid4())

    async def add_events(count: int):
        tracker = await JSONLTracker.create(jsonl_config, conv_id)
        for i in range(count):
            # Provide created_at strictly.
            tracker.add_event(Event(type="message", payload={"count": i}, created_at=datetime.datetime.utcnow()))
        await tracker.persist()

    await asyncio.gather(
        add_events(5),
        add_events(5),
        add_events(5),
    )
    final_tracker = await JSONLTracker.create(jsonl_config, conv_id)
    assert len(final_tracker.events) == 15
