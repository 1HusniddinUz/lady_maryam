"""
Admin: Tezkor sotuv (do'konda mijoz turganda)
YANGILANGAN: admin qo'lda boshqa narx kiritishi mumkin
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.engine import get_session
from services.product_service import get_all_products, get_product
from services.order_service import create_quick_sale
from services.user_service import get_user_by_tg_id
from keyboards.admin_kb import (
    quick_sale_pick_product_kb, admin_main_kb, cancel_kb, skip_cancel_kb
)
from handlers.filters import IsAdmin
from handlers.states import QuickSale
from utils.formatters import fmt_money, fmt_qty, parse_amount


router = Router(name="admin_quick_sale")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "💰 Tezkor sotuv")
async def quick_sale_start(message: Message, state: FSMContext) -> None:
    async with get_session() as session:
        products = await get_all_products(
            session, only_active=True, only_in_stock=True
        )

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

    await state.update_data(
        qs_pid=pid,
        qs_pname=p.name,
        qs_unit=p.unit,
        qs_max=p.stock_quantity,
        qs_default_price=p.sale_price,   # ⬅️ asl narxni saqlab qo'yamiz
    )
    await state.set_state(QuickSale.quantity)
    await call.message.answer(
        f"💰 <b>{p.name}</b>\n"
        f"💵 Asl narxi: {fmt_money(p.sale_price)}\n"
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
        await message.answer(
            f"❌ Bundan ko'p qoldiq yo'q (max: {data['qs_max']:g})"
        )
        return

    await state.update_data(qs_qty=qty)

    # ⬇️ YANGI QADAM: sotilgan summani so'raymiz
    default_price = data["qs_default_price"]
    default_total = default_price * qty

    await state.set_state(QuickSale.custom_price)
    await message.answer(
        f"💰 <b>Sotilgan summani kiriting</b>\n\n"
        f"📦 {data['qs_pname']} × {qty:g}\n"
        f"💵 Asl narxda bo'lardi: <b>{fmt_money(default_total)}</b>\n\n"
        f"➤ <b>Bir dona narxi</b>ni yozing (so'mda)\n"
        f"   <i>Misol: 180000</i>\n\n"
        f"➤ Yoki <b>⏭ O'tkazib yuborish</b> — asl narxda sotiladi",
        reply_markup=skip_cancel_kb(),
    )


@router.message(QuickSale.custom_price, F.text)
async def qs_custom_price(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    data = await state.get_data()

    # Agar admin "O'tkazib yuborish" bossa, asl narx ishlatiladi
    if message.text.startswith("⏭"):
        custom_price = None  # asl narx
    else:
        price = parse_amount(message.text)
        if price is None or price <= 0:
            await message.answer(
                "❌ Noto'g'ri narx. Faqat raqam yozing\n"
                "<i>(Masalan: 180000)</i>"
            )
            return
        custom_price = price

    await state.update_data(qs_custom_price=custom_price)
    await state.set_state(QuickSale.buyer)

    # Tasdiq ma'lumotlari
    qty = data["qs_qty"]
    actual_price = custom_price if custom_price is not None else data["qs_default_price"]
    total = actual_price * qty
    diff = data["qs_default_price"] - actual_price

    confirm_text = (
        f"📋 <b>Sotuv tafsilotlari:</b>\n\n"
        f"📦 Mahsulot: {data['qs_pname']}\n"
        f"🔢 Miqdor: {qty:g} {data['qs_unit']}\n"
        f"💵 Bir dona narxi: <b>{fmt_money(actual_price)}</b>\n"
    )
    if diff > 0:
        confirm_text += f"📉 Chegirma: -{fmt_money(diff * qty)}\n"
    elif diff < 0:
        confirm_text += f"📈 Qo'shimcha: +{fmt_money(abs(diff) * qty)}\n"
    confirm_text += (
        f"💰 <b>Jami summa: {fmt_money(total)}</b>\n\n"
        f"👤 Xaridor ismini kiriting (yoki <b>—</b>):"
    )

    await message.answer(confirm_text, reply_markup=cancel_kb())


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
            custom_price=data.get("qs_custom_price"),  # ⬅️ qo'lda kiritilgan narx
        )

        # Ma'lumotlarni session ichida olib qolamiz
        if order:
            order_id = order.id
            order_total = order.total_amount
            order_tax = order.tax_amount
            order_profit = order.total_profit
            order_notes = order.notes
        else:
            order_id = None

    await state.clear()

    if order_id is None:
        await message.answer(
            "❌ Sotuvni amalga oshirib bo'lmadi",
            reply_markup=admin_main_kb(),
        )
        return

    # Natija xabari
    qty = data["qs_qty"]
    actual_price = (
        data.get("qs_custom_price")
        if data.get("qs_custom_price") is not None
        else data["qs_default_price"]
    )

    result_text = (
        f"✅ <b>Sotuv amalga oshirildi!</b>\n\n"
        f"📋 Buyurtma: #{order_id}\n"
        f"📦 {data['qs_pname']} × {qty:g}\n"
        f"💵 Bir dona: {fmt_money(actual_price)}\n"
        f"👤 Xaridor: {buyer}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Summa: <b>{fmt_money(order_total)}</b>\n"
        f"🧾 Soliq: {fmt_money(order_tax)}\n"
        f"📈 Sof foyda: <b>{fmt_money(order_profit)}</b>"
    )

    if order_notes:
        result_text += f"\n\n📝 <i>{order_notes}</i>"

    await message.answer(result_text, reply_markup=admin_main_kb())
