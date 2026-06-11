"""
Admin — Qarzlar (debts) moduli

Qarz qo'shish (FSM), ro'yxat (faol / muddati o'tgan / to'langan),
qisman to'lov, mijozga to'g'ridan eslatma yuborish.
"""

import logging
from datetime import date, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from database.engine import get_session
from database.models import DebtStatus
from handlers.filters import IsAdmin
from handlers.states import AddDebt, DebtPayment
from keyboards.admin_kb import (
    admin_main_kb, cancel_kb, skip_cancel_kb,
    debts_menu_kb, debts_list_kb, debt_detail_kb, debt_tone_kb,
    debt_confirm_kb, debt_items_kb, debt_status_emoji,
)
from services.debt_service import (
    create_debt, get_debt, list_debts, add_payment, delete_debt,
    get_debt_stats, generate_reminder_text, log_reminder,
    outstanding, days_until_due,
)
from utils.formatters import fmt_money, fmt_date, parse_amount

logger = logging.getLogger(__name__)

router = Router(name="admin_debts")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


FILTER_TITLES = {
    "all": "📋 Barcha qarzlar",
    "active": "🟡 Faol qarzlar",
    "overdue": "🔴 Muddati o'tgan",
    "paid": "🟢 To'langan",
}


# ─── YORDAMCHILAR ─────────────────────────────────────────────────────

def _parse_due_date(text: str):
    """'KK.OO.YYYY', 'KK.OO' yoki '+N' (N kundan keyin) -> date | None"""
    text = (text or "").strip().lower()
    if not text:
        return None
    if text.startswith("+"):
        try:
            n = int(text[1:].strip().split()[0])
            return date.today() + timedelta(days=n)
        except (ValueError, IndexError):
            return None
    for sep in (".", "/", "-"):
        if sep in text:
            parts = [p for p in text.split(sep) if p.strip()]
            try:
                d = int(parts[0])
                m = int(parts[1])
                y = int(parts[2]) if len(parts) > 2 else date.today().year
                if y < 100:
                    y += 2000
                return date(y, m, d)
            except (ValueError, IndexError):
                return None
    return None


def _parse_items(text: str):
    """Har qator: 'Nomi | soni | narxi' -> (items_list, jami_summa)"""
    items, total = [], 0.0
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        name = parts[0]
        qty = (parse_amount(parts[1]) if len(parts) >= 2 else None) or 1.0
        price = (parse_amount(parts[2]) if len(parts) >= 3 else None) or 0.0
        items.append({"name": name, "qty": qty, "price": price})
        total += qty * price
    return items, total


def _debt_detail_text(debt) -> str:
    lines = [f"{debt_status_emoji(debt)} <b>Qarz #{debt.id}</b>\n"]
    lines.append(f"👤 <b>{debt.customer_name}</b>")
    lines.append(f"📞 {debt.customer_phone}")
    if debt.customer_telegram:
        lines.append(f"💬 @{debt.customer_telegram}")

    if debt.items:
        lines.append("\n🛍 <b>Mahsulotlar:</b>")
        for it in debt.items:
            q = it.get("qty", 1) or 0
            p = it.get("price", 0) or 0
            lines.append(f"  • {it.get('name', '?')} × {q:g} = {fmt_money(q * p)}")

    lines.append("")
    lines.append(f"💰 Umumiy: <b>{fmt_money(debt.total_amount)}</b>")
    lines.append(f"✅ To'langan: {fmt_money(debt.paid_amount)}")
    lines.append(f"🔴 Qoldiq: <b>{fmt_money(outstanding(debt))}</b>")
    lines.append(f"📅 Olingan: {fmt_date(debt.taken_date)}")

    days = days_until_due(debt)
    if debt.status == DebtStatus.PAID:
        due_info = fmt_date(debt.due_date)
    elif days < 0:
        due_info = f"{fmt_date(debt.due_date)} ({abs(days)} kun o'tgan)"
    elif days == 0:
        due_info = f"{fmt_date(debt.due_date)} (bugun)"
    else:
        due_info = f"{fmt_date(debt.due_date)} ({days} kun qoldi)"
    lines.append(f"⏰ Muddat: {due_info}")

    if debt.notes:
        lines.append(f"📝 {debt.notes}")
    if debt.reminders:
        lines.append(f"\n🔔 {len(debt.reminders)} ta eslatma yuborilgan")
    if not debt.customer_chat_id and debt.status == DebtStatus.ACTIVE:
        lines.append("\n⚠️ <i>Mijoz bot bilan bog'lanmagan — eslatma qo'lda yuboriladi</i>")
    return "\n".join(lines)


# ─── MENYU ────────────────────────────────────────────────────────────

@router.message(F.text == "📒 Qarzlar")
async def debts_main(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with get_session() as session:
        stats = await get_debt_stats(session)
    text = (
        "📒 <b>Qarzlar daftari</b>\n\n"
        f"🔴 Qoldiq jami: <b>{fmt_money(stats['total_outstanding'])}</b>\n"
        f"🟡 Faol: {stats['active_count']} ta\n"
        f"⏰ Muddati o'tgan: {stats['overdue_count']} ta\n"
        f"🟢 To'langan: {stats['paid_count']} ta"
    )
    await message.answer(text, reply_markup=debts_menu_kb())


@router.callback_query(F.data == "db:menu")
async def debts_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with get_session() as session:
        stats = await get_debt_stats(session)
    text = (
        "📒 <b>Qarzlar daftari</b>\n\n"
        f"🔴 Qoldiq jami: <b>{fmt_money(stats['total_outstanding'])}</b>\n"
        f"🟡 Faol: {stats['active_count']} ta\n"
        f"⏰ Muddati o'tgan: {stats['overdue_count']} ta\n"
        f"🟢 To'langan: {stats['paid_count']} ta"
    )
    await call.message.answer(text, reply_markup=debts_menu_kb())
    await call.answer()


# ─── RO'YXAT VA KO'RISH ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("db:list:"))
async def debts_list(call: CallbackQuery) -> None:
    flt = call.data.split(":")[2]
    async with get_session() as session:
        debts = await list_debts(session, status_filter=flt)
    title = FILTER_TITLES.get(flt, "Qarzlar")
    if not debts:
        await call.message.answer(
            f"{title}\n\n<i>Bu bo'limda qarz yo'q.</i>",
            reply_markup=debts_list_kb([], flt),
        )
    else:
        await call.message.answer(
            f"{title} ({len(debts)} ta)",
            reply_markup=debts_list_kb(debts, flt),
        )
    await call.answer()


@router.callback_query(F.data.startswith("db:view:"))
async def debt_view(call: CallbackQuery) -> None:
    debt_id = int(call.data.split(":")[2])
    async with get_session() as session:
        debt = await get_debt(session, debt_id)
    if not debt:
        await call.answer("Qarz topilmadi", show_alert=True)
        return
    await call.message.answer(_debt_detail_text(debt), reply_markup=debt_detail_kb(debt))
    await call.answer()


@router.callback_query(F.data.startswith("db:del:"))
async def debt_delete(call: CallbackQuery) -> None:
    debt_id = int(call.data.split(":")[2])
    async with get_session() as session:
        ok = await delete_debt(session, debt_id)
    if ok:
        await call.message.answer("🗑 Qarz o'chirildi.", reply_markup=debts_menu_kb())
    else:
        await call.answer("Topilmadi", show_alert=True)
    await call.answer()


# ─── YANGI QARZ (FSM) ─────────────────────────────────────────────────

@router.callback_query(F.data == "db:new")
async def debt_new(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddDebt.customer_name)
    await call.message.answer(
        "➕ <b>Yangi qarz</b>\n\n👤 Mijozning ism-familiyasini kiriting:",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AddDebt.customer_name, F.text)
async def debt_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Juda qisqa. Ism-familiyani to'liq kiriting:")
        return
    await state.update_data(d_name=name)
    await state.set_state(AddDebt.customer_phone)
    await message.answer("📞 Mijozning telefon raqamini kiriting:", reply_markup=cancel_kb())


@router.message(AddDebt.customer_phone, F.text)
async def debt_phone(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    if len(phone) < 7:
        await message.answer("❌ Telefon raqam noto'g'ri. Qaytadan kiriting:")
        return
    await state.update_data(d_phone=phone)
    await state.set_state(AddDebt.customer_telegram)
    await message.answer(
        "💬 Mijozning Telegram username'ini kiriting (masalan: @mijoz)\n"
        "<i>Bu eslatmalarni to'g'ridan yuborish uchun kerak.</i>",
        reply_markup=skip_cancel_kb(),
    )


@router.message(AddDebt.customer_telegram, F.text)
async def debt_telegram(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    tg = None if text.startswith("⏭") or text in ("-", "yo'q", "yoq") else text.lstrip("@")
    await state.update_data(d_tg=tg)
    await state.set_state(AddDebt.items)
    await message.answer(
        "🛍 Mahsulotlarni kiriting. Har bir mahsulot alohida qatorda:\n"
        "<code>Nomi | soni | narxi</code>\n\n"
        "<i>Masalan:\nKuylak | 1 | 450000\nShim | 2 | 200000</i>\n\n"
        "Yoki mahsulotsiz davom etish uchun tugmani bosing 👇",
        reply_markup=debt_items_kb(),
    )


@router.callback_query(AddDebt.items, F.data == "db:items_skip")
async def debt_items_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(d_items=[], d_items_total=0.0)
    await state.set_state(AddDebt.total)
    await call.message.answer(
        "💰 Umumiy qarz summasini kiriting (so'mda):",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AddDebt.items, F.text)
async def debt_items(message: Message, state: FSMContext) -> None:
    items, items_total = _parse_items(message.text)
    await state.update_data(d_items=items, d_items_total=items_total)
    await state.set_state(AddDebt.total)
    hint = ""
    if items_total > 0:
        hint = (
            f"\n\nMahsulotlar yig'indisi: <b>{fmt_money(items_total)}</b>\n"
            f"Shu summani qabul qilish uchun <code>=</code> yuboring yoki boshqa summa kiriting:"
        )
    await message.answer(
        f"💰 Umumiy qarz summasini kiriting (so'mda):{hint}",
        reply_markup=cancel_kb(),
    )


@router.message(AddDebt.total, F.text)
async def debt_total(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = message.text.strip()
    if text in ("=", "+") and data.get("d_items_total", 0) > 0:
        total = float(data["d_items_total"])
    else:
        total = parse_amount(text)
    if total is None or total <= 0:
        await message.answer("❌ Noto'g'ri summa. Qaytadan kiriting:")
        return
    await state.update_data(d_total=total)
    await state.set_state(AddDebt.due_date)
    await message.answer(
        "📅 To'lov muddatini kiriting:\n"
        "<code>KK.OO.YYYY</code> formatda (masalan 15.07.2026)\n"
        "yoki <code>+14</code> (14 kundan keyin):",
        reply_markup=cancel_kb(),
    )


@router.message(AddDebt.due_date, F.text)
async def debt_due(message: Message, state: FSMContext) -> None:
    due = _parse_due_date(message.text)
    if not due:
        await message.answer("❌ Sanani tushunmadim. Masalan: <code>15.07.2026</code> yoki <code>+14</code>")
        return
    await state.update_data(d_due=due)
    await state.set_state(AddDebt.notes)
    await message.answer(
        "📝 Izoh kiriting (ixtiyoriy) yoki o'tkazib yuboring:",
        reply_markup=skip_cancel_kb(),
    )


@router.message(AddDebt.notes, F.text)
async def debt_notes(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    notes = None if text.startswith("⏭") or text in ("-", "yo'q", "yoq") else text
    await state.update_data(d_notes=notes)
    await state.set_state(AddDebt.confirm)

    data = await state.get_data()
    items = data.get("d_items", [])
    items_txt = ""
    if items:
        items_txt = "\n🛍 Mahsulotlar:\n" + "\n".join(
            f"  • {it['name']} × {it.get('qty', 1):g} = {fmt_money((it.get('qty', 1) or 0) * (it.get('price', 0) or 0))}"
            for it in items
        )
    summary = (
        "✅ <b>Tasdiqlang:</b>\n\n"
        f"👤 {data['d_name']}\n"
        f"📞 {data['d_phone']}\n"
        f"💬 {('@' + data['d_tg']) if data.get('d_tg') else '—'}"
        f"{items_txt}\n\n"
        f"💰 Summa: <b>{fmt_money(data['d_total'])}</b>\n"
        f"📅 Muddat: {fmt_date(data['d_due'])}\n"
        f"📝 Izoh: {notes or '—'}"
    )
    await message.answer(summary, reply_markup=debt_confirm_kb())


@router.callback_query(AddDebt.confirm, F.data == "db:save")
async def debt_save(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    async with get_session() as session:
        debt = await create_debt(
            session,
            customer_name=data["d_name"],
            customer_phone=data["d_phone"],
            customer_telegram=data.get("d_tg"),
            items=data.get("d_items", []),
            total_amount=data["d_total"],
            due_date=data["d_due"],
            notes=data.get("d_notes"),
        )
        debt_id = debt.id
        linked = debt.customer_chat_id is not None

    text = f"✅ Qarz qo'shildi! (#{debt_id})\n\n👤 {data['d_name']} — {fmt_money(data['d_total'])}"
    if not linked:
        try:
            me = await call.bot.me()
            link = f"https://t.me/{me.username}?start=debt_{debt_id}"
            text += (
                "\n\n💡 Mijoz bot bilan bog'lanmagan. Quyidagi havolani mijozga yuboring — "
                "u bossa, avtomatik eslatmalar to'g'ridan unga boradi:\n"
                f"<code>{link}</code>"
            )
        except Exception:
            pass
    await call.message.answer(text, reply_markup=admin_main_kb())
    await call.answer("Saqlandi ✅")


@router.callback_query(F.data == "db:cancel")
async def debt_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
    await call.answer()


# ─── TO'LOV ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("db:pay:"))
async def debt_pay_start(call: CallbackQuery, state: FSMContext) -> None:
    debt_id = int(call.data.split(":")[2])
    async with get_session() as session:
        debt = await get_debt(session, debt_id)
    if not debt:
        await call.answer("Topilmadi", show_alert=True)
        return
    await state.set_state(DebtPayment.amount)
    await state.update_data(pay_debt_id=debt_id)
    await call.message.answer(
        f"💵 <b>To'lov</b>\n\nQoldiq: <b>{fmt_money(outstanding(debt))}</b>\n\n"
        f"To'lov summasini kiriting (so'mda):",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(DebtPayment.amount, F.text)
async def debt_pay_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None or amount <= 0:
        await message.answer("❌ Noto'g'ri summa. Qaytadan kiriting:")
        return
    data = await state.get_data()
    debt_id = data.get("pay_debt_id")
    await state.clear()
    async with get_session() as session:
        debt = await add_payment(session, debt_id, amount)
        if not debt:
            await message.answer("❌ Qarz topilmadi.", reply_markup=admin_main_kb())
            return
        remaining = outstanding(debt)
        is_paid = debt.status == DebtStatus.PAID

    if is_paid:
        text = f"✅ To'lov qabul qilindi: {fmt_money(amount)}\n\n🟢 Qarz to'liq yopildi!"
    else:
        text = (
            f"✅ To'lov qabul qilindi: {fmt_money(amount)}\n\n"
            f"🔴 Qoldiq: <b>{fmt_money(remaining)}</b>"
        )
    await message.answer(text, reply_markup=admin_main_kb())


# ─── ESLATMA ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("db:remind:"))
async def debt_remind(call: CallbackQuery) -> None:
    debt_id = int(call.data.split(":")[2])
    await call.message.answer(
        "🔔 Eslatma ohangini tanlang:",
        reply_markup=debt_tone_kb(debt_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("db:send:"))
async def debt_send_reminder(call: CallbackQuery) -> None:
    _, _, debt_id_s, tone = call.data.split(":")
    debt_id = int(debt_id_s)

    async with get_session() as session:
        debt = await get_debt(session, debt_id)
        if not debt:
            await call.answer("Topilmadi", show_alert=True)
            return
        text = generate_reminder_text(debt, tone)
        chat_id = debt.customer_chat_id

        if chat_id:
            try:
                await call.bot.send_message(chat_id, text)
                await log_reminder(session, debt_id, tone, text, "sent")
                await call.message.answer("✅ Eslatma mijozga yuborildi.", reply_markup=debts_menu_kb())
            except (TelegramForbiddenError, TelegramBadRequest):
                await log_reminder(session, debt_id, tone, text, "failed")
                await call.message.answer(
                    "⚠️ Mijozga yuborib bo'lmadi (botni bloklagan bo'lishi mumkin).\n\n"
                    "Quyidagi matnni qo'lda yuboring:\n\n" + text,
                    reply_markup=debts_menu_kb(),
                )
        else:
            await log_reminder(session, debt_id, tone, text, "manual")
            await call.message.answer(
                "📋 Mijoz bot bilan bog'lanmagan. Quyidagi matnni qo'lda yuboring:\n\n" + text,
                reply_markup=debts_menu_kb(),
            )
    await call.answer()
