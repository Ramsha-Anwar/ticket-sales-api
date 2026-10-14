"""
Tests for the free-seat listing endpoint:

    GET /events/{event_id}/seats/free
"""
from app.models import Seat


def test_returns_all_free_seats_for_event(client):
    """A freshly seeded event returns all its free seats."""
    response = client.get("/events/1/seats/free")

    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == 1
    assert len(body["seats"]) == 10

    seat_numbers = {s["seat_number"] for s in body["seats"]}
    assert seat_numbers == {f"A{i}" for i in range(1, 11)}


def test_excludes_reserved_seats(client, db_session):
    """Reserved seats are not returned."""
    # Mark seat A1 as reserved directly in the DB.
    seat = db_session.query(Seat).filter_by(event_id=1, seat_number="A1").one()
    seat.status = "reserved"
    db_session.commit()

    response = client.get("/events/1/seats/free")
    assert response.status_code == 200
    seat_numbers = {s["seat_number"] for s in response.json()["seats"]}
    assert "A1" not in seat_numbers
    assert len(seat_numbers) == 9


def test_returns_empty_list_when_all_reserved(client, db_session):
    """An event with no free seats returns 200 with an empty list."""
    db_session.query(Seat).filter_by(event_id=1).update({"status": "reserved"})
    db_session.commit()

    response = client.get("/events/1/seats/free")
    assert response.status_code == 200
    assert response.json() == {"event_id": 1, "seats": []}


def test_returns_404_for_missing_event(client):
    """A non-existent event returns 404, not an empty list."""
    response = client.get("/events/999/seats/free")
    assert response.status_code == 404
    assert "999" in response.json()["detail"]


def test_response_fields_only_include_id_and_seat_number(client):
    """Response minimization: no internal fields leak to the client."""
    response = client.get("/events/1/seats/free")
    assert response.status_code == 200
    seats = response.json()["seats"]
    assert len(seats) > 0
    for seat in seats:
        assert set(seat.keys()) == {"id", "seat_number"}