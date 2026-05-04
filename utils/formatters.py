"""
Yordamchi format funksiyalar
"""

from datetime import datetime


def fmt_money(amount: float | int | None) -> str:
    """1250000 -> '1 250 000 so'm'"""
    if amount is None:
        amount = 0
    return f"{float(amount):,.0f}".replace(",", " ") + " so'm"


def fmt_qty(qty: float | int | None, unit: str = "dona") -> str:
    """Miqdorni birlik bilan formatlash"""
    if qty is None:
        qty = 0
    if float(qty).is_integer():
        return f"{int(qty)} {unit}"
    return f"{float(qty):.2f} {unit}"


def fmt_pct(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def fmt_date(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d.%m.%Y")


def fmt_datetime(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


def fmt_time(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%H:%M")


def parse_amount(text: str) -> float | None:
    """'1 250 000' yoki '1,250,000' yoki '1250000.50' -> float"""
    if not text:
        return None
    cleaned = text.strip().replace(" ", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def truncate(text: str, max_len: int = 30) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def status_emoji(status: str) -> str:
    """Buyurtma statusiga emoji"""
    return {
        "yangi":         "🆕",
        "tasdiqlangan":  "✅",
        "yetkazilmoqda": "🚚",
        "yakunlangan":   "✔️",
        "bekor":         "❌",
    }.get(status, "📦")


def stock_emoji(qty: float, threshold: int = 5) -> str:
    if qty <= 0:
        return "❌"
    if qty <= threshold:
        return "⚠️"
    return "✅"


def profit_arrow(amount: float) -> str:
    if amount > 0:
        return "📈"
    if amount < 0:
        return "📉"
    return "➖"
