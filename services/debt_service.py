"""
Qarzlar xizmati (debts)

Mijoz qarzlarini qayd qilish, to'lovlarni boshqarish, statistika va
eslatma matnlarini (o'zbek shablonlar) tayyorlash.
"""

from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Debt, DebtReminder, DebtStatus
from services.user_service import get_user_by_username
from utils.formatters import fmt_money, fmt_date


# ─── HELPERS ──────────────────────────────────────────────────────────

def outstanding(debt: Debt) -> float:
    """Qoldiq qarz summasi"""
    return max(0.0, debt.total_amount - debt.paid_amount)


def days_until_due(debt: Debt, today: Optional[date] = None) -> int:
    """Muddatgacha qolgan kunlar (manfiy bo'lsa - muddati o'tgan)"""
    today = today or date.today()
    return (debt.due_date - today).days


def is_overdue(debt: Debt, today: Optional[date] = None) -> bool:
    today = today or date.today()
    return debt.status == DebtStatus.ACTIVE and debt.due_date < today


# ─── CRUD ─────────────────────────────────────────────────────────────

async def create_debt(
    session: AsyncSession,
    *,
    customer_name: str,
    customer_phone: str,
    customer_telegram: Optional[str] = None,
    items: Optional[list] = None,
    total_amount: float,
    taken_date: Optional[date] = None,
    due_date: date,
    notes: Optional[str] = None,
) -> Debt:
    """Yangi qarz yaratadi. Mijoz bot foydalanuvchisi bo'lsa - chat_id'ni bog'laydi."""
    customer_user_id = None
    customer_chat_id = None

    if customer_telegram:
        user = await get_user_by_username(session, customer_telegram)
        if user:
            customer_user_id = user.id
            customer_chat_id = user.telegram_id

    debt = Debt(
        customer_user_id=customer_user_id,
        customer_chat_id=customer_chat_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_telegram=(customer_telegram.lstrip("@") if customer_telegram else None),
        items=items or [],
        total_amount=total_amount,
        paid_amount=0.0,
        taken_date=taken_date or date.today(),
        due_date=due_date,
        notes=notes,
        status=DebtStatus.ACTIVE,
    )
    session.add(debt)
    await session.flush()
    return debt


async def get_debt(session: AsyncSession, debt_id: int) -> Optional[Debt]:
    stmt = (
        select(Debt)
        .options(selectinload(Debt.reminders))
        .where(Debt.id == debt_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_debts(
    session: AsyncSession,
    status_filter: str = "all",
    search: Optional[str] = None,
) -> List[Debt]:
    """status_filter: all | active | overdue | paid"""
    stmt = select(Debt)

    today = date.today()
    if status_filter == "active":
        stmt = stmt.where(Debt.status == DebtStatus.ACTIVE)
    elif status_filter == "overdue":
        stmt = stmt.where(Debt.status == DebtStatus.ACTIVE, Debt.due_date < today)
    elif status_filter == "paid":
        stmt = stmt.where(Debt.status == DebtStatus.PAID)

    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(
            Debt.customer_name.ilike(like),
            Debt.customer_phone.ilike(like),
            Debt.customer_telegram.ilike(like),
        ))

    stmt = stmt.order_by(Debt.due_date.asc(), Debt.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


async def add_payment(session: AsyncSession, debt_id: int, amount: float) -> Optional[Debt]:
    """Qarzga to'lov qo'shadi. To'liq qoplansa - status 'to'langan'."""
    debt = await get_debt(session, debt_id)
    if not debt or amount <= 0:
        return debt

    debt.paid_amount += amount
    if debt.paid_amount >= debt.total_amount:
        debt.paid_amount = debt.total_amount
        debt.status = DebtStatus.PAID
    await session.flush()
    return debt


async def update_debt(session: AsyncSession, debt_id: int, **fields) -> Optional[Debt]:
    debt = await get_debt(session, debt_id)
    if not debt:
        return None
    allowed = {
        "customer_name", "customer_phone", "customer_telegram",
        "items", "total_amount", "paid_amount", "due_date", "notes", "status",
    }
    for key, value in fields.items():
        if key in allowed and value is not None:
            setattr(debt, key, value)
    await session.flush()
    return debt


async def delete_debt(session: AsyncSession, debt_id: int) -> bool:
    debt = await get_debt(session, debt_id)
    if not debt:
        return False
    await session.delete(debt)
    return True


# ─── STATISTIKA ───────────────────────────────────────────────────────

async def get_debt_stats(session: AsyncSession) -> dict:
    today = date.today()

    total_outstanding = (await session.execute(
        select(func.coalesce(func.sum(Debt.total_amount - Debt.paid_amount), 0.0))
        .where(Debt.status == DebtStatus.ACTIVE)
    )).scalar() or 0.0

    active_count = (await session.execute(
        select(func.count(Debt.id)).where(Debt.status == DebtStatus.ACTIVE)
    )).scalar() or 0

    overdue_count = (await session.execute(
        select(func.count(Debt.id)).where(
            Debt.status == DebtStatus.ACTIVE, Debt.due_date < today
        )
    )).scalar() or 0

    paid_count = (await session.execute(
        select(func.count(Debt.id)).where(Debt.status == DebtStatus.PAID)
    )).scalar() or 0

    return {
        "total_outstanding": float(total_outstanding),
        "active_count": int(active_count),
        "overdue_count": int(overdue_count),
        "paid_count": int(paid_count),
    }


# ─── SCHEDULER YORDAMCHILARI ──────────────────────────────────────────

async def get_due_debts(session: AsyncSession, today: Optional[date] = None) -> List[Debt]:
    """
    Muddati kelgan (yoki o'tgan), hali to'liq to'lanmagan va bugun eslatma
    yuborilmagan qarzlar — scheduler uchun.
    """
    today = today or date.today()
    today_start = datetime(today.year, today.month, today.day)

    reminded_today = select(DebtReminder.debt_id).where(
        DebtReminder.sent_at >= today_start
    )

    stmt = select(Debt).where(
        Debt.status == DebtStatus.ACTIVE,
        Debt.due_date <= today,
        Debt.paid_amount < Debt.total_amount,
        ~Debt.id.in_(reminded_today),
    )
    return list((await session.execute(stmt)).scalars().all())


async def bind_customer_chat(
    session: AsyncSession,
    debt_id: int,
    chat_id: int,
    user_id: Optional[int] = None,
) -> bool:
    """Deep-link orqali mijoz chat_id'sini qarzga bog'laydi (bo'sh bo'lsa)."""
    debt = await get_debt(session, debt_id)
    if not debt:
        return False
    if not debt.customer_chat_id:
        debt.customer_chat_id = chat_id
        if user_id and not debt.customer_user_id:
            debt.customer_user_id = user_id
        await session.flush()
        return True
    return False


async def log_reminder(
    session: AsyncSession,
    debt_id: int,
    tone: str,
    message: str,
    delivery_status: str,
    channel: str = "telegram",
) -> DebtReminder:
    rem = DebtReminder(
        debt_id=debt_id,
        tone=tone,
        message=message,
        delivery_status=delivery_status,
        channel=channel,
    )
    session.add(rem)
    await session.flush()
    return rem


# ─── ESLATMA MATNI (O'ZBEK SHABLONLAR) ────────────────────────────────

def generate_reminder_text(debt: Debt, tone: str = "polite") -> str:
    """
    Mijozga yuboriladigan o'zbekcha eslatma matni.
    tone: polite | urgent | friendly
    """
    days = days_until_due(debt)
    amount = fmt_money(outstanding(debt))
    due = fmt_date(debt.due_date)
    name = debt.customer_name

    if days < 0:
        day_line = f"To'lov muddati <b>{abs(days)} kun</b> avval o'tib ketdi."
    elif days == 0:
        day_line = "To'lov muddati <b>bugun</b> tugaydi."
    else:
        day_line = f"To'lov muddatigacha <b>{days} kun</b> qoldi."

    if tone == "urgent":
        body = (
            f"Hurmatli <b>{name}</b>,\n\n"
            f"Sizning <b>{amount}</b> miqdoridagi qarzingiz bo'yicha eslatma. {day_line}\n"
            f"Iltimos, to'lovni imkon qadar tezroq amalga oshiring ({due}).\n\n"
            f"Tushunganingiz uchun rahmat."
        )
    elif tone == "friendly":
        body = (
            f"Assalomu alaykum, <b>{name}</b>! 🌸\n\n"
            f"Kichik eslatma: <b>{amount}</b> qarzingiz bor. {day_line}\n"
            f"Qulay vaqtda ({due} gacha) to'lab qo'ysangiz bo'ladi. Rahmat! 💐"
        )
    else:  # polite
        body = (
            f"Hurmatli <b>{name}</b>,\n\n"
            f"Sizda <b>{amount}</b> miqdorida qarz mavjud. {day_line}\n"
            f"Iltimos, to'lovni belgilangan muddatda ({due}) amalga oshiring.\n\n"
            f"Hamkorligingiz uchun rahmat."
        )

    return f"{body}\n\n— <i>Lady Maryam Atelier</i>"
