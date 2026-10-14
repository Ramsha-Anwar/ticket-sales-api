"""
Database-level concurrency test.

Verifies the atomic guarantee directly at the SQL level: two concurrent
UPDATEs against the same free seat cannot both succeed. This is the
underlying mechanism that makes the API safe; testing it here isolates
the guarantee from any application code.
"""
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import update

from app.models import Seat


def _attempt_reserve(engine, seat_id: int) -> int:
    """Run the same atomic UPDATE the service uses, and return rowcount."""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        result = session.execute(
            update(Seat)
            .where(
                Seat.id == seat_id,
                Seat.event_id == 1,
                Seat.status == "free",
            )
            .values(status="reserved")
        )
        session.commit()
        return result.rowcount


def test_two_concurrent_updates_only_one_wins(test_engine, db_session):
    """Exactly one of two concurrent atomic UPDATEs changes the row."""
    seat_id = 1

    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(_attempt_reserve, test_engine, seat_id)
        future2 = executor.submit(_attempt_reserve, test_engine, seat_id)
        rowcounts = {future1.result(), future2.result()}

    assert rowcounts == {0, 1}, f"expected one winner and one loser, got {rowcounts}"

    # The database reflects exactly one reservation.
    db_session.expire_all()
    seat = db_session.query(Seat).filter_by(id=seat_id).one()
    assert seat.status == "reserved"


def test_repeated_concurrent_updates_are_consistent(test_engine, db_session):
    """Across multiple fresh seats, the atomic guarantee holds every time."""
    from sqlalchemy import insert

    # Add 10 more seats so we can repeat the test quickly.
    extra_seats = [
        {"event_id": 1, "seat_number": f"B{i}", "status": "free"}
        for i in range(1, 11)
    ]
    db_session.execute(insert(Seat), extra_seats)
    db_session.commit()

    seat_ids = [
        row.id
        for row in db_session.query(Seat).filter_by(event_id=1).all()
        if row.seat_number.startswith("B")
    ]

    for seat_id in seat_ids:
        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(_attempt_reserve, test_engine, seat_id)
            f2 = executor.submit(_attempt_reserve, test_engine, seat_id)
            rowcounts = {f1.result(), f2.result()}
        assert rowcounts == {0, 1}, f"seat {seat_id}: got {rowcounts}"