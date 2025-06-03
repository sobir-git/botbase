import datetime
import logging
import uuid

import aiohttp
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from botbase.channels.base import BaseChannel
from botbase.events import handle_event
from botbase.tracker.base import ConversationTracker, Event
from botbase.tracker.factory import create_tracker

logger = logging.getLogger(__name__)


class JivoChatChannel(BaseChannel):
    """
    A channel for integrating with JivoChat using their Bot API.

    JivoChat Bot API interaction:
    - JivoChat sends events (like CLIENT_MESSAGE) to this bot's endpoint.
      The endpoint URL configured in JivoChat includes a shared token:
      `https://<your_bot_server>/<channel_name>/{shared_token}`
    - This bot sends BOT_MESSAGE events back to JivoChat's API endpoint:
      `https://bot.jivosite.com/webhooks/{provider_id}/{shared_token}`

    Args:
        name (str): A name for this channel instance (e.g., "my_jivo_bot").
        provider_id (str): Your JivoChat Provider ID. If you are connecting a single bot
                           and not acting as a multi-tenant bot platform, this might be
                           a unique ID you define or one provided by JivoChat for your bot.
        shared_token (str): A secret token that you define. This token is used in the URL
                            for both incoming requests from JivoChat and outgoing requests
                            to JivoChat, ensuring that communication is authorized.
        jivo_api_base_url (str): The base URL for JivoChat's Bot API.
                                 Defaults to "https://bot.jivosite.com/webhooks".
    """

    def __init__(
        self,
        name: str,
        provider_id: str,
        shared_token: str,
        jivo_api_base_url: str = "https://bot.jivosite.com/webhooks",
    ):
        super().__init__(name)
        self.provider_id = provider_id
        self.shared_token = shared_token
        self.jivo_api_base_url = jivo_api_base_url

        self.router.post(f"/{self.shared_token}")(self.process_request)

    def register_routes(self, app: FastAPI):
        app.include_router(self.router)
        logger.info(
            f"JivoChat routes registered for channel '{self.name}'. "
            f"Jivo should be configured to call: .../channels/{self.name}/{self.shared_token}"
        )

    async def process_request(
        self,
        request: Request,
        background_tasks: BackgroundTasks,
    ):
        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON from JivoChat request: {e}")
            raise HTTPException(
                status_code=400, detail={"error": {"code": "invalid_request", "message": "Invalid JSON format."}}
            ) from e

        event_type = data.get("event")
        logger.debug(f"Processing incoming JivoChat event: {event_type}, data: {data}")

        if event_type == "CLIENT_MESSAGE":
            message_data = data.get("message", {})
            text = message_data.get("text")
            chat_id = data.get("chat_id")
            client_id = data.get("client_id")

            if not chat_id:
                logger.warning(f"JivoChat CLIENT_MESSAGE missing 'chat_id'. Data: {data}")
                return {"error": {"code": "invalid_request", "message": "CLIENT_MESSAGE missing 'chat_id'."}}

            logger.info(f"Received JivoChat CLIENT_MESSAGE for chat_id: {chat_id} from client_id: {client_id}")
            tracker = await create_tracker(chat_id)

            tracker.register_callback(lambda bot_event: self.on_tracker_event(bot_event, tracker))

            timestamp_unix = message_data.get("timestamp", int(datetime.datetime.utcnow().timestamp()))
            try:
                created_dt = datetime.datetime.fromtimestamp(timestamp_unix, tz=datetime.timezone.utc)
            except (TypeError, ValueError):
                logger.warning(f"Invalid timestamp format from Jivo: {timestamp_unix}. Using current time.")
                created_dt = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

            user_event = Event(
                type="user",
                text=text if text is not None else "",
                user_id=str(client_id) if client_id else None,
                created_at=created_dt,
                payload=data,
            )
            tracker.add_event(user_event)
            logger.debug(f"User event from JivoChat (chat_id: {chat_id}) added to tracker.")

            background_tasks.add_task(handle_event, tracker)
            background_tasks.add_task(tracker.persist)

            return {"status": "ok", "message": "CLIENT_MESSAGE received and processing initiated."}

        elif event_type in [
            "AGENT_JOINED",
            "AGENT_UNAVAILABLE",
            "CHAT_CLOSED",
            "INVITE_AGENT_ACCEPTED",
            "CONTACT_FORM_SENT",
        ]:
            logger.info(
                f"Received JivoChat informational event: {event_type} "
                f"for chat_id: {data.get('chat_id')}. Payload: {data}"
            )
            return {"status": "ok", "message": f"{event_type} received."}
        else:
            logger.warning(f"Received unhandled or unknown JivoChat event type: {event_type}. Data: {data}")
            return {
                "error": {"code": "unsupported_event", "message": f"Unsupported or unknown event type: {event_type}"}
            }

    async def on_tracker_event(self, event: Event, tracker: ConversationTracker):
        if event.type == "bot":
            logger.info(f"New bot event detected for JivoChat conversation {tracker.conv_id}: '{event.text}'")
            await self.dispatch_bot_event(event, tracker.conv_id)

    async def dispatch_bot_event(self, event: Event, conv_id: str):
        if not self.provider_id or not self.shared_token:
            logger.error("JivoChat provider_id or shared_token not configured. Cannot dispatch BOT_MESSAGE.")
            return

        webhook_url = f"{self.jivo_api_base_url}/{self.provider_id}/{self.shared_token}"

        message_content = {
            "type": "TEXT",
            "text": event.text or "",
            "timestamp": int(
                event.created_at.timestamp() if event.created_at else datetime.datetime.utcnow().timestamp()
            ),
        }

        if event.payload:
            if "jivo_message" in event.payload and isinstance(event.payload["jivo_message"], dict):
                message_content = event.payload["jivo_message"]
                if "timestamp" not in message_content:
                    message_content["timestamp"] = int(
                        event.created_at.timestamp() if event.created_at else datetime.datetime.utcnow().timestamp()
                    )
            elif "buttons" in event.payload and isinstance(event.payload["buttons"], list):
                message_content["type"] = "BUTTONS"
                message_content["title"] = str(event.payload.get("title", event.text or "Please choose:"))
                message_content["buttons"] = event.payload["buttons"]
                message_content["text"] = str(
                    event.payload.get("fallback_text", event.text or message_content["title"])
                )

        jivo_payload = {"event": "BOT_MESSAGE", "id": str(uuid.uuid4()), "chat_id": conv_id, "message": message_content}

        logger.info(f"Dispatching BOT_MESSAGE to JivoChat ({webhook_url}) for chat_id {conv_id}: {jivo_payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=jivo_payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    response_text = await resp.text()
                    if resp.status == 200:
                        logger.info(
                            f"Successfully dispatched BOT_MESSAGE to JivoChat for chat_id {conv_id}. "
                            f"Response status: {resp.status}, body: {response_text[:200]}"
                        )
                    else:
                        logger.error(
                            f"Failed to dispatch BOT_MESSAGE to JivoChat for chat_id {conv_id}. "
                            f"HTTP status: {resp.status}, Response: {response_text}"
                        )
        except Exception as e:
            logger.error(
                f"Exception dispatching BOT_MESSAGE to JivoChat for chat_id {conv_id}: {str(e)}", exc_info=True
            )

    def close(self):
        pass
