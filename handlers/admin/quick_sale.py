"""
Admin: Tezkor sotuv (do'konda mijoz turganda)
v2: Qidiruv + Sahifalash qo'shildi
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.engine import get_session
from services.product_service import get_all_products, get_product, search_products
from services.order_service import create_quick_sale
from services.user_service import get_user_by_tg_id
from keyboards.admin_kb import quick_sale_pick_product_kb, admin_main_kb, cancel_kb
from handlers.filters import IsAdmin
from handlers.states import QuickSale
from utils.formatters import fmt_money, fmt_qty, parse_amount


router = Router(name="admin_quick_sale")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# Qo'shimcha state — qidiruv uchun
class QuickSaleSearch(StatesGroup):
    query = State()


# ─── BOSHLANISH ──────────────────────────────────────────────────────

@router.message(F.text == "💰 Tezkor sotuv")
async def quick_sale_start(message: Message, state: FSMContext) -> None:
    async with get_session() as session:
        # only_in_stock=False — barcha mahsulotlarni ko'rsatamiz, lekin
        # qoldig'i 0 bo'lganlarni "❌" belgi bilan
        products = await get_all_products(session, only_active=True, only_in_stock=False)

    if not products:
        await message.answer("📦 Sotuvga mahsulot yo'q. Avval mahsulot qo'shing.")
        return

    await state.update_data(qs_page=0, qs_search="")
    await message.answer(
        f"💰 <b>Tezkor sotuv</b>\n\n"
        f"📊 Jami: {len(products)} ta mahsulot\n\n"
        f"Mahsulot tanlang yoki <b>🔍 Qidirish</b> orqali tezda toping:",
        reply_markup=quick_sale_pick_product_kb(products, page=0, search=""),
    )


# ─── PAGINATION ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("qs:page:"))
async def qs_change_page(call: CallbackQuery, state: FSMContext) -> None:
    page = int(call.data.split(":")[2])
    data = await state.get_data()
    search_q = data.get("qs_search", "")

    async with get_session() as session:
        if search_q:
            products = await search_products(session, search_q)
            products = [p for p in products if p.is_active]
        else:
            products = await get_all_products(session, only_active=True, only_in_stock=False)

    await state.update_data(qs_page=page)
    try:
        await call.message.edit_reply_markup(
            reply_markup=quick_sale_pick_product_kb(products, page=page, search=search_q)
        )
    except Exception:
        pass
    await call.answer()


# ─── QIDIRUV ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "qs:search")
async def qs_search_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuickSaleSearch.query)
    await call.message.answer(
        "🔍 Mahsulot nomini yozing (yoki bir qism):\n"
        "<i>Masalan: ko'ylak, shim, libos...</i>",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(QuickSaleSearch.query, F.text)
async def qs_search_result(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    query = message.text.strip()
    if len(query) < 2:
        await message.answer("❌ Kamida 2 ta harf yozing")
        return

    async with get_session() as session:
        products = await search_products(session, query)
        products = [p for p in products if p.is_active]

    await state.set_state(None)  # Search state'dan chiqish
    await state.update_data(qs_page=0, qs_search=query)

    if not products:
        await message.answer(
            f"😕 «{query}» bo'yicha hech narsa topilmadi.\n\n"
            f"Boshqa nom bilan urinib ko'ring yoki ❌ Bekor bosing.",
            reply_markup=cancel_kb(),
        )
        await state.set_state(QuickSaleSearch.query)
        return

    await message.answer(
        f"🔍 «{query}» bo'yicha topildi: <b>{len(products)}</b> ta\n\n"
        f"Tanlang:",
        reply_markup=quick_sale_pick_product_kb(products, page=0, search=query),
    )


@router.callback_query(F.data == "qs:clear_search")
async def qs_clear_search(call: CallbackQuery, state: FSMContext) -> None:
    """Qidiruv natijasini tozalab, butun ro'yxatga qaytish"""
    async with get_session() as session:
        products = await get_all_products(session, only_active=True, only_in_stock=False)

    await state.update_data(qs_page=0, qs_search="")
    try:
        await call.message.edit_text(
            f"💰 <b>Tezkor sotuv</b>\n\n"
            f"📊 Jami: {len(products)} ta mahsulot\n\n"
            f"Mahsulot tanlang yoki <b>🔍 Qidirish</b> orqali tezda toping:",
            reply_markup=quick_sale_pick_product_kb(products, page=0, search=""),
        )
    except Exception:
        pass
    await call.answer("✅ Barcha mahsulotlar")


# ─── BEKOR ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "qs:cancel")
async def qs_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "qs:noop")
async def qs_noop(call: CallbackQuery) -> None:
    """Sahifa ma'lumot tugmasi (bosilganda hech narsa qilmaydi)"""
    await call.answer()


# ─── MAHSULOTNI TANLASH ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("qs:p:"))
async def qs_pick_qty(call: CallbackQuery, state: FSMContext) -> None:
    pid = int(call.data.split(":")[2])
    async with get_session() as session:
        p = await get_product(session, pid)

    if not p:
        await call.answer("❌ Mahsulot topilmadi", show_alert=True)
        return

    if not p.is_in_stock:
        await call.answer(
            f"❌ «{p.name}» qoldig'i 0 — sotib bo'lmaydi.\n"
            f"Avval ombor → kirim qiling.",
            show_alert=True,
        )
        return

    await state.update_data(qs_pid=pid, qs_pname=p.name, qs_unit=p.unit, qs_max=p.stock_quantity)
    await state.set_state(QuickSale.quantity)
    await call.message.answer(
        f"💰 <b>{p.name}</b>\n"
        f"💵 Narxi: {fmt_money(p.sale_price)}\n"
        f"📦 Qoldiq: {fmt_qty(p.stock_quantity, p.unit)}\n\n"
        f"Sotilayotgan miqdorni kiriting:",
        reply_markup=cancel_kb(),
    )
    await call.answer()


# ─── MIQDOR ──────────────────────────────────────────────────────────

@router.message(QuickSale.quantity, F.text)
async def qs_quantity(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    qty = parse_amount(message.text)
    data = await state.get_data()

    if qty is None or qty <= 0:
        await message.answer("❌ Noto'g'ri miqdor")
        return
    if qty > data["qs_max"]:
        await message.answer(f"❌ Bundan ko'p qoldiq yo'q (max: {data['qs_max']:g})")
        return

    await state.update_data(qs_qty=qty)
    await state.set_state(QuickSale.buyer)
    await message.answer(
        "👤 Xaridor ismini kiriting (yoki <b>—</b>):",
        reply_markup=cancel_kb(),
    )


# ─── XARIDOR ─────────────────────────────────────────────────────────

@router.message(QuickSale.buyer, F.text)
async def qs_buyer(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    buyer = message.text.strip() if message.text.strip() != "—" else "Mehmon"
    data = await state.get_data()

    async with get_session() as session:
        admin_user = await get_user_by_tg_id(session, message.from_user.id)
        if not admin_user:
            await message.answer("❌ Xato")
            await state.clear()
            return

        order = await create_quick_sale(
            session,
            user_id=admin_user.id,
            product_id=data["qs_pid"],
            quantity=data["qs_qty"],
            buyer_name=buyer,
        )

    await state.clear()

    if not order:
        await message.answer("❌ Sotuvni amalga oshirib bo'lmadi", reply_markup=admin_main_kb())
        return

    await message.answer(
        f"✅ <b>Sotuv amalga oshirildi!</b>\n\n"
        f"📋 #{order.id}\n"
        f"📦 {data['qs_pname']} × {data['qs_qty']:g}\n"
        f"👤 Xaridor: {buyer}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Summa: <b>{fmt_money(order.total_amount)}</b>\n"
        f"🧾 Soliq: {fmt_money(order.tax_amount)}\n"
        f"📈 Sof foyda: <b>{fmt_money(order.total_profit)}</b>",
        reply_markup=admin_main_kb(),
    )
