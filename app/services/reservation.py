"""
Reservation service.

The reservation logic lives here rather than in the route handler because it
is business logic, not HTTP logic. It has one job: atomically move a seat
from 'free' to 'reserved' and record the resulting order — or fail safely
without leaving the database in an inconsistent state.
"""
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Event, Order, Seat
from app.schemas.order import ReservationResponse


def reserve_seat(db: Session, event_id: int, seat_id: int) -> ReservationResponse:
    """Atomically reserve a seat for an event.

    Raises:
        HTTPException 404 if the event, the seat, or the seat-event pairing
            does not exist.
        HTTPException 409 if the seat is already reserved.

    Returns:
        A ReservationResponse describing the created order.
    """
    # 1. Explicit existence checks — these give precise 404s.
    if db.scalar(select(Event.id).where(Event.id == event_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    seat = db.scalar(select(Seat).where(Seat.id == seat_id))
    if seat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seat {seat_id} not found",
        )
    if seat.event_id != event_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seat {seat_id} does not belong to event {event_id}",
        )

    # 2. Atomic reservation — check and write in one statement.
    try:
        result = db.execute(
            update(Seat)
            .where(
                Seat.id == seat_id,
                Seat.event_id == event_id,
                Seat.status == "free",
            )
            .values(status="reserved")
        )

        if result.rowcount == 0:
            # Existence is already verified; the only remaining reason is that
            # another request beat us to it.
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Seat {seat_id} is already reserved",
            )

        # 3. Record the order in the same transaction.
        order = Order(seat_id=seat_id)
        db.add(order)
        db.commit()
        db.refresh(order)

    except HTTPException:
        # Already rolled back above where needed; re-raise without wrapping.
        raise
    except Exception:
        # Any unexpected failure must not leave a half-finished reservation.
        db.rollback()
        raise

    return ReservationResponse(
        order_id=order.id,
        seat_id=seat.id,
        seat_number=seat.seat_number,
        event_id=event_id,
    )