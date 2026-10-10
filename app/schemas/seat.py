from pydantic import BaseModel, ConfigDict


class SeatOut(BaseModel):
    """A single seat as exposed by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    seat_number: str


class FreeSeatsResponse(BaseModel):
    """Response body for the free-seat listing endpoint."""

    event_id: int
    seats: list[SeatOut]