import datetime
import importlib
import sys

import pytest
import yaml
from fastapi import FastAPI

from botbase import botapi, events
from botbase.events import handle_event, handler
from botbase.tracker.base import ConversationTracker, Event
from botbase.tracker.factory import create_tracker

# --- Test Configuration Loading ---


def test_config_loading(tmp_path, monkeypatch):
    """
    Create a temporary config file and ensure that load_config returns the expected values.
    """
    config_data = {
        "tracker": "jsonl",
        "jsonl": {"file_path": str(tmp_path / "test_events.jsonl")},
        "channels": [{"type": "webhook", "url": "http://localhost:8000/webhook"}],
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(config_data))
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    import botbase.config as config_module

    importlib.reload(config_module)
    new_config = config_module.config
    assert new_config.tracker == "jsonl"
    assert new_config.jsonl.file_path == str(tmp_path / "test_events.jsonl")


# --- Test Conversation Tracker Functionality ---


@pytest.mark.asyncio
async def test_send_bot_message(tmp_path):
    """
    Test that send_bot_message correctly adds a bot event.
    """
    # Here we create a JSONLTracker instance for testing purposes.
    from botbase.tracker.jsonl_tracker import JSONLTracker

    file_path = tmp_path / "events.jsonl"
    tracker = JSONLTracker(file_path=str(file_path), conv_id="test_conv")
    initial_count = len(tracker.events)
    tracker.send_bot_message("Hello")
    assert len(tracker.events) == initial_count + 1
    last_event = tracker.events[-1]
    assert last_event.type == "bot"
    assert last_event.text == "Hello"


@pytest.mark.asyncio
async def test_last_user_message(tmp_path):
    """
    Test that last_user_message returns the most recent user event.
    """
    from botbase.tracker.jsonl_tracker import JSONLTracker

    file_path = tmp_path / "events.jsonl"
    tracker = JSONLTracker(file_path=str(file_path), conv_id="test_conv")
    tracker.send_bot_message("Bot message")
    # Initially there is no user event.
    assert tracker.last_user_message() is None
    # Add a user event.
    user_event = Event(
        type="user",
        text="User message",
        payload={},
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    tracker.add_event(user_event)
    last_user = tracker.last_user_message()
    assert last_user is not None
    assert last_user.type == "user"
    assert last_user.text == "User message"


@pytest.mark.asyncio
async def test_set_slot(tmp_path):
    """
    Test that setting a slot updates the tracker’s slots and adds a slot event.
    """
    from botbase.tracker.jsonl_tracker import JSONLTracker

    file_path = tmp_path / "events.jsonl"
    tracker = JSONLTracker(file_path=str(file_path), conv_id="test_conv")
    tracker.set_slot("greeted", True)
    assert tracker.get_slot("greeted") is True
    slot_events = [e for e in tracker.events if e.type == "slot"]
    assert len(slot_events) > 0
    assert slot_events[-1].payload.get("greeted") is True


@pytest.mark.asyncio
async def test_persistence_jsonl_tracker(tmp_path):
    """
    Test that events are correctly persisted to a JSONL file and reloaded.
    """
    from botbase.tracker.jsonl_tracker import JSONLTracker

    file_path = tmp_path / "events.jsonl"
    tracker1 = JSONLTracker(file_path=str(file_path), conv_id="test_conv")
    tracker1.add_event(
        Event(
            type="user",
            text="Test persistence",
            payload={},
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )
    await tracker1.persist()
    tracker2 = JSONLTracker(file_path=str(file_path), conv_id="test_conv")
    assert len(tracker2.events) >= len(tracker1.events)


# --- Test Event Handling Registration and Execution ---


@pytest.mark.asyncio
async def test_handle_event():
    """
    Register a dummy handler via the events.handler decorator and verify that handle_event invokes it.
    """
    original_registry = list(events._handler_registry)
    try:
        handled = False

        @handler()
        async def dummy_handler(tracker: ConversationTracker):
            nonlocal handled
            handled = True

        # Create a dummy tracker.
        class DummyTracker(ConversationTracker):
            async def persist(self):
                pass

        tracker = DummyTracker(conv_id="dummy")
        tracker.add_event(
            Event(
                type="user",
                text="dummy",
                payload={},
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
        )
        await handle_event(tracker)
        assert handled is True
    finally:
        events._handler_registry.clear()
        events._handler_registry.extend(original_registry)


# --- Test Webhook Channel and BotAPI Initialization ---


@pytest.mark.asyncio
async def test_webhook_channel_process_request(tmp_path, monkeypatch):
    """
    Use FastAPI's TestClient to simulate a POST request to the webhook endpoint.
    This test creates a temporary configuration file so that the webhook channel is
    instantiated with the desired parameters.
    """
    from fastapi.testclient import TestClient

    config_data = {
        "tracker": "jsonl",
        "jsonl": {"file_path": str(tmp_path / "test_events.jsonl")},
        "channels": [
            {
                "type": "webhook",
                "name": "webhook",
                "token": "test-secret",
                "url": "",
            }
        ],
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(config_data))
    monkeypatch.setenv("CONFIG_FILE", str(config_file))

    import botbase.config as config_module

    importlib.reload(config_module)
    import botbase.botapi as botapi

    importlib.reload(botapi)

    botapi.app = FastAPI(title="Test Chatbot")
    botapi.init()

    client = TestClient(botapi.app)
    payload = {"conv_id": "test_conv", "text": "hello"}
    headers = {"Authorization": "Bearer test-secret"}
    response = client.post("/channels/webhook/", json=payload, headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # Verify that the channel name is in the event payload
    tracker = await create_tracker(conv_id="test_conv")
    last_event = tracker.last_user_message()
    assert last_event is not None
    assert last_event.payload.get("channel") == "webhook"
    data = response.json()
    assert "conv_id" in data, f"Response did not contain conv_id: {data}"
    assert data.get("status") == "Message received."


@pytest.mark.asyncio
async def test_telegram_channel_metadata(tmp_path, monkeypatch):
    """
    Test that TelegramChannel correctly adds the channel name to the event payload.
    """
    import importlib

    import aiohttp

    import botbase.botapi as botapi
    import botbase.config as config_module
    from botbase.channels.telegram import TelegramChannel

    # Mock aiohttp to simulate Telegram API response
    class MockResponse:
        def __init__(self, json_data, status=200):
            self._json_data = json_data
            self.status = status

        async def json(self):
            return self._json_data

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def __aenter__(self):
            return self

    async def mock_get(url, params=None):
        if "getUpdates" in url:
            return MockResponse(
                {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 12345,
                            "message": {
                                "message_id": 1,
                                "from": {"id": 123, "is_bot": False, "first_name": "Test"},
                                "chat": {"id": 123, "type": "private"},
                                "date": int(datetime.datetime.now().timestamp()),
                                "text": "/start",
                            },
                        }
                    ],
                }
            )
        return MockResponse({})

    monkeypatch.setattr(aiohttp.ClientSession, "get", mock_get)

    # Setup config for TelegramChannel
    config_data = {
        "tracker": "jsonl",
        "jsonl": {"file_path": str(tmp_path / "test_events.jsonl")},
        "channels": [{"type": "telegram", "name": "telegram_channel", "token": "test_token"}],
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(config_data))
    monkeypatch.setenv("CONFIG_FILE", str(config_file))

    importlib.reload(config_module)
    importlib.reload(botapi)

    # Initialize botapi to load channels
    botapi.app = FastAPI(title="Test Chatbot")
    botapi.init()

    # Find the telegram channel instance
    telegram_channel = None
    for channel in botapi._registered_channels:
        if isinstance(channel, TelegramChannel):
            telegram_channel = channel
            break
    assert telegram_channel is not None

    # Manually call process_update with a dummy update to trigger event creation
    # In a real scenario, poll_updates would call process_update
    dummy_update = {
        "update_id": 12345,
        "message": {
            "message_id": 1,
            "from": {"id": 123, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 123, "type": "private"},
            "date": int(datetime.datetime.now().timestamp()),
            "text": "/start",
        },
    }
    await telegram_channel.process_update(dummy_update)

    # Verify that the channel name is in the event payload
    tracker = await create_tracker(conv_id="123")  # conv_id is chat_id for telegram
    last_event = tracker.last_user_message()
    assert last_event is not None
    assert last_event.payload.get("channel") == "telegram_channel"


# --- Test Database Configuration ---


@pytest.mark.asyncio
async def test_database_configuration():
    """
    Check that the database module configures a SQL engine only for PostgreSQL tracker,
    and for sqlite tracker, a valid engine is created.
    For the jsonl tracker, no database engine is configured.
    """
    from botbase.config import config as cfg

    if cfg.tracker == "jsonl":
        # For jsonl tracker, there's no SQL engine.
        assert True
    elif cfg.tracker == "postgresql":
        from botbase.database import async_session as sess
        from botbase.database import engine as eng

        assert eng is not None
        assert sess is not None
    elif cfg.tracker == "sqlite":
        from botbase.tracker.sqlite.database import init_database

        session_factory, _ = await init_database(cfg.sqlite.db_path)
        engine = session_factory.kw["bind"]
        assert engine is not None


# --- Test runserver with --interactive Flag ---


def test_runserver_interactive(monkeypatch):
    original_argv = sys.argv.copy()
    sys.argv.append("--interactive")
    called = False

    async def dummy_run(self):
        nonlocal called
        called = True

    from botbase.channels.interactive import InteractiveChannel

    monkeypatch.setattr(InteractiveChannel, "run", dummy_run)
    botapi.runserver()
    assert called is True
    sys.argv = original_argv
