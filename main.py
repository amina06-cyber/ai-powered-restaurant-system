from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import database, models
from datetime import datetime, timedelta

class ReservationCreate(BaseModel):
    customer_name: str
    customer_phone: str = ""
    table_id: int
    reservation_time: datetime
    party_size: int
class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int

class OrderCreate(BaseModel):
    customer_name: str
    customer_phone: str = ""
    delivery_address: str = ""
    items: List[OrderItemCreate]

class MenuItemCreate(BaseModel):
    name: str
    description: str = ""
    price: float
    category: str = ""
    available: bool = True

app = FastAPI()

models.Base.metadata.create_all(bind=database.engine)

@app.get("/")
def root():
    return {"status": "backend is alive"}

@app.get("/menu")
def get_menu(db: Session = Depends(database.get_db)):
    items = db.query(models.MenuItem).all()
    return items

@app.post("/menu")
def create_menu_item(item: MenuItemCreate, db: Session = Depends(database.get_db)):
    new_item = models.MenuItem(**item.dict())
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

# ---- NEW CODE GOES HERE, AT THE END ----

@app.post("/orders")
def create_order(order: OrderCreate, db: Session = Depends(database.get_db)):
    # 1. Find or create the customer
    customer = db.query(models.Customer).filter(
        models.Customer.phone == order.customer_phone
    ).first()

    if not customer:
        customer = models.Customer(
            name=order.customer_name,
            phone=order.customer_phone
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

    # 2. Create the order shell (total starts at 0, we'll update it)
    new_order = models.Order(
        customer_id=customer.id,
        delivery_address=order.delivery_address,
        status=models.OrderStatus.confirmed,
        total_price=0.0
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # 3. Add each item, look up its real price from the menu
    total = 0.0
    for item in order.items:
        menu_item = db.query(models.MenuItem).filter(
            models.MenuItem.id == item.menu_item_id
        ).first()

        if not menu_item:
            continue

        order_item = models.OrderItem(
            order_id=new_order.id,
            menu_item_id=menu_item.id,
            quantity=item.quantity,
            price_at_order=menu_item.price
        )
        db.add(order_item)
        total += menu_item.price * item.quantity

    # 4. Update the order's total price
    new_order.total_price = total
    db.commit()
    db.refresh(new_order)

    return new_order

@app.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(database.get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        return {"error": "Order not found"}

    items_list = []
    for order_item in order.items:
        items_list.append({
            "menu_item_name": order_item.menu_item.name,
            "quantity": order_item.quantity,
            "price_at_order": order_item.price_at_order
        })

    return {
        "id": order.id,
        "status": order.status,
        "delivery_address": order.delivery_address,
        "total_price": order.total_price,
        "customer_name": order.customer.name,
        "customer_phone": order.customer.phone,
        "items": items_list
    }

@app.post("/reservations")
def create_reservation(res: ReservationCreate, db: Session = Depends(database.get_db)):
    # 1. Find or create the customer
    customer = db.query(models.Customer).filter(
        models.Customer.phone == res.customer_phone
    ).first()

    if not customer:
        customer = models.Customer(
            name=res.customer_name,
            phone=res.customer_phone
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

    # 2. Check the table exists and has enough capacity
    table = db.query(models.Table).filter(models.Table.id == res.table_id).first()
    if not table:
        return {"error": "Table not found"}
    if table.capacity < res.party_size:
        return {"error": f"Table {table.table_number} only seats {table.capacity}, but party size is {res.party_size}"}

    # 3. THE CRITICAL PART: check for overlapping reservations
    # We treat each reservation as blocking a 2-hour window
    window_start = res.reservation_time - timedelta(hours=2)
    window_end = res.reservation_time + timedelta(hours=2)

    conflict = db.query(models.Reservation).filter(
        models.Reservation.table_id == res.table_id,
        models.Reservation.status == models.ReservationStatus.confirmed,
        models.Reservation.reservation_time > window_start,
        models.Reservation.reservation_time < window_end
    ).first()

    if conflict:
        return {"error": f"Table {table.table_number} is already booked near that time. Please choose another time or table."}

    # 4. No conflict — create the reservation
    new_reservation = models.Reservation(
        customer_id=customer.id,
        table_id=res.table_id,
        reservation_time=res.reservation_time,
        party_size=res.party_size,
        status=models.ReservationStatus.confirmed
    )
    db.add(new_reservation)
    db.commit()
    db.refresh(new_reservation)

    return new_reservation

@app.patch("/reservations/{reservation_id}/cancel")
def cancel_reservation(reservation_id: int, db: Session = Depends(database.get_db)):
    reservation = db.query(models.Reservation).filter(
        models.Reservation.id == reservation_id
    ).first()

    if not reservation:
        return {"error": "Reservation not found"}

    reservation.status = models.ReservationStatus.cancelled
    db.commit()
    db.refresh(reservation)

    return reservation

@app.get("/tables/{table_id}/availability")
def check_availability(table_id: int, reservation_time: datetime, db: Session = Depends(database.get_db)):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        return {"error": "Table not found"}

    window_start = reservation_time - timedelta(hours=2)
    window_end = reservation_time + timedelta(hours=2)

    conflict = db.query(models.Reservation).filter(
        models.Reservation.table_id == table_id,
        models.Reservation.status == models.ReservationStatus.confirmed,
        models.Reservation.reservation_time > window_start,
        models.Reservation.reservation_time < window_end
    ).first()

    if conflict:
        return {
            "table_id": table_id,
            "table_number": table.table_number,
            "requested_time": reservation_time,
            "available": False
        }

    return {
        "table_id": table_id,
        "table_number": table.table_number,
        "requested_time": reservation_time,
        "available": True
    }
@app.get("/reservations/{reservation_id}")
def get_reservation(reservation_id: int, db: Session = Depends(database.get_db)):
    reservation = db.query(models.Reservation).filter(
        models.Reservation.id == reservation_id
    ).first()

    if not reservation:
        return {"error": "Reservation not found"}

    return {
        "id": reservation.id,
        "status": reservation.status,
        "reservation_time": reservation.reservation_time,
        "party_size": reservation.party_size,
        "table_number": reservation.table.table_number,
        "customer_name": reservation.customer.name,
        "customer_phone": reservation.customer.phone
    }