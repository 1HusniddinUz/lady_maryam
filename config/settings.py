"""
Bot konfiguratsiyasi - .env fayldan yoki env variable'lardan o'qiladi
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    bot_token: str
    admin_ids: List[int]
    db_path: str = "erp.db"
    old_db_path: str = "savdo.db"
    database_url: str = ""   # PostgreSQL URL (Render production)

    # Soliq sozlamalari (O'zbekiston)
    default_tax_rate: float = 0.04
    default_tax_name: str = "Aylanma solig'i"

    # Kam qoldiq chegarasi
    low_stock_threshold: int = 5

    # Sahifalashtirish
    products_per_page: int = 8
    orders_per_page: int = 5

    # Do'kon ma'lumotlari
    shop_name: str = "@muhabbat0093"
    shop_description: str = "Sifatli mahsulotlar"
    shop_phone: str = "+998 XX XXX-XX-XX"
    shop_address: str = "Toshkent shahri"

    payment_methods: List[str] = field(default_factory=lambda: [
        "Naqd pul",
        "Plastik karta",
        "Click / Payme",
    ])


def _parse_admin_ids(raw: str) -> List[int]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(';', ',').split(',') if p.strip()]
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            continue
    return result


def _load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

    if not token:
        raise ValueError(
            "❌ BOT_TOKEN topilmadi! .env faylida BOT_TOKEN=... yozing"
        )
    if not admin_ids:
        raise ValueError(
            "❌ ADMIN_IDS topilmadi! .env faylida ADMIN_IDS=123456 yozing"
        )

    return Settings(
        bot_token=token,
        admin_ids=admin_ids,
        db_path=os.getenv("DB_PATH", "erp.db"),
        old_db_path=os.getenv("OLD_DB_PATH", "savdo.db"),
        database_url=os.getenv("DATABASE_URL", ""),
        shop_name=os.getenv("SHOP_NAME", "@muhabbat0093"),
        shop_phone=os.getenv("SHOP_PHONE", "+998 XX XXX-XX-XX"),
        shop_address=os.getenv("SHOP_ADDRESS", "Toshkent shahri"),
    )


settings = _load_settings()
