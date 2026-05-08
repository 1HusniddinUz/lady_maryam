"""
Buyurtma xizmati
"""

from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Order, OrderItem, OrderStatus, PaymentMethod,
    CartItem, Product, StockMovement, StockMovementType, User
)
from services.cart_service import get_cart, clear_cart
from services.settings_service import get_tax_rate


async def create_order_from_cart(
    session: AsyncSession,
    user_id: int,
    delivery_address: str,
    phone: str,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    notes: Optional[str] = None,
) -> Optional[Order]:
    """Savatdan buyurtma yaratadi"""
    cart_items = await get_cart(session, user_id)
    if not cart_items:
        return None

    tax_rate = await get_tax_rate(session)

    order = Order(
        user_id=user_id,
        delivery_address=delivery_address,
        phone=phone,
        payment_method=payment_method,
        notes=notes,
        status=OrderStatus.NEW,
        tax_rate=tax_rate,
    )
    session.add(order)
    await session.flush()

    total_amount = 0.0
    total_cost = 0.0

    for ci in cart_items:
        p = ci.product
        if not p or not p.is_active or p.stock_quantity < ci.quantity:
            continue

        item = OrderItem(
            order_id=order.id,
            product_id=p.id,
            product_name=p.name,
            quantity=ci.quantity,
            sale_price=p.sale_price,
            cost_price=p.cost_price,
            profit=(p.sale_price - p.cost_price) * ci.quantity,
        )
        session.add(item)

        total_amount += ci.quantity * p.sale_price
        total_cost   += ci.quantity * p.cost_price

    order.total_amount = total_amount
    order.total_cost = total_cost
    order.tax_amount = total_amount * tax_rate
    # Sof foyda = tushum - tan narxi - soliq
    order.total_profit = total_amount - total_cost - order.tax_amount

    await clear_cart(session, user_id)
    await session.flush()

    return order


async def create_quick_sale(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    quantity: float,
    buyer_name: str = "Noma'lum",
    custom_price: Optional[float] = None,
) -> Optional[Order]:
    """
    Admin tomonidan tezkor sotuv (savatsiz)
    custom_price: agar berilgan bo'lsa, listed price o'rniga shu narx ishlatiladi
                  (chegirma yoki ko'tarish uchun)
    """
    product = await session.get(Product, product_id)
    if not product or product.stock_quantity < quantity:
        return None

    # Sotuv narxi: custom_price yoki standart sale_price
    actual_price = custom_price if custom_price and custom_price > 0 else product.sale_price

    tax_rate = await get_tax_rate(session)
    total_amount = actual_price * quantity
    total_cost = product.cost_price * quantity
    tax_amount = total_amount * tax_rate

    # Izoh - agar custom_price berilgan bo'lsa
    notes = None
    if custom_price and custom_price != product.sale_price:
        diff = custom_price - product.sale_price
        if diff < 0:
            notes = f"Chegirma: {abs(diff):,.0f} so'm (asl: {product.sale_price:,.0f} → sotilgan: {custom_price:,.0f})"
        else:
            notes = f"Ko'tarilgan narx: +{diff:,.0f} so'm (asl: {product.sale_price:,.0f} → sotilgan: {custom_price:,.0f})"

    order = Order(
        user_id=user_id,
        total_amount=total_amount,
        total_cost=total_cost,
        tax_amount=tax_amount,
        tax_rate=tax_rate,
        total_profit=total_amount - total_cost - tax_amount,
        status=OrderStatus.COMPLETED,
        delivery_address="Do'konda",
        phone=buyer_name,
        payment_method=PaymentMethod.CASH,
        notes=notes,
    )
    session.add(order)
    await session.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        product_name=product.name,
        quantity=quantity,
        sale_price=actual_price,
        cost_price=product.cost_price,
        profit=(actual_price - product.cost_price) * quantity,
    )
    session.add(item)

    # Ombordan ayirish + harakat tarixi
    product.stock_quantity -= quantity
    session.add(StockMovement(
        product_id=product.id,
        type=StockMovementType.SALE,
        quantity=quantity,
        cost_price_at_time=product.cost_price,
        reason=f"Buyurtma #{order.id}",
    ))

    return order


async def confirm_order(session: AsyncSession, order_id: int) -> Optional[Order]:
    """Buyurtmani tasdiqlash + ombordan ayirish"""
    order = await get_order(session, order_id)
    if not order or order.status != OrderStatus.NEW:
        return None

    # Mahsulotlarni ombordan ayirish
    for item in order.items:
        product = await session.get(Product, item.product_id)
        if product:
            product.stock_quantity = max(0, product.stock_quantity - item.quantity)
            session.add(StockMovement(
                product_id=product.id,
                type=StockMovementType.SALE,
                quantity=item.quantity,
                cost_price_at_time=item.cost_price,
                reason=f"Buyurtma #{order.id}",
            ))

    order.status = OrderStatus.CONFIRMED
    return order


async def update_order_status(
    session: AsyncSession,
    order_id: int,
    new_status: OrderStatus,
) -> Optional[Order]:
    order = await get_order(session, order_id)
    if not order:
        return None

    # Bekor qilinganda ombordga qaytarish (agar tasdiqlangan bo'lgan bo'lsa)
    if new_status == OrderStatus.CANCELLED and order.status in (
        OrderStatus.CONFIRMED, OrderStatus.DELIVERING
    ):
        for item in order.items:
            product = await session.get(Product, item.product_id)
            if product:
                product.stock_quantity += item.quantity
                session.add(StockMovement(
                    product_id=product.id,
                    type=StockMovementType.RETURN,
                    quantity=item.quantity,
                    cost_price_at_time=item.cost_price,
                    reason=f"Buyurtma #{order.id} bekor qilindi",
                ))

    order.status = new_status
    return order


async def get_order(session: AsyncSession, order_id: int) -> Optional[Order]:
    stmt = (
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.user),
        )
        .where(Order.id == order_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_orders(
    session: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> List[Order]:
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_orders_by_status(
    session: AsyncSession,
    status: Optional[OrderStatus] = None,
    limit: int = 50,
) -> List[Order]:
    stmt = (
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.user),
        )
    )
    if status:
        stmt = stmt.where(Order.status == status)
    stmt = stmt.order_by(Order.created_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def count_new_orders(session: AsyncSession) -> int:
    stmt = select(func.count(Order.id)).where(Order.status == OrderStatus.NEW)
    return (await session.execute(stmt)).scalar() or 0
