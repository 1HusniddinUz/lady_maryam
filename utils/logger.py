"""
Logging sozlamalari
"""

import logging
import sys


def setup_logging() -> None:
    """Logging ni sozlash - emoji va unicode ni qo'llab-quvvatlaydi"""

    # Windows uchun stdout ni UTF-8 ga o'tkazish
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass

    log_format = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

    # File handler (UTF-8)
    file_handler = logging.FileHandler("bot.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_format))

    # Stream handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(log_format))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, stream_handler],
    )

    # Shovqinni kamaytirish
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
