"""
Admin: Tezkor sotuv (do'konda mijoz turganda)
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.engine import get_session
from services.product_service import get_all_products, get_product
from services.order_service import create_quick_sale
from services.user_service import get_user_by_tg_id
from keyboards.admin_kb import quick_sale_pick_product_kb, admin_main_kb, cancel_kb
from handlers.filters import IsAdmin
from handlers.states import QuickSale
from utils.formatters import fmt_money, fmt_qty, parse_amount


router = Router(name="admin_quick_sale")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "💰 Tezkor sotuv")
async def quick_sale_start(message: Message, state: FSMContext) -> None:
    async with get_session() as session:
        products = await get_all_products(session, only_active=True, only_in_stock=True)

    if not products:
        await message.answer("📦 Sotuvga mahsulot yo'q")
        return

    await message.answer(
        "💰 <b>Tezkor sotuv</b>\n\n"
        "Sotilayotgan mahsulotni tanlang:",
        reply_markup=quick_sale_pick_product_kb(products[:30]),
    )


@router.callback_query(F.data == "qs:cancel")
async def qs_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data.startswith("qs:p:"))
async def qs_pick_qty(call: CallbackQuery, state: FSMContext) -> None:
    pid = int(call.data.split(":")[2])
    async with get_session() as session:
        p = await get_product(session, pid)

    if not p or not p.is_in_stock:
        await call.answer("❌ Mavjud emas", show_alert=True)
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
