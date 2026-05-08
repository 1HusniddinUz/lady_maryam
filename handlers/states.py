"""
FSM holatlar
"""

from aiogram.fsm.state import State, StatesGroup


class CustomerRegister(StatesGroup):
    full_name = State()
    phone = State()


class Checkout(StatesGroup):
    address = State()
    phone = State()
    payment = State()
    confirm = State()


class Search(StatesGroup):
    query = State()


class AddProduct(StatesGroup):
    name = State()
    cost = State()
    sell = State()
    stock = State()
    unit = State()
    category = State()
    photo = State()
    description = State()


class EditProductField(StatesGroup):
    value = State()


class StockOp(StatesGroup):
    quantity = State()
    cost_price = State()  # faqat kirim uchun
    reason = State()


class AddExpense(StatesGroup):
    title = State()
    amount = State()


class Broadcast(StatesGroup):
    message = State()
    confirm = State()


class QuickSale(StatesGroup):
    quantity = State()
    custom_price = State()  # Boshqa narx kiritish (chegirma yoki ko'tarish)
    buyer = State()


class AddCategory(StatesGroup):
    name = State()


class CustomAddress(StatesGroup):
    address = State()
