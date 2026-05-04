"""
Admin huquqini tekshiruvchi filter
"""

from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery, TelegramObject

from database.engine import get_session
from services.user_service import is_admin


class IsAdmin(Filter):
    """Faqat admin foydalanuvchilar uchun"""

    async def __call__(self, event: TelegramObject) -> bool:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if not user_id:
            return False

        async with get_session() as session:
            return await is_admin(session, user_id)
