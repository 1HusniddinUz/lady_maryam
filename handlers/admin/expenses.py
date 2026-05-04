"""
Admin: Xarajatlar boshqaruvi
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.engine import get_session
from services.expense_service import (
    add_expense, get_expenses, expenses_total, expenses_by_category
)
from keyboards.admin_kb import (
    expenses_menu_kb, expense_category_kb, admin_main_kb, cancel_kb
)
from handlers.filters import IsAdmin
from handlers.states import AddExpense
from utils.formatters import fmt_money, fmt_datetime, parse_amount


router = Router(name="admin_expenses")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "💸 Xarajatlar")
async def expenses_main(message: Message) -> None:
    async with get_session() as session:
        total = await expenses_total(session)
        by_cat = await expenses_by_category(session)

    text = f"💸 <b>Xarajatlar</b>\n\n💰 Jami: <b>{fmt_money(total)}</b>\n"
    if by_cat:
        text += "\n<b>Kategoriya bo'yicha:</b>\n"
        cat_names = {
            "ijara": "🏪 Ijara",
            "ish_haqi": "👷 Ish haqi",
            "transport": "🚚 Transport",
            "reklama": "📢 Reklama",
            "kommunal": "💡 Kommunal",
            "boshqa": "📦 Boshqa",
        }
        for cat, amount in by_cat.items():
            text += f"  {cat_names.get(cat, cat)}: {fmt_money(amount)}\n"

    await message.answer(text, reply_markup=expenses_menu_kb())


@router.callback_query(F.data == "ex:new")
async def expense_new(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.answer(
        "💸 <b>Yangi xarajat</b>\n\nKategoriyani tanlang:",
        reply_markup=expense_category_kb(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("ex:cat:"))
async def expense_cat_picked(call: CallbackQuery, state: FSMContext) -> None:
    category = call.data.split(":")[2]
    await state.update_data(expense_category=category)
    await state.set_state(AddExpense.title)
    await call.message.answer(
        "📝 Xarajat nomini kiriting:\n<i>(Misol: Ofis ijarasi, Reklama Instagram'da)</i>",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AddExpense.title, F.text)
async def expense_title(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    title = message.text.strip()
    if len(title) < 2:
        await message.answer("❌ Juda qisqa")
        return

    await state.update_data(expense_title=title)
    await state.set_state(AddExpense.amount)
    await message.answer(
        "💰 Summani kiriting (so'mda):",
        reply_markup=cancel_kb(),
    )


@router.message(AddExpense.amount, F.text)
async def expense_amount(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    amount = parse_amount(message.text)
    if amount is None or amount <= 0:
        await message.answer("❌ Noto'g'ri summa")
        return

    data = await state.get_data()
    async with get_session() as session:
        await add_expense(
            session,
            title=data["expense_title"],
            amount=amount,
            category=data["expense_category"],
        )

    await state.clear()
    await message.answer(
        f"✅ Xarajat qo'shildi!\n\n"
        f"📝 {data['expense_title']}\n"
        f"💰 {fmt_money(amount)}",
        reply_markup=admin_main_kb(),
    )


@router.callback_query(F.data == "ex:list")
async def expense_list(call: CallbackQuery) -> None:
    async with get_session() as session:
        expenses = await get_expenses(session, limit=20)

    if not expenses:
        await call.answer("📭 Xarajatlar yo'q", show_alert=True)
        return

    cat_emoji = {
        "ijara": "🏪", "ish_haqi": "👷", "transport": "🚚",
        "reklama": "📢", "kommunal": "💡", "boshqa": "📦",
    }

    text = "📋 <b>Oxirgi xarajatlar</b>:\n\n"
    for e in expenses:
        emoji = cat_emoji.get(e.category, "📦")
        text += (
            f"{emoji} <b>{e.title}</b>\n"
            f"   💰 {fmt_money(e.amount)} • 📅 {fmt_datetime(e.expense_date)}\n\n"
        )

    await call.message.answer(text)
    await call.answer()
