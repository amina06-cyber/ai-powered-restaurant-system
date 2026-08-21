from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import database
import models
import json
import requests

from routers import menu, orders, reservations

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=database.engine)


@app.get("/")
def root():
    return {"status": "backend is alive"}


app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(reservations.router)


# ============================================================
# VAPI TOOL BRIDGE
# ============================================================

@app.post("/vapi/tools")
async def vapi_tools(request: Request):

    body = await request.json()

    message = body.get("message", {})

    tool_calls = message.get("toolCalls", [])

    if not tool_calls:
        tool_calls = message.get("toolCallList", [])

    results = []

    # One database session for the tool request
    db: Session = database.SessionLocal()

    try:

        for tool_call in tool_calls:

            tool_name = None
            arguments = {}

            function = tool_call.get("function", {})

            if function:
                tool_name = function.get("name")
                arguments = function.get("arguments", {})

            if not tool_name:
                tool_name = tool_call.get("name")

            if not arguments:
                arguments = tool_call.get("arguments", {})

            # Vapi can send arguments as JSON string
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}

            print(f"VAPI TOOL: {tool_name}")

            try:

                # ==================================================
                # GET MENU
                # ==================================================

                if tool_name == "get_menu":

                    menu_items = (
                        db.query(models.MenuItem)
                        .filter(models.MenuItem.available == True)
                        .all()
                    )

                    result = []

                    for item in menu_items:
                        result.append({
                            "id": item.id,
                            "name": item.name,
                            "description": item.description,
                            "price": item.price,
                            "category": item.category,
                            "available": item.available,
                            "is_popular": item.is_popular
                        })


                # ==================================================
                # CREATE ORDER
                # ==================================================

                elif tool_name == "create_order":

                    customer_name = arguments["customer_name"]
                    customer_phone = arguments.get(
                        "customer_phone",
                        ""
                    )
                    customer_email = arguments["customer_email"]
                    delivery_address = arguments.get(
                        "delivery_address",
                        ""
                    )
                    items = arguments["items"]

                    # Find customer
                    customer = (
                        db.query(models.Customer)
                        .filter(
                            models.Customer.phone == customer_phone
                        )
                        .first()
                    )

                    if not customer:

                        customer = models.Customer(
                            name=customer_name,
                            phone=customer_phone,
                            email=customer_email
                        )

                        db.add(customer)
                        db.commit()
                        db.refresh(customer)

                    else:

                        customer.name = customer_name

                        if customer_email:
                            customer.email = customer_email

                        db.commit()
                        db.refresh(customer)

                    # Create order
                    new_order = models.Order(
                        customer_id=customer.id,
                        delivery_address=delivery_address,
                        status=models.OrderStatus.confirmed,
                        total_price=0.0
                    )

                    db.add(new_order)
                    db.commit()
                    db.refresh(new_order)

                    total = 0.0
                    items_summary = []

                    for item in items:

                        menu_item_id = item["menu_item_id"]
                        quantity = item["quantity"]

                        menu_item = (
                            db.query(models.MenuItem)
                            .filter(
                                models.MenuItem.id == menu_item_id
                            )
                            .first()
                        )

                        if not menu_item:
                            continue

                        order_item = models.OrderItem(
                            order_id=new_order.id,
                            menu_item_id=menu_item.id,
                            quantity=quantity,
                            price_at_order=menu_item.price
                        )

                        db.add(order_item)

                        total += menu_item.price * quantity

                        items_summary.append({
                            "name": menu_item.name,
                            "quantity": quantity,
                            "price": menu_item.price
                        })

                    new_order.total_price = total

                    db.commit()
                    db.refresh(new_order)

                    # Send confirmation to n8n
                    try:

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

                    except Exception as e:

                        print(
                            "n8n webhook failed:",
                            str(e)
                        )

                    result = {
                        "success": True,
                        "order_id": new_order.id,
                        "status": new_order.status,
                        "customer_name": customer.name,
                        "total_price": new_order.total_price,
                        "items": items_summary,
                        "message": "Order placed successfully. Confirmation email will be sent shortly."
                    }


                # ==================================================
                # CHECK ORDER STATUS
                # ==================================================

                elif tool_name == "check_order_status":

                    order_id = arguments["order_id"]

                    order = (
                        db.query(models.Order)
                        .filter(
                            models.Order.id == order_id
                        )
                        .first()
                    )

                    if not order:

                        result = {
                            "success": False,
                            "error": "Order not found"
                        }

                    else:

                        items_list = []

                        for order_item in order.items:

                            items_list.append({
                                "menu_item_name": order_item.menu_item.name,
                                "quantity": order_item.quantity,
                                "price_at_order": order_item.price_at_order
                            })

                        result = {
                            "success": True,
                            "id": order.id,
                            "status": order.status,
                            "delivery_address": order.delivery_address,
                            "total_price": order.total_price,
                            "customer_name": order.customer.name,
                            "customer_phone": order.customer.phone,
                            "items": items_list
                        }


                # ==================================================
                # CHECK AVAILABILITY
                # ==================================================

                elif tool_name == "check_availability":

                    reservation_time = datetime.fromisoformat(
                        arguments["reservation_time"]
                    )

                    party_size = int(
                        arguments["party_size"]
                    )

                    tables = (
                        db.query(models.Table)
                        .filter(
                            models.Table.capacity >= party_size
                        )
                        .order_by(
                            models.Table.capacity.asc()
                        )
                        .all()
                    )

                    if not tables:

                        result = {
                            "available": False,
                            "message": (
                                f"No table can accommodate "
                                f"{party_size} people."
                            )
                        }

                    else:

                        window_start = (
                            reservation_time -
                            timedelta(hours=2)
                        )

                        window_end = (
                            reservation_time +
                            timedelta(hours=2)
                        )

                        available_table = None

                        for table in tables:

                            conflict = (
                                db.query(models.Reservation)
                                .filter(
                                    models.Reservation.table_id == table.id,
                                    models.Reservation.status ==
                                    models.ReservationStatus.confirmed,
                                    models.Reservation.reservation_time >
                                    window_start,
                                    models.Reservation.reservation_time <
                                    window_end
                                )
                                .first()
                            )

                            if not conflict:

                                available_table = table
                                break

                        if available_table:

                            result = {
                                "available": True,
                                "table_id": available_table.id,
                                "table_number": available_table.table_number,
                                "capacity": available_table.capacity,
                                "requested_time": reservation_time,
                                "party_size": party_size,
                                "message": (
                                    f"Table {available_table.table_number} "
                                    f"is available."
                                )
                            }

                        else:

                            result = {
                                "available": False,
                                "requested_time": reservation_time,
                                "party_size": party_size,
                                "message": (
                                    f"No tables are available for "
                                    f"{party_size} people at that time."
                                )
                            }


                # ==================================================
                # CREATE RESERVATION
                # ==================================================

                elif tool_name == "create_reservation":

                    customer_name = arguments["customer_name"]
                    customer_phone = arguments.get(
                        "customer_phone",
                        ""
                    )

                    table_id = int(
                        arguments["table_id"]
                    )

                    reservation_time = datetime.fromisoformat(
                        arguments["reservation_time"]
                    )

                    party_size = int(
                        arguments["party_size"]
                    )

                    customer = (
                        db.query(models.Customer)
                        .filter(
                            models.Customer.phone ==
                            customer_phone
                        )
                        .first()
                    )

                    if not customer:

                        customer = models.Customer(
                            name=customer_name,
                            phone=customer_phone
                        )

                        db.add(customer)
                        db.commit()
                        db.refresh(customer)

                    else:

                        customer.name = customer_name

                        db.commit()
                        db.refresh(customer)

                    table = (
                        db.query(models.Table)
                        .filter(
                            models.Table.id == table_id
                        )
                        .first()
                    )

                    if not table:

                        result = {
                            "success": False,
                            "error": "Table not found"
                        }

                    elif table.capacity < party_size:

                        result = {
                            "success": False,
                            "error": (
                                f"Table {table.table_number} "
                                f"only seats {table.capacity} people."
                            )
                        }

                    else:

                        window_start = (
                            reservation_time -
                            timedelta(hours=2)
                        )

                        window_end = (
                            reservation_time +
                            timedelta(hours=2)
                        )

                        conflict = (
                            db.query(models.Reservation)
                            .filter(
                                models.Reservation.table_id == table_id,
                                models.Reservation.status ==
                                models.ReservationStatus.confirmed,
                                models.Reservation.reservation_time >
                                window_start,
                                models.Reservation.reservation_time <
                                window_end
                            )
                            .first()
                        )

                        if conflict:

                            result = {
                                "success": False,
                                "error": (
                                    f"Table {table.table_number} "
                                    f"is already booked near that time."
                                )
                            }

                        else:

                            new_reservation = models.Reservation(
                                customer_id=customer.id,
                                table_id=table.id,
                                reservation_time=reservation_time,
                                party_size=party_size,
                                status=models.ReservationStatus.confirmed
                            )

                            db.add(new_reservation)

                            db.commit()
                            db.refresh(new_reservation)

                            result = {
                                "success": True,
                                "reservation_id": new_reservation.id,
                                "status": new_reservation.status,
                                "customer_name": customer.name,
                                "table_number": table.table_number,
                                "reservation_time": reservation_time,
                                "party_size": party_size,
                                "message": (
                                    "Reservation confirmed. "
                                    "Email confirmation will be sent shortly."
                                )
                            }


                # ==================================================
                # CANCEL RESERVATION
                # ==================================================

                elif tool_name == "cancel_reservation":

                    reservation_id = int(
                        arguments["reservation_id"]
                    )

                    reservation = (
                        db.query(models.Reservation)
                        .filter(
                            models.Reservation.id ==
                            reservation_id
                        )
                        .first()
                    )

                    if not reservation:

                        result = {
                            "success": False,
                            "error": "Reservation not found"
                        }

                    else:

                        reservation.status = (
                            models.ReservationStatus.cancelled
                        )

                        db.commit()
                        db.refresh(reservation)

                        result = {
                            "success": True,
                            "reservation_id": reservation.id,
                            "status": reservation.status,
                            "message": "Reservation cancelled successfully."
                        }


                # ==================================================
                # UNKNOWN TOOL
                # ==================================================

                else:

                    result = {
                        "success": False,
                        "error": f"Unknown tool: {tool_name}"
                    }

            except Exception as e:

                db.rollback()

                print(f"VAPI TOOL ERROR [{tool_name}]: {e}")

                result = {
                    "success": False,
                    "error": str(e)
                }

            results.append({
                "name": tool_name,
                "toolCallId": tool_call.get("id"),
                "result": result
            })

    finally:

        db.close()

    final_response = {
        "results": results
    }

    return final_response
