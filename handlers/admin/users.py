"""
Admin: Foydalanuvchilar boshqaruvi va broadcast
"""

import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config.settings import settings
from database.engine import get_session
from database.models import UserRole
from services.user_service import (
    get_all_users, count_users, block_user, get_user_by_tg_id,
    get_user_by_username, is_superadmin, set_admin,
)
from keyboards.admin_kb import (
    users_menu_kb, user_actions_kb, admin_main_kb, cancel_kb, admins_manage_kb
)
from handlers.filters import IsAdmin
from handlers.states import Broadcast, AddAdmin
from utils.formatters import fmt_datetime


router = Router(name="admin_users")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _users_menu_text(stats: dict) -> str:
    return (
        f"👥 <b>Foydalanuvchilar</b>\n\n"
        f"📊 Jami: <b>{stats['total']}</b>\n"
        f"🛡 Adminlar: {stats['admins']}\n"
        f"🛒 Mijozlar: {stats['customers']}\n"
        f"🚫 Bloklangan: {stats['blocked']}"
    )


@router.message(F.text == "👥 Foydalanuvchilar")
async def users_main(message: Message) -> None:
    async with get_session() as session:
        stats = await count_users(session)
    await message.answer(
        _users_menu_text(stats),
        reply_markup=users_menu_kb(is_super=is_superadmin(message.from_user.id)),
    )


@router.callback_query(F.data == "us:menu")
async def users_menu_cb(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with get_session() as session:
        stats = await count_users(session)
    await call.message.answer(
        _users_menu_text(stats),
        reply_markup=users_menu_kb(is_super=is_superadmin(call.from_user.id)),
    )
    await call.answer()


@router.callback_query(F.data == "us:list")
async def users_list(call: CallbackQuery) -> None:
    async with get_session() as session:
        users = await get_all_users(session, only_customers=True)

    if not users:
        await call.answer("👥 Mijozlar yo'q", show_alert=True)
        return

    text = f"📋 <b>Mijozlar ro'yxati</b> ({len(users)} ta):\n\n"
    for u in users[:30]:
        block_icon = "🚫 " if u.is_blocked else ""
        text += (
            f"{block_icon}<b>{u.full_name}</b>\n"
            f"   📱 {u.phone or '—'} • 🆔 <code>{u.telegram_id}</code>\n"
            f"   📅 {fmt_datetime(u.created_at)}\n\n"
        )
    if len(users) > 30:
        text += f"<i>... va yana {len(users) - 30} ta</i>"

    await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data.startswith("us:block:"))
async def block_user_cb(call: CallbackQuery) -> None:
    tid = int(call.data.split(":")[2])
    async with get_session() as session:
        await block_user(session, tid, blocked=True)
    await call.answer("🚫 Bloklandi", show_alert=True)


@router.callback_query(F.data.startswith("us:unblock:"))
async def unblock_user_cb(call: CallbackQuery) -> None:
    tid = int(call.data.split(":")[2])
    async with get_session() as session:
        await block_user(session, tid, blocked=False)
    await call.answer("✅ Blokdan chiqarildi", show_alert=True)


# ─── ADMINLARNI BOSHQARISH (faqat superadmin) ─────────────────────────

async def _show_admins(target) -> None:
    """target: Message yoki CallbackQuery.message — adminlar ro'yxatini ko'rsatadi."""
    async with get_session() as session:
        users = await get_all_users(session)
    admins = [
        u for u in users
        if u.telegram_id in settings.admin_ids or u.role == UserRole.ADMIN
    ]
    await target.answer(
        f"🛡 <b>Adminlar</b> ({len(admins)} ta)\n\n"
        f"👑 — superadmin (himoyalangan)\n"
        f"⬇️ — adminlikdan olib tashlash",
        reply_markup=admins_manage_kb(admins, settings.superadmin_id),
    )


@router.callback_query(F.data == "us:admins")
async def admins_list(call: CallbackQuery) -> None:
    if not is_superadmin(call.from_user.id):
        await call.answer("🚫 Faqat superadmin uchun", show_alert=True)
        return
    await _show_admins(call.message)
    await call.answer()


@router.callback_query(F.data == "us:addadmin")
async def add_admin_start(call: CallbackQuery, state: FSMContext) -> None:
    if not is_superadmin(call.from_user.id):
        await call.answer("🚫 Faqat superadmin uchun", show_alert=True)
        return
    await state.set_state(AddAdmin.identifier)
    await call.message.answer(
        "➕ <b>Admin qo'shish</b>\n\n"
        "Foydalanuvchining <b>@username</b> yoki <b>Telegram ID</b> sini yuboring.\n"
        "<i>(Foydalanuvchi avval botni /start qilgan bo'lishi kerak.)</i>",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AddAdmin.identifier, F.text)
async def add_admin_apply(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return
    if not is_superadmin(message.from_user.id):
        await state.clear()
        return

    raw = message.text.strip()
    await state.clear()

    async with get_session() as session:
        if raw.lstrip("@").isdigit():
            user = await get_user_by_tg_id(session, int(raw.lstrip("@")))
        else:
            user = await get_user_by_username(session, raw)

        if not user:
            await message.answer(
                "❌ Foydalanuvchi topilmadi.\n"
                "U avval botni <b>/start</b> qilishi kerak, keyin qayta urinib ko'ring.",
                reply_markup=admin_main_kb(),
            )
            return

        await set_admin(session, user.telegram_id, True)

    await message.answer(
        f"✅ <b>{user.full_name}</b> endi admin!\n🆔 <code>{user.telegram_id}</code>",
        reply_markup=admin_main_kb(),
    )


@router.callback_query(F.data.startswith("us:rmadmin:"))
async def remove_admin(call: CallbackQuery) -> None:
    if not is_superadmin(call.from_user.id):
        await call.answer("🚫 Faqat superadmin uchun", show_alert=True)
        return
    tid = int(call.data.split(":")[2])

    if is_superadmin(tid):
        await call.answer("👑 Superadminni o'zgartirib bo'lmaydi", show_alert=True)
        return
    if tid in settings.admin_ids:
        await call.answer(
            "⚙️ Bu admin .env (ADMIN_IDS) orqali belgilangan. "
            "Olib tashlash uchun Render env'dan o'chiring.",
            show_alert=True,
        )
        return

    async with get_session() as session:
        await set_admin(session, tid, False)
    await call.answer("✅ Adminlikdan olib tashlandi", show_alert=True)
    await _show_admins(call.message)


# ─── BROADCAST ────────────────────────────────────────────────────────

@router.callback_query(F.data == "us:broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Broadcast.message)
    await call.message.answer(
        "📢 <b>Ommaviy xabar</b>\n\n"
        "Yuboriladigan xabarni yozing\n"
        "<i>(HTML formatlash mumkin)</i>:",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(Broadcast.message, F.text)
async def broadcast_preview(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    await state.update_data(broadcast_text=message.text)

    async with get_session() as session:
        users = await get_all_users(session, only_customers=True)
    active_users = [u for u in users if not u.is_blocked]

    await message.answer(
        f"📢 <b>Yuborish tasdiqi</b>\n\n"
        f"👥 Qabul qiluvchilar: <b>{len(active_users)} ta</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Xabar:</b>\n\n{message.text}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Yuborish uchun <b>HA</b> deb yozing yoki bekor qilish uchun ❌:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(Broadcast.confirm)


@router.message(Broadcast.confirm, F.text)
async def broadcast_run(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text.upper().strip() not in ("HA", "ХА", "ДА", "DA", "YES"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    data = await state.get_data()
    text = data.get("broadcast_text", "")
    await state.clear()

    async with get_session() as session:
        users = await get_all_users(session, only_customers=True)
    active_users = [u for u in users if not u.is_blocked]

    sent = 0
    failed = 0
    progress = await message.answer(f"📤 Yuborilmoqda... 0/{len(active_users)}")

    for i, u in enumerate(active_users, 1):
        try:
            await bot.send_message(u.telegram_id, text)
            sent += 1
        except Exception as e:
            failed += 1
            logging.warning(f"Broadcast {u.telegram_id}: {e}")

        if i % 10 == 0:
            try:
                await progress.edit_text(f"📤 Yuborilmoqda... {i}/{len(active_users)}")
            except Exception:
                pass
        await asyncio.sleep(0.05)  # rate limit

    await message.answer(
        f"✅ <b>Tugadi!</b>\n\n"
        f"📤 Yuborildi: {sent}\n"
        f"❌ Yuborilmadi: {failed}",
        reply_markup=admin_main_kb(),
    )
