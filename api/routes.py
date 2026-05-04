"""
WebApp uchun JSON API endpoint'lari
"""

import json
import logging
from aiohttp import web

from database.engine import get_session
from services.product_service import (
    get_all_products, get_product, get_all_categories
)
from services.cart_service import (
    add_to_cart, get_cart, update_cart_quantity, remove_from_cart, clear_cart, cart_total
)
from services.order_service import create_order_from_cart
from services.user_service import get_or_create_user
from database.models import PaymentMethod
from api.auth import get_telegram_id_from_request, verify_telegram_init_data


# ─── Yordamchi: foydalanuvchi olish ───────────────────────────────────

async def _get_user_or_unauthorized(request):
    """Telegram initData orqali user olish, aks holda 401"""
    tg_id = get_telegram_id_from_request(request)
    if not tg_id:
        return None, web.json_response({"error": "Unauthorized"}, status=401)

    init_data = request.headers.get("X-Telegram-Init-Data", "")
    auth = verify_telegram_init_data(init_data)
    user_data = auth.get("user", {})

    async with get_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=tg_id,
            full_name=user_data.get("first_name", "User") +
                     (" " + user_data.get("last_name", "") if user_data.get("last_name") else ""),
            username=user_data.get("username"),
        )
        return user.id, None


# ─── PRODUCTS ─────────────────────────────────────────────────────────

async def api_products(request: web.Request):
    """
    GET /api/products
    Query params:
      ?category_id=<int>  (ixtiyoriy)
      ?featured=1         (faqat bestseller'lar)
      ?limit=<int>        (default 50)
    """
    cat_id = request.query.get("category_id")
    featured = request.query.get("featured") == "1"
    limit = int(request.query.get("limit", 50))

    async with get_session() as session:
        products = await get_all_products(
            session,
            only_active=True,
            only_in_stock=False,
            category_id=int(cat_id) if cat_id else None,
        )

    # Featured = eng yangi 6 tasi (oddiy mantiq)
    if featured:
        products = sorted(products, key=lambda p: p.created_at, reverse=True)[:6]
    else:
        products = products[:limit]

    return web.json_response({
        "products": [_product_to_dict(p) for p in products]
    })


async def api_product_detail(request: web.Request):
    """GET /api/products/{id}"""
    pid = int(request.match_info["id"])
    async with get_session() as session:
        p = await get_product(session, pid)
        if not p or not p.is_active:
            return web.json_response({"error": "Not found"}, status=404)
        return web.json_response(_product_to_dict(p, full=True))


async def api_categories(request: web.Request):
    """GET /api/categories"""
    async with get_session() as session:
        cats = await get_all_categories(session)
    return web.json_response({
        "categories": [
            {"id": c.id, "name": c.name}
            for c in cats
        ]
    })


# ─── CART ─────────────────────────────────────────────────────────────

async def api_cart_get(request: web.Request):
    """GET /api/cart"""
    user_id, err = await _get_user_or_unauthorized(request)
    if err:
        return err

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
                "photo": ci.product.photo_file_id,
                "max_stock": ci.product.stock_quantity,
            })
        return web.json_response({
            "items": items,
            "total": cart["total"],
            "count": cart["count"],
        })


async def api_cart_add(request: web.Request):
    """POST /api/cart/add  body: {product_id, quantity}"""
    user_id, err = await _get_user_or_unauthorized(request)
    if err:
        return err

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
    """POST /api/cart/update  body: {product_id, quantity}"""
    user_id, err = await _get_user_or_unauthorized(request)
    if err:
        return err

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
    """POST /api/cart/clear"""
    user_id, err = await _get_user_or_unauthorized(request)
    if err:
        return err

    async with get_session() as session:
        await clear_cart(session, user_id)

    return web.json_response({"success": True})


# ─── ORDERS ───────────────────────────────────────────────────────────

async def api_order_create(request: web.Request):
    """POST /api/orders  body: {address, phone, payment_method}"""
    user_id, err = await _get_user_or_unauthorized(request)
    if err:
        return err

    data = await request.json()
    address = (data.get("address") or "").strip()
    phone = (data.get("phone") or "").strip()
    payment_str = data.get("payment_method", "cash")

    if not address or not phone:
        return web.json_response({"error": "Address va phone kerak"}, status=400)

    method_map = {"cash": PaymentMethod.CASH, "card": PaymentMethod.CARD, "online": PaymentMethod.ONLINE}
    method = method_map.get(payment_str, PaymentMethod.CASH)

    async with get_session() as session:
        order = await create_order_from_cart(
            session,
            user_id=user_id,
            delivery_address=address,
            phone=phone,
            payment_method=method,
        )
        if not order:
            return web.json_response({"error": "Cart is empty"}, status=400)

        result = {
            "success": True,
            "order_id": order.id,
            "total": order.total_amount,
        }

    # TODO: Adminlarga xabar yuborish (bot reference kerak)
    return web.json_response(result)


# ─── HELPER ───────────────────────────────────────────────────────────

def _product_to_dict(p, full: bool = False) -> dict:
    """Mahsulotni JSON uchun dict ga aylantirish"""
    data = {
        "id": p.id,
        "name": p.name,
        "price": p.sale_price,
        "stock": p.stock_quantity,
        "in_stock": p.stock_quantity > 0,
        "unit": p.unit,
        "photo_file_id": p.photo_file_id,
        "category_id": p.category_id,
    }
    if full:
        data.update({
            "description": p.description,
            "barcode": p.barcode,
        })
    return data


# ─── ROUTES REGISTRATION ──────────────────────────────────────────────

def register_api_routes(app: web.Application) -> None:
    """API marshrutlarini ulash"""
    app.router.add_get("/api/products", api_products)
    app.router.add_get("/api/products/{id}", api_product_detail)
    app.router.add_get("/api/categories", api_categories)

    app.router.add_get("/api/cart", api_cart_get)
    app.router.add_post("/api/cart/add", api_cart_add)
    app.router.add_post("/api/cart/update", api_cart_update)
    app.router.add_post("/api/cart/clear", api_cart_clear)

    app.router.add_post("/api/orders", api_order_create)
