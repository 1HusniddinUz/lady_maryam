"""
Qarz eslatmalari uchun rejalashtiruvchi (scheduler).

Har kuni 09:00 (Asia/Tashkent = UTC+5) da muddati kelgan qarzlarni tekshiradi
va mijozlarga to'g'ridan o'zbekcha eslatma yuboradi. Qo'shimcha kutubxona
(APScheduler / pytz) talab qilmaydi — keep-alive pattern asosida.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config.settings import settings
from database.engine import get_session
from services.debt_service import (
    get_due_debts, generate_reminder_text, log_reminder,
    days_until_due, outstanding,
)
from utils.formatters import fmt_money, fmt_date


TASHKENT = timezone(timedelta(hours=5))  # Asia/Tashkent (DST yo'q)
REMINDER_HOUR = 9


def _seconds_until_next_run() -> float:
    """Keyingi 09:00 (Tashkent) gacha qolgan soniyalar."""
    now = datetime.now(TASHKENT)
    next_run = now.replace(hour=REMINDER_HOUR, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()


async def _notify_admins(bot: Bot, header: str, debt, text: str) -> None:
    msg = (
        f"{header}\n\n"
        f"👤 {debt.customer_name} ({debt.customer_phone})\n"
        f"🔴 Qoldiq: {fmt_money(outstanding(debt))}\n"
        f"📅 Muddat: {fmt_date(debt.due_date)}\n\n"
        f"📋 Eslatma matni:\n{text}"
    )
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, msg)
        except Exception:
            pass


async def run_due_reminders(bot: Bot) -> dict:
    """Muddati kelgan qarzlar bo'yicha eslatmalarni yuboradi. Statistika qaytaradi."""
    today = datetime.now(TASHKENT).date()
    sent = failed = manual = 0

    async with get_session() as session:
        due = await get_due_debts(session, today)
        if not due:
            logging.info("⏰ Bugun eslatma yuboriladigan qarz yo'q")
            return {"sent": 0, "failed": 0, "manual": 0}

        for debt in due:
            days = days_until_due(debt, today)
            tone = "urgent" if days < 0 else "polite"
            text = generate_reminder_text(debt, tone)

            if debt.customer_chat_id:
                try:
                    await bot.send_message(debt.customer_chat_id, text)
                    await log_reminder(session, debt.id, tone, text, "sent")
                    sent += 1
                except (TelegramForbiddenError, TelegramBadRequest):
                    await log_reminder(session, debt.id, tone, text, "failed")
                    failed += 1
                    await _notify_admins(bot, "⚠️ Mijozga eslatma yuborilmadi", debt, text)
            else:
                await log_reminder(session, debt.id, tone, text, "manual")
                manual += 1
                await _notify_admins(bot, "📋 Qarz eslatmasi (qo'lda yuborish kerak)", debt, text)

    logging.info(f"⏰ Eslatmalar: {sent} yuborildi, {failed} xato, {manual} qo'lda")
    return {"sent": sent, "failed": failed, "manual": manual}


async def reminder_scheduler_task(bot: Bot) -> None:
    """Har kuni 09:00 (Tashkent) da ishlaydigan background task."""
    logging.info("⏰ Qarz eslatma scheduler yoqildi (har kuni 09:00, Asia/Tashkent)")
    while True:
        try:
            await asyncio.sleep(_seconds_until_next_run())
        except asyncio.CancelledError:
            logging.info("⏰ Scheduler to'xtatildi")
            break

        try:
            await run_due_reminders(bot)
        except asyncio.CancelledError:
            logging.info("⏰ Scheduler to'xtatildi")
            break
        except Exception as e:
            logging.error(f"⏰ Scheduler xatosi: {e}")
