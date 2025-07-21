"""log_setup.py Logging utilities.

This module centralizes logging configuration for the project. It adds
color‑coded output, trace/node context, and separate formatting rules for
stream vs. file handlers.

Typical usage example:
    >>> from oxygent.log_setup import setup_logging
    >>> logger = setup_logging()
    >>> logger.info("Regular info log", extra={"trace_id": "abc123", "node_id": "node-1"})

The implementation relies on *Colorama* for terminal color rendering and a
small *Config* helper to read user‑defined preferences such as the minimum
log level, where to store the log file, and whether to highlight the full
line or the message body only.
"""

import logging
import os

from colorama import Back, Fore, Style

from .config import Config
from .schemas.color import Color

# Logging level to color mapping
LEVEL_COLOR_MAP = {
    logging.DEBUG: Color.BLACK,
    logging.INFO: Color.GREEN,
    logging.WARNING: Color.MAGENTA,
    logging.ERROR: Color.RED,
    logging.CRITICAL: Color.RED,
}


class IDAwareFormatter(logging.Formatter):
    """Formatter that injects *trace_id* and *node_id* into the log line.

    If the *LogRecord* already contains those attributes they will be
    rendered between dashes, e.g. ``- 123 -``. Otherwise they default to an
    empty string so the surrounding formatting still works.
    """

    def format(self, record):
        # trace_id
        if hasattr(record, "trace_id"):
            record.trace_id = f" - {record.trace_id} -"
        else:
            record.trace_id = ""
        # node_id
        if hasattr(record, "node_id"):
            record.node_id = f" {record.node_id} -"
        else:
            record.node_id = ""
        return super().format(record)


def get_style_by_record(record):
    """Return ANSI style string (may be empty) for *record*.

    The style is derived in this order:
    1. User-provided ``record.color`` attribute (string or ``Color`` enum).
    2. Pre-defined mapping based on log level.

    If a color is not recognized, :class:`ValueError` is raised.
    """
    bold_style = Style.BRIGHT if Config.get_log_is_bright() else ""
    layer = Back if Config.get_log_color_is_on_background() else Fore
    level_color = LEVEL_COLOR_MAP.get(record.levelno, layer.WHITE)
    if level_color is Color.DEFAULT:
        color_style = ""
    else:
        color_style = getattr(layer, level_color.name)
    if hasattr(record, "color"):
        if isinstance(record.color, str):
            color_upper = record.color.upper()
        elif isinstance(record.color, Color):
            color_upper = record.color.name
        else:
            raise Exception(
                "Tyle not supported: please pass a valid ``Color`` enum value or a recognized color name."
            )
        if color_upper == Color.DEFAULT.name:
            color_style = ""
        elif hasattr(layer, color_upper):
            color_style = getattr(layer, color_upper)
        else:
            raise Exception(
                "Undefined color: please pass a valid ``Color`` enum value or a recognized color name."
            )
    return bold_style + color_style


class ColorFormatter(IDAwareFormatter):
    """Formatter that adds ANSI color codes to the **entire** log line."""

    def format(self, record):
        # 1. call super().format to get the original message
        # 2. get the style for the entire line
        # 3. apply the style to the entire message
        return f"{get_style_by_record(record)}{super().format(record)}{Style.RESET_ALL}"


class ColorMessageFormatter(IDAwareFormatter):
    """Formatter that adds ANSI color codes to the **message** part only."""

    def formatMessage(self, record):
        # message is the only part that gets colored
        record.message = (
            f"{get_style_by_record(record)}{record.getMessage()}{Style.RESET_ALL}"
        )
        return super().formatMessage(record)


def setup_logging():
    """Configure root logger with colored stream handler and plain file handler.

    The configuration parameters are read from :class:`~oxygent.config.Config`.
    After setup, the root logger is returned for convenience so that callers
    can immediately emit logs without querying ``logging.getLogger()``.

    Returns
    -------
    logging.Logger
        The fully configured root logger.
    """
    # # Reduce noise from third‑party libraries
    logging.getLogger("mcp").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)

    # File handler – no colors
    os.makedirs(os.path.dirname(Config.get_log_path()), exist_ok=True)
    file_handler = logging.FileHandler(Config.get_log_path(), encoding="utf-8")
    file_handler.setLevel(Config.get_log_level_file())
    file_formatter = IDAwareFormatter(
        "%(asctime)s - %(levelname)s%(trace_id)s%(node_id)s %(pathname)s line:%(lineno)d - %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # Stream handler – optional colors
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(Config.get_log_level_terminal())
    class_type = (
        ColorMessageFormatter if Config.get_log_only_message_color() else ColorFormatter
    )
    stream_formatter = class_type(
        "%(asctime)s - %(levelname)s%(trace_id)s%(node_id)s %(message)s"
    )
    stream_handler.setFormatter(stream_formatter)

    # Root logger wiring
    logging.basicConfig(
        level=Config.get_log_level_root(), handlers=[stream_handler, file_handler]
    )
    return logging.getLogger()


if __name__ == "__main__":
    logger = setup_logging()
    logger.info("Regular info log")
    logger.warning("Warning log (default magenta)")
    logger.error("Error log (default red)")
    logger.info(
        "Custom color log",
        extra={"color": "red", "trace_id": "abc123", "node_id": "node-1"},
    )
    Config.set_log_color_is_on_background(True)
    logger.error("Error log with background color", extra={"color": "blue"})
