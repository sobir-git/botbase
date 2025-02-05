import asyncio
import datetime
import logging

import aiohttp
from fastapi import APIRouter
from md2tgmd import escape

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

    def __init__(self, name: str, token: str, message_age_threshold: int = None, **kwargs):
        super().__init__(name)
        self.router = APIRouter()  # No HTTP routes needed for polling.
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0  # Telegram API requires an offset to avoid duplicate messages.
        self.message_age_threshold = message_age_threshold
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
                                asyncio.create_task(self.process_update(update))
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

        if self.message_age_threshold is not None and "date" in message:
            message_age = datetime.datetime.now().timestamp() - message["date"]
            if message_age > self.message_age_threshold:
                logger.info(
                    f"Skipping message from {message_age:.1f} seconds ago (threshold: {self.message_age_threshold}s)"
                )
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

    @staticmethod
    def adapt_markdown(text: str) -> str:
        """
        Converts markdown text to Telegram's MarkdownV2 format.
        Uses md2tgmd for reliable conversion.

        Args:
            text: Text with markdown formatting

        Returns:
            Text formatted for Telegram MarkdownV2
        """
        return escape(text)

    async def send_message(self, chat_id: int, text: str):
        """
        Sends a message back to Telegram using the sendMessage API.
        Converts markdown formatting to Telegram's MarkdownV2 format.

        Note:
            The text is assumed to be in markdown format and will be
            converted to Telegram's MarkdownV2 format using telegramify-markdown.
        """
        telegram_text = self.adapt_markdown(text)

        async with aiohttp.ClientSession() as session:
            payload = {"chat_id": chat_id, "text": telegram_text, "parse_mode": "MarkdownV2"}
            async with session.post(f"{self.base_url}/sendMessage", json=payload) as resp:
                result = await resp.json()
                if not result.get("ok"):
                    logger.error(f"TelegramChannel: Failed to send message to chat {chat_id}: {result}")
                    logger.debug(f"Original markdown: {text}")
                    logger.debug(f"Telegram MarkdownV2: {telegram_text}")
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
