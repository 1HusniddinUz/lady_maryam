"""
@muhabbat0093 ERP Bot — Render + WebApp (v3)
Bot polling + HTTP server (API + Static WebApp) + Keep-Alive
YANGI: Render uxlamasligi uchun har 14 daqiqada o'ziga ping yuboradi
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
from aiohttp import web, ClientSession, ClientTimeout

from config.settings import settings
from database.engine import init_db, migrate_old_data
from handlers import register_all_handlers
from utils.logger import setup_logging
from api import register_api_routes


WEBAPP_DIR = Path(__file__).parent / "webapp"
PING_INTERVAL = 840  # 14 daqiqa (Render free tier 15 daqiqadan keyin uxlaydi)


# ─── HTTP endpoints ───────────────────────────────────────────────────

async def root_handler(request: web.Request) -> web.Response:
    raise web.HTTPFound("/webapp/")


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="OK", status=200)


async def webapp_index(request: web.Request) -> web.Response:
    """ /webapp/ uchun index.html ni yuborish """
    index_path = WEBAPP_DIR / "index.html"
    if not index_path.exists():
        return web.Response(text="WebApp topilmadi", status=404)
    return web.FileResponse(index_path, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
    })


async def webapp_redirect(request: web.Request) -> web.Response:
    raise web.HTTPMovedPermanently("/webapp/")


def create_web_app(bot: Bot) -> web.Application:
    app = web.Application()

    # API routes (avval qo'yiladi - prioritetli)
    register_api_routes(app)

    app["bot"] = bot

    # Health
    app.router.add_get("/health", health_handler)
    app.router.add_get("/healthz", health_handler)
    app.router.add_get("/ping", health_handler)
    app.router.add_get("/", root_handler)

    # ⚡ MUHIM: Index'ni alohida route qilamiz (static'dan oldin)
    app.router.add_get("/webapp", webapp_redirect)
    app.router.add_get("/webapp/", webapp_index)
    app.router.add_get("/webapp/index.html", webapp_index)

    # Endi static fayllar (CSS, JS, rasmlar)
    if WEBAPP_DIR.exists():
        app.router.add_static(
            "/webapp/",
            path=str(WEBAPP_DIR),
            name="webapp_static",
            show_index=False,
            follow_symlinks=False,
        )
        logging.info(f"📂 WebApp dir: {WEBAPP_DIR}")
    else:
        logging.warning(f"⚠️ WebApp dir topilmadi: {WEBAPP_DIR}")

    return app


# ─── KEEP-ALIVE (Render uxlamasligi uchun) ──────────────────────────

async def keep_alive_task() -> None:
    """
    Har 14 daqiqada o'z serveriga /health endpoint orqali ping yuboradi.
    Render free tier 15 daqiqalik bekorlikdan keyin servisni uxlatib qo'yadi.

    URL prioriteti:
      1. PING_URL env variable (qo'lda berilsa)
      2. RENDER_EXTERNAL_URL (Render avtomatik beradi)
      3. WEBAPP_URL (fallback)
    """
    ping_url = (
        os.getenv("PING_URL", "").strip()
        or os.getenv("RENDER_EXTERNAL_URL", "").strip()
        or os.getenv("WEBAPP_URL", "").strip()
    )

    if not ping_url:
        logging.warning("⚠️ PING_URL/RENDER_EXTERNAL_URL yo'q — keep-alive o'chirildi")
        return

    # URL'ni tozalaymiz: oxiridagi / va /webapp ni olib tashlaymiz
    ping_url = ping_url.rstrip("/")
    if "/webapp" in ping_url:
        ping_url = ping_url.split("/webapp")[0]
    health_url = f"{ping_url}/health"

    logging.info(f"💓 Keep-alive yoqildi: {health_url} (har {PING_INTERVAL}s)")

    # Server to'liq ko'tarilishi uchun biroz kutamiz
    await asyncio.sleep(60)

    timeout = ClientTimeout(total=30)

    while True:
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.get(health_url) as resp:
                    logging.info(f"💓 Ping: {resp.status}")
        except asyncio.CancelledError:
            logging.info("💓 Keep-alive to'xtatildi")
            break
        except Exception as e:
            logging.warning(f"💓 Ping xatosi: {e}")

        try:
            await asyncio.sleep(PING_INTERVAL)
        except asyncio.CancelledError:
            logging.info("💓 Keep-alive to'xtatildi")
            break


# ─── BOT EVENTS ───────────────────────────────────────────────────────

async def on_startup(bot: Bot) -> None:
    me = await bot.get_me()
    logging.info(f"✅ Bot @{me.username} ishga tushdi")

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

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"🚀 Bot ishga tushdi!\n\n"
                f"🤖 @{me.username}\n"
                f"🛍 WebApp: {'✅ ulangan' if webapp_url else '❌ sozlanmagan'}"
            )
        except Exception as e:
            logging.warning(f"Adminga xabar: {e}")


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

    port = int(os.getenv("PORT", 10000))
    app = create_web_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"🌐 HTTP server: 0.0.0.0:{port}")

    # 💓 Keep-alive task'ni background'da ishga tushiramiz
    keep_alive = asyncio.create_task(keep_alive_task())

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("🤖 Bot polling boshlandi")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        # Keep-alive'ni to'xtatamiz
        keep_alive.cancel()
        try:
            await keep_alive
        except asyncio.CancelledError:
            pass
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("👋 Bot to'xtatildi")