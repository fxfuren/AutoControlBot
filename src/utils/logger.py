from loguru import logger

logger.add("bot.log", rotation="5 MB")

__all__ = ["logger"]
