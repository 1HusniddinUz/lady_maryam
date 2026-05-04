"""
Mijoz uchun buyurtma berish (checkout)
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from config.settings import settings
from database.engine import get_session
from database.models import PaymentMethod, OrderStatus
from services.cart_service import cart_total
from services.order_service import create_order_from_cart, get_user_orders
from services.user_service import get_user_by_tg_id
from keyboards.customer_kb import (
    payment_method_kb, confirm_order_kb, customer_main_kb, share_location_kb
)
from utils.formatters import fmt_money, fmt_datetime, status_emoji
from handlers.states import Checkout


router = Router(name="customer_orders")


@router.callback_query(F.data == "checkout")
async def checkout_start(call: CallbackQuery, state: FSMContext) -> None:
    async with get_session() as session:
        user = await get_user_by_tg_id(session, call.from_user.id)
        if not user:
            await call.answer("❌ Xato")
            return
        cart = await cart_total(session, user.id)

    if not cart["items"]:
        await call.answer("🛒 Savatingiz bo'sh", show_alert=True)
        return

    try:
        await call.message.delete()
    except Exception:
        pass

    await state.set_state(Checkout.address)
    await state.update_data(cart_total=cart["total"])

    await call.message.answer(
        "📍 <b>Yetkazib berish manzili</b>\n\n"
        "Lokatsiya yuboring yoki manzilni yozib bering:",
        reply_markup=share_location_kb(),
    )
    await call.answer()


@router.message(Checkout.address, F.text == "❌ Bekor qilish")
async def checkout_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=customer_main_kb())


@router.message(Checkout.address, F.location)
async def checkout_address_location(message: Message, state: FSMContext) -> None:
    loc = message.location
    address = f"📍 Lokatsiya: {loc.latitude}, {loc.longitude}"
    await state.update_data(delivery_address=address)
    await _ask_phone(message, state)


@router.message(Checkout.address, F.text == "✍️ Manzilni yozib yuborish")
async def checkout_address_typed(message: Message, state: FSMContext) -> None:
    await message.answer(
        "✍️ Manzilingizni to'liq yozing:\n\n"
        "Misol: <i>Toshkent sh., Yunusobod tumani, Amir Temur 5-uy, 12-xonadon</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Checkout.address, F.text)
async def checkout_address_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) < 10:
        await message.answer("❌ Manzil juda qisqa. Iltimos, to'liq yozing:")
        return
    await state.update_data(delivery_address=text)
    await _ask_phone(message, state)


async def _ask_phone(message: Message, state: FSMContext) -> None:
    """Telefon raqamni so'rash"""
    async with get_session() as session:
        user = await get_user_by_tg_id(session, message.from_user.id)

    saved_phone = user.phone if user else None
    if saved_phone:
        # Mavjud telefonni tasdiqlash
        await state.update_data(phone=saved_phone)
        await message.answer(
            f"📱 Bog'lanish uchun telefon: <code>{saved_phone}</code>\n\n"
            f"Boshqa raqam yozsangiz - yozing, yoki <b>OK</b> deb javob bering:",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.set_state(Checkout.phone)
    else:
        await message.answer(
            "📱 Telefon raqamingizni yozing:\n\n"
            "Misol: <code>+998 90 123 45 67</code>",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.set_state(Checkout.phone)


@router.message(Checkout.phone, F.text)
async def checkout_phone(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    data = await state.get_data()

    if text.upper() in ("OK", "ХА", "HA", "ДА", "DA"):
        phone = data.get("phone", "")
    else:
        if len(text) < 7:
            await message.answer("❌ Telefon juda qisqa. Qayta yozing:")
            return
        phone = text
        await state.update_data(phone=phone)

    await message.answer(
        "💳 <b>To'lov turini tanlang:</b>",
        reply_markup=payment_method_kb(),
    )
    await state.set_state(Checkout.payment)


@router.callback_query(Checkout.payment, F.data.startswith("pay:"))
async def checkout_payment(call: CallbackQuery, state: FSMContext) -> None:
    method_str = call.data.split(":")[1]
    method_map = {
        "cash": PaymentMethod.CASH,
        "card": PaymentMethod.CARD,
        "online": PaymentMethod.ONLINE,
    }
    method_names = {
        PaymentMethod.CASH: "💵 Naqd pul",
        PaymentMethod.CARD: "💳 Plastik karta",
        PaymentMethod.ONLINE: "📱 Click / Payme",
    }
    method = method_map.get(method_str, PaymentMethod.CASH)
    await state.update_data(payment_method=method.value, payment_name=method_names[method])

    data = await state.get_data()

    # Savatni ko'rsatish
    async with get_session() as session:
        user = await get_user_by_tg_id(session, call.from_user.id)
        cart = await cart_total(session, user.id)

    text = "📋 <b>Buyurtmani tasdiqlang:</b>\n\n"
    for i, item in enumerate(cart["items"], 1):
        text += (
            f"{i}. {item.product.name}\n"
            f"   {item.quantity:g} × {fmt_money(item.product.sale_price)}\n"
        )
    text += "\n━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 <b>Jami: {fmt_money(cart['total'])}</b>\n"
    text += f"📍 Manzil: {data['delivery_address']}\n"
    text += f"📱 Tel: {data['phone']}\n"
    text += f"💳 To'lov: {data['payment_name']}"

    await call.message.edit_text(text, reply_markup=confirm_order_kb())
    await state.set_state(Checkout.confirm)
    await call.answer()


@router.callback_query(Checkout.confirm, F.data == "order_confirm")
async def checkout_confirm(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()

    async with get_session() as session:
        user = await get_user_by_tg_id(session, call.from_user.id)
        if not user:
            await call.answer("❌ Xato", show_alert=True)
            return

        method = PaymentMethod(data.get("payment_method", "naqd"))
        order = await create_order_from_cart(
            session,
            user_id=user.id,
            delivery_address=data["delivery_address"],
            phone=data["phone"],
            payment_method=method,
        )

    await state.clear()

    if not order:
        await call.message.edit_text("❌ Buyurtma yaratilmadi. Savatingizni tekshiring.")
        await call.answer()
        return

    # Mijozga
    success_text = (
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"📋 Buyurtma raqami: <b>#{order.id}</b>\n"
        f"💰 Jami: <b>{fmt_money(order.total_amount)}</b>\n"
        f"📦 Status: 🆕 Yangi\n\n"
        f"📞 Tez orada operator siz bilan bog'lanadi!"
    )
    await call.message.edit_text(success_text)
    await call.message.answer("Asosiy menyu 👇", reply_markup=customer_main_kb())
    await call.answer("✅ Buyurtma qabul qilindi!", show_alert=True)

    # Adminlarga xabar
    admin_text = (
        f"🔔 <b>YANGI BUYURTMA #{order.id}</b>\n\n"
        f"👤 Mijoz: {user.full_name}\n"
        f"📱 Tel: {order.phone}\n"
        f"📍 Manzil: {order.delivery_address}\n"
        f"💳 To'lov: {data['payment_name']}\n\n"
        f"📦 <b>Mahsulotlar:</b>\n"
    )
    for item in order.items:
        admin_text += f"  • {item.product_name} × {item.quantity:g} = {fmt_money(item.total)}\n"
    admin_text += f"\n💰 <b>Jami: {fmt_money(order.total_amount)}</b>\n"
    admin_text += f"📈 Sof foyda: {fmt_money(order.total_profit)}"

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception as e:
            logging.warning(f"Adminga xabar yuborilmadi {admin_id}: {e}")


@router.callback_query(F.data == "checkout_cancel")
async def checkout_cancel_cb(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer("❌ Bekor qilindi.", reply_markup=customer_main_kb())
    await call.answer()


# ─── BUYURTMALARIM ────────────────────────────────────────────────────

@router.message(F.text == "📦 Buyurtmalarim")
async def my_orders(message: Message) -> None:
    async with get_session() as session:
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("❌ Avval /start bosing")
            return
        orders = await get_user_orders(session, user.id, limit=10)

    if not orders:
        await message.answer(
            "📦 Sizda hali buyurtmalar yo'q.",
            reply_markup=customer_main_kb(),
        )
        return

    text = "📦 <b>Sizning buyurtmalaringiz:</b>\n\n"
    for o in orders:
        text += (
            f"{status_emoji(o.status.value)} <b>Buyurtma #{o.id}</b>\n"
            f"   📅 {fmt_datetime(o.created_at)}\n"
            f"   💰 {fmt_money(o.total_amount)}\n"
            f"   📊 Status: <b>{o.status.value.capitalize()}</b>\n\n"
        )

    await message.answer(text, reply_markup=customer_main_kb())
