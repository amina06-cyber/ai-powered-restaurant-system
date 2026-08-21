from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import requests

import database
import models
import schemas

router = APIRouter()

N8N_RESERVATION_WEBHOOK = "https://aminaashfaq.app.n8n.cloud/webhook/reservation-confirmation"


@router.post("/reservations")
def create_reservation(
    res: schemas.ReservationCreate,
    db: Session = Depends(database.get_db)
):

    customer = (
        db.query(models.Customer)
        .filter(
            models.Customer.phone == res.customer_phone
        )
        .first()
    )

    if not customer:
        customer = models.Customer(
            name=res.customer_name,
            phone=res.customer_phone,
            email=res.customer_email
        )

        db.add(customer)
        db.commit()
        db.refresh(customer)

    else:
        customer.name = res.customer_name
        customer.email = res.customer_email

        db.commit()
        db.refresh(customer)

    table = (
        db.query(models.Table)
        .filter(
            models.Table.id == res.table_id
        )
        .first()
    )

    if not table:
        return {
            "success": False,
            "error": "Table not found"
        }

    if table.capacity < res.party_size:
        return {
            "success": False,
            "error": (
                f"Table {table.table_number} only seats "
                f"{table.capacity}, but party size is "
                f"{res.party_size}"
            )
        }

    window_start = (
        res.reservation_time -
        timedelta(hours=2)
    )

    window_end = (
        res.reservation_time +
        timedelta(hours=2)
    )

    conflict = (
        db.query(models.Reservation)
        .filter(
            models.Reservation.table_id == res.table_id,
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
        return {
            "success": False,
            "error": (
                f"Table {table.table_number} is already "
                f"booked near that time."
            )
        }

    new_reservation = models.Reservation(
        customer_id=customer.id,
        table_id=table.id,
        reservation_time=res.reservation_time,
        party_size=res.party_size,
        status=models.ReservationStatus.confirmed
    )

    db.add(new_reservation)

    try:
        db.commit()
        db.refresh(new_reservation)

    except Exception:
        db.rollback()

        return {
            "success": False,
            "error": (
                f"Table {table.table_number} is already "
                f"booked near that time."
            )
        }

    try:
        n8n_response = requests.post(
            N8N_RESERVATION_WEBHOOK,
            json={
                "reservation_id": new_reservation.id,
                "customer_name": customer.name,
                "customer_email": customer.email,
                "customer_phone": customer.phone,
                "reservation_time": (
                    new_reservation.reservation_time.isoformat()
                ),
                "party_size": new_reservation.party_size,
                "table_number": table.table_number,
                "status": str(new_reservation.status)
            },
            timeout=10
        )

        print(
            "N8N reservation webhook:",
            n8n_response.status_code
        )

    except Exception as e:
        # IMPORTANT:
        # Do NOT cancel the reservation just because
        # the email workflow failed.
        print(
            "N8N reservation webhook failed:",
            str(e)
        )
    return {
        "success": True,
        "reservation_id": new_reservation.id,
        "status": new_reservation.status,
        "customer_name": customer.name,
        "customer_email": customer.email,
        "customer_phone": customer.phone,
        "table_number": table.table_number,
        "reservation_time": new_reservation.reservation_time,
        "party_size": new_reservation.party_size,
        "message": (
            "Reservation confirmed. "
            "A confirmation email will be sent shortly."
        )
    }

@router.patch("/reservations/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: int,
    db: Session = Depends(database.get_db)
):
    reservation = (
        db.query(models.Reservation)
        .filter(
            models.Reservation.id == reservation_id
        )
        .first()
    )

    if not reservation:
        return {
            "success": False,
            "error": "Reservation not found"
        }

    reservation.status = (
        models.ReservationStatus.cancelled
    )

    db.commit()
    db.refresh(reservation)
    return {
        "success": True,
        "reservation_id": reservation.id,
        "status": reservation.status,
        "message": "Reservation cancelled successfully."
    }

@router.get("/tables/availability")
def find_available_table(
    reservation_time: datetime,
    party_size: int,
    db: Session = Depends(database.get_db)
):
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
        return {
            "available": False,
            "message": (
                f"No table can accommodate "
                f"{party_size} people."
            )
        }

    window_start = (
        reservation_time -
        timedelta(hours=2)
    )

    window_end = (
        reservation_time +
        timedelta(hours=2)
    )

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
            return {
                "available": True,
                "table_id": table.id,
                "table_number": table.table_number,
                "capacity": table.capacity,
                "requested_time": reservation_time,
                "party_size": party_size
            }

    return {
        "available": False,
        "requested_time": reservation_time,
        "party_size": party_size,
        "message": (
            f"No tables are available for "
            f"{party_size} people at that time."
        )
    }

@router.get("/tables/{table_id}/availability")
def check_availability(
    table_id: int,
    reservation_time: datetime,
    db: Session = Depends(database.get_db)
):
    table = (
        db.query(models.Table)
        .filter(
            models.Table.id == table_id
        )
        .first()
    )

    if not table:
        return {
            "error": "Table not found"
        }

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

@router.get("/reservations/{reservation_id}")
def get_reservation(
    reservation_id: int,
    db: Session = Depends(database.get_db)
):
    reservation = (
        db.query(models.Reservation)
        .filter(
            models.Reservation.id == reservation_id
        )
        .first()
    )

    if not reservation:
        return {
            "error": "Reservation not found"
        }

    return {
        "id": reservation.id,
        "status": reservation.status,
        "reservation_time": reservation.reservation_time,
        "party_size": reservation.party_size,
        "table_number": reservation.table.table_number,
        "customer_name": reservation.customer.name,
        "customer_email": reservation.customer.email,
        "customer_phone": reservation.customer.phone
    }

@router.get("/reservations")
def get_all_reservations(
    db: Session = Depends(database.get_db)
):
    reservations = (
        db.query(models.Reservation)
        .all()
    )

    result = []

    for reservation in reservations:

        result.append({
            "id": reservation.id,
            "status": reservation.status,
            "reservation_time": reservation.reservation_time,
            "party_size": reservation.party_size,
            "table_number": reservation.table.table_number,
            "customer_name": reservation.customer.name,
            "customer_email": reservation.customer.email,
            "customer_phone": reservation.customer.phone
        })

    return result

@router.get("/tables")
def get_all_tables(
    db: Session = Depends(database.get_db)
):
    tables = (
        db.query(models.Table)
        .all()
    )

    return [
        {
            "id": table.id,
            "table_number": table.table_number,
            "capacity": table.capacity
        }
        for table in tables
    ]