from pydantic import BaseModel
from typing import List
from datetime import datetime


class MenuItemCreate(BaseModel):
    name: str
    description: str = ""
    price: float
    category: str = ""
    available: bool = True
    is_popular: bool = False


class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int


class OrderCreate(BaseModel):
    customer_name: str
    customer_phone: str = ""
    customer_email: str = ""
    delivery_address: str = ""
    items: List[OrderItemCreate]


class OrderStatusUpdate(BaseModel):
    status: str


class ReservationCreate(BaseModel):
    customer_name: str
    customer_phone: str = ""
    table_id: int
    reservation_time: datetime
    party_size: int