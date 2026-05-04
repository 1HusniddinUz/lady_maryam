"""
Foydalanuvchi xizmati
"""

from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserRole
from config.settings import settings


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str] = None,
    phone: Optional[str] = None,
) -> User:
    """Foydalanuvchini topadi yoki yaratadi"""
    stmt = select(User).where(User.telegram_id == telegram_id)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is None:
        role = UserRole.ADMIN if telegram_id in settings.admin_ids else UserRole.CUSTOMER
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            phone=phone,
            role=role,
        )
        session.add(user)
        await session.flush()
    else:
        # Ma'lumotlarni yangilash
        if username and user.username != username:
            user.username = username
        if phone and not user.phone:
            user.phone = phone
        # Adminlik huquqini tekshirish
        if telegram_id in settings.admin_ids and user.role != UserRole.ADMIN:
            user.role = UserRole.ADMIN

    return user


async def get_user_by_tg_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    stmt = select(User).where(User.telegram_id == telegram_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_all_users(session: AsyncSession, only_customers: bool = False) -> List[User]:
    stmt = select(User).order_by(User.created_at.desc())
    if only_customers:
        stmt = stmt.where(User.role == UserRole.CUSTOMER)
    return list((await session.execute(stmt)).scalars().all())


async def block_user(session: AsyncSession, telegram_id: int, blocked: bool = True) -> bool:
    user = await get_user_by_tg_id(session, telegram_id)
    if user:
        user.is_blocked = blocked
        return True
    return False


async def update_phone(session: AsyncSession, telegram_id: int, phone: str) -> None:
    user = await get_user_by_tg_id(session, telegram_id)
    if user:
        user.phone = phone


async def is_admin(session: AsyncSession, telegram_id: int) -> bool:
    if telegram_id in settings.admin_ids:
        return True
    user = await get_user_by_tg_id(session, telegram_id)
    return bool(user and user.role == UserRole.ADMIN)


async def count_users(session: AsyncSession) -> dict:
    total = (await session.execute(select(func.count(User.id)))).scalar() or 0
    admins = (await session.execute(
        select(func.count(User.id)).where(User.role == UserRole.ADMIN)
    )).scalar() or 0
    blocked = (await session.execute(
        select(func.count(User.id)).where(User.is_blocked == True)
    )).scalar() or 0
    return {
        "total": total,
        "admins": admins,
        "customers": total - admins,
        "blocked": blocked,
    }
