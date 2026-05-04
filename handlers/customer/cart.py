"""
Mijoz savati handlerlari
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.engine import get_session
from services.cart_service import (
    cart_total, update_cart_quantity, remove_from_cart, clear_cart, get_cart
)
from services.user_service import get_user_by_tg_id
from keyboards.customer_kb import cart_kb, customer_main_kb
from utils.formatters import fmt_money


router = Router(name="customer_cart")


def _format_cart_text(cart: dict) -> str:
    if not cart["items"]:
        return "🛒 <b>Savatingiz bo'sh</b>\n\nKatalogga o'ting va xarid qiling!"

    text = "🛒 <b>Sizning savatingiz:</b>\n\n"
    for i, item in enumerate(cart["items"], 1):
        p = item.product
        line_total = item.quantity * p.sale_price
        text += (
            f"{i}. <b>{p.name}</b>\n"
            f"   {item.quantity:g} × {fmt_money(p.sale_price)} = {fmt_money(line_total)}\n\n"
        )
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 <b>Jami: {fmt_money(cart['total'])}</b>"
    return text


@router.message(F.text == "🛒 Savatim")
async def show_cart_msg(message: Message) -> None:
    async with get_session() as session:
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("❌ Avval /start bosing")
            return
        cart = await cart_total(session, user.id)

    if not cart["items"]:
        await message.answer(
            "🛒 <b>Savatingiz bo'sh</b>\n\n"
            "🛍 Katalog bo'limidan mahsulot tanlang!",
            reply_markup=customer_main_kb(),
        )
        return

    await message.answer(
        _format_cart_text(cart),
        reply_markup=cart_kb(cart["items"]),
    )


@router.callback_query(F.data == "open_cart")
async def open_cart_cb(call: CallbackQuery) -> None:
    async with get_session() as session:
        user = await get_user_by_tg_id(session, call.from_user.id)
        if not user:
            await call.answer("❌ Xato")
            return
        cart = await cart_total(session, user.id)

    try:
        await call.message.delete()
    except Exception:
        pass

    if not cart["items"]:
        await call.message.answer(
            "🛒 Savatingiz bo'sh.",
            reply_markup=customer_main_kb(),
        )
        return

    await call.message.answer(
        _format_cart_text(cart),
        reply_markup=cart_kb(cart["items"]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("qty+:"))
async def qty_plus(call: CallbackQuery) -> None:
    product_id = int(call.data.split(":")[1])
    async with get_session() as session:
        user = await get_user_by_tg_id(session, call.from_user.id)
        if not user:
            await call.answer("❌ Xato")
            return

        cart = await get_cart(session, user.id)
        item = next((i for i in cart if i.product_id == product_id), None)
        if not item:
            await call.answer("❌ Topilmadi")
            return

        new_qty = item.quantity + 1
        if new_qty > item.product.stock_quantity:
            await call.answer("❌ Bundan ko'p qoldiq yo'q", show_alert=True)
            return

        await update_cart_quantity(session, user.id, product_id, new_qty)
        cart_data = await cart_total(session, user.id)

    try:
        await call.message.edit_text(
            _format_cart_text(cart_data),
            reply_markup=cart_kb(cart_data["items"]),
        )
    except Exception:
        pass
    await call.answer("➕")


@router.callback_query(F.data.startswith("qty-:"))
async def qty_minus(call: CallbackQuery) -> None:
    product_id = int(call.data.split(":")[1])
    async with get_session() as session:
        user = await get_user_by_tg_id(session, call.from_user.id)
        if not user:
            return

        cart = await get_cart(session, user.id)
        item = next((i for i in cart if i.product_id == product_id), None)
        if not item:
            return

        new_qty = item.quantity - 1
        await update_cart_quantity(session, user.id, product_id, new_qty)
        cart_data = await cart_total(session, user.id)

    if not cart_data["items"]:
        await call.message.edit_text("🛒 Savatingiz bo'sh.")
        await call.answer()
        return

    try:
        await call.message.edit_text(
            _format_cart_text(cart_data),
            reply_markup=cart_kb(cart_data["items"]),
        )
    except Exception:
        pass
    await call.answer("➖")


@router.callback_query(F.data.startswith("qtyx:"))
async def qty_remove(call: CallbackQuery) -> None:
    product_id = int(call.data.split(":")[1])
    async with get_session() as session:
        user = await get_user_by_tg_id(session, call.from_user.id)
        if not user:
            return
        await remove_from_cart(session, user.id, product_id)
        cart_data = await cart_total(session, user.id)

    if not cart_data["items"]:
        await call.message.edit_text("🛒 Savatingiz bo'sh.")
        await call.answer("🗑 O'chirildi")
        return

    try:
        await call.message.edit_text(
            _format_cart_text(cart_data),
            reply_markup=cart_kb(cart_data["items"]),
        )
    except Exception:
        pass
    await call.answer("🗑 O'chirildi")


@router.callback_query(F.data == "clear_cart")
async def clear_cart_cb(call: CallbackQuery) -> None:
    async with get_session() as session:
        user = await get_user_by_tg_id(session, call.from_user.id)
        if not user:
            return
        await clear_cart(session, user.id)
    await call.message.edit_text("🛒 Savat tozalandi.")
    await call.answer("✅ Tozalandi")
