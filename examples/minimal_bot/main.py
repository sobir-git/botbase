from botbase import botapi
from botbase.events import handler
from botbase.tracker import ConversationTracker


@handler()
async def my_handler(tracker: ConversationTracker):
    last = tracker.last_user_message()
    if last and last.text.lower() == "hello":
        tracker.send_bot_message("Hi there!")
    else:
        tracker.send_bot_message("Echo: " + (last.text if last else ""))


if __name__ == "__main__":
    # Run using Uvicorn
    botapi.runserver(host="0.0.0.0", port=8000)
