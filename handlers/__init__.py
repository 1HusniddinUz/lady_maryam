"""
Barcha handlerlarni dispatcherga ulash
"""

from aiogram import Dispatcher

from handlers import common
from handlers.customer import catalog as customer_catalog
from handlers.customer import cart as customer_cart
from handlers.customer import orders as customer_orders
from handlers.admin import products as admin_products
from handlers.admin import warehouse as admin_warehouse
from handlers.admin import orders as admin_orders
from handlers.admin import reports as admin_reports
from handlers.admin import expenses as admin_expenses
from handlers.admin import users as admin_users
from handlers.admin import settings as admin_settings
from handlers.admin import quick_sale as admin_quick_sale


def register_all_handlers(dp: Dispatcher) -> None:
    """Routerlarni to'g'ri tartibda ulash"""

    # 1. Umumiy (start, cancel, help) - eng birinchi
    dp.include_router(common.router)

    # 2. Admin handlerlari (filterlar bilan, mijoz handlerlaridan oldin)
    dp.include_router(admin_products.router)
    dp.include_router(admin_warehouse.router)
    dp.include_router(admin_orders.router)
    dp.include_router(admin_reports.router)
    dp.include_router(admin_expenses.router)
    dp.include_router(admin_users.router)
    dp.include_router(admin_settings.router)
    dp.include_router(admin_quick_sale.router)

    # 3. Mijoz handlerlari
    dp.include_router(customer_catalog.router)
    dp.include_router(customer_cart.router)
    dp.include_router(customer_orders.router)
