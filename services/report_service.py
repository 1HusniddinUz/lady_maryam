"""
Hisobotlar xizmati - asosiy analitika
"""

from datetime import datetime, timedelta
from typing import List, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Order, OrderItem, OrderStatus, Product, User, Expense
)
from services.expense_service import expenses_total


def get_period_range(period: str) -> Tuple[datetime, datetime, str]:
    """Davr nomi -> (boshlanish, tugash, ko'rsatiladigan nomi)"""
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)

    if period == "today":
        return today_start, now, "Bugun"
    if period == "yesterday":
        y_start = today_start - timedelta(days=1)
        return y_start, today_start, "Kecha"
    if period == "week":
        return today_start - timedelta(days=7), now, "Oxirgi 7 kun"
    if period == "month":
        m_start = datetime(now.year, now.month, 1)
        return m_start, now, f"{now.strftime('%B %Y')}"
    if period == "all":
        return datetime(2020, 1, 1), now, "Butun davr"
    return today_start, now, "Bugun"


async def sales_summary(
    session: AsyncSession,
    start: datetime,
    end: datetime,
) -> dict:
    """Davr uchun sotuv summari"""
    # Faqat tasdiqlangan/yetkazilgan/yakunlangan buyurtmalar
    valid_statuses = [OrderStatus.CONFIRMED, OrderStatus.DELIVERING, OrderStatus.COMPLETED]

    stmt = select(
        func.count(Order.id),
        func.coalesce(func.sum(Order.total_amount), 0),
        func.coalesce(func.sum(Order.total_cost), 0),
        func.coalesce(func.sum(Order.tax_amount), 0),
        func.coalesce(func.sum(Order.total_profit), 0),
    ).where(
        and_(
            Order.status.in_(valid_statuses),
            Order.created_at >= start,
            Order.created_at <= end,
        )
    )
    row = (await session.execute(stmt)).one()

    # Mahsulotlar soni
    items_stmt = (
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            and_(
                Order.status.in_(valid_statuses),
                Order.created_at >= start,
                Order.created_at <= end,
            )
        )
    )
    total_items = float((await session.execute(items_stmt)).scalar() or 0)

    expenses = await expenses_total(session, start, end)

    revenue = float(row[1] or 0)
    cost = float(row[2] or 0)
    tax = float(row[3] or 0)
    gross_profit = revenue - cost
    net_after_tax = gross_profit - tax  # Soliqdan keyingi foyda
    final_net = net_after_tax - expenses  # Xarajatlardan keyin sof

    return {
        "orders_count": int(row[0] or 0),
        "items_count": total_items,
        "revenue": revenue,
        "cost": cost,
        "gross_profit": gross_profit,
        "tax": tax,
        "tax_rate": (tax / revenue) if revenue else 0,
        "net_after_tax": net_after_tax,
        "expenses": expenses,
        "final_net": final_net,
        "margin_pct": (gross_profit / revenue * 100) if revenue else 0,
        "net_pct": (final_net / revenue * 100) if revenue else 0,
    }


async def top_products(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    limit: int = 10,
) -> List[dict]:
    """Eng ko'p sotilgan mahsulotlar"""
    valid_statuses = [OrderStatus.CONFIRMED, OrderStatus.DELIVERING, OrderStatus.COMPLETED]

    stmt = (
        select(
            OrderItem.product_id,
            OrderItem.product_name,
            func.sum(OrderItem.quantity).label("qty"),
            func.sum(OrderItem.quantity * OrderItem.sale_price).label("revenue"),
            func.sum(OrderItem.profit).label("profit"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            and_(
                Order.status.in_(valid_statuses),
                Order.created_at >= start,
                Order.created_at <= end,
            )
        )
        .group_by(OrderItem.product_id, OrderItem.product_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "product_id": r[0],
            "name": r[1],
            "quantity": float(r[2] or 0),
            "revenue": float(r[3] or 0),
            "profit": float(r[4] or 0),
        }
        for r in rows
    ]


async def top_customers(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    limit: int = 10,
) -> List[dict]:
    """Eng ko'p xarid qilgan mijozlar"""
    valid_statuses = [OrderStatus.CONFIRMED, OrderStatus.DELIVERING, OrderStatus.COMPLETED]

    stmt = (
        select(
            User.id,
            User.full_name,
            User.phone,
            func.count(Order.id).label("orders"),
            func.sum(Order.total_amount).label("total_spent"),
        )
        .join(Order, Order.user_id == User.id)
        .where(
            and_(
                Order.status.in_(valid_statuses),
                Order.created_at >= start,
                Order.created_at <= end,
            )
        )
        .group_by(User.id)
        .order_by(func.sum(Order.total_amount).desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "user_id": r[0],
            "name": r[1],
            "phone": r[2],
            "orders": int(r[3] or 0),
            "spent": float(r[4] or 0),
        }
        for r in rows
    ]


async def daily_sales_chart_data(
    session: AsyncSession,
    days: int = 30,
) -> List[dict]:
    """Oxirgi N kun uchun kunlik sotuv ma'lumotlari (grafik uchun)"""
    valid_statuses = [OrderStatus.CONFIRMED, OrderStatus.DELIVERING, OrderStatus.COMPLETED]
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    stmt = (
        select(
            func.date(Order.created_at).label("day"),
            func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            func.coalesce(func.sum(Order.total_profit), 0).label("profit"),
            func.count(Order.id).label("orders"),
        )
        .where(
            and_(
                Order.status.in_(valid_statuses),
                Order.created_at >= start,
            )
        )
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "date": str(r[0]),
            "revenue": float(r[1] or 0),
            "profit": float(r[2] or 0),
            "orders": int(r[3] or 0),
        }
        for r in rows
    ]
