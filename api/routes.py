"""
WebApp API endpoint'lari (v4) — wishlist, my orders, search qo'shildi
"""

import logging
from datetime import date
from aiohttp import web
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from config.settings import settings
from database.engine import get_session
from database.models import (
    Product, Category, OrderStatus, PaymentMethod, WishlistItem, DebtStatus
)
from services.product_service import (
    get_all_products, get_product, get_all_categories, search_products
)
from services.cart_service import (
    add_to_cart, get_cart, update_cart_quantity, clear_cart, cart_total
)
from services.order_service import (
    create_order_from_cart, get_order, get_user_orders
)
from services.user_service import get_or_create_user, is_admin
from services.debt_service import (
    create_debt, get_debt, list_debts, add_payment, update_debt, delete_debt,
    get_debt_stats, generate_reminder_text, log_reminder, outstanding,
)
from api.auth import get_telegram_id_from_request, verify_telegram_init_data


# ─── HELPERS ──────────────────────────────────────────────────────────

async def _get_user_or_unauthorized(request):
    tg_id = get_telegram_id_from_request(request)
    if not tg_id:
        return None, None, web.json_response({"error": "Unauthorized"}, status=401)

    init_data = request.headers.get("X-Telegram-Init-Data", "")
    auth = verify_telegram_init_data(init_data)
    user_data = auth.get("user", {}) if auth else {}

    full_name = (
        user_data.get("first_name", "User") +
        (" " + user_data.get("last_name", "") if user_data.get("last_name") else "")
    )

    async with get_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=tg_id,
            full_name=full_name,
            username=user_data.get("username"),
        )
        return user.id, full_name, None


async def _get_admin_or_unauthorized(request):
    """Faqat adminlar uchun. Returns (tg_id, None) yoki (None, error_response)."""
    tg_id = get_telegram_id_from_request(request)
    if not tg_id:
        return None, web.json_response({"error": "Unauthorized"}, status=401)
    async with get_session() as session:
        if not await is_admin(session, tg_id):
            return None, web.json_response({"error": "Forbidden"}, status=403)
    return tg_id, None


def _parse_iso_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def _debt_to_dict(debt, today=None) -> dict:
    today = today or date.today()
    days = (debt.due_date - today).days if debt.due_date else None
    overdue = debt.status == DebtStatus.ACTIVE and debt.due_date and debt.due_date < today
    return {
        "id": debt.id,
        "customer_name": debt.customer_name,
        "customer_phone": debt.customer_phone,
        "customer_telegram": debt.customer_telegram,
        "items": debt.items or [],
        "total_amount": debt.total_amount,
        "paid_amount": debt.paid_amount,
        "outstanding": outstanding(debt),
        "taken_date": debt.taken_date.isoformat() if debt.taken_date else None,
        "due_date": debt.due_date.isoformat() if debt.due_date else None,
        "days_until_due": days,
        "is_overdue": bool(overdue),
        "notes": debt.notes,
        "status": debt.status.value,
        "has_chat": debt.customer_chat_id is not None,
    }


def _product_to_dict(p, full=False) -> dict:
    data = {
        "id": p.id,
        "name": p.name,
        "price": p.sale_price,
        "stock": p.stock_quantity,
        "in_stock": p.stock_quantity > 0,
        "unit": p.unit,
        "photo_url": f"/api/photo/{p.id}" if p.photo_file_id else None,
        "category_id": p.category_id,
    }
    if full:
        data.update({
            "description": p.description,
            "barcode": p.barcode,
        })
    return data


# ─── SHOP INFO ────────────────────────────────────────────────────────

async def api_shop_info(request: web.Request):
    return web.json_response({
        "name": settings.shop_name,
        "phone": settings.shop_phone,
        "address": settings.shop_address,
        "description": settings.shop_description,
    })


# ─── PHOTO PROXY ──────────────────────────────────────────────────────

async def api_product_photo(request: web.Request):
    pid = int(request.match_info["id"])
    async with get_session() as session:
        p = await get_product(session, pid)
        if not p or not p.photo_file_id:
            raise web.HTTPNotFound()
        file_id = p.photo_file_id

    bot = request.app.get("bot")
    if not bot:
        raise web.HTTPInternalServerError(text="Bot not available")

    try:
        file = await bot.get_file(file_id)
        bio = await bot.download_file(file.file_path)
        data = bio.read()

        ext = (file.file_path or "").lower()
        if ext.endswith(".png"):
            ctype = "image/png"
        elif ext.endswith(".webp"):
            ctype = "image/webp"
        else:
            ctype = "image/jpeg"

        return web.Response(
            body=data,
            content_type=ctype,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception as e:
        logging.warning(f"Photo proxy xato (product {pid}): {e}")
        raise web.HTTPNotFound()


# ─── PRODUCTS + SEARCH ────────────────────────────────────────────────

async def api_products(request: web.Request):
    cat_id = request.query.get("category_id")
    featured = request.query.get("featured") == "1"
    search_q = (request.query.get("search") or "").strip()
    sort_by = request.query.get("sort", "newest")  # newest | price_asc | price_desc | name
    limit = int(request.query.get("limit", 100))

    async with get_session() as session:
        if search_q:
            products = await search_products(session, search_q)
        else:
            products = await get_all_products(
                session,
                only_active=True,
                only_in_stock=False,
                category_id=int(cat_id) if cat_id else None,
            )

    # Sort
    if sort_by == "price_asc":
        products.sort(key=lambda p: p.sale_price)
    elif sort_by == "price_desc":
        products.sort(key=lambda p: -p.sale_price)
    elif sort_by == "name":
        products.sort(key=lambda p: p.name.lower())
    else:  # newest
        products.sort(key=lambda p: p.created_at, reverse=True)

    if featured:
        products = products[:6]
    else:
        products = products[:limit]

    return web.json_response({
        "products": [_product_to_dict(p) for p in products],
        "count": len(products),
    })


async def api_product_detail(request: web.Request):
    pid = int(request.match_info["id"])
    async with get_session() as session:
        p = await get_product(session, pid)
        if not p or not p.is_active:
            return web.json_response({"error": "Not found"}, status=404)
        cat_name = p.category.name if p.category else None
        result = _product_to_dict(p, full=True)
        result["category_name"] = cat_name
        return web.json_response(result)


async def api_categories(request: web.Request):
    async with get_session() as session:
        cats = await get_all_categories(session)
    return web.json_response({
        "categories": [{"id": c.id, "name": c.name} for c in cats]
    })


# ─── CART ─────────────────────────────────────────────────────────────

async def api_cart_get(request: web.Request):
    user_id, _, err = await _get_user_or_unauthorized(request)
    if err: return err

    async with get_session() as session:
        cart = await cart_total(session, user_id)
        items = []
        for ci in cart["items"]:
            items.append({
                "product_id": ci.product.id,
                "name": ci.product.name,
                "price": ci.product.sale_price,
                "quantity": ci.quantity,
                "total": ci.quantity * ci.product.sale_price,
                "photo": f"/api/photo/{ci.product.id}" if ci.product.photo_file_id else None,
                "max_stock": ci.product.stock_quantity,
            })
        return web.json_response({
            "items": items,
            "total": cart["total"],
            "count": cart["count"],
        })


async def api_cart_add(request: web.Request):
    user_id, _, err = await _get_user_or_unauthorized(request)
    if err: return err

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    product_id = int(data.get("product_id", 0))
    quantity = float(data.get("quantity", 1))

    if product_id <= 0 or quantity <= 0:
        return web.json_response({"error": "Invalid params"}, status=400)

    async with get_session() as session:
        item = await add_to_cart(session, user_id, product_id, quantity)
        if not item:
            return web.json_response({"error": "Cannot add"}, status=400)
        cart = await cart_total(session, user_id)

    return web.json_response({
        "success": True,
        "cart_total": cart["total"],
        "cart_count": cart["count"],
    })


async def api_cart_update(request: web.Request):
    user_id, _, err = await _get_user_or_unauthorized(request)
    if err: return err

    data = await request.json()
    product_id = int(data.get("product_id", 0))
    quantity = float(data.get("quantity", 0))

    async with get_session() as session:
        await update_cart_quantity(session, user_id, product_id, quantity)
        cart = await cart_total(session, user_id)

    return web.json_response({
        "success": True,
        "cart_total": cart["total"],
        "cart_count": cart["count"],
    })


async def api_cart_clear(request: web.Request):
    user_id, _, err = await _get_user_or_unauthorized(request)
    if err: return err

    async with get_session() as session:
        await clear_cart(session, user_id)

    return web.json_response({"success": True})


# ─── WISHLIST ─────────────────────────────────────────────────────────

async def api_wishlist_get(request: web.Request):
    """GET /api/wishlist - foydalanuvchi sevimlilari"""
    user_id, _, err = await _get_user_or_unauthorized(request)
    if err: return err

    async with get_session() as session:
        stmt = (
            select(WishlistItem)
            .options(selectinload(WishlistItem.product))
            .where(WishlistItem.user_id == user_id)
            .order_by(WishlistItem.created_at.desc())
        )
        items = list((await session.execute(stmt)).scalars().all())

        products = []
        ids = []
        for item in items:
            p = item.product
            if p and p.is_active:
                products.append(_product_to_dict(p))
                ids.append(p.id)

    return web.json_response({
        "products": products,
        "ids": ids,
        "count": len(products),
    })


async def api_wishlist_toggle(request: web.Request):
    """POST /api/wishlist/toggle - qo'shish/o'chirish"""
    user_id, _, err = await _get_user_or_unauthorized(request)
    if err: return err

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    product_id = int(data.get("product_id", 0))
    if product_id <= 0:
        return web.json_response({"error": "Invalid product_id"}, status=400)

    async with get_session() as session:
        # Mahsulot mavjudmi tekshirish
        p = await get_product(session, product_id)
        if not p:
            return web.json_response({"error": "Product not found"}, status=404)

        # Mavjud item ni tekshirish
        stmt = select(WishlistItem).where(
            WishlistItem.user_id == user_id,
            WishlistItem.product_id == product_id,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()

        if existing:
            await session.delete(existing)
            in_wishlist = False
        else:
            session.add(WishlistItem(user_id=user_id, product_id=product_id))
            in_wishlist = True

    return web.json_response({
        "success": True,
        "in_wishlist": in_wishlist,
        "product_id": product_id,
    })


# ─── MY ORDERS ────────────────────────────────────────────────────────

async def api_my_orders(request: web.Request):
    """GET /api/orders/my - foydalanuvchi buyurtmalari tarixi"""
    user_id, _, err = await _get_user_or_unauthorized(request)
    if err: return err

    async with get_session() as session:
        orders = await get_user_orders(session, user_id, limit=50)

        result = []
        for o in orders:
            items_data = []
            for item in o.items:
                items_data.append({
                    "name": item.product_name,
                    "quantity": item.quantity,
                    "price": item.sale_price,
                    "total": item.total,
                    "photo": f"/api/photo/{item.product_id}",
                })
            result.append({
                "id": o.id,
                "status": o.status.value,
                "total_amount": o.total_amount,
                "delivery_address": o.delivery_address,
                "phone": o.phone,
                "payment_method": o.payment_method.value,
                "created_at": o.created_at.isoformat(),
                "items": items_data,
                "items_count": sum(i.quantity for i in o.items),
            })

    return web.json_response({"orders": result})


# ─── ORDER CREATE ─────────────────────────────────────────────────────

async def api_order_create(request: web.Request):
    user_id, full_name, err = await _get_user_or_unauthorized(request)
    if err: return err

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    address = (data.get("address") or "").strip()
    phone = (data.get("phone") or "").strip()
    payment_str = data.get("payment_method", "cash")
    notes = (data.get("notes") or "").strip() or None

    if len(address) < 5:
        return web.json_response({"error": "Manzil kerak"}, status=400)
    if len(phone) < 7:
        return web.json_response({"error": "Telefon kerak"}, status=400)

    method_map = {
        "cash": PaymentMethod.CASH,
        "card": PaymentMethod.CARD,
        "online": PaymentMethod.ONLINE,
    }
    payment_label_map = {
        "cash": "💵 Naqd pul",
        "card": "💳 Plastik karta",
        "online": "📱 Click / Payme",
    }
    method = method_map.get(payment_str, PaymentMethod.CASH)
    payment_label = payment_label_map.get(payment_str, "Naqd pul")

    async with get_session() as session:
        order = await create_order_from_cart(
            session,
            user_id=user_id,
            delivery_address=address,
            phone=phone,
            payment_method=method,
            notes=notes,
        )
        if not order:
            return web.json_response({"error": "Savat bo'sh"}, status=400)

        order_full = await get_order(session, order.id)
        order_id = order_full.id
        order_total = order_full.total_amount
        order_profit = order_full.total_profit

        items_lines = []
        for it in order_full.items:
            items_lines.append(
                f"  • {it.product_name} × {it.quantity:g} = " +
                f"{int(it.total):,}".replace(",", " ") + " so'm"
            )
        items_text = "\n".join(items_lines)

    bot = request.app.get("bot")
    if bot:
        admin_text = (
            f"🔔 <b>YANGI BUYURTMA #{order_id}</b>\n"
            f"<i>(WebApp orqali)</i>\n\n"
            f"👤 Mijoz: <b>{full_name}</b>\n"
            f"📱 Tel: <code>{phone}</code>\n"
            f"📍 Manzil: {address}\n"
            f"💳 To'lov: {payment_label}\n"
        )
        if notes:
            admin_text += f"📝 Izoh: {notes}\n"
        admin_text += (
            f"\n📦 <b>Mahsulotlar:</b>\n{items_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Jami: <b>" + f"{int(order_total):,}".replace(",", " ") + " so'm</b>\n"
            f"📈 Sof foyda: " + f"{int(order_profit):,}".replace(",", " ") + " so'm"
        )

        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(admin_id, admin_text)
            except Exception as e:
                logging.warning(f"Admin xabar xato {admin_id}: {e}")

    return web.json_response({
        "success": True,
        "order_id": order_id,
        "total": order_total,
    })


# ─── ME (admin tekshiruvi) ────────────────────────────────────────────

async def api_me(request: web.Request):
    tg_id = get_telegram_id_from_request(request)
    if not tg_id:
        return web.json_response({"is_admin": False})
    async with get_session() as session:
        admin = await is_admin(session, tg_id)
    return web.json_response({"is_admin": bool(admin)})


# ─── ADMIN: QARZLAR ───────────────────────────────────────────────────

async def api_admin_debts(request: web.Request):
    _, err = await _get_admin_or_unauthorized(request)
    if err:
        return err
    status_filter = request.query.get("status", "all")
    search = request.query.get("search") or None
    async with get_session() as session:
        debts = await list_debts(session, status_filter, search)
        stats = await get_debt_stats(session)
        result = [_debt_to_dict(d) for d in debts]
    return web.json_response({"debts": result, "stats": stats})


async def api_admin_debt_create(request: web.Request):
    _, err = await _get_admin_or_unauthorized(request)
    if err:
        return err
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    customer = data.get("customer") or {}
    name = (customer.get("name") or data.get("customer_name") or "").strip()
    phone = (customer.get("phone") or data.get("customer_phone") or "").strip()
    tg = customer.get("telegram") or data.get("customer_telegram")
    items = data.get("items") or []
    due = _parse_iso_date(data.get("due_date"))
    taken = _parse_iso_date(data.get("taken_date"))

    total = data.get("total_amount")
    if total is None:
        total = sum((it.get("qty", 1) or 0) * (it.get("price", 0) or 0) for it in items)

    if not name or not phone or not due or not total or float(total) <= 0:
        return web.json_response(
            {"error": "name, phone, due_date va total_amount majburiy"}, status=400
        )

    async with get_session() as session:
        debt = await create_debt(
            session,
            customer_name=name,
            customer_phone=phone,
            customer_telegram=tg,
            items=items,
            total_amount=float(total),
            taken_date=taken,
            due_date=due,
            notes=(data.get("notes") or None),
        )
        result = _debt_to_dict(debt)
    return web.json_response({"success": True, "debt": result})


async def api_admin_debt_update(request: web.Request):
    _, err = await _get_admin_or_unauthorized(request)
    if err:
        return err
    debt_id = int(request.match_info["id"])
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    fields = {}
    for k in ("customer_name", "customer_phone", "customer_telegram",
              "notes", "total_amount", "paid_amount", "items"):
        if k in data:
            fields[k] = data[k]
    if "due_date" in data:
        fields["due_date"] = _parse_iso_date(data["due_date"])
    if "status" in data:
        try:
            fields["status"] = DebtStatus(data["status"])
        except ValueError:
            pass

    async with get_session() as session:
        debt = await update_debt(session, debt_id, **fields)
        if not debt:
            return web.json_response({"error": "Topilmadi"}, status=404)
        result = _debt_to_dict(debt)
    return web.json_response({"success": True, "debt": result})


async def api_admin_debt_delete(request: web.Request):
    _, err = await _get_admin_or_unauthorized(request)
    if err:
        return err
    debt_id = int(request.match_info["id"])
    async with get_session() as session:
        ok = await delete_debt(session, debt_id)
    if not ok:
        return web.json_response({"error": "Topilmadi"}, status=404)
    return web.json_response({"success": True})


async def api_admin_debt_payment(request: web.Request):
    _, err = await _get_admin_or_unauthorized(request)
    if err:
        return err
    debt_id = int(request.match_info["id"])
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    amount = float(data.get("amount", 0) or 0)
    if amount <= 0:
        return web.json_response({"error": "Summa noto'g'ri"}, status=400)
    async with get_session() as session:
        debt = await add_payment(session, debt_id, amount)
        if not debt:
            return web.json_response({"error": "Topilmadi"}, status=404)
        result = _debt_to_dict(debt)
    return web.json_response({"success": True, "debt": result})


async def api_admin_debt_reminder(request: web.Request):
    _, err = await _get_admin_or_unauthorized(request)
    if err:
        return err
    debt_id = int(request.match_info["id"])
    try:
        data = await request.json()
    except Exception:
        data = {}
    tone = data.get("tone", "polite")
    bot = request.app.get("bot")

    async with get_session() as session:
        debt = await get_debt(session, debt_id)
        if not debt:
            return web.json_response({"error": "Topilmadi"}, status=404)
        text = generate_reminder_text(debt, tone)
        chat_id = debt.customer_chat_id

        if chat_id and bot:
            try:
                await bot.send_message(chat_id, text)
                await log_reminder(session, debt_id, tone, text, "sent")
                delivery = "sent"
            except (TelegramForbiddenError, TelegramBadRequest):
                await log_reminder(session, debt_id, tone, text, "failed")
                delivery = "failed"
        else:
            await log_reminder(session, debt_id, tone, text, "manual")
            delivery = "manual"

    return web.json_response({"success": True, "delivery_status": delivery, "message": text})


# ─── ROUTES ──────────────────────────────────────────────────────────

def register_api_routes(app: web.Application) -> None:
    app.router.add_get("/api/shop", api_shop_info)
    app.router.add_get("/api/photo/{id}", api_product_photo)

    app.router.add_get("/api/products", api_products)
    app.router.add_get("/api/products/{id}", api_product_detail)
    app.router.add_get("/api/categories", api_categories)

    app.router.add_get("/api/cart", api_cart_get)
    app.router.add_post("/api/cart/add", api_cart_add)
    app.router.add_post("/api/cart/update", api_cart_update)
    app.router.add_post("/api/cart/clear", api_cart_clear)

    app.router.add_get("/api/wishlist", api_wishlist_get)
    app.router.add_post("/api/wishlist/toggle", api_wishlist_toggle)

    app.router.add_get("/api/orders/my", api_my_orders)
    app.router.add_post("/api/orders", api_order_create)

    # Admin — me + qarzlar
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/admin/debts", api_admin_debts)
    app.router.add_post("/api/admin/debts", api_admin_debt_create)
    app.router.add_patch("/api/admin/debts/{id}", api_admin_debt_update)
    app.router.add_delete("/api/admin/debts/{id}", api_admin_debt_delete)
    app.router.add_post("/api/admin/debts/{id}/payment", api_admin_debt_payment)
    app.router.add_post("/api/admin/debts/{id}/reminder", api_admin_debt_reminder)
