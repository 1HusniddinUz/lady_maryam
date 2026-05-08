"""
Admin uchun klaviaturalar
"""

from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Product, Order, OrderStatus
from utils.formatters import fmt_money, stock_emoji, truncate, status_emoji


def admin_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Mahsulotlar"), KeyboardButton(text="🏪 Ombor")],
            [KeyboardButton(text="🛒 Buyurtmalar"), KeyboardButton(text="💰 Tezkor sotuv")],
            [KeyboardButton(text="📊 Hisobotlar"), KeyboardButton(text="💸 Xarajatlar")],
            [KeyboardButton(text="👥 Foydalanuvchilar"), KeyboardButton(text="⚙️ Sozlamalar")],
            [KeyboardButton(text="🛍 Mijoz rejimi")],
        ],
        resize_keyboard=True,
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def skip_cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ O'tkazib yuborish")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )


# ─── MAHSULOTLAR ──────────────────────────────────────────────────────

def products_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Yangi mahsulot", callback_data="ap:new")
    kb.button(text="📋 Barcha mahsulotlar", callback_data="ap:list:0")
    kb.button(text="📥 Excel'ga eksport", callback_data="ap:export")
    kb.button(text="📂 Kategoriyalar", callback_data="ap:cats")
    kb.adjust(1)
    return kb.as_markup()


def admin_products_list_kb(
    products: list[Product],
    page: int = 0,
    per_page: int = 8,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    start = page * per_page
    chunk = products[start: start + per_page]
    for p in chunk:
        emoji = stock_emoji(p.stock_quantity)
        kb.row(InlineKeyboardButton(
            text=f"{emoji} {truncate(p.name, 22)} — {fmt_money(p.sale_price)} ({p.stock_quantity:g})",
            callback_data=f"ap:view:{p.id}",
        ))

    nav = []
    total_pages = (len(products) + per_page - 1) // per_page
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"ap:list:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if start + per_page < len(products):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"ap:list:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="ap:menu"))
    return kb.as_markup()


def product_view_kb(product_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Nomi", callback_data=f"ap:edit:name:{product_id}")
    kb.button(text="🏷 Tan narxi", callback_data=f"ap:edit:cost:{product_id}")
    kb.button(text="💰 Sotuv narxi", callback_data=f"ap:edit:sell:{product_id}")
    kb.button(text="📷 Rasm", callback_data=f"ap:edit:photo:{product_id}")
    kb.button(text="📝 Tavsif", callback_data=f"ap:edit:desc:{product_id}")
    kb.button(text="📂 Kategoriya", callback_data=f"ap:edit:cat:{product_id}")
    kb.button(text="📈 Harakatlar tarixi", callback_data=f"ap:hist:{product_id}")
    kb.button(text="🗑 O'chirish", callback_data=f"ap:del:{product_id}")
    kb.button(text="🔙 Orqaga", callback_data="ap:list:0")
    kb.adjust(2, 2, 2, 1, 1, 1)
    return kb.as_markup()


def categories_pick_kb(categories: list, prefix: str = "pickcat") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in categories:
        kb.button(text=f"📂 {c.name}", callback_data=f"{prefix}:{c.id}")
    kb.button(text="⏭ Kategoriyasiz", callback_data=f"{prefix}:0")
    kb.adjust(2)
    return kb.as_markup()


def categories_admin_kb(categories: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in categories:
        kb.row(
            InlineKeyboardButton(text=f"📂 {c.name}", callback_data="noop"),
            InlineKeyboardButton(text="🗑", callback_data=f"ap:catdel:{c.id}"),
        )
    kb.row(InlineKeyboardButton(text="➕ Yangi kategoriya", callback_data="ap:catnew"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="ap:menu"))
    return kb.as_markup()


# ─── OMBOR ────────────────────────────────────────────────────────────

def warehouse_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 Kirim qilish", callback_data="wh:in")
    kb.button(text="📤 Chiqim qilish", callback_data="wh:out")
    kb.button(text="⚠️ Kam qoldiq", callback_data="wh:low")
    kb.button(text="❌ Tugaganlar", callback_data="wh:zero")
    kb.button(text="💰 Ombor qiymati", callback_data="wh:value")
    kb.button(text="🔙 Orqaga", callback_data="ap:menu")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def warehouse_pick_product_kb(products: list, action: str) -> InlineKeyboardMarkup:
    """action: 'in' yoki 'out'"""
    kb = InlineKeyboardBuilder()
    for p in products:
        kb.row(InlineKeyboardButton(
            text=f"{stock_emoji(p.stock_quantity)} {truncate(p.name, 25)} — {p.stock_quantity:g} {p.unit}",
            callback_data=f"wh:{action}p:{p.id}",
        ))
    kb.row(InlineKeyboardButton(text="🔙 Bekor", callback_data="wh:menu"))
    return kb.as_markup()


# ─── BUYURTMALAR ──────────────────────────────────────────────────────

def orders_filter_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🆕 Yangi", callback_data="ord:f:new")
    kb.button(text="✅ Tasdiqlangan", callback_data="ord:f:confirmed")
    kb.button(text="🚚 Yetkazilmoqda", callback_data="ord:f:delivering")
    kb.button(text="✔️ Yakunlangan", callback_data="ord:f:completed")
    kb.button(text="❌ Bekor qilingan", callback_data="ord:f:cancelled")
    kb.button(text="📋 Hammasi", callback_data="ord:f:all")
    kb.adjust(2)
    return kb.as_markup()


def orders_list_kb(orders: list[Order], current_filter: str = "all") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for o in orders[:20]:
        kb.row(InlineKeyboardButton(
            text=f"{status_emoji(o.status.value)} #{o.id} — {fmt_money(o.total_amount)}",
            callback_data=f"ord:view:{o.id}",
        ))
    kb.row(InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"ord:f:{current_filter}"))
    kb.row(InlineKeyboardButton(text="🔙 Filter", callback_data="ord:menu"))
    return kb.as_markup()


def order_actions_kb(order: Order) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    s = order.status

    if s == OrderStatus.NEW:
        kb.button(text="✅ Tasdiqlash", callback_data=f"ord:s:{order.id}:confirmed")
        kb.button(text="❌ Bekor qilish", callback_data=f"ord:s:{order.id}:cancelled")
    elif s == OrderStatus.CONFIRMED:
        kb.button(text="🚚 Yetkazilmoqda", callback_data=f"ord:s:{order.id}:delivering")
        kb.button(text="✔️ Yakunlash", callback_data=f"ord:s:{order.id}:completed")
        kb.button(text="❌ Bekor qilish", callback_data=f"ord:s:{order.id}:cancelled")
    elif s == OrderStatus.DELIVERING:
        kb.button(text="✔️ Yakunlash", callback_data=f"ord:s:{order.id}:completed")
        kb.button(text="❌ Bekor qilish", callback_data=f"ord:s:{order.id}:cancelled")

    kb.button(text="🔙 Orqaga", callback_data="ord:menu")
    kb.adjust(1)
    return kb.as_markup()


# ─── HISOBOTLAR ───────────────────────────────────────────────────────

def reports_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Bugun", callback_data="rp:p:today")
    kb.button(text="📆 Kecha", callback_data="rp:p:yesterday")
    kb.button(text="🗓 Hafta", callback_data="rp:p:week")
    kb.button(text="📋 Bu oy", callback_data="rp:p:month")
    kb.button(text="📊 Butun davr", callback_data="rp:p:all")
    kb.button(text="🏆 TOP mahsulotlar", callback_data="rp:top:products")
    kb.button(text="👥 TOP mijozlar", callback_data="rp:top:customers")
    kb.button(text="🏪 Ombor qiymati", callback_data="wh:value")
    kb.button(text="🔙 Orqaga", callback_data="ap:menu")
    kb.adjust(2, 2, 1, 2, 1, 1)
    return kb.as_markup()


def report_period_actions_kb(period: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Excel hisobot", callback_data=f"rp:excel:{period}")
    kb.button(text="📈 Grafik", callback_data=f"rp:chart:{period}")
    kb.button(text="🔙 Hisobotlar", callback_data="rp:menu")
    kb.adjust(1)
    return kb.as_markup()


# ─── XARAJATLAR ───────────────────────────────────────────────────────

def expenses_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Yangi xarajat", callback_data="ex:new")
    kb.button(text="📋 Tarix", callback_data="ex:list")
    kb.button(text="🔙 Orqaga", callback_data="ap:menu")
    kb.adjust(1)
    return kb.as_markup()


def expense_category_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    cats = [
        ("🏪 Ijara", "ijara"),
        ("👷 Ish haqi", "ish_haqi"),
        ("🚚 Transport", "transport"),
        ("📢 Reklama", "reklama"),
        ("💡 Kommunal", "kommunal"),
        ("📦 Boshqa", "boshqa"),
    ]
    for label, key in cats:
        kb.button(text=label, callback_data=f"ex:cat:{key}")
    kb.adjust(2)
    return kb.as_markup()


# ─── FOYDALANUVCHILAR ────────────────────────────────────────────────

def users_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Mijozlar ro'yxati", callback_data="us:list")
    kb.button(text="📢 Ommaviy xabar", callback_data="us:broadcast")
    kb.button(text="🔙 Orqaga", callback_data="ap:menu")
    kb.adjust(1)
    return kb.as_markup()


def user_actions_kb(user_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if is_blocked:
        kb.button(text="✅ Blokdan chiqarish", callback_data=f"us:unblock:{user_id}")
    else:
        kb.button(text="🚫 Bloklash", callback_data=f"us:block:{user_id}")
    kb.button(text="🔙 Orqaga", callback_data="us:list")
    kb.adjust(1)
    return kb.as_markup()


# ─── SOZLAMALAR ───────────────────────────────────────────────────────

def settings_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🧾 Soliq turi", callback_data="st:tax")
    kb.button(text="ℹ️ Tizim ma'lumoti", callback_data="st:info")
    kb.button(text="🔙 Orqaga", callback_data="ap:menu")
    kb.adjust(1)
    return kb.as_markup()


def tax_settings_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Aylanma solig'i — 4%", callback_data="st:tax:aylanma")
    kb.button(text="💼 QQS — 12%", callback_data="st:tax:qqs")
    kb.button(text="📜 Patent — 0%", callback_data="st:tax:patent")
    kb.button(text="🔙 Orqaga", callback_data="st:menu")
    kb.adjust(1)
    return kb.as_markup()


# ─── TEZKOR SOTUV (admin) ─────────────────────────────────────────────

QS_PER_PAGE = 8  # Tezkor sotuvda har sahifada nechta mahsulot


def quick_sale_pick_product_kb(
    products: list[Product],
    page: int = 0,
    search: str = "",
) -> InlineKeyboardMarkup:
    """
    Tezkor sotuv uchun mahsulotlar ro'yxati — pagination + search bilan.

    products: barcha mahsulotlar
    page:     hozirgi sahifa (0-dan boshlanadi)
    search:   qidiruv matni (bo'lsa, "Tozalash" tugmasi chiqadi)
    """
    kb = InlineKeyboardBuilder()
    total = len(products)

    if total == 0:
        kb.row(InlineKeyboardButton(text="❌ Bekor", callback_data="qs:cancel"))
        return kb.as_markup()

    total_pages = (total + QS_PER_PAGE - 1) // QS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * QS_PER_PAGE
    page_products = products[start:start + QS_PER_PAGE]

    # Mahsulotlar
    for p in page_products:
        if p.stock_quantity > 0:
            stock_mark = f"({p.stock_quantity:g})"
        else:
            stock_mark = "❌"

        name = p.name if len(p.name) <= 25 else p.name[:23] + "…"

        kb.row(InlineKeyboardButton(
            text=f"{name} — {fmt_money(p.sale_price)} {stock_mark}",
            callback_data=f"qs:p:{p.id}",
        ))

    # Pagination
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"qs:page:{page - 1}"))
        nav.append(InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="qs:noop",
        ))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"qs:page:{page + 1}"))
        kb.row(*nav)

    # Qidirish / Tozalash
    if search:
        kb.row(InlineKeyboardButton(
            text=f"🔄 Tozalash («{search[:15]}»)",
            callback_data="qs:clear_search",
        ))
    else:
        kb.row(InlineKeyboardButton(text="🔍 Qidirish", callback_data="qs:search"))

    kb.row(InlineKeyboardButton(text="❌ Bekor", callback_data="qs:cancel"))
    return kb.as_markup()
