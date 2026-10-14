"""
API-level concurrency test.

Two simultaneous HTTP POSTs to reserve the same seat must produce exactly
one 201 Created and exactly one 409 Conflict. This directly mirrors the
brief's requirement.
"""
from concurrent.futures import ThreadPoolExecutor

from app.models import Order


def test_two_concurrent_reservations_one_succeeds(client, db_session):
    """Two simultaneous POSTs on the same seat → exactly one 201 and one 409."""
    seat_id = 1
    url = f"/events/1/seats/{seat_id}/reserve"

    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(client.post, url)
        future2 = executor.submit(client.post, url)
        statuses = sorted([future1.result().status_code, future2.result().status_code])

    assert statuses == [201, 409], f"expected one 201 and one 409, got {statuses}"

    # Exactly one order exists for that seat.
    db_session.expire_all()
    orders = db_session.query(Order).filter_by(seat_id=seat_id).all()
    assert len(orders) == 1


def test_concurrent_reservations_on_multiple_seats(client, db_session):
    """The guarantee holds across several seats in one session."""
    for seat_id in (2, 3, 4, 5):
        url = f"/events/1/seats/{seat_id}/reserve"
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(client.post, url) for _ in range(2)]
            statuses = sorted(f.result().status_code for f in futures)
        assert statuses == [201, 409], (
            f"seat {seat_id}: expected one 201 and one 409, got {statuses}"
        )

        db_session.expire_all()
        order_count = db_session.query(Order).filter_by(seat_id=seat_id).count()
        assert order_count == 1, f"seat {seat_id}: expected 1 order, got {order_count}"