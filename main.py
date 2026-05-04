"""
@muhabbat0093 ERP Bot — Render uchun moslashtirilgan
Bot polling + HTTP server (UptimeRobot ping uchun)
"""

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from config.settings import settings
from database.engine import init_db, migrate_old_data
from handlers import register_all_handlers
from utils.logger import setup_logging


# ─── HTTP endpoints (Render + UptimeRobot ping uchun) ────────────────

async def root_handler(request: web.Request) -> web.Response:
    return web.Response(
        text="🤖 @muhabbat0093 ERP Bot ishlayapti\n\nStatus: ✅ OK",
        content_type="text/plain",
    )


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="OK", status=200)


def create_web_app() -> web.Application:
    app = web.Application()
    app.router.add_get('/', root_handler)
    app.router.add_get('/health', health_handler)
    app.router.add_get('/healthz', health_handler)
    app.router.add_get('/ping', health_handler)
    return app


# ─── BOT EVENTS ───────────────────────────────────────────────────────

async def on_startup(bot: Bot) -> None:
    me = await bot.get_me()
    logging.info(f"✅ Bot @{me.username} ishga tushdi")

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"🚀 Bot ishga tushdi!\n\n"
                f"🤖 @{me.username}\n"
                f"🌐 Server: Render Cloud\n"
                f"📊 Holat: faol\n"
                f"⚙️ Versiya: 3.0 ERP"
            )
        except Exception as e:
            logging.warning(f"Adminga xabar yuborilmadi {admin_id}: {e}")


# ─── ASOSIY ───────────────────────────────────────────────────────────

async def main() -> None:
    setup_logging()
    logging.info("🔧 Bot tayyorlanmoqda...")

    await init_db()
    logging.info("✅ Ma'lumotlar bazasi tayyor")

    await migrate_old_data()

    # Bot va dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    register_all_handlers(dp)
    dp.startup.register(on_startup)

    # HTTP server (Render port'da tinglash MAJBURIY)
    port = int(os.getenv('PORT', 10000))
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"🌐 HTTP server ishga tushdi: 0.0.0.0:{port}")

    # Bot va HTTP server parallel ishlaydi
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("🤖 Bot polling boshlandi")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await runner.cleanup()
        await bot.session.close()
        logging.info("👋 Bot to'xtatildi")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("👋 Bot to'xtatildi")
