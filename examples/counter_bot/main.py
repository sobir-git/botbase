import asyncio
import logging

from botbase import botapi
from botbase.events import handler
from botbase.tracker import ConversationTracker

logger = logging.getLogger(__name__)


@handler()
async def handle_greet(tracker: ConversationTracker):
    last = tracker.last_user_message()
    if last and last.text.lower() in ["hello", "hi", "hey"]:
        first_greeting = not tracker.slots.get("greeted", False)
        if first_greeting:
            tracker.send_bot_message("Hi!", metadata={"first_greeting": True})
        else:
            tracker.send_bot_message("You have already greeted me.")
        tracker.set_slot("greeted", True)


@handler()
async def handle_counter(tracker: ConversationTracker):
    last = tracker.last_user_message()
    if last and last.text.lower().startswith("count "):
        try:
            count = int(last.text.split()[1])
            for i in range(1, count + 1):
                tracker.send_bot_message(f"Counting: {i}")
                if i != count:
                    await asyncio.sleep(1)  # <-- Non-blocking sleep!
        except ValueError:
            tracker.send_bot_message("Please provide a valid number after 'count'.")


if __name__ == "__main__":
    # Start the server
    botapi.runserver(host="0.0.0.0", port=8000)
