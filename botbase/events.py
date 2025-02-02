import asyncio
import logging
from typing import Any, Awaitable, Callable, List

from botbase.tracker import ConversationTracker

logger = logging.getLogger(__name__)
_handler_registry: List[Callable[[ConversationTracker], Awaitable[Any]]] = []


def handler():
    """
    Decorator to register an event handler.
    Prevents duplicate registration if the same function is already in the registry.
    """

    def decorator(func: Callable[[ConversationTracker], Awaitable[Any]]):
        if func not in _handler_registry:
            _handler_registry.append(func)
            logger.info(f"Registered handler: {func.__name__}")
        else:
            logger.debug(f"Handler {func.__name__} already registered, skipping duplicate registration.")
        return func

    return decorator


async def handle_event(tracker: ConversationTracker):
    """
    Shared entry point to process a conversation: runs all registered handlers concurrently.
    """
    logger.info(f"Processing event for conversation: {tracker.conv_id}")
    tasks = [func(tracker) for func in _handler_registry]
    try:
        await asyncio.gather(*tasks)
        logger.info(f"Successfully processed event for conversation: {tracker.conv_id}")
    except Exception as e:
        logger.error(f"Error processing event for conversation {tracker.conv_id}: {str(e)}", exc_info=True)
        raise
