import asyncio
import datetime
import logging

import aiohttp
from fastapi import APIRouter

from botbase.channels.base import BaseChannel
from botbase.events import handle_event
from botbase.tracker.base import Event
from botbase.tracker.factory import create_tracker

logger = logging.getLogger(__name__)


class TelegramChannel(BaseChannel):
    """
    TelegramChannel implements a Telegram bot channel using long polling.
    Instead of receiving webhooks, it polls Telegram's getUpdates endpoint and processes messages.
    """

    def __init__(self, name: str, token: str, **kwargs):
        super().__init__(name)
        self.router = APIRouter()  # No HTTP routes needed for polling.
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0  # Telegram API requires an offset to avoid duplicate messages.
        logger.info(f"TelegramChannel initialized with token ending with ...{self.token[-4:]}")

    def register_routes(self, app):
        """
        Instead of registering HTTP routes, we register a startup event that launches the long-polling loop.
        """

        @app.on_event("startup")
        async def start_polling():
            logger.info("TelegramChannel: Starting long polling for Telegram updates")
            asyncio.create_task(self.poll_updates())

        logger.info("TelegramChannel: Registered startup event for polling.")

    async def poll_updates(self):
        """
        Continuously poll Telegram for new updates.
        Uses a timeout of 10 seconds and sleeps briefly between polling cycles.
        """
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    params = {"offset": self.offset, "timeout": 10}
                    async with session.get(f"{self.base_url}/getUpdates", params=params) as resp:
                        data = await resp.json()
                        for update in data.get("result", []):
                            self.offset = update["update_id"] + 1
                            logger.info(f"TelegramChannel: Received update: {update}")
                            if "message" in update:
                                await self.process_update(update)
                except Exception as e:
                    logger.error(f"TelegramChannel: Error during polling: {e}", exc_info=True)
                await asyncio.sleep(1)  # Pause before next poll to avoid hitting rate limits.

    async def process_update(self, update: dict):
        """
        Processes an individual update from Telegram.
        - Extracts the chat ID and text.
        - Creates a user event.
        - Registers a callback to send bot replies.
        - Triggers BotBase event handlers.
        """
        message = update.get("message")
        if not message:
            return

        chat = message.get("chat")
        if not chat:
            return

        chat_id = chat.get("id")
        text = message.get("text")
        if not text:
            return

        logger.info(f"TelegramChannel: Received message from chat {chat_id}: {text}")

        # Use the Telegram chat ID as the conversation ID.
        tracker = await create_tracker(str(chat_id))

        # Register a callback to handle bot responses.
        tracker.register_callback(lambda event: self.on_bot_event(event, chat_id))

        # Create and add a user event.
        user_event = Event(
            type="user",
            text=text,
            payload=update,  # Store full update payload.
            created_at=datetime.datetime.utcnow(),
        )
        tracker.add_event(user_event)

        # Process event via BotBase handlers and persist conversation state.
        await handle_event(tracker)
        await tracker.persist()

    async def on_bot_event(self, event: Event, chat_id: int):
        """
        Callback function that gets triggered whenever a bot event occurs.
        Sends the bot's reply to the corresponding Telegram chat.
        """
        if event.type == "bot" and event.text:
            await self.send_message(chat_id, event.text)

    async def send_message(self, chat_id: int, text: str):
        """
        Sends a message back to Telegram using the sendMessage API.
        """
        async with aiohttp.ClientSession() as session:
            payload = {"chat_id": chat_id, "text": text}
            async with session.post(f"{self.base_url}/sendMessage", json=payload) as resp:
                result = await resp.json()
                if not result.get("ok"):
                    logger.error(f"TelegramChannel: Failed to send message to chat {chat_id}: {result}")
                return result

    async def process_request(self, request, background_tasks):
        """
        Not used for polling-based integrations.
        """
        pass

    def close(self):
        """
        Any necessary cleanup can be implemented here.
        """
        pass
