"""
SQLAlchemy async engine va session
PostgreSQL (production) yoki SQLite (lokal) ni qo'llab-quvvatlaydi
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


def _build_db_url() -> str:
    """
    Database URL ni qurish:
    - DATABASE_URL env bor bo'lsa - PostgreSQL (Render production)
    - Aks holda - SQLite (lokal sinov)
    """
    db_url = os.getenv("DATABASE_URL", "").strip()

    if db_url:
        # Render `postgres://` beradi, SQLAlchemy `postgresql+asyncpg://` kutadi
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        logging.info("🗄  Database: PostgreSQL (Render)")
        return db_url

    # Lokal SQLite
    logging.info(f"🗄  Database: SQLite ({settings.db_path})")
    return f"sqlite+aiosqlite:///{settings.db_path}"


engine = create_async_engine(
    _build_db_url(),
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
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

        existing_cats = (await session.execute(select(Category))).scalars().all()
        if not existing_cats:
            for cat_name in ["Asosiy", "Yangi mahsulotlar", "Aksiya"]:
                session.add(Category(name=cat_name))

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
    """
    Eski savdo.db dan ko'chirish (faqat lokal SQLite uchun).
    Production (PostgreSQL) da bu o'tkazib yuboriladi.
    """
    if os.getenv("DATABASE_URL"):
        return

    if not os.path.exists(settings.old_db_path):
        return

    logging.info(f"📦 Eski baza topildi: {settings.old_db_path} - ko'chirilmoqda...")

    try:
        old_conn = sqlite3.connect(settings.old_db_path)
        old_conn.row_factory = sqlite3.Row

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
            existing_count = len(
                (await session.execute(select(Product))).scalars().all()
            )
            if existing_count > 0:
                logging.info("✅ Bazada mahsulotlar bor, ko'chirish o'tkazib yuborildi")
                return

            default_cat = (await session.execute(
                select(Category).where(Category.name == "Asosiy")
            )).scalar_one_or_none()

            count = 0
            for row in old_products:
                session.add(Product(
                    name=row['name'],
                    cost_price=row['cost_price'] or 0,
                    sale_price=row['sell_price'] or 0,
                    stock_quantity=row['stock'] or 0,
                    category_id=default_cat.id if default_cat else None,
                    is_active=True,
                ))
                count += 1

            logging.info(f"✅ {count} ta mahsulot ko'chirildi")
    except Exception as e:
        logging.error(f"❌ Eski bazadan ko'chirishda xato: {e}")
