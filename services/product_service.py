"""
Mahsulot xizmati
"""

from typing import Optional, List
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Product, Category, StockMovement, StockMovementType
)


async def create_product(
    session: AsyncSession,
    name: str,
    cost_price: float,
    sale_price: float,
    stock_quantity: float = 0,
    category_id: Optional[int] = None,
    description: Optional[str] = None,
    photo_file_id: Optional[str] = None,
    unit: str = "dona",
    barcode: Optional[str] = None,
) -> Product:
    product = Product(
        name=name,
        cost_price=cost_price,
        sale_price=sale_price,
        stock_quantity=stock_quantity,
        category_id=category_id,
        description=description,
        photo_file_id=photo_file_id,
        unit=unit,
        barcode=barcode,
    )
    session.add(product)
    await session.flush()

    # Boshlang'ich qoldiq uchun kirim yozuvini yaratish
    if stock_quantity > 0:
        session.add(StockMovement(
            product_id=product.id,
            type=StockMovementType.IN,
            quantity=stock_quantity,
            cost_price_at_time=cost_price,
            reason="Boshlang'ich qoldiq",
        ))

    return product


async def get_product(session: AsyncSession, product_id: int) -> Optional[Product]:
    stmt = (
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_all_products(
    session: AsyncSession,
    only_active: bool = True,
    only_in_stock: bool = False,
    category_id: Optional[int] = None,
) -> List[Product]:
    stmt = select(Product).options(selectinload(Product.category))
    if only_active:
        stmt = stmt.where(Product.is_active == True)
    if only_in_stock:
        stmt = stmt.where(Product.stock_quantity > 0)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    stmt = stmt.order_by(Product.name)
    return list((await session.execute(stmt)).scalars().all())


async def search_products(session: AsyncSession, query: str) -> List[Product]:
    q = f"%{query.lower()}%"
    stmt = (
        select(Product)
        .where(Product.is_active == True)
        .where(or_(
            func.lower(Product.name).like(q),
            Product.barcode == query,
        ))
        .order_by(Product.name)
        .limit(20)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_low_stock_products(
    session: AsyncSession,
    threshold: int = 5,
) -> List[Product]:
    stmt = (
        select(Product)
        .where(Product.is_active == True)
        .where(Product.stock_quantity > 0)
        .where(Product.stock_quantity <= threshold)
        .order_by(Product.stock_quantity)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_out_of_stock_products(session: AsyncSession) -> List[Product]:
    stmt = (
        select(Product)
        .where(Product.is_active == True)
        .where(Product.stock_quantity <= 0)
        .order_by(Product.name)
    )
    return list((await session.execute(stmt)).scalars().all())


async def update_product(
    session: AsyncSession,
    product_id: int,
    **fields,
) -> Optional[Product]:
    product = await get_product(session, product_id)
    if not product:
        return None
    for key, value in fields.items():
        if hasattr(product, key) and value is not None:
            setattr(product, key, value)
    return product


async def delete_product(session: AsyncSession, product_id: int) -> bool:
    """Soft delete"""
    product = await get_product(session, product_id)
    if not product:
        return False
    product.is_active = False
    return True


async def stock_in(
    session: AsyncSession,
    product_id: int,
    quantity: float,
    new_cost_price: Optional[float] = None,
    reason: str = "Kirim",
) -> Optional[Product]:
    """Ombordga mahsulot kirim qilish"""
    product = await get_product(session, product_id)
    if not product:
        return None

    if new_cost_price is not None and new_cost_price > 0:
        product.cost_price = new_cost_price

    product.stock_quantity += quantity
    session.add(StockMovement(
        product_id=product.id,
        type=StockMovementType.IN,
        quantity=quantity,
        cost_price_at_time=product.cost_price,
        reason=reason,
    ))
    return product


async def stock_out(
    session: AsyncSession,
    product_id: int,
    quantity: float,
    reason: str = "Chiqim",
) -> Optional[Product]:
    """Ombordan chiqim (buzilgan, yo'qotilgan)"""
    product = await get_product(session, product_id)
    if not product:
        return None
    product.stock_quantity = max(0, product.stock_quantity - quantity)
    session.add(StockMovement(
        product_id=product.id,
        type=StockMovementType.OUT,
        quantity=quantity,
        cost_price_at_time=product.cost_price,
        reason=reason,
    ))
    return product


async def get_stock_history(
    session: AsyncSession,
    product_id: int,
    limit: int = 20,
) -> List[StockMovement]:
    stmt = (
        select(StockMovement)
        .where(StockMovement.product_id == product_id)
        .order_by(StockMovement.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def warehouse_value(session: AsyncSession) -> dict:
    """Ombordagi tovarlar jami qiymati"""
    stmt = select(
        func.coalesce(func.sum(Product.stock_quantity * Product.cost_price), 0),
        func.coalesce(func.sum(Product.stock_quantity * Product.sale_price), 0),
        func.coalesce(func.sum(Product.stock_quantity), 0),
        func.count(Product.id),
    ).where(Product.is_active == True)
    result = (await session.execute(stmt)).one()
    return {
        "cost_value": float(result[0] or 0),
        "sale_value": float(result[1] or 0),
        "total_units": float(result[2] or 0),
        "products_count": int(result[3] or 0),
    }


# ─── KATEGORIYALAR ────────────────────────────────────────────────────

async def get_all_categories(session: AsyncSession, only_active: bool = True) -> List[Category]:
    stmt = select(Category)
    if only_active:
        stmt = stmt.where(Category.is_active == True)
    stmt = stmt.order_by(Category.name)
    return list((await session.execute(stmt)).scalars().all())


async def get_category(session: AsyncSession, category_id: int) -> Optional[Category]:
    return await session.get(Category, category_id)


async def create_category(
    session: AsyncSession,
    name: str,
    parent_id: Optional[int] = None,
) -> Category:
    cat = Category(name=name, parent_id=parent_id)
    session.add(cat)
    await session.flush()
    return cat


async def delete_category(session: AsyncSession, category_id: int) -> bool:
    cat = await get_category(session, category_id)
    if not cat:
        return False
    cat.is_active = False
    return True
