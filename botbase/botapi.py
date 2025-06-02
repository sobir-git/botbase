import logging
import sys
from contextlib import asynccontextmanager
from importlib import import_module

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from botbase.channels.base import BaseChannel
from botbase.config import ChannelConfig, config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # Executed on startup
    logger.info("Registered routes at startup:")
    for route_idx, route in enumerate(fastapi_app.routes):
        logger.info(f"Route #{route_idx}:")
        if hasattr(route, "path"):
            logger.info(f"  Name: {getattr(route, 'name', 'N/A')}")
            logger.info(f"  Path: {route.path}")
            logger.info(f"  Methods: {getattr(route, 'methods', 'N/A')}")
            if hasattr(route, "endpoint"):
                logger.info(
                    f"  Endpoint: {route.endpoint.__name__ if hasattr(route.endpoint, '__name__') else route.endpoint}"
                )
        elif hasattr(route, "routes"):  # For APIRouters or mounted sub-applications
            logger.info(f"  Router/Mount at prefix: {getattr(route, 'prefix', getattr(route, 'path_format', 'N/A'))}")
            for sub_route_idx, sub_route in enumerate(route.routes):
                if hasattr(sub_route, "path"):
                    logger.info(f"    Sub-route #{sub_route_idx}:")
                    logger.info(f"      Name: {getattr(sub_route, 'name', 'N/A')}")
                    logger.info(f"      Path: {sub_route.path}")  # This path is relative to the router's prefix
                    logger.info(f"      Full Path (estimated): {getattr(route, 'prefix', '')}{sub_route.path}")
                    logger.info(f"      Methods: {getattr(sub_route, 'methods', 'N/A')}")
                    if hasattr(sub_route, "endpoint"):
                        endpoint = (
                            sub_route.endpoint.__name__
                            if hasattr(sub_route.endpoint, "__name__")
                            else sub_route.endpoint
                        )
                        logger.info(f"      Endpoint: {endpoint}")
        else:
            logger.info(f"  Unknown route type: {type(route)}")
        logger.info("-" * 20)

    yield  # This is where the app runs


app = FastAPI(
    title="Ultimate Chatbot Framework",
    description=(
        "An async chatbot framework with conversation persistence, event handling, and flexible channel routing."
    ),
    lifespan=lifespan,
)


def init():
    """
    Initialize the framework by loading configuration and user-defined modules.
    """
    _add_cors_middleware()
    _load_and_register_channels()


def _add_cors_middleware():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _load_and_register_channels():
    for chan_cfg in config.channels:
        ChannelClass = _get_channel_class(chan_cfg.type)
        if not ChannelClass:
            continue

        channel_instance = _instantiate_channel(ChannelClass, chan_cfg)
        if not channel_instance:
            continue

        channel_instance.register_routes(app)
        logger.info(f"Channel {chan_cfg.name}:{chan_cfg.type} registered")


def _get_channel_class(channel_type: str) -> type[BaseChannel]:
    if "." in channel_type:
        return _get_custom_channel_class(channel_type)
    else:
        return _get_builtin_channel_class(channel_type)


def _get_custom_channel_class(channel_type: str) -> type[BaseChannel]:
    module_path, class_name = channel_type.rsplit(".", 1)
    try:
        mod = import_module(module_path)
        return getattr(mod, class_name)
    except (ImportError, AttributeError) as e:
        logger.error(f"Error loading custom channel '{channel_type}': {e}")
        return None


def _get_builtin_channel_class(channel_type: str) -> type[BaseChannel]:
    try:
        module_name = f"botbase.channels.{channel_type}"
        mod = import_module(module_name)
        return getattr(mod, f"{channel_type.capitalize()}Channel")
    except (ImportError, AttributeError) as e:
        logger.error(f"Error loading built-in channel '{channel_type}': {e}")
        return None


def _instantiate_channel(ChannelClass: type[BaseChannel], chan_cfg: ChannelConfig) -> BaseChannel:
    kwargs = chan_cfg.arguments
    try:
        return ChannelClass(name=chan_cfg.name, **kwargs)
    except Exception as e:
        logger.error(f"Error instantiating channel '{chan_cfg.name}' with params {kwargs}: {e}")
        return None


def runserver(**uvicorn_kwargs):
    """
    Run the server using Uvicorn with the provided keyword arguments.
    Handles CLI arguments for both interactive and server modes.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Run the bot in interactive or server mode")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive terminal mode")
    parser.add_argument(
        "--conv-id",
        type=str,
        default=None,
        help="Specify a conversation ID for interactive mode. If not provided, a UUID will be generated.",
    )

    # Parse only known args to allow additional uvicorn args
    args, remaining_argv = parser.parse_known_args()

    # Update sys.argv to only contain unparsed args
    sys.argv[1:] = remaining_argv

    if args.interactive:
        logger.info("Starting interactive terminal channel")
        from botbase.channels.interactive import run_interactive

        run_interactive(conv_id=args.conv_id)
        return

    # Otherwise, start the web server
    import uvicorn

    logger.info("Running Uvicorn server...")
    # Disable Uvicorn's default logging configuration so our logs are used
    uvicorn_kwargs.setdefault("log_config", None)

    uvicorn.run("botbase.botapi:app", **uvicorn_kwargs)


init()
