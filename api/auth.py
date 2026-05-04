"""
Telegram WebApp initData ni tekshirish (xavfsizlik)

Foydalanuvchi WebApp'ni ochganda Telegram unga signed initData beradi.
Backend bu data'ni serverda tekshirib, kim kirganini bilishi kerak.
"""

import hashlib
import hmac
import json
from typing import Optional, Dict, Any
from urllib.parse import parse_qsl

from config.settings import settings


def verify_telegram_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    """
    Telegram WebApp initData ni tekshiradi.

    Returns: foydalanuvchi ma'lumotlari yoki None (yaroqsiz bo'lsa)
    """
    if not init_data:
        return None

    try:
        # Parse query string
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        # Data check string yarash
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        # Secret key = HMAC-SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            b"WebAppData",
            settings.bot_token.encode(),
            hashlib.sha256,
        ).digest()

        # Hisoblangan hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Tekshirish
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        # User ma'lumotini ajratish
        user_json = parsed.get("user")
        if not user_json:
            return None

        user_data = json.loads(user_json)
        return {
            "user": user_data,
            "auth_date": parsed.get("auth_date"),
            "query_id": parsed.get("query_id"),
        }
    except Exception:
        return None


def get_telegram_id_from_request(request) -> Optional[int]:
    """Request header'dan Telegram ID olish"""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    auth = verify_telegram_init_data(init_data)
    if not auth:
        return None
    user = auth.get("user", {})
    return user.get("id")
