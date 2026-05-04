"""
Savat xizmati
"""

from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import CartItem, Product, User


async def add_to_cart(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    quantity: float = 1,
) -> Optional[CartItem]:
    # Mavjud item ni tekshirish
    stmt = select(CartItem).where(
        CartItem.user_id == user_id,
        CartItem.product_id == product_id,
    )
    item = (await session.execute(stmt)).scalar_one_or_none()

    product = await session.get(Product, product_id)
    if not product or not product.is_active:
        return None

    if item:
        new_qty = item.quantity + quantity
        if new_qty > product.stock_quantity:
            new_qty = product.stock_quantity
        item.quantity = new_qty
    else:
        if quantity > product.stock_quantity:
            quantity = product.stock_quantity
        if quantity <= 0:
            return None
        item = CartItem(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
        )
        session.add(item)
        await session.flush()
    return item


async def update_cart_quantity(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    quantity: float,
) -> bool:
    stmt = select(CartItem).where(
        CartItem.user_id == user_id,
        CartItem.product_id == product_id,
    )
    item = (await session.execute(stmt)).scalar_one_or_none()
    if not item:
        return False

    if quantity <= 0:
        await session.delete(item)
    else:
        product = await session.get(Product, product_id)
        if product and quantity > product.stock_quantity:
            quantity = product.stock_quantity
        item.quantity = quantity
    return True


async def remove_from_cart(
    session: AsyncSession,
    user_id: int,
    product_id: int,
) -> bool:
    stmt = delete(CartItem).where(
        CartItem.user_id == user_id,
        CartItem.product_id == product_id,
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


async def get_cart(session: AsyncSession, user_id: int) -> List[CartItem]:
    stmt = (
        select(CartItem)
        .options(selectinload(CartItem.product))
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.created_at)
    )
    return list((await session.execute(stmt)).scalars().all())


async def cart_total(session: AsyncSession, user_id: int) -> dict:
    items = await get_cart(session, user_id)
    total = sum(item.quantity * item.product.sale_price for item in items)
    count = sum(item.quantity for item in items)
    return {
        "items": items,
        "total": total,
        "count": count,
    }


async def clear_cart(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(CartItem).where(CartItem.user_id == user_id))
