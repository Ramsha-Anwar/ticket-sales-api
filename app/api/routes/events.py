from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Event, Seat
from app.schemas.seat import FreeSeatsResponse, SeatOut

router = APIRouter(prefix="/events", tags=["events"])


@router.get(
    "/{event_id}/seats/free",
    response_model=FreeSeatsResponse,
    status_code=status.HTTP_200_OK,
)
def list_free_seats(event_id: int, db: Session = Depends(get_db)) -> FreeSeatsResponse:
    """Return all free seats for the given event.

    Returns 404 if the event does not exist. Returns an empty list if the
    event exists but has no free seats.
    """
    event_exists = db.scalar(select(Event.id).where(Event.id == event_id))
    if event_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    seats = db.scalars(
        select(Seat)
        .where(Seat.event_id == event_id, Seat.status == "free")
        .order_by(Seat.id)
    ).all()

    return FreeSeatsResponse(
        event_id=event_id,
        seats=[SeatOut.model_validate(s) for s in seats],
    )
