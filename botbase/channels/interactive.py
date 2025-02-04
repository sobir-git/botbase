import asyncio
import datetime
import logging
import uuid
from typing import Optional

from prompt_toolkit import HTML, PromptSession, print_formatted_text
from prompt_toolkit.styles import Style

from botbase.events import handle_event
from botbase.tracker.base import Event
from botbase.tracker.factory import create_tracker

logger = logging.getLogger(__name__)

# Define a style dictionary for prompt_toolkit.
# - 'prompt' will be used for the input prompt and user messages.
# - 'bot' will be used for bot messages.
# - '' (empty string) will be used as the default style for user input.
prompt_style = Style.from_dict(
    {
        "prompt": "#ffff00 bold",  # Yellow and bold for the prompt
        "bot": "#00ff00 bold",  # Green and bold for bot messages
        "": "#ffff00 bold",  # Default style (yellow and bold) for user input
    }
)


class InteractiveChannel:
    """
    An interactive channel that uses prompt_toolkit's styling features.
    The user prompt and user messages appear in yellow, and bot messages appear in green.
    """

    def __init__(self, conv_id: Optional[str] = None):
        # Generate UUID if no conv_id provided
        if conv_id is None:
            conv_id = str(uuid.uuid4())
            logger.info(f"Generated new conversation ID: {conv_id}")

        # Create or load a conversation tracker
        self.tracker = create_tracker(conv_id)
        logger.info(f"Initialized interactive channel with conversation ID: {conv_id}")

        # Register a callback to display bot messages
        self.tracker.register_callback(self.on_bot_event)

        # Create a PromptSession with a styled prompt
        self.session = PromptSession(
            HTML("<prompt>You:</prompt> "),
            style=prompt_style,
            input_processors=[],  # Clear any default processors
            style_transformation=None,  # Clear any default transformations
            color_depth="DEPTH_24_BIT",  # Enable true color support
        )

    async def on_bot_event(self, event: Event):
        """Display bot messages using the defined bot style."""
        if event.type == "bot":
            print_formatted_text(HTML(f"<bot>Bot: {event.text}</bot>"), style=prompt_style)

    async def run(self):
        """Run the interactive chat loop."""
        print_formatted_text(
            HTML("<prompt>Interactive Terminal Chatbot. Type <b>exit</b> or <b>quit</b> to stop.</prompt>"),
            style=prompt_style,
        )
        while True:
            try:
                # Await asynchronous input with the styled prompt.
                user_input = await self.session.prompt_async()
            except (EOFError, KeyboardInterrupt):
                print_formatted_text(HTML("<prompt>\nExiting...</prompt>"), style=prompt_style)
                break

            if user_input.strip().lower() in ("exit", "quit"):
                print_formatted_text(HTML("<prompt>Exiting...</prompt>"), style=prompt_style)
                break

            # Don't echo the input since PromptSession will show it in yellow
            # print_formatted_text(HTML(f'<prompt>You: {user_input}</prompt>'), style=prompt_style)

            # Create a user event.
            user_event = Event(
                type="user",
                text=user_input,
                payload={},
                created_at=datetime.datetime.utcnow(),
            )
            self.tracker.add_event(user_event)

            # Process the event using registered handlers.
            try:
                await handle_event(self.tracker)
            except Exception as e:
                print_formatted_text(HTML(f"<prompt>Error processing event:</prompt> {e}"), style=prompt_style)

            # Persist any new events.
            await self.tracker.persist()


def run_interactive(conv_id: Optional[str] = None):
    """Run the interactive terminal channel.

    Args:
        conv_id: Optional conversation ID. If not provided, a UUID will be generated.
    """
    channel = InteractiveChannel(conv_id=conv_id)
    asyncio.run(channel.run())


if __name__ == "__main__":
    run_interactive()
