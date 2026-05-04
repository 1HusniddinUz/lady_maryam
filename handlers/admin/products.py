"""
Admin: Mahsulotlar boshqaruvi
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from database.engine import get_session
from services.product_service import (
    create_product, get_product, get_all_products, update_product,
    delete_product, get_stock_history,
    get_all_categories, create_category, delete_category
)
from services.export_service import export_products_excel
from keyboards.admin_kb import (
    admin_main_kb, products_menu_kb, admin_products_list_kb,
    product_view_kb, categories_pick_kb, categories_admin_kb, cancel_kb,
    skip_cancel_kb
)
from handlers.filters import IsAdmin
from handlers.states import AddProduct, EditProductField, AddCategory
from utils.formatters import (
    fmt_money, fmt_qty, parse_amount, stock_emoji, fmt_pct
)
from services.settings_service import get_tax_rate


router = Router(name="admin_products")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "📦 Mahsulotlar")
async def products_main(message: Message) -> None:
    async with get_session() as session:
        products = await get_all_products(session, only_active=True)
    text = (
        f"📦 <b>Mahsulotlar boshqaruvi</b>\n\n"
        f"📊 Jami: <b>{len(products)} ta</b> mahsulot\n\n"
        f"Quyidagilardan birini tanlang 👇"
    )
    await message.answer(text, reply_markup=products_menu_kb())


@router.callback_query(F.data == "ap:menu")
async def products_menu_cb(call: CallbackQuery) -> None:
    async with get_session() as session:
        products = await get_all_products(session, only_active=True)
    text = (
        f"📦 <b>Mahsulotlar boshqaruvi</b>\n\n"
        f"📊 Jami: <b>{len(products)} ta</b> mahsulot"
    )
    try:
        await call.message.edit_text(text, reply_markup=products_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=products_menu_kb())
    await call.answer()


# ─── RO'YXAT ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ap:list:"))
async def products_list(call: CallbackQuery) -> None:
    page = int(call.data.split(":")[2])
    async with get_session() as session:
        products = await get_all_products(session, only_active=True)
        tax_rate = await get_tax_rate(session)

    if not products:
        await call.answer("📦 Mahsulot yo'q", show_alert=True)
        return

    text = f"📦 <b>Barcha mahsulotlar</b> ({len(products)} ta)\n\n"
    text += f"<i>Soliq stavkasi: {fmt_pct(tax_rate)}</i>\n\n"
    text += "Boshqarish uchun tanlang 👇"

    try:
        await call.message.edit_text(
            text, reply_markup=admin_products_list_kb(products, page=page)
        )
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "ap:export")
async def export_products(call: CallbackQuery) -> None:
    async with get_session() as session:
        products = await get_all_products(session, only_active=True)
    if not products:
        await call.answer("📦 Mahsulot yo'q", show_alert=True)
        return

    excel_bytes = export_products_excel(products)
    await call.message.answer_document(
        BufferedInputFile(excel_bytes, filename="mahsulotlar.xlsx"),
        caption=f"📊 Mahsulotlar ro'yxati ({len(products)} ta)",
    )
    await call.answer("✅ Eksport tayyor")


# ─── MAHSULOT KO'RISH ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ap:view:"))
async def view_product(call: CallbackQuery) -> None:
    pid = int(call.data.split(":")[2])
    async with get_session() as session:
        p = await get_product(session, pid)
        tax_rate = await get_tax_rate(session)

    if not p:
        await call.answer("❌ Topilmadi", show_alert=True)
        return

    tax_per = p.sale_price * tax_rate
    net = p.sale_price - p.cost_price - tax_per
    margin_pct = (net / p.sale_price * 100) if p.sale_price else 0

    cat_name = p.category.name if p.category else "—"

    text = (
        f"📦 <b>{p.name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📂 Kategoriya: {cat_name}\n"
        f"📝 Tavsif: {p.description or '—'}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏷 Tan narxi: <b>{fmt_money(p.cost_price)}</b>\n"
        f"💰 Sotuv narxi: <b>{fmt_money(p.sale_price)}</b>\n"
        f"🧾 Soliq ({fmt_pct(tax_rate)}): -{fmt_money(tax_per)}\n"
        f"📈 Sof marja: <b>{fmt_money(net)}</b> ({margin_pct:.1f}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Qoldiq: {stock_emoji(p.stock_quantity)} <b>{fmt_qty(p.stock_quantity, p.unit)}</b>\n"
        f"💎 Ombor qiymati: {fmt_money(p.stock_quantity * p.cost_price)}"
    )

    try:
        if p.photo_file_id:
            try:
                await call.message.delete()
            except Exception:
                pass
            await call.message.answer_photo(
                photo=p.photo_file_id, caption=text,
                reply_markup=product_view_kb(p.id),
            )
        else:
            await call.message.edit_text(text, reply_markup=product_view_kb(p.id))
    except Exception:
        await call.message.answer(text, reply_markup=product_view_kb(p.id))

    await call.answer()


# ─── O'CHIRISH ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ap:del:"))
async def del_product(call: CallbackQuery) -> None:
    pid = int(call.data.split(":")[2])
    async with get_session() as session:
        p = await get_product(session, pid)
        if not p:
            await call.answer("❌ Topilmadi")
            return
        await delete_product(session, pid)
    await call.answer(f"🗑 {p.name} o'chirildi", show_alert=True)
    try:
        await call.message.delete()
    except Exception:
        pass


# ─── HARAKATLAR TARIXI ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ap:hist:"))
async def stock_history(call: CallbackQuery) -> None:
    pid = int(call.data.split(":")[2])
    async with get_session() as session:
        p = await get_product(session, pid)
        if not p:
            await call.answer("❌ Topilmadi")
            return
        movements = await get_stock_history(session, pid, limit=20)

    text = f"📈 <b>{p.name}</b> harakatlar tarixi:\n\n"
    if not movements:
        text += "Hech qanday harakat yo'q."
    else:
        for m in movements:
            icon = {"kirim": "📥", "chiqim": "📤", "sotuv": "💰",
                    "qaytarish": "🔄", "tuzatish": "✏️"}.get(m.type.value, "📋")
            text += (
                f"{icon} <b>{m.type.value.capitalize()}</b>: {fmt_qty(m.quantity, p.unit)}\n"
                f"   📅 {m.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"   📝 {m.reason or '—'}\n\n"
            )
    await call.message.answer(text)
    await call.answer()


# ─── YANGI MAHSULOT QO'SHISH ──────────────────────────────────────────

@router.callback_query(F.data == "ap:new")
async def new_product_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddProduct.name)
    await call.message.answer(
        "📝 <b>Yangi mahsulot qo'shish</b>\n\n"
        "1️⃣ Mahsulot nomini kiriting:",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AddProduct.name, F.text)
async def ap_name(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Nom juda qisqa")
        return

    await state.update_data(name=name)
    await state.set_state(AddProduct.cost)
    await message.answer(
        f"🏷 <b>Tan narxini</b> kiriting (so'mda):\n"
        f"<i>(Mahsulotni xarid qilgan/ishlab chiqarish narxingiz)</i>",
        reply_markup=cancel_kb(),
    )


@router.message(AddProduct.cost, F.text)
async def ap_cost(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    val = parse_amount(message.text)
    if val is None or val < 0:
        await message.answer("❌ Noto'g'ri raqam. Qayta kiriting:")
        return

    await state.update_data(cost=val)
    await state.set_state(AddProduct.sell)
    await message.answer(
        f"💰 <b>Sotuv narxini</b> kiriting:",
        reply_markup=cancel_kb(),
    )


@router.message(AddProduct.sell, F.text)
async def ap_sell(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    val = parse_amount(message.text)
    if val is None or val < 0:
        await message.answer("❌ Noto'g'ri raqam. Qayta kiriting:")
        return

    data = await state.get_data()
    cost = data["cost"]

    async with get_session() as session:
        tax_rate = await get_tax_rate(session)

    tax = val * tax_rate
    net = val - cost - tax
    margin_pct = (net / val * 100) if val else 0

    await state.update_data(sell=val)
    await state.set_state(AddProduct.stock)
    await message.answer(
        f"✅ <b>Hisob-kitob:</b>\n"
        f"🏷 Tan: {fmt_money(cost)}\n"
        f"💰 Sotuv: {fmt_money(val)}\n"
        f"🧾 Soliq ({fmt_pct(tax_rate)}): -{fmt_money(tax)}\n"
        f"📈 Sof marja: <b>{fmt_money(net)}</b> ({margin_pct:.1f}%)\n\n"
        f"📦 Boshlang'ich qoldiqni kiriting:",
        reply_markup=cancel_kb(),
    )


@router.message(AddProduct.stock, F.text)
async def ap_stock(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    val = parse_amount(message.text)
    if val is None or val < 0:
        await message.answer("❌ Noto'g'ri raqam. Qayta kiriting:")
        return

    await state.update_data(stock=val)
    await state.set_state(AddProduct.unit)
    await message.answer(
        f"📏 <b>Birlik nomini</b> kiriting (yoki <b>⏭ O'tkazib yuborish</b>):\n\n"
        f"Misol: dona, kg, litr, metr...",
        reply_markup=skip_cancel_kb(),
    )


@router.message(AddProduct.unit, F.text)
async def ap_unit(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    if message.text.startswith("⏭"):
        unit = "dona"
    else:
        unit = message.text.strip().lower()
        if len(unit) > 20:
            unit = unit[:20]

    await state.update_data(unit=unit)
    await state.set_state(AddProduct.category)

    async with get_session() as session:
        cats = await get_all_categories(session)

    await message.answer(
        f"📂 <b>Kategoriyani tanlang:</b>",
        reply_markup=categories_pick_kb(cats, prefix="apc"),
    )


@router.callback_query(AddProduct.category, F.data.startswith("apc:"))
async def ap_category(call: CallbackQuery, state: FSMContext) -> None:
    cat_id = int(call.data.split(":")[1])
    if cat_id == 0:
        cat_id = None
    await state.update_data(category_id=cat_id)
    await state.set_state(AddProduct.photo)
    await call.message.answer(
        f"📷 <b>Mahsulot rasmini yuboring</b>\n\n"
        f"Yoki <b>⏭ O'tkazib yuborish</b> tugmasini bosing:",
        reply_markup=skip_cancel_kb(),
    )
    await call.answer()


@router.message(AddProduct.photo, F.photo)
async def ap_photo(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)
    await state.set_state(AddProduct.description)
    await message.answer(
        "📝 <b>Tavsif kiriting</b> (yoki <b>⏭ O'tkazib yuborish</b>):",
        reply_markup=skip_cancel_kb(),
    )


@router.message(AddProduct.photo, F.text)
async def ap_photo_skip(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return
    if message.text.startswith("⏭"):
        await state.set_state(AddProduct.description)
        await message.answer(
            "📝 <b>Tavsif kiriting</b> (yoki <b>⏭ O'tkazib yuborish</b>):",
            reply_markup=skip_cancel_kb(),
        )
    else:
        await message.answer("Iltimos, rasm yuboring yoki o'tkazib yuboring:")


@router.message(AddProduct.description, F.text)
async def ap_description(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    desc = None if message.text.startswith("⏭") else message.text.strip()
    data = await state.get_data()

    async with get_session() as session:
        product = await create_product(
            session,
            name=data["name"],
            cost_price=data["cost"],
            sale_price=data["sell"],
            stock_quantity=data["stock"],
            unit=data.get("unit", "dona"),
            category_id=data.get("category_id"),
            photo_file_id=data.get("photo_file_id"),
            description=desc,
        )
        pid = product.id
        pname = product.name

    await state.clear()
    await message.answer(
        f"✅ <b>Mahsulot qo'shildi!</b>\n\n"
        f"📦 {pname}\n"
        f"🆔 ID: {pid}\n\n"
        f"Endi mijozlar uni katalogdan ko'rishi mumkin!",
        reply_markup=admin_main_kb(),
    )


# ─── TAHRIRLASH ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ap:edit:"))
async def edit_field_start(call: CallbackQuery, state: FSMContext) -> None:
    parts = call.data.split(":")
    field = parts[2]
    pid = int(parts[3])

    field_prompts = {
        "name": ("nomini", "📝", "matn"),
        "cost": ("tan narxini", "🏷", "raqam"),
        "sell": ("sotuv narxini", "💰", "raqam"),
        "desc": ("tavsifini", "📝", "matn"),
        "photo": ("rasmini", "📷", "rasm"),
        "cat": ("kategoriyasini", "📂", "tanlash"),
    }
    label, icon, kind = field_prompts.get(field, ("ma'lumotini", "✏️", "matn"))

    await state.update_data(edit_pid=pid, edit_field=field)
    await state.set_state(EditProductField.value)

    if field == "cat":
        async with get_session() as session:
            cats = await get_all_categories(session)
        await call.message.answer(
            f"{icon} Yangi kategoriyani tanlang:",
            reply_markup=categories_pick_kb(cats, prefix="apec"),
        )
    elif field == "photo":
        await call.message.answer(
            f"{icon} Yangi rasm yuboring:",
            reply_markup=cancel_kb(),
        )
    else:
        await call.message.answer(
            f"{icon} Yangi {label} kiriting:",
            reply_markup=cancel_kb(),
        )
    await call.answer()


@router.callback_query(EditProductField.value, F.data.startswith("apec:"))
async def edit_category_apply(call: CallbackQuery, state: FSMContext) -> None:
    cat_id = int(call.data.split(":")[1])
    if cat_id == 0:
        cat_id = None
    data = await state.get_data()
    pid = data["edit_pid"]
    async with get_session() as session:
        await update_product(session, pid, category_id=cat_id)
    await state.clear()
    await call.message.answer("✅ Kategoriya yangilandi", reply_markup=admin_main_kb())
    await call.answer()


@router.message(EditProductField.value, F.photo)
async def edit_photo_apply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("edit_field") != "photo":
        return
    photo_id = message.photo[-1].file_id
    async with get_session() as session:
        await update_product(session, data["edit_pid"], photo_file_id=photo_id)
    await state.clear()
    await message.answer("✅ Rasm yangilandi", reply_markup=admin_main_kb())


@router.message(EditProductField.value, F.text)
async def edit_value_apply(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return

    data = await state.get_data()
    pid = data["edit_pid"]
    field = data["edit_field"]
    text = message.text.strip()

    fields_map = {
        "name": ("name", text, "matn"),
        "desc": ("description", text, "matn"),
        "cost": ("cost_price", parse_amount(text), "raqam"),
        "sell": ("sale_price", parse_amount(text), "raqam"),
    }
    if field not in fields_map:
        await state.clear()
        return

    db_field, value, kind = fields_map[field]

    if kind == "raqam" and (value is None or value < 0):
        await message.answer("❌ Noto'g'ri raqam. Qayta kiriting:")
        return

    async with get_session() as session:
        await update_product(session, pid, **{db_field: value})

    await state.clear()
    await message.answer(f"✅ Yangilandi", reply_markup=admin_main_kb())


# ─── KATEGORIYALAR ────────────────────────────────────────────────────

@router.callback_query(F.data == "ap:cats")
async def cats_menu(call: CallbackQuery) -> None:
    async with get_session() as session:
        cats = await get_all_categories(session)
    text = "📂 <b>Kategoriyalar</b>\n\n"
    if not cats:
        text += "Hozircha kategoriyalar yo'q."
    else:
        for c in cats:
            text += f"• {c.name}\n"
    await call.message.edit_text(text, reply_markup=categories_admin_kb(cats))
    await call.answer()


@router.callback_query(F.data == "ap:catnew")
async def cat_new(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddCategory.name)
    await call.message.answer(
        "📂 Yangi kategoriya nomini kiriting:",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AddCategory.name, F.text)
async def cat_new_save(message: Message, state: FSMContext) -> None:
    if message.text.startswith("❌"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Nom juda qisqa")
        return
    async with get_session() as session:
        await create_category(session, name)
    await state.clear()
    await message.answer(f"✅ '{name}' kategoriyasi yaratildi", reply_markup=admin_main_kb())


@router.callback_query(F.data.startswith("ap:catdel:"))
async def cat_del(call: CallbackQuery) -> None:
    cat_id = int(call.data.split(":")[2])
    async with get_session() as session:
        await delete_category(session, cat_id)
    await call.answer("🗑 Kategoriya o'chirildi", show_alert=True)
    # Menyu yangilash
    async with get_session() as session:
        cats = await get_all_categories(session)
    text = "📂 <b>Kategoriyalar</b>\n\n"
    for c in cats:
        text += f"• {c.name}\n"
    if not cats:
        text += "Hozircha kategoriyalar yo'q."
    try:
        await call.message.edit_text(text, reply_markup=categories_admin_kb(cats))
    except Exception:
        pass
