"""
Admin: Ombor boshqaruvi
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.engine import get_session
from services.product_service import (
    get_all_products, get_product, stock_in, stock_out,
    get_low_stock_products, get_out_of_stock_products, warehouse_value
)
from keyboards.admin_kb import (
    warehouse_menu_kb, warehouse_pick_product_kb, admin_main_kb,
    cancel_kb
)
from handlers.filters import IsAdmin
from handlers.states import StockOp
from utils.formatters import (
    fmt_money, fmt_qty, parse_amount, stock_emoji
)
from config.settings import settings


router = Router(name="admin_warehouse")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "🏪 Ombor")
async def warehouse_main(message: Message) -> None:
    async with get_session() as session:
        wh = await warehouse_value(session)
        low = await get_low_stock_products(session, settings.low_stock_threshold)
        out = await get_out_of_stock_products(session)

    text = (
        f"🏪 <b>Ombor boshqaruvi</b>\n\n"
        f"📦 Mahsulotlar: <b>{wh['products_count']} ta</b>\n"
        f"🔢 Jami birlik: <b>{wh['total_units']:.0f}</b>\n"
        f"💰 Tan narxi qiymati: <b>{fmt_money(wh['cost_value'])}</b>\n"
        f"💎 Sotuv qiymati: <b>{fmt_money(wh['sale_value'])}</b>\n\n"
        f"⚠️ Kam qoldiq: <b>{len(low)}</b>\n"
        f"❌ Tugagan: <b>{len(out)}</b>"
    )
    await message.answer(text, reply_markup=warehouse_menu_kb())


@router.callback_query(F.data == "wh:menu")
async def wh_menu_cb(call: CallbackQuery) -> None:
    async with get_session() as session:
        wh = await warehouse_value(session)
    text = (
        f"🏪 <b>Ombor boshqaruvi</b>\n\n"
        f"📦 Mahsulotlar: <b>{wh['products_count']} ta</b>\n"
        f"💎 Sotuv qiymati: <b>{fmt_money(wh['sale_value'])}</b>"
    )
    try:
        await call.message.edit_text(text, reply_markup=warehouse_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=warehouse_menu_kb())
    await call.answer()


# ─── KIRIM ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "wh:in")
async def wh_in_pick(call: CallbackQuery) -> None:
    async with get_session() as session:
        products = await get_all_products(session, only_active=True)
    if not products:
        await call.answer("📦 Mahsulot yo'q", show_alert=True)
        return
    await call.message.answer(
        "📥 <b>Kirim qilish uchun mahsulotni tanlang:</b>",
        reply_markup=warehouse_pick_product_kb(products[:30], action="in"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("wh:inp:"))
async def wh_in_qty(call: CallbackQuery, state: FSMContext) -> None:
    pid = int(call.data.split(":")[2])
    async with get_session() as session:
        p = await get_product(session, pid)
    if not p:
        await call.answer("❌ Topilmadi")
        return

    await state.update_data(stock_pid=pid, stock_action="in")
    await state.set_state(StockOp.quantity)
    await call.message.answer(
        f"📥 <b>{p.name}</b>\n"
        f"Joriy qoldiq: {fmt_qty(p.stock_quantity, p.unit)}\n"
        f"Joriy tan narxi: {fmt_money(p.cost_price)}\n\n"
        f"Kirim qilinayotgan miqdorni kiriting:",
        reply_markup=cancel_kb(),
    )
    await call.answer()


# ─── CHIQIM ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "wh:out")
async def wh_out_pick(call: CallbackQuery) -> None:
    async with get_session() as session:
        products = await get_all_products(session, only_active=True, only_in_stock=True)
    if not products:
        await call.answer("📦 Qoldiqda mahsulot yo'q", show_alert=True)
        return
    await call.message.answer(
        "📤 <b>Chiqim qilish uchun mahsulotni tanlang:</b>",
        reply_markup=warehouse_pick_product_kb(products[:30], action="out"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("wh:outp:"))
async def wh_out_qty(call: CallbackQuery, state: FSMContext) -> None:
    pid = int(call.data.split(":")[2])
    async with get_session() as session:
        p = await get_product(session, pid)
    if not p:
        await call.answer("❌ Topilmadi")
        return

    await state.update_data(stock_pid=pid, stock_action="out")
    await state.set_state(StockOp.quantity)
    await call.message.answer(
        f"📤 <b>{p.name}</b>\n"
        f"Joriy qoldiq: {fmt_qty(p.stock_quantity, p.unit)}\n\n"
        f"Chiqim miqdorini kiriting:",
        reply_markup=cancel_kb(),
    )
    await call.answer()


# ─── MIQDORNI QABUL QILISH ───────────────────────────────────────────

@router.message(StockOp.quantity, F.text)
async def stock_qty_input(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    qty = parse_amount(message.text)
    if qty is None or qty <= 0:
        await message.answer("❌ Noto'g'ri raqam. Qayta kiriting:")
        return

    data = await state.get_data()
    action = data["stock_action"]
    await state.update_data(stock_qty=qty)

    if action == "in":
        await state.set_state(StockOp.cost_price)
        await message.answer(
            f"🏷 Yangi tan narxini kiriting "
            f"(yoki <b>0</b> deb yozsangiz, hozirgi narx saqlanadi):",
            reply_markup=cancel_kb(),
        )
    else:
        await state.set_state(StockOp.reason)
        await message.answer(
            "📝 Sababni kiriting (masalan: 'Buzilgan', 'Yo'qotilgan'):",
            reply_markup=cancel_kb(),
        )


@router.message(StockOp.cost_price, F.text)
async def stock_cost_input(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    cost = parse_amount(message.text)
    if cost is None or cost < 0:
        await message.answer("❌ Noto'g'ri raqam:")
        return

    await state.update_data(stock_cost=cost)
    await state.set_state(StockOp.reason)
    await message.answer(
        "📝 Izoh kiriting (kim/qaerdan, yoki <b>—</b> deb yozing):",
        reply_markup=cancel_kb(),
    )


@router.message(StockOp.reason, F.text)
async def stock_reason_apply(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    data = await state.get_data()
    pid = data["stock_pid"]
    qty = data["stock_qty"]
    action = data["stock_action"]
    reason = message.text.strip() if message.text.strip() != "—" else None

    async with get_session() as session:
        if action == "in":
            new_cost = data.get("stock_cost", 0)
            new_cost = new_cost if new_cost > 0 else None
            p = await stock_in(session, pid, qty, new_cost_price=new_cost,
                               reason=reason or "Kirim")
            if p:
                msg = (
                    f"✅ Kirim bajarildi!\n\n"
                    f"📦 {p.name}\n"
                    f"➕ Qo'shildi: {fmt_qty(qty, p.unit)}\n"
                    f"📊 Yangi qoldiq: <b>{fmt_qty(p.stock_quantity, p.unit)}</b>\n"
                    f"🏷 Tan narxi: {fmt_money(p.cost_price)}"
                )
            else:
                msg = "❌ Xatolik"
        else:
            p = await stock_out(session, pid, qty, reason=reason or "Chiqim")
            if p:
                msg = (
                    f"✅ Chiqim bajarildi!\n\n"
                    f"📦 {p.name}\n"
                    f"➖ Chiqim: {fmt_qty(qty, p.unit)}\n"
                    f"📊 Qoldiq: <b>{fmt_qty(p.stock_quantity, p.unit)}</b>"
                )
            else:
                msg = "❌ Xatolik"

    await state.clear()
    await message.answer(msg, reply_markup=admin_main_kb())


# ─── KAM QOLDIQ / TUGAGAN / QIYMAT ───────────────────────────────────

@router.callback_query(F.data == "wh:low")
async def wh_low(call: CallbackQuery) -> None:
    async with get_session() as session:
        products = await get_low_stock_products(session, settings.low_stock_threshold)

    if not products:
        await call.answer("✅ Kam qoldiqli mahsulot yo'q", show_alert=True)
        return

    text = f"⚠️ <b>Kam qoldiqli mahsulotlar</b> (≤ {settings.low_stock_threshold}):\n\n"
    for p in products:
        text += f"• <b>{p.name}</b> — {fmt_qty(p.stock_quantity, p.unit)}\n"
    await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data == "wh:zero")
async def wh_zero(call: CallbackQuery) -> None:
    async with get_session() as session:
        products = await get_out_of_stock_products(session)

    if not products:
        await call.answer("✅ Tugagan mahsulot yo'q", show_alert=True)
        return

    text = f"❌ <b>Tugagan mahsulotlar</b> ({len(products)} ta):\n\n"
    for p in products[:30]:
        text += f"• {p.name}\n"
    if len(products) > 30:
        text += f"\n<i>... va yana {len(products) - 30} ta</i>"
    await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data == "wh:value")
async def wh_value(call: CallbackQuery) -> None:
    async with get_session() as session:
        wh = await warehouse_value(session)

    potential_profit = wh["sale_value"] - wh["cost_value"]

    text = (
        f"💎 <b>Ombor qiymati</b>\n\n"
        f"📦 Mahsulotlar: <b>{wh['products_count']} ta</b>\n"
        f"🔢 Jami birlik: <b>{wh['total_units']:.0f}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏷 Tan narxi qiymati:\n   <b>{fmt_money(wh['cost_value'])}</b>\n"
        f"💰 Sotilganda olinadi:\n   <b>{fmt_money(wh['sale_value'])}</b>\n"
        f"📈 Potentsial yalpi foyda:\n   <b>{fmt_money(potential_profit)}</b>"
    )
    await call.message.answer(text)
    await call.answer()
