"""
Mijoz uchun klaviaturalar
"""

from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Product, Category
from utils.formatters import fmt_money, stock_emoji, truncate


# ─── Reply (asosiy menyu) ─────────────────────────────────────────────

def customer_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Katalog"), KeyboardButton(text="🛒 Savatim")],
            [KeyboardButton(text="🔍 Qidiruv"), KeyboardButton(text="📦 Buyurtmalarim")],
            [KeyboardButton(text="📞 Bog'lanish"), KeyboardButton(text="ℹ️ Biz haqimizda")],
        ],
        resize_keyboard=True,
    )


def share_phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def share_location_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)],
            [KeyboardButton(text="✍️ Manzilni yozib yuborish")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )


# ─── Inline klaviaturalar ─────────────────────────────────────────────

def categories_kb(categories: list[Category]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in categories:
        kb.button(text=f"📂 {cat.name}", callback_data=f"cat:{cat.id}")
    kb.button(text="📦 Barcha mahsulotlar", callback_data="cat:all")
    kb.adjust(2)
    return kb.as_markup()


def products_list_kb(
    products: list[Product],
    page: int = 0,
    per_page: int = 8,
    category_id: int | str = "all",
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    start = page * per_page
    chunk = products[start: start + per_page]

    for p in chunk:
        emoji = stock_emoji(p.stock_quantity)
        kb.row(InlineKeyboardButton(
            text=f"{emoji} {truncate(p.name, 25)} — {fmt_money(p.sale_price)}",
            callback_data=f"prod:{p.id}",
        ))

    # Sahifalashtirish
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️", callback_data=f"page:{category_id}:{page - 1}"
        ))
    total_pages = (len(products) + per_page - 1) // per_page
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}", callback_data="noop"
        ))
    if start + per_page < len(products):
        nav_row.append(InlineKeyboardButton(
            text="▶️", callback_data=f"page:{category_id}:{page + 1}"
        ))
    if nav_row:
        kb.row(*nav_row)

    kb.row(InlineKeyboardButton(text="🔙 Kategoriyalar", callback_data="back_to_cats"))
    return kb.as_markup()


def product_detail_kb(product: Product, in_cart: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if product.is_in_stock:
        kb.button(text="➕ Savatga qo'shish", callback_data=f"add:{product.id}")
    if in_cart:
        kb.button(text="🛒 Savatga o'tish", callback_data="open_cart")
    kb.button(text="🔙 Orqaga", callback_data="back_to_products")
    kb.adjust(1)
    return kb.as_markup()


def cart_kb(items: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in items:
        p = item.product
        kb.row(
            InlineKeyboardButton(text="➖", callback_data=f"qty-:{p.id}"),
            InlineKeyboardButton(
                text=f"{truncate(p.name, 18)} ({item.quantity:g})",
                callback_data=f"prod:{p.id}",
            ),
            InlineKeyboardButton(text="➕", callback_data=f"qty+:{p.id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"qtyx:{p.id}"),
        )
    if items:
        kb.row(InlineKeyboardButton(text="✅ Buyurtma berish", callback_data="checkout"))
        kb.row(InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart"))
    kb.row(InlineKeyboardButton(text="🛍 Xaridni davom ettirish", callback_data="back_to_cats"))
    return kb.as_markup()


def payment_method_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💵 Naqd pul", callback_data="pay:cash")
    kb.button(text="💳 Plastik karta", callback_data="pay:card")
    kb.button(text="📱 Click / Payme", callback_data="pay:online")
    kb.button(text="❌ Bekor qilish", callback_data="checkout_cancel")
    kb.adjust(1)
    return kb.as_markup()


def confirm_order_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Buyurtmani tasdiqlash", callback_data="order_confirm")
    kb.button(text="❌ Bekor qilish", callback_data="checkout_cancel")
    kb.adjust(1)
    return kb.as_markup()
