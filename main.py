"""
@muhabbat0093 ERP Bot — Render + WebApp
Bot polling + HTTP server (API + Static WebApp)
"""

import asyncio
import logging
import os
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo
from aiohttp import web

from config.settings import settings
from database.engine import init_db, migrate_old_data
from handlers import register_all_handlers
from utils.logger import setup_logging
from api import register_api_routes


# ─── HTTP endpoints ───────────────────────────────────────────────────

async def root_handler(request: web.Request) -> web.Response:
    """Root - WebApp ga redirect"""
    raise web.HTTPFound("/webapp/")


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="OK", status=200)


def create_web_app(bot: Bot) -> web.Application:
    app = web.Application()

    # API routes
    register_api_routes(app)

    # Bot ni request'larga injekt qilish (admin bildirishnomalari uchun)
    app["bot"] = bot

    # Health check
    app.router.add_get("/health", health_handler)
    app.router.add_get("/healthz", health_handler)
    app.router.add_get("/ping", health_handler)
    app.router.add_get("/", root_handler)

    # Static WebApp fayllar
    webapp_dir = Path(__file__).parent / "webapp"
    if webapp_dir.exists():
        app.router.add_static(
            "/webapp/",
            path=str(webapp_dir),
            name="webapp",
            show_index=True,  # index.html avto-yuklanadi
        )
        logging.info(f"📂 WebApp dir: {webapp_dir}")
    else:
        logging.warning(f"⚠️ WebApp dir topilmadi: {webapp_dir}")

    return app


# ─── BOT EVENTS ───────────────────────────────────────────────────────

async def on_startup(bot: Bot) -> None:
    me = await bot.get_me()
    logging.info(f"✅ Bot @{me.username} ishga tushdi")

    # Menu button: WebApp'ni ochuvchi doimiy tugma
    webapp_url = os.getenv("WEBAPP_URL", "").strip()
    if webapp_url:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🛍 Do'kon",
                    web_app=WebAppInfo(url=webapp_url),
                )
            )
            logging.info(f"✅ Menu button WebApp ulandi: {webapp_url}")
        except Exception as e:
            logging.warning(f"Menu button xato: {e}")

    # Adminlarga xabar
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"🚀 Bot ishga tushdi!\n\n"
                f"🤖 @{me.username}\n"
                f"🌐 Server: Render Cloud\n"
                f"🛍 WebApp: {webapp_url or 'sozlanmagan'}"
            )
        except Exception as e:
            logging.warning(f"Adminga xabar yuborilmadi {admin_id}: {e}")


async def main() -> None:
    setup_logging()
    logging.info("🔧 Bot tayyorlanmoqda...")

    await init_db()
    logging.info("✅ Ma'lumotlar bazasi tayyor")
    await migrate_old_data()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    register_all_handlers(dp)
    dp.startup.register(on_startup)

    # HTTP server
    port = int(os.getenv("PORT", 10000))
    app = create_web_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"🌐 HTTP server ishga tushdi: 0.0.0.0:{port}")

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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("👋 Bot to'xtatildi")
