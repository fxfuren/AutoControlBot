from loguru import logger

logger.add(
    "bot.log",
    rotation="5 MB",
    retention="7 days",
    compression="zip"
)

__all__ = ["logger"]
