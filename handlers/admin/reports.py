"""
Admin: Hisobotlar va analitika
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from database.engine import get_session
from services.report_service import (
    sales_summary, top_products, top_customers,
    daily_sales_chart_data, get_period_range
)
from services.export_service import (
    export_sales_report_excel, make_sales_chart, make_top_products_chart
)
from services.settings_service import get_tax_name
from keyboards.admin_kb import reports_menu_kb, report_period_actions_kb
from handlers.filters import IsAdmin
from utils.formatters import fmt_money, profit_arrow


router = Router(name="admin_reports")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "📊 Hisobotlar")
async def reports_main(message: Message) -> None:
    text = (
        "📊 <b>Hisobotlar va analitika</b>\n\n"
        "Davrni yoki hisobot turini tanlang 👇"
    )
    await message.answer(text, reply_markup=reports_menu_kb())


@router.callback_query(F.data == "rp:menu")
async def reports_menu_cb(call: CallbackQuery) -> None:
    text = "📊 <b>Hisobotlar va analitika</b>\n\nTanlang 👇"
    try:
        await call.message.edit_text(text, reply_markup=reports_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=reports_menu_kb())
    await call.answer()


# ─── DAVRIY HISOBOT ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rp:p:"))
async def report_period(call: CallbackQuery) -> None:
    period = call.data.split(":")[2]
    start, end, label = get_period_range(period)

    async with get_session() as session:
        summary = await sales_summary(session, start, end)
        tax_name = await get_tax_name(session)

    arrow = profit_arrow(summary["final_net"])
    text = (
        f"📊 <b>Hisobot — {label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Buyurtmalar: <b>{summary['orders_count']}</b>\n"
        f"🛒 Sotilgan: <b>{summary['items_count']:.0f}</b> dona\n\n"
        f"💰 Tushum: <b>{fmt_money(summary['revenue'])}</b>\n"
        f"🏷 Tan narxi: -{fmt_money(summary['cost'])}\n"
        f"📈 Yalpi foyda: <b>{fmt_money(summary['gross_profit'])}</b>\n"
        f"   Marja: {summary['margin_pct']:.1f}%\n\n"
        f"🧾 {tax_name}: -{fmt_money(summary['tax'])}\n"
        f"💼 Soliqdan keyin: {fmt_money(summary['net_after_tax'])}\n"
        f"💸 Xarajatlar: -{fmt_money(summary['expenses'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{arrow} <b>SOF FOYDA: {fmt_money(summary['final_net'])}</b>\n"
        f"   ({summary['net_pct']:.1f}% rentabellik)"
    )

    await call.message.answer(text, reply_markup=report_period_actions_kb(period))
    await call.answer()


# ─── EXCEL EKSPORT ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rp:excel:"))
async def report_excel(call: CallbackQuery) -> None:
    period = call.data.split(":")[2]
    start, end, label = get_period_range(period)

    await call.answer("⏳ Excel tayyorlanmoqda...")

    async with get_session() as session:
        summary = await sales_summary(session, start, end)
        top_p = await top_products(session, start, end, limit=10)
        top_c = await top_customers(session, start, end, limit=10)
        daily = await daily_sales_chart_data(session, days=30)

    excel_bytes = export_sales_report_excel(
        summary=summary,
        top_products_list=top_p,
        top_customers_list=top_c,
        daily_data=daily,
        period_name=label,
    )

    filename = f"hisobot_{period}.xlsx"
    await call.message.answer_document(
        BufferedInputFile(excel_bytes, filename=filename),
        caption=f"📊 Hisobot — {label}",
    )


# ─── GRAFIK ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rp:chart:"))
async def report_chart(call: CallbackQuery) -> None:
    period = call.data.split(":")[2]
    _, _, label = get_period_range(period)

    await call.answer("⏳ Grafik tayyorlanmoqda...")

    async with get_session() as session:
        daily = await daily_sales_chart_data(session, days=30)

    chart_bytes = make_sales_chart(daily, period_name=label)
    await call.message.answer_photo(
        BufferedInputFile(chart_bytes, filename=f"grafik_{period}.png"),
        caption=f"📈 Sotuv dinamikasi — {label}",
    )


# ─── TOP MAHSULOTLAR ──────────────────────────────────────────────────

@router.callback_query(F.data == "rp:top:products")
async def top_products_view(call: CallbackQuery) -> None:
    start, end, label = get_period_range("month")
    async with get_session() as session:
        top_p = await top_products(session, start, end, limit=10)

    if not top_p:
        await call.answer("📦 Sotilgan mahsulot yo'q", show_alert=True)
        return

    text = f"🏆 <b>TOP-10 mahsulotlar</b> ({label}):\n\n"
    for i, p in enumerate(top_p, 1):
        text += (
            f"{i}. <b>{p['name']}</b>\n"
            f"   📦 {p['quantity']:.0f} dona • 💰 {fmt_money(p['revenue'])}\n"
            f"   📈 Foyda: {fmt_money(p['profit'])}\n\n"
        )

    await call.message.answer(text)

    # Grafik ham yuborish
    chart_bytes = make_top_products_chart(top_p)
    await call.message.answer_photo(
        BufferedInputFile(chart_bytes, filename="top_products.png"),
        caption=f"📊 TOP-10 mahsulotlar grafigi"
    )
    await call.answer()


# ─── TOP MIJOZLAR ─────────────────────────────────────────────────────

@router.callback_query(F.data == "rp:top:customers")
async def top_customers_view(call: CallbackQuery) -> None:
    start, end, label = get_period_range("all")
    async with get_session() as session:
        top_c = await top_customers(session, start, end, limit=10)

    if not top_c:
        await call.answer("👥 Mijozlar topilmadi", show_alert=True)
        return

    text = f"👑 <b>TOP-10 mijozlar</b> ({label}):\n\n"
    for i, c in enumerate(top_c, 1):
        text += (
            f"{i}. <b>{c['name']}</b>\n"
            f"   📱 {c['phone'] or '—'}\n"
            f"   🛒 {c['orders']} buyurtma • 💰 {fmt_money(c['spent'])}\n\n"
        )

    await call.message.answer(text)
    await call.answer()
