"""
Sozlamalar xizmati
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AppSetting
from config.settings import settings


async def get_setting(
    session: AsyncSession,
    key: str,
    default: Optional[str] = None,
) -> Optional[str]:
    stmt = select(AppSetting).where(AppSetting.key == key)
    s = (await session.execute(stmt)).scalar_one_or_none()
    return s.value if s else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    stmt = select(AppSetting).where(AppSetting.key == key)
    s = (await session.execute(stmt)).scalar_one_or_none()
    if s:
        s.value = value
    else:
        session.add(AppSetting(key=key, value=value))


async def get_tax_rate(session: AsyncSession) -> float:
    val = await get_setting(session, "tax_rate", str(settings.default_tax_rate))
    try:
        return float(val)
    except (ValueError, TypeError):
        return settings.default_tax_rate


async def get_tax_name(session: AsyncSession) -> str:
    return await get_setting(session, "tax_name", settings.default_tax_name) or settings.default_tax_name


async def set_tax(session: AsyncSession, name: str, rate: float) -> None:
    await set_setting(session, "tax_name", name)
    await set_setting(session, "tax_rate", str(rate))
