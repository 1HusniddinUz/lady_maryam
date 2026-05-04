"""
Admin: Buyurtmalar boshqaruvi
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery

from database.engine import get_session
from database.models import OrderStatus
from services.order_service import (
    get_orders_by_status, get_order, update_order_status, confirm_order,
    count_new_orders
)
from keyboards.admin_kb import (
    orders_filter_kb, orders_list_kb, order_actions_kb, admin_main_kb
)
from handlers.filters import IsAdmin
from utils.formatters import (
    fmt_money, fmt_datetime, status_emoji
)


router = Router(name="admin_orders")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


_FILTER_MAP = {
    "new": OrderStatus.NEW,
    "confirmed": OrderStatus.CONFIRMED,
    "delivering": OrderStatus.DELIVERING,
    "completed": OrderStatus.COMPLETED,
    "cancelled": OrderStatus.CANCELLED,
    "all": None,
}

_STATUS_FROM_CB = {
    "new": OrderStatus.NEW,
    "confirmed": OrderStatus.CONFIRMED,
    "delivering": OrderStatus.DELIVERING,
    "completed": OrderStatus.COMPLETED,
    "cancelled": OrderStatus.CANCELLED,
}


@router.message(F.text == "🛒 Buyurtmalar")
async def orders_main(message: Message) -> None:
    async with get_session() as session:
        new_count = await count_new_orders(session)

    text = (
        f"🛒 <b>Buyurtmalar boshqaruvi</b>\n\n"
        f"🆕 Yangi buyurtmalar: <b>{new_count}</b>\n\n"
        f"Filterni tanlang 👇"
    )
    await message.answer(text, reply_markup=orders_filter_kb())


@router.callback_query(F.data == "ord:menu")
async def orders_menu_cb(call: CallbackQuery) -> None:
    async with get_session() as session:
        new_count = await count_new_orders(session)
    text = (
        f"🛒 <b>Buyurtmalar boshqaruvi</b>\n\n"
        f"🆕 Yangi: <b>{new_count}</b>\n\n"
        f"Filterni tanlang 👇"
    )
    try:
        await call.message.edit_text(text, reply_markup=orders_filter_kb())
    except Exception:
        await call.message.answer(text, reply_markup=orders_filter_kb())
    await call.answer()


@router.callback_query(F.data.startswith("ord:f:"))
async def orders_filter(call: CallbackQuery) -> None:
    f = call.data.split(":")[2]
    status = _FILTER_MAP.get(f)

    async with get_session() as session:
        orders = await get_orders_by_status(session, status)

    if not orders:
        await call.answer("📦 Bu filterda buyurtma yo'q", show_alert=True)
        return

    label = {
        "new": "🆕 Yangi",
        "confirmed": "✅ Tasdiqlangan",
        "delivering": "🚚 Yetkazilmoqda",
        "completed": "✔️ Yakunlangan",
        "cancelled": "❌ Bekor qilingan",
        "all": "📋 Barcha",
    }.get(f, "Buyurtmalar")

    text = f"<b>{label}</b> ({len(orders)} ta):\n\nTafsilotlar uchun tanlang 👇"
    try:
        await call.message.edit_text(text, reply_markup=orders_list_kb(orders, current_filter=f))
    except Exception:
        await call.message.answer(text, reply_markup=orders_list_kb(orders, current_filter=f))
    await call.answer()


@router.callback_query(F.data.startswith("ord:view:"))
async def order_view(call: CallbackQuery) -> None:
    oid = int(call.data.split(":")[2])
    async with get_session() as session:
        order = await get_order(session, oid)

    if not order:
        await call.answer("❌ Topilmadi", show_alert=True)
        return

    user = order.user
    text = (
        f"{status_emoji(order.status.value)} <b>Buyurtma #{order.id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Status: <b>{order.status.value.capitalize()}</b>\n"
        f"📅 Sana: {fmt_datetime(order.created_at)}\n\n"
        f"👤 Mijoz: <b>{user.full_name}</b>\n"
        f"📱 Tel: {order.phone or '—'}\n"
        f"📍 Manzil: {order.delivery_address or '—'}\n"
        f"💳 To'lov: {order.payment_method.value.capitalize()}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Mahsulotlar:</b>\n"
    )
    for item in order.items:
        text += f"  • {item.product_name} × {item.quantity:g}\n"
        text += f"    {fmt_money(item.sale_price)} = {fmt_money(item.total)}\n"

    text += (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Jami: <b>{fmt_money(order.total_amount)}</b>\n"
        f"🏷 Tan narxi: {fmt_money(order.total_cost)}\n"
        f"🧾 Soliq: {fmt_money(order.tax_amount)}\n"
        f"📈 Sof foyda: <b>{fmt_money(order.total_profit)}</b>"
    )

    try:
        await call.message.edit_text(text, reply_markup=order_actions_kb(order))
    except Exception:
        await call.message.answer(text, reply_markup=order_actions_kb(order))
    await call.answer()


@router.callback_query(F.data.startswith("ord:s:"))
async def order_status_change(call: CallbackQuery, bot: Bot) -> None:
    parts = call.data.split(":")
    oid = int(parts[2])
    new_status_str = parts[3]
    new_status = _STATUS_FROM_CB.get(new_status_str)

    if not new_status:
        await call.answer("❌ Noto'g'ri status")
        return

    async with get_session() as session:
        # Tasdiqlanish — alohida (chunki ombordan ayrish kerak)
        if new_status == OrderStatus.CONFIRMED:
            order = await confirm_order(session, oid)
        else:
            order = await update_order_status(session, oid, new_status)

        if not order:
            await call.answer("❌ Bajarib bo'lmadi", show_alert=True)
            return

        # Mijozga xabar
        user = order.user
        try:
            customer_text = {
                OrderStatus.CONFIRMED: f"✅ Buyurtma #{order.id} tasdiqlandi! Tez orada tayyorlanadi.",
                OrderStatus.DELIVERING: f"🚚 Buyurtma #{order.id} yetkazilmoqda!",
                OrderStatus.COMPLETED: f"✔️ Buyurtma #{order.id} yakunlandi. Tashrifingiz uchun rahmat!",
                OrderStatus.CANCELLED: f"❌ Buyurtma #{order.id} bekor qilindi.",
            }.get(new_status, f"📦 Buyurtma #{order.id} statusi: {new_status.value}")

            await bot.send_message(user.telegram_id, customer_text)
        except Exception as e:
            logging.warning(f"Mijozga xabar yuborilmadi: {e}")

    await call.answer(f"✅ Status yangilandi: {new_status.value}", show_alert=True)

    # Sahifani yangilash
    async with get_session() as session:
        order = await get_order(session, oid)
    user = order.user
    text = (
        f"{status_emoji(order.status.value)} <b>Buyurtma #{order.id}</b>\n"
        f"📊 Status: <b>{order.status.value.capitalize()}</b>\n"
        f"📅 {fmt_datetime(order.created_at)}\n\n"
        f"👤 {user.full_name} • {order.phone or '—'}\n"
        f"💰 {fmt_money(order.total_amount)} • 📈 {fmt_money(order.total_profit)}"
    )
    try:
        await call.message.edit_text(text, reply_markup=order_actions_kb(order))
    except Exception:
        pass
