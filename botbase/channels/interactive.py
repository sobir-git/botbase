import asyncio
import datetime
import logging
import uuid
from enum import Enum
from typing import Optional

from prompt_toolkit import HTML, PromptSession, print_formatted_text
from prompt_toolkit.styles import Style

from botbase.events import handle_event
from botbase.tracker.base import Event
from botbase.tracker.factory import create_tracker

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Enum for special command types."""

    RESTART = "/restart"
    EXIT = "exit"
    QUIT = "quit"


prompt_style = Style.from_dict(
    {
        "prompt": "#ffff00 bold",
        "bot": "#00ff00 bold",
        "": "#ffff00 bold",
        "system": "#ff00ff bold",
    }
)


class InteractiveChannel:
    """
    An interactive channel that uses prompt_toolkit's styling features.
    Supports special commands like /restart and provides styled output for different message types.
    """

    def __init__(self, conv_id: Optional[str] = None):
        self.session = self._create_prompt_session()
        self.conv_id = conv_id
        self.tracker = None

    def _create_prompt_session(self) -> PromptSession:
        return PromptSession(
            HTML("<prompt>You:</prompt> "),
            style=prompt_style,
            input_processors=[],
            style_transformation=None,
            color_depth="DEPTH_24_BIT",
        )

    async def _initialize_conversation(self, conv_id: Optional[str] = None) -> None:
        if conv_id is None:
            conv_id = str(uuid.uuid4())
            logger.info(f"Generated new conversation ID: {conv_id}")
        self.tracker = await create_tracker(conv_id)
        logger.info(f"Initialized interactive channel with conversation ID: {conv_id}")
        self.tracker.register_callback(self.on_bot_event)

    async def _handle_restart(self) -> None:
        """Handle the /restart command by creating a new conversation."""
        new_conv_id = str(uuid.uuid4())
        self.conv_id = new_conv_id  # Update the interactive channel's conversation ID!
        await self._initialize_conversation(new_conv_id)
        self._print_styled(f"Started new conversation with ID: {new_conv_id}", "system")

    def _print_styled(self, text: str, style_class: str = "prompt") -> None:
        print_formatted_text(HTML(f"<{style_class}>{text}</{style_class}>"), style=prompt_style)

    async def _process_user_input(self, user_input: str) -> bool:
        user_input = user_input.strip()
        if user_input.lower() in (CommandType.EXIT.value, CommandType.QUIT.value):
            self._print_styled("Exiting...")
            return False
        elif user_input == CommandType.RESTART.value:
            await self._handle_restart()  # Now properly awaits the restart
            return True

        user_event = Event(
            type="user",
            text=user_input,
            payload={},
            created_at=datetime.datetime.utcnow(),
        )
        self.tracker.add_event(user_event)
        try:
            await handle_event(self.tracker)
            await self.tracker.persist()
        except Exception as e:
            self._print_styled(f"Error processing event: {e}")
            logger.error(f"Error processing event: {e}", exc_info=True)
        return True

    async def on_bot_event(self, event: Event) -> None:
        if event.type == "bot":
            self._print_styled(f"Bot: {event.text}", "bot")

    async def run(self) -> None:
        welcome_msg = (
            "Interactive Terminal Chatbot.\n"
            "Commands: <b>exit</b>/<b>quit</b> to stop, <b>/restart</b> for new conversation."
        )
        self._print_styled(welcome_msg, "system")
        await self._initialize_conversation(self.conv_id)
        while True:
            try:
                user_input = await self.session.prompt_async()
                should_continue = await self._process_user_input(user_input)
                if not should_continue:
                    break
            except (EOFError, KeyboardInterrupt):
                self._print_styled("\nExiting...", "system")
                break


def run_interactive(conv_id: Optional[str] = None):
    channel = InteractiveChannel(conv_id=conv_id)
    asyncio.run(channel.run())


if __name__ == "__main__":
    run_interactive()
