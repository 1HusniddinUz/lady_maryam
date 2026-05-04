"""
Admin: Sozlamalar
"""

import sys
import platform
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from database.engine import get_session
from services.settings_service import get_tax_rate, get_tax_name, set_tax
from services.product_service import warehouse_value
from services.user_service import count_users
from services.order_service import count_new_orders
from keyboards.admin_kb import settings_menu_kb, tax_settings_kb, admin_main_kb
from handlers.filters import IsAdmin
from utils.formatters import fmt_money, fmt_pct
from config.settings import settings as cfg


router = Router(name="admin_settings")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "⚙️ Sozlamalar")
async def settings_main(message: Message) -> None:
    async with get_session() as session:
        tax_name = await get_tax_name(session)
        tax_rate = await get_tax_rate(session)

    text = (
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"🧾 Joriy soliq: <b>{tax_name}</b> ({fmt_pct(tax_rate)})\n"
        f"🏪 Do'kon: {cfg.shop_name}\n"
        f"📞 Tel: {cfg.shop_phone}"
    )
    await message.answer(text, reply_markup=settings_menu_kb())


@router.callback_query(F.data == "st:menu")
async def settings_menu_cb(call: CallbackQuery) -> None:
    async with get_session() as session:
        tax_name = await get_tax_name(session)
        tax_rate = await get_tax_rate(session)
    text = (
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"🧾 Soliq: <b>{tax_name}</b> ({fmt_pct(tax_rate)})"
    )
    try:
        await call.message.edit_text(text, reply_markup=settings_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=settings_menu_kb())
    await call.answer()


@router.callback_query(F.data == "st:tax")
async def tax_settings(call: CallbackQuery) -> None:
    async with get_session() as session:
        tax_name = await get_tax_name(session)
        tax_rate = await get_tax_rate(session)

    text = (
        f"🧾 <b>Soliq sozlamalari</b>\n\n"
        f"Joriy: <b>{tax_name}</b> ({fmt_pct(tax_rate)})\n\n"
        f"📚 <b>O'zbekiston soliq turlari:</b>\n\n"
        f"• <b>Aylanma solig'i</b> — 4%\n"
        f"  Yillik aylanmasi 1 mlrd so'mgacha\n\n"
        f"• <b>QQS</b> — 12%\n"
        f"  Yillik aylanmasi 1 mlrd so'mdan ortiq\n\n"
        f"• <b>Patent</b> — 0%\n"
        f"  Patent asosida ishlovchilar\n\n"
        f"Yangisini tanlang 👇"
    )
    try:
        await call.message.edit_text(text, reply_markup=tax_settings_kb())
    except Exception:
        await call.message.answer(text, reply_markup=tax_settings_kb())
    await call.answer()


@router.callback_query(F.data.startswith("st:tax:"))
async def tax_change(call: CallbackQuery) -> None:
    tax_type = call.data.split(":")[2]
    tax_map = {
        "aylanma": ("Aylanma solig'i", 0.04),
        "qqs": ("QQS", 0.12),
        "patent": ("Patent", 0.0),
    }
    if tax_type not in tax_map:
        return

    name, rate = tax_map[tax_type]
    async with get_session() as session:
        await set_tax(session, name, rate)

    await call.answer(f"✅ {name} ({fmt_pct(rate)}) o'rnatildi", show_alert=True)
    text = (
        f"⚙️ <b>Sozlamalar yangilandi</b>\n\n"
        f"🧾 Yangi soliq: <b>{name}</b> ({fmt_pct(rate)})\n\n"
        f"<i>Yangi sotuvlar shu stavkada hisoblanadi.</i>"
    )
    try:
        await call.message.edit_text(text, reply_markup=settings_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=settings_menu_kb())


@router.callback_query(F.data == "st:info")
async def system_info(call: CallbackQuery) -> None:
    async with get_session() as session:
        users = await count_users(session)
        wh = await warehouse_value(session)
        new_orders = await count_new_orders(session)

    text = (
        f"ℹ️ <b>Tizim ma'lumoti</b>\n\n"
        f"🏪 Do'kon: <b>{cfg.shop_name}</b>\n"
        f"📞 Tel: {cfg.shop_phone}\n"
        f"📍 Manzil: {cfg.shop_address}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>📊 Statistika:</b>\n"
        f"👥 Foydalanuvchilar: {users['total']}\n"
        f"🛡 Adminlar: {users['admins']}\n"
        f"📦 Mahsulotlar: {wh['products_count']}\n"
        f"💎 Ombor qiymati: {fmt_money(wh['sale_value'])}\n"
        f"🆕 Yangi buyurtmalar: {new_orders}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>⚙️ Texnik:</b>\n"
        f"🐍 Python: {sys.version.split()[0]}\n"
        f"💻 Platforma: {platform.system()}\n"
        f"🤖 Versiya: 3.0 ERP"
    )
    await call.message.answer(text)
    await call.answer()
