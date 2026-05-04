"""
SQLAlchemy async engine va session
"""

import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy import select

from config.settings import settings
from database.models import (
    Base, User, UserRole, Category, Product, AppSetting,
    StockMovement, StockMovementType
)


engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.db_path}",
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Session olish uchun context manager"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Bazani yaratish va dastlabki sozlamalarni o'rnatish"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Adminlarni yaratish
    async with get_session() as session:
        for admin_id in settings.admin_ids:
            stmt = select(User).where(User.telegram_id == admin_id)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if user:
                if user.role != UserRole.ADMIN:
                    user.role = UserRole.ADMIN
            else:
                session.add(User(
                    telegram_id=admin_id,
                    full_name="Admin",
                    role=UserRole.ADMIN,
                ))

        # Default kategoriyalar
        existing_cats = (await session.execute(select(Category))).scalars().all()
        if not existing_cats:
            for cat_name in ["Asosiy", "Yangi mahsulotlar", "Aksiya"]:
                session.add(Category(name=cat_name))

        # Default sozlamalar
        for key, value in [
            ("tax_rate", str(settings.default_tax_rate)),
            ("tax_name", settings.default_tax_name),
        ]:
            existing = (await session.execute(
                select(AppSetting).where(AppSetting.key == key)
            )).scalar_one_or_none()
            if not existing:
                session.add(AppSetting(key=key, value=value))


async def migrate_old_data() -> None:
    """Eski savdo.db dan ma'lumotlarni ko'chirish"""
    if not os.path.exists(settings.old_db_path):
        return

    logging.info(f"📦 Eski baza topildi: {settings.old_db_path} - ko'chirilmoqda...")

    try:
        old_conn = sqlite3.connect(settings.old_db_path)
        old_conn.row_factory = sqlite3.Row

        # Eski mahsulotlarni o'qish
        try:
            old_products = old_conn.execute(
                "SELECT name, cost_price, sell_price, stock FROM products"
            ).fetchall()
        except sqlite3.OperationalError:
            try:
                old_products = old_conn.execute(
                    "SELECT name, 0 as cost_price, price as sell_price, stock FROM products"
                ).fetchall()
            except sqlite3.OperationalError:
                old_products = []

        old_conn.close()

        if not old_products:
            return

        async with get_session() as session:
            # Tekshirish: agar mahsulot allaqachon bor bo'lsa, ko'chirmaymiz
            existing_count = len(
                (await session.execute(select(Product))).scalars().all()
            )
            if existing_count > 0:
                logging.info("✅ Yangi bazada mahsulotlar mavjud, ko'chirish o'tkazib yuborildi")
                return

            # Default kategoriya
            default_cat = (await session.execute(
                select(Category).where(Category.name == "Asosiy")
            )).scalar_one_or_none()

            count = 0
            for row in old_products:
                product = Product(
                    name=row['name'],
                    cost_price=row['cost_price'] or 0,
                    sale_price=row['sell_price'] or 0,
                    stock_quantity=row['stock'] or 0,
                    category_id=default_cat.id if default_cat else None,
                    is_active=True,
                )
                session.add(product)
                count += 1

            logging.info(f"✅ {count} ta mahsulot ko'chirildi")
    except Exception as e:
        logging.error(f"❌ Eski bazadan ko'chirishda xato: {e}")
