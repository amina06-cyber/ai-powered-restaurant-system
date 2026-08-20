from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import requests
import database
import models
import schemas

router = APIRouter()

@router.post("/orders")
def create_order(order: schemas.OrderCreate, db: Session = Depends(database.get_db)):
    # 1. Find or create the customer
    customer = db.query(models.Customer).filter(
        models.Customer.phone == order.customer_phone
    ).first()

    if not customer:
        customer = models.Customer(
            name=order.customer_name,
            phone=order.customer_phone,
            email=order.customer_email
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
    else:
        # Update customer details if new information is provided
        customer.name = order.customer_name

        if order.customer_email:
            customer.email = order.customer_email

        db.commit()
        db.refresh(customer)

    # 2. Create the order shell
    new_order = models.Order(
        customer_id=customer.id,
        delivery_address=order.delivery_address,
        status=models.OrderStatus.confirmed,
        total_price=0.0
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # 3. Add each item and get the real price from the menu
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

    # 4. Update total
    new_order.total_price = total
    db.commit()
    db.refresh(new_order)

    # 5. Trigger n8n order confirmation workflow
    try:
        items_summary = [
            {
                "name": db.query(models.MenuItem)
                .filter(models.MenuItem.id == item.menu_item_id)
                .first()
                .name,
                "quantity": item.quantity
            }
            for item in order.items
        ]

        response = requests.post(
            "https://aminaashfaq.app.n8n.cloud/webhook/order-confirmation",
            json={
                "order_id": new_order.id,
                "customer_name": customer.name,
                "customer_email": customer.email,
                "customer_phone": customer.phone,
                "total_price": new_order.total_price,
                "items": items_summary
            },
            timeout=5
        )

        print(
            f"n8n webhook response: "
            f"{response.status_code} - {response.text}"
        )

    except Exception as e:
        print(f"n8n webhook FAILED: {e}")

    return new_order

@router.get("/orders/{order_id}")
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


@router.get("/orders")
def get_all_orders(db: Session = Depends(database.get_db)):
    orders = db.query(models.Order).all()

    result = []
    for order in orders:
        items_list = []
        for order_item in order.items:
            items_list.append({
                "menu_item_name": order_item.menu_item.name,
                "quantity": order_item.quantity,
                "price_at_order": order_item.price_at_order
            })

        result.append({
            "id": order.id,
            "status": order.status,
            "delivery_address": order.delivery_address,
            "total_price": order.total_price,
            "customer_name": order.customer.name,
            "customer_phone": order.customer.phone,
            "items": items_list
        })

    return result


@router.patch("/orders/{order_id}/status")
def update_order_status(order_id: int, update: schemas.OrderStatusUpdate, db: Session = Depends(database.get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()

    if not order:
        return {"error": "Order not found"}

    valid_statuses = [s.value for s in models.OrderStatus]
    if update.status not in valid_statuses:
        return {"error": f"Invalid status. Must be one of: {valid_statuses}"}

    order.status = update.status
    db.commit()
    db.refresh(order)

    return {
        "id": order.id,
        "status": order.status,
        "customer_name": order.customer.name
    }