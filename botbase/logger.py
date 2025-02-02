import logging
import os
from datetime import datetime

# ANSI color codes for console output
COLORS = {
    "DEBUG": "\033[36m",  # Cyan
    "INFO": "\033[32m",  # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[41m",  # Red background
    "MODULE": "\033[35m",  # Magenta for module names
}
RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    """
    A logging formatter that adds color to log level names and module names, and includes milliseconds.
    """

    def format(self, record):
        level_color = COLORS.get(record.levelname, RESET)
        module_color = COLORS["MODULE"]
        record.levelname = f"{level_color}{record.levelname}{RESET}"
        record.name = f"{module_color}{record.name}{RESET}"
        record.created_ms = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return super().format(record)


def setup_logging():
    """
    Set up the root logger with a custom colored formatter.
    Reads log level from the BOTBASE_LOG_LEVEL environment variable (default: DEBUG).
    """
    log_level = os.getenv("BOTBASE_LOG_LEVEL", "DEBUG").upper()
    numeric_level = getattr(logging, log_level, logging.DEBUG)

    console_handler = logging.StreamHandler()
    formatter = ColorFormatter(
        fmt="%(created_ms)s [%(levelname)s] %(name)s: %(message)s",
    )
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
