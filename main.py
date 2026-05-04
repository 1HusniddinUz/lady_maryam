"""
@muhabbat0093 ERP Bot — Asosiy fayl
Mijozlar uchun onlayn-do'kon + Admin uchun ERP tizimi
"""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import settings
from database.engine import init_db, migrate_old_data
from handlers import register_all_handlers
from utils.logger import setup_logging


async def on_startup(bot: Bot) -> None:
    """Bot ishga tushganida bajariladi"""
    me = await bot.get_me()
    logging.info(f"✅ Bot @{me.username} ishga tushdi")

    # Adminlarga xabar
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"🚀 Bot ishga tushdi!\n\n"
                f"🤖 @{me.username}\n"
                f"📊 Holat: faol\n"
                f"⚙️ Versiya: 3.0 ERP"
            )
        except Exception as e:
            logging.warning(f"Adminga xabar yuborilmadi {admin_id}: {e}")


async def on_shutdown(bot: Bot) -> None:
    """Bot to'xtaganida bajariladi"""
    logging.info("⛔ Bot to'xtatilmoqda...")
    await bot.session.close()


async def main() -> None:
    setup_logging()
    logging.info("🔧 Bot tayyorlanmoqda...")

    # Bazani yaratish
    await init_db()
    logging.info("✅ Ma'lumotlar bazasi tayyor")

    # Eski botdan ma'lumotlarni ko'chirish (agar bor bo'lsa)
    await migrate_old_data()

    # Bot va dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Barcha handlerlarni ulash
    register_all_handlers(dp)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("👋 Bot to'xtatildi")
