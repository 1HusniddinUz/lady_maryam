"""
Xarajat xizmati
"""

from typing import List
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Expense


async def add_expense(
    session: AsyncSession,
    title: str,
    amount: float,
    category: str = "boshqa",
) -> Expense:
    exp = Expense(title=title, amount=amount, category=category)
    session.add(exp)
    await session.flush()
    return exp


async def get_expenses(
    session: AsyncSession,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 50,
) -> List[Expense]:
    stmt = select(Expense)
    if start:
        stmt = stmt.where(Expense.expense_date >= start)
    if end:
        stmt = stmt.where(Expense.expense_date <= end)
    stmt = stmt.order_by(Expense.expense_date.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def expenses_total(
    session: AsyncSession,
    start: datetime | None = None,
    end: datetime | None = None,
) -> float:
    stmt = select(func.coalesce(func.sum(Expense.amount), 0))
    if start:
        stmt = stmt.where(Expense.expense_date >= start)
    if end:
        stmt = stmt.where(Expense.expense_date <= end)
    return float((await session.execute(stmt)).scalar() or 0)


async def expenses_by_category(
    session: AsyncSession,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    stmt = select(Expense.category, func.coalesce(func.sum(Expense.amount), 0))
    if start:
        stmt = stmt.where(Expense.expense_date >= start)
    if end:
        stmt = stmt.where(Expense.expense_date <= end)
    stmt = stmt.group_by(Expense.category)
    rows = (await session.execute(stmt)).all()
    return {row[0]: float(row[1] or 0) for row in rows}
