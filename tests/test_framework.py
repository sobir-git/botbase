import datetime
import importlib
import sys

import pytest
import yaml
from fastapi import FastAPI

from botbase import botapi, events
from botbase.events import handle_event, handler
from botbase.tracker.base import ConversationTracker, Event
from botbase.tracker.jsonl_tracker import JSONLTracker

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
    # Reload the config module so that load_config uses the temporary file.
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
    file_path = tmp_path / "events.jsonl"
    tracker = JSONLTracker(file_path=str(file_path), conv_id="test_conv")
    # Add a bot event first.
    tracker.send_bot_message("Bot message")
    # Initially there is no user message.
    assert tracker.last_user_message() is None
    # Add a user event with a valid created_at timestamp.
    user_event = Event(type="user", text="User message", payload={}, created_at=datetime.datetime.utcnow())
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
    file_path = tmp_path / "events.jsonl"
    tracker = JSONLTracker(file_path=str(file_path), conv_id="test_conv")
    tracker.set_slot("greeted", True)
    assert tracker.slots.get("greeted") is True
    slot_events = [e for e in tracker.events if e.type == "slot"]
    assert len(slot_events) > 0
    assert slot_events[-1].payload.get("greeted") is True


@pytest.mark.asyncio
async def test_persistence_jsonl_tracker(tmp_path):
    """
    Test that events are correctly persisted to a JSONL file and reloaded.
    """
    file_path = tmp_path / "events.jsonl"
    # Create a tracker, add an event with a valid datetime, and persist.
    tracker1 = JSONLTracker(file_path=str(file_path), conv_id="test_conv")
    tracker1.add_event(Event(type="user", text="Test persistence", payload={}, created_at=datetime.datetime.utcnow()))
    await tracker1.persist()

    # Create a new tracker for the same conversation.
    tracker2 = JSONLTracker(file_path=str(file_path), conv_id="test_conv")
    # The new tracker should load at least as many events as tracker1 had.
    assert len(tracker2.events) >= len(tracker1.events)


# --- Test Event Handling Registration and Execution ---


@pytest.mark.asyncio
async def test_handle_event():
    """
    Register a dummy handler via the events.handler decorator and verify that handle_event invokes it.
    """
    # Save the original registry so we can restore it.
    original_registry = list(events._handler_registry)
    try:
        handled = False

        @handler()
        async def dummy_handler(tracker: ConversationTracker):
            nonlocal handled
            handled = True

        # Create a dummy tracker that does nothing on persist.
        class DummyTracker(ConversationTracker):
            async def persist(self):
                pass

        tracker = DummyTracker(conv_id="dummy")
        # Add a dummy user event with a valid datetime.
        tracker.add_event(Event(type="user", text="dummy", payload={}, created_at=datetime.datetime.utcnow()))
        await handle_event(tracker)
        assert handled is True
    finally:
        # Restore the original handler registry.
        events._handler_registry.clear()
        events._handler_registry.extend(original_registry)


# --- Test Webhook Channel and BotAPI Initialization ---


@pytest.mark.asyncio
async def test_webhook_channel_process_request(tmp_path, monkeypatch):
    """
    Use FastAPI's TestClient to simulate a POST request to the webhook endpoint.
    This test now creates its own temporary configuration file so that the webhook
    channel is instantiated with the desired parameters.
    """
    # Create a temporary configuration file with our desired webhook channel config.
    config_data = {
        "tracker": "jsonl",
        "jsonl": {"file_path": str(tmp_path / "test_events.jsonl")},
        "channels": [
            {
                "type": "webhook",
                "name": "webhook",
                # The token is set to "test-secret" and url is empty so that dispatching is skipped.
                "token": "test-secret",
                "url": "",
            }
        ],
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(config_data))
    # Set the environment variable so that load_config() picks up our temporary config.
    monkeypatch.setenv("CONFIG_FILE", str(config_file))

    # Reload the configuration module so that it picks up our temporary config.
    import botbase.config as config_module

    importlib.reload(config_module)

    # Reload the botapi module so that channels are re-instantiated with our config.
    import botbase.botapi as botapi

    importlib.reload(botapi)

    # Create a new FastAPI app and reinitialize the framework.
    botapi.app = FastAPI(title="Test Chatbot")
    botapi.init()

    from fastapi.testclient import TestClient

    client = TestClient(botapi.app)
    payload = {"conv_id": "test_conv", "text": "hello"}
    headers = {"Authorization": "Bearer test-secret"}
    response = client.post("/webhook/webhook/", json=payload, headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    # We expect the webhook endpoint to return a response containing the conv_id.
    assert "conv_id" in data, f"Response did not contain conv_id: {data}"
    assert data.get("status") == "Message received."


def test_database_configuration():
    """
    Check that the database module configures SQL engine only for PostgreSQL tracker.
    """
    from botbase.config import config as cfg
    from botbase.database import async_session as sess
    from botbase.database import engine as eng

    if cfg.tracker == "jsonl":
        assert eng is None
        assert sess is None
    elif cfg.tracker == "postgresql":
        assert eng is not None
        assert sess is not None


# --- Test runserver with --interactive Flag ---


def test_runserver_interactive(monkeypatch):
    """
    Test that when '--interactive' is in sys.argv, runserver runs the interactive channel.
    This is done by monkey-patching InteractiveChannel.run.
    """
    original_argv = sys.argv.copy()
    sys.argv.append("--interactive")
    called = False

    async def dummy_run(self):
        nonlocal called
        called = True

    # Patch InteractiveChannel.run with our dummy_run.
    from botbase.channels.interactive import InteractiveChannel

    monkeypatch.setattr(InteractiveChannel, "run", dummy_run)
    # Call runserver; since --interactive is in sys.argv, it should invoke InteractiveChannel.run.
    botapi.runserver()
    assert called is True
    sys.argv = original_argv
