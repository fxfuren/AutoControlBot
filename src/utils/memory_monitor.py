"""Утилита для мониторинга использования памяти."""
import gc
import psutil
from src.utils.logger import logger


def log_memory_usage(context: str = "") -> None:
    """Логирует текущее использование памяти процессом."""
    try:
        process = psutil.Process()
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / 1024 / 1024  # RSS в мегабайтах
        
        prefix = f"[{context}] " if context else ""
        logger.info(f"💾 {prefix}Использование памяти: {mem_mb:.1f} MB")
    except Exception as e:
        logger.warning(f"Не удалось получить информацию о памяти: {e}")


def force_garbage_collection() -> None:
    """Принудительно запускает сборщик мусора и логирует результат."""
    collected = gc.collect()
    logger.debug(f"🗑️ Сборка мусора завершена: удалено {collected} объектов")
