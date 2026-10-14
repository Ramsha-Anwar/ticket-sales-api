from pydantic import BaseModel, ConfigDict


class ReservationResponse(BaseModel):
    """Response body for a successful seat reservation."""

    model_config = ConfigDict(from_attributes=True)

    order_id: int
    seat_id: int
    seat_number: str
    event_id: int