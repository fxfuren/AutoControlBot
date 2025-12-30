from loguru import logger

# Настройка логгера с ротацией и ограничением хранения
logger.add(
    "bot.log",
    rotation="5 MB",
    retention="7 days",  # Автоудаление старых логов
    compression="zip",   # Сжатие для экономии места
    enqueue=True,        # Асинхронная запись для производительности
    backtrace=False,     # Отключение backtrace для экономии памяти
    diagnose=False       # Отключение детальной диагностики
)

__all__ = ["logger"]
