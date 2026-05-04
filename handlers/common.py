"""
Umumiy handlerlar - /start, /help, mode switch
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, Contact, ReplyKeyboardRemove

from config.settings import settings
from database.engine import get_session
from services.user_service import get_or_create_user, is_admin, update_phone
from keyboards.customer_kb import customer_main_kb, share_phone_kb
from keyboards.admin_kb import admin_main_kb
from handlers.states import CustomerRegister


router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not message.from_user:
        return

    async with get_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )

        if user.is_blocked:
            await message.answer("🚫 Sizning hisobingiz bloklangan.")
            return

        admin_flag = await is_admin(session, message.from_user.id)

        # Telefon yo'q bo'lsa - so'rash (faqat mijozlar uchun)
        if not admin_flag and not user.phone:
            await message.answer(
                f"👋 Salom, <b>{user.full_name}</b>!\n\n"
                f"🛍 <b>{settings.shop_name}</b> rasmiy botiga xush kelibsiz!\n\n"
                f"Davom etish uchun telefon raqamingizni yuboring 👇",
                reply_markup=share_phone_kb(),
            )
            await state.set_state(CustomerRegister.phone)
            return

    if admin_flag:
        await message.answer(
            f"👋 Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n\n"
            f"🛡 Admin paneliga kirdingiz.\n"
            f"📊 <b>{settings.shop_name}</b> ERP tizimi\n\n"
            f"Bo'limni tanlang 👇",
            reply_markup=admin_main_kb(),
        )
    else:
        await message.answer(
            f"👋 Salom, <b>{user.full_name}</b>!\n\n"
            f"🛍 <b>{settings.shop_name}</b> ga xush kelibsiz!\n\n"
            f"Quyidagi menyudan tanlang 👇",
            reply_markup=customer_main_kb(),
        )


@router.message(CustomerRegister.phone, F.contact)
async def get_contact(message: Message, state: FSMContext) -> None:
    contact: Contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer("❌ Iltimos, o'z telefoningizni yuboring.")
        return

    async with get_session() as session:
        await update_phone(session, message.from_user.id, contact.phone_number)

    await state.clear()
    await message.answer(
        f"✅ Ro'yxatdan o'tdingiz!\n\n"
        f"🛍 Endi xarid qilishingiz mumkin.",
        reply_markup=customer_main_kb(),
    )


@router.message(CustomerRegister.phone)
async def phone_invalid(message: Message) -> None:
    await message.answer(
        "📱 Iltimos, telefon raqamni quyidagi tugma orqali yuboring 👇",
        reply_markup=share_phone_kb(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "ℹ️ <b>Yordam</b>\n\n"
        "/start - Botni qayta ishga tushirish\n"
        "/help - Yordam menyusi\n"
        "/cancel - Joriy amalni bekor qilish\n\n"
        "Asosiy menyu tugmalaridan foydalaning."
    )
    await message.answer(text)


@router.message(Command("cancel"))
@router.message(F.text == "❌ Bekor qilish")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with get_session() as session:
        admin = await is_admin(session, message.from_user.id)

    if admin:
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
    else:
        await message.answer("❌ Bekor qilindi.", reply_markup=customer_main_kb())


@router.message(F.text == "🛍 Mijoz rejimi")
async def to_customer_mode(message: Message, state: FSMContext) -> None:
    """Admin mijoz rejimiga o'tadi"""
    async with get_session() as session:
        admin = await is_admin(session, message.from_user.id)
    if not admin:
        return
    await state.clear()
    await message.answer(
        "🛍 Mijoz rejimi yoqildi.\n"
        "Admin panelga qaytish uchun /start buyrug'ini bering.",
        reply_markup=customer_main_kb(),
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    async with get_session() as session:
        admin = await is_admin(session, message.from_user.id)
    if not admin:
        await message.answer("🚫 Sizda admin huquqlari yo'q.")
        return
    await state.clear()
    await message.answer("🛡 Admin panelga qaytdingiz.", reply_markup=admin_main_kb())
