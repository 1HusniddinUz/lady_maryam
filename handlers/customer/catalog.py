"""
Mijoz uchun katalog va mahsulotlar
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from database.engine import get_session
from services.product_service import (
    get_all_products, get_all_categories, get_product, search_products
)
from services.cart_service import add_to_cart, get_cart
from services.user_service import get_user_by_tg_id, is_admin
from keyboards.customer_kb import (
    categories_kb, products_list_kb, product_detail_kb, customer_main_kb
)
from utils.formatters import fmt_money, fmt_qty, stock_emoji
from handlers.states import Search
from config.settings import settings


router = Router(name="customer_catalog")


# Mijoz va admin ham katalogni ko'rishi mumkin (admin mijoz rejimida)
async def _block_admin_only(message: Message) -> bool:
    """Faqat admin matni kelganda False qaytaradi"""
    return True


@router.message(F.text == "🛍 Katalog")
async def open_catalog(message: Message) -> None:
    async with get_session() as session:
        cats = await get_all_categories(session)

    if not cats:
        await message.answer("📂 Hozircha kategoriyalar yo'q.")
        return

    await message.answer(
        "🛍 <b>Katalog</b>\n\nKategoriyani tanlang 👇",
        reply_markup=categories_kb(cats),
    )


@router.callback_query(F.data == "back_to_cats")
async def back_to_cats(call: CallbackQuery) -> None:
    async with get_session() as session:
        cats = await get_all_categories(session)
    try:
        await call.message.edit_text(
            "🛍 <b>Katalog</b>\n\nKategoriyani tanlang 👇",
            reply_markup=categories_kb(cats),
        )
    except Exception:
        await call.message.answer(
            "🛍 <b>Katalog</b>\n\nKategoriyani tanlang 👇",
            reply_markup=categories_kb(cats),
        )
    await call.answer()


@router.callback_query(F.data.startswith("cat:"))
async def show_category(call: CallbackQuery) -> None:
    cat_str = call.data.split(":", 1)[1]
    cat_id = None if cat_str == "all" else int(cat_str)

    async with get_session() as session:
        products = await get_all_products(
            session, only_active=True, category_id=cat_id
        )

    if not products:
        await call.answer("📦 Bu kategoriyada mahsulot yo'q", show_alert=True)
        return

    await call.message.edit_text(
        f"📦 <b>Mahsulotlar</b> ({len(products)} ta)\n\nTanlang 👇",
        reply_markup=products_list_kb(products, page=0, category_id=cat_str),
    )
    await call.answer()


@router.callback_query(F.data.startswith("page:"))
async def paginate_products(call: CallbackQuery) -> None:
    _, cat_str, page_str = call.data.split(":")
    page = int(page_str)
    cat_id = None if cat_str == "all" else int(cat_str)

    async with get_session() as session:
        products = await get_all_products(
            session, only_active=True, category_id=cat_id
        )
    await call.message.edit_reply_markup(
        reply_markup=products_list_kb(products, page=page, category_id=cat_str)
    )
    await call.answer()


@router.callback_query(F.data.startswith("prod:"))
async def show_product(call: CallbackQuery) -> None:
    product_id = int(call.data.split(":")[1])

    async with get_session() as session:
        product = await get_product(session, product_id)
        if not product or not product.is_active:
            await call.answer("❌ Mahsulot topilmadi", show_alert=True)
            return

        # Savatga qo'shilganmi tekshirish
        user = await get_user_by_tg_id(session, call.from_user.id)
        in_cart = False
        if user:
            cart = await get_cart(session, user.id)
            in_cart = any(ci.product_id == product.id for ci in cart)

    text_parts = [f"📦 <b>{product.name}</b>\n"]
    if product.description:
        text_parts.append(f"📝 {product.description}\n")
    text_parts.append(f"💰 Narx: <b>{fmt_money(product.sale_price)}</b>")
    text_parts.append(
        f"🏪 Holat: " +
        (f"✅ Mavjud ({fmt_qty(product.stock_quantity, product.unit)})"
         if product.is_in_stock else "❌ Mavjud emas")
    )

    text = "\n".join(text_parts)
    kb = product_detail_kb(product, in_cart=in_cart)

    try:
        if product.photo_file_id:
            try:
                await call.message.delete()
            except Exception:
                pass
            await call.message.answer_photo(
                photo=product.photo_file_id,
                caption=text,
                reply_markup=kb,
            )
        else:
            await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)

    await call.answer()


@router.callback_query(F.data.startswith("add:"))
async def add_to_cart_cb(call: CallbackQuery) -> None:
    product_id = int(call.data.split(":")[1])

    async with get_session() as session:
        user = await get_user_by_tg_id(session, call.from_user.id)
        if not user:
            await call.answer("❌ Avval /start bosing", show_alert=True)
            return

        product = await get_product(session, product_id)
        if not product or not product.is_in_stock:
            await call.answer("❌ Mahsulot mavjud emas", show_alert=True)
            return

        await add_to_cart(session, user.id, product_id, 1)

    await call.answer(f"✅ {product.name} savatga qo'shildi!")


@router.callback_query(F.data == "back_to_products")
async def back_to_products(call: CallbackQuery) -> None:
    """Mahsulot tafsilotidan ro'yxatga qaytish"""
    try:
        await call.message.delete()
    except Exception:
        pass

    async with get_session() as session:
        cats = await get_all_categories(session)

    await call.message.answer(
        "🛍 <b>Katalog</b>\n\nKategoriyani tanlang 👇",
        reply_markup=categories_kb(cats),
    )
    await call.answer()


# ─── QIDIRUV ──────────────────────────────────────────────────────────

@router.message(F.text == "🔍 Qidiruv")
async def search_start(message: Message, state: FSMContext) -> None:
    await state.set_state(Search.query)
    await message.answer(
        "🔍 Qidirilayotgan mahsulot nomi yoki barcode ni yozing:",
        reply_markup=customer_main_kb(),
    )


@router.message(Search.query)
async def search_run(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Kamida 2 ta belgi yozing")
        return

    await state.clear()

    async with get_session() as session:
        products = await search_products(session, message.text.strip())

    if not products:
        await message.answer(
            f"❌ <b>{message.text}</b> bo'yicha hech narsa topilmadi.",
            reply_markup=customer_main_kb(),
        )
        return

    text = f"🔍 <b>Qidiruv natijalari</b> ({len(products)} ta):\n\n"
    for p in products[:15]:
        emoji = stock_emoji(p.stock_quantity)
        text += f"{emoji} {p.name} — {fmt_money(p.sale_price)}\n"

    await message.answer(
        text,
        reply_markup=products_list_kb(products, page=0, category_id="search"),
    )


# ─── INFO BO'LIMLARI ──────────────────────────────────────────────────

@router.message(F.text == "📞 Bog'lanish")
async def contacts(message: Message) -> None:
    text = (
        f"📞 <b>Bog'lanish</b>\n\n"
        f"🛍 Do'kon: {settings.shop_name}\n"
        f"☎️ Telefon: {settings.shop_phone}\n"
        f"📍 Manzil: {settings.shop_address}\n\n"
        f"Savollar yoki takliflar bo'lsa, biz bilan bog'laning!"
    )
    await message.answer(text)


@router.message(F.text == "ℹ️ Biz haqimizda")
async def about(message: Message) -> None:
    text = (
        f"ℹ️ <b>Biz haqimizda</b>\n\n"
        f"🛍 <b>{settings.shop_name}</b>\n"
        f"📝 {settings.shop_description}\n\n"
        f"✨ Sifatli mahsulotlar\n"
        f"🚚 Tez yetkazib berish\n"
        f"💯 Ishonchli xizmat"
    )
    await message.answer(text)


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer()
