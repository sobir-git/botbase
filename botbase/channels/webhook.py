import datetime
import logging
from typing import Optional

import aiohttp
from fastapi import BackgroundTasks, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from botbase.channels.base import BaseChannel
from botbase.events import handle_event
from botbase.tracker.base import ConversationTracker, Event
from botbase.tracker.factory import create_tracker

logger = logging.getLogger(__name__)

auth_scheme = HTTPBearer()
get_token = Depends(auth_scheme)


class WebhookChannel(BaseChannel):
    def __init__(self, name: str, token: Optional[str] = None, url: Optional[str] = None):
        super().__init__(name)
        # Register the webhook endpoint route
        self.router.post("/")(self.process_request)
        self.token = token
        self.url = url

    def register_routes(self, app):
        app.include_router(self.router)
        logger.info(f"Routes registered for channel: {self.name}")

    async def process_request(
        self,
        request: Request,
        background_tasks: BackgroundTasks,
        token: HTTPAuthorizationCredentials = get_token,
    ):
        logger.debug("Processing incoming webhook request")

        # Verify token if provided
        if self.token and token.credentials != self.token:
            logger.warning(f"Invalid token received: {token.credentials}")
            return {"status": "error", "message": "Invalid token"}

        data = await request.json()
        conv_id = data.get("conv_id")
        text = data.get("text")
        if not text:
            logger.warning("Webhook request missing 'text' field")
            return {"error": "No text provided in the request."}

        logger.info(f"Received message for conversation: {conv_id}")
        tracker = await create_tracker(conv_id)

        # Register a callback for this tracker that dispatches bot events immediately.
        # We use a lambda to capture the current tracker.
        tracker.register_callback(lambda event: self.on_tracker_event(event, tracker))

        # Create and add a user event.
        user_event = Event(
            type="user",
            text=text,
            created_at=datetime.datetime.utcnow(),
            payload=data,
        )
        tracker.add_event(user_event)
        logger.debug("User event added to tracker")

        # Schedule other background tasks (e.g. event handling and persistence).
        background_tasks.add_task(handle_event, tracker)
        background_tasks.add_task(tracker.persist)
        background_tasks.add_task(self.close)
        logger.info("Scheduled background tasks for event handling, persistence, and dispatching bot events")

        return {"conv_id": tracker.conv_id, "status": "Message received."}

    async def on_tracker_event(self, event: Event, tracker: ConversationTracker):
        """Callback invoked for every new event. If the event is a bot message, dispatch it."""
        if event.type == "bot":
            logger.info(f"New bot event detected for conversation {tracker.conv_id}: {event.text}")
            await self.dispatch_bot_event(event, tracker.conv_id)

    async def dispatch_bot_event(self, event: Event, conv_id: str):
        """Dispatch a single bot event to the configured webhook URL."""
        if not self.url:
            logger.warning("No webhook URL configured; skipping dispatch.")
            return

        webhook_url = self.url
        payload = {
            "conv_id": conv_id,
            "text": event.text,
            "metadata": event.payload,
            "timestamp": event.created_at.isoformat() if event.created_at else None,
        }
        logger.info(f"Dispatching bot event to webhook {webhook_url}: {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(f"Successfully dispatched bot event: {event.text}")
                    else:
                        logger.error(f"Failed to dispatch bot event: {event.text}. HTTP status: {resp.status}")
        except Exception as e:
            logger.error(f"Exception dispatching bot event: {event.text}: {str(e)}", exc_info=True)

    def close(self):
        logger.debug("Closing webhook channel (flushing pending messages if any)")
        # Implement any necessary cleanup; for now, we leave it empty.
        pass
