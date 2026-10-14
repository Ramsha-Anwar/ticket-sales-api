from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.order import ReservationResponse
from app.services.reservation import reserve_seat

router = APIRouter(prefix="/events", tags=["reservations"])


@router.post(
    "/{event_id}/seats/{seat_id}/reserve",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def reserve(
    event_id: int,
    seat_id: int,
    db: Session = Depends(get_db),
) -> ReservationResponse:
    """Atomically reserve a specific seat for an event.

    Returns 201 Created with the created order on success.
    Returns 404 if the event or seat does not exist (or the seat belongs to
    a different event).
    Returns 409 if the seat is already reserved.
    """
    return reserve_seat(db, event_id=event_id, seat_id=seat_id)