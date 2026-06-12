"""
Chatni toza saqlash: har yangi xabardan keyin eski xabar o'chib boradi.

Ikki qism:
  1. Outgoing (session) middleware — bot yangi MATNLI xabar yuborganda,
     o'sha chatdagi oldingi bot matnli xabarini o'chiradi.
     Rasm/hujjat (grafik, Excel) larga tegmaydi — ular saqlanib qoladi.
  2. Incoming (dispatcher) middleware — foydalanuvchi yozgan xabarni
     handler ishlab bo'lgach o'chiradi.

Natija: chatda doimo faqat eng oxirgi menyu/xabar ko'rinib turadi.
"""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.methods import SendMessage
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)

# chat_id -> oxirgi bot matnli xabarining message_id si
_last_bot_message: Dict[int, int] = {}


async def cleanup_outgoing(make_request, bot, method):
    """
    Session request middleware.

    Bot matnli xabar (SendMessage) yuborganda — o'sha chatdagi oldingi
    bot matnli xabarini o'chiradi. Rasm/hujjatlar bunga aralashmaydi
    (na o'chiriladi, na oldingisini o'chiradi).
    """
    result = await make_request(bot, method)
    try:
        if isinstance(method, SendMessage) and isinstance(result, Message):
            chat_id = result.chat.id
            new_id = result.message_id
            prev_id = _last_bot_message.get(chat_id)
            _last_bot_message[chat_id] = new_id
            if prev_id and prev_id != new_id:
                try:
                    await bot.delete_message(chat_id, prev_id)
                except Exception:
                    # eski / allaqachon o'chgan / 48 soatdan oshgan xabar — e'tiborsiz
                    pass
    except Exception as e:
        logger.debug(f"cleanup_outgoing: {e}")
    return result


def forget_chat(chat_id: int) -> None:
    """Kerak bo'lsa, chat uchun kuzatuvni tozalash (masalan, qo'lda)."""
    _last_bot_message.pop(chat_id, None)


class DeleteIncomingMiddleware(BaseMiddleware):
    """Foydalanuvchi yuborgan xabarni (handler ishlab bo'lgach) o'chiradi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        result = await handler(event, data)
        if isinstance(event, Message):
            try:
                await event.bot.delete_message(event.chat.id, event.message_id)
            except Exception:
                pass
        return result
