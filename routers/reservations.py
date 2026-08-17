from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

import database
import models
import schemas

router = APIRouter()


@router.post("/reservations")
def create_reservation(res: schemas.ReservationCreate, db: Session = Depends(database.get_db)):
    customer = db.query(models.Customer).filter(
        models.Customer.phone == res.customer_phone
    ).first()

    if not customer:
        customer = models.Customer(name=res.customer_name, phone=res.customer_phone)
        db.add(customer)
        db.commit()
        db.refresh(customer)

    table = db.query(models.Table).filter(models.Table.id == res.table_id).first()
    if not table:
        return {"error": "Table not found"}
    if table.capacity < res.party_size:
        return {"error": f"Table {table.table_number} only seats {table.capacity}, but party size is {res.party_size}"}

    window_start = res.reservation_time - timedelta(hours=2)
    window_end = res.reservation_time + timedelta(hours=2)

    conflict = db.query(models.Reservation).filter(
        models.Reservation.table_id == res.table_id,
        models.Reservation.status == models.ReservationStatus.confirmed,
        models.Reservation.reservation_time > window_start,
        models.Reservation.reservation_time < window_end
    ).first()

    if conflict:
        return {"error": f"Table {table.table_number} is already booked near that time."}

    new_reservation = models.Reservation(
        customer_id=customer.id,
        table_id=res.table_id,
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
        return {"error": f"Table {table.table_number} is already booked near that time (conflict detected)."}

    return new_reservation


@router.patch("/reservations/{reservation_id}/cancel")
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


@router.get("/tables/{table_id}/availability")
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


@router.get("/reservations/{reservation_id}")
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


@router.get("/reservations")
def get_all_reservations(db: Session = Depends(database.get_db)):
    reservations = db.query(models.Reservation).all()

    result = []
    for reservation in reservations:
        result.append({
            "id": reservation.id,
            "status": reservation.status,
            "reservation_time": reservation.reservation_time,
            "party_size": reservation.party_size,
            "table_number": reservation.table.table_number,
            "customer_name": reservation.customer.name,
            "customer_phone": reservation.customer.phone
        })

    return result