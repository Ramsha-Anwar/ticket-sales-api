"""
Tests for the reservation endpoint:

    POST /events/{event_id}/seats/{seat_id}/reserve
"""
from app.models import Order, Seat


def test_reserve_free_seat_returns_201(client, db_session):
    """A free seat can be reserved."""
    response = client.post("/events/1/seats/1/reserve")

    assert response.status_code == 201
    body = response.json()
    assert body["event_id"] == 1
    assert body["seat_id"] == 1
    assert body["seat_number"] == "A1"
    assert isinstance(body["order_id"], int)


def test_reserve_creates_order_and_updates_seat(client, db_session):
    """On success, exactly one order is created and the seat is reserved."""
    response = client.post("/events/1/seats/1/reserve")
    assert response.status_code == 201

    # Refresh to see commits made by the API's separate session.
    db_session.expire_all()

    orders = db_session.query(Order).filter_by(seat_id=1).all()
    assert len(orders) == 1

    seat = db_session.query(Seat).filter_by(id=1).one()
    assert seat.status == "reserved"


def test_reserve_twice_returns_409(client):
    """Reserving an already-reserved seat returns 409."""
    first = client.post("/events/1/seats/1/reserve")
    assert first.status_code == 201

    second = client.post("/events/1/seats/1/reserve")
    assert second.status_code == 409
    assert "already reserved" in second.json()["detail"]


def test_reserve_unknown_seat_returns_404(client):
    """A non-existent seat returns 404."""
    response = client.post("/events/1/seats/999999/reserve")
    assert response.status_code == 404
    assert "999999" in response.json()["detail"]


def test_reserve_unknown_event_returns_404(client):
    """A non-existent event returns 404."""
    response = client.post("/events/999/seats/1/reserve")
    assert response.status_code == 404
    assert "999" in response.json()["detail"]


def test_reserve_seat_from_other_event_returns_404(client, db_session):
    """A seat that belongs to a different event cannot be reserved via the wrong event."""
    # Add a second event with its own seat.
    from datetime import datetime, timedelta, timezone
    from app.models import Event
    from sqlalchemy import insert

    starts_at = datetime.now(timezone.utc) + timedelta(days=60)
    event2_id = db_session.execute(
        insert(Event).returning(Event.id),
        [{"name": "Other Concert", "starts_at": starts_at}],
    ).scalar_one()
    seat2_id = db_session.execute(
        insert(Seat).returning(Seat.id),
        [{"event_id": event2_id, "seat_number": "B1", "status": "free"}],
    ).scalar_one()
    db_session.commit()

    # Try to reserve event 2's seat via event 1's endpoint.
    response = client.post(f"/events/1/seats/{seat2_id}/reserve")
    assert response.status_code == 404
    assert "does not belong" in response.json()["detail"]


def test_failed_reservation_does_not_create_order(client, db_session):
    """A 409 does not create a new order."""
    client.post("/events/1/seats/1/reserve")          # creates 1 order
    client.post("/events/1/seats/1/reserve")          # 409, no new order

    db_session.expire_all()
    orders = db_session.query(Order).filter_by(seat_id=1).all()
    assert len(orders) == 1