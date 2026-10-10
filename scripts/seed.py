
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, select

from app.db.database import SessionLocal
from app.models import Event, Order, Seat

EVENT_COUNT = 4
SEATS_PER_EVENT = 3000
SEAT_SECTIONS = ["A", "B", "C"]


def _guard() -> bool:
    """Refuse to run unless the operator has explicitly opted in."""
    if os.getenv("ALLOW_DB_WIPE") != "true":
        print(
            "Refusing to wipe the database. "
            "Set ALLOW_DB_WIPE=true in your .env to proceed."
        )
        return False
    return True


def _wipe(session) -> None:
    """Delete all rows in FK-safe order (children before parents)."""
    session.execute(delete(Order))
    session.execute(delete(Seat))
    session.execute(delete(Event))
    session.commit()
    print("Wiped existing events, seats, and orders.")


def _create_events(session) -> list[int]:
    now = datetime.now(timezone.utc)
    rows = [
        {
            "name": f"Concert {chr(ord('A') + i)}",
            "starts_at": now + timedelta(days=30 + i * 7),
        }
        for i in range(EVENT_COUNT)
    ]
    result = session.execute(insert(Event).returning(Event.id), rows)
    event_ids = [row[0] for row in result.fetchall()]
    session.commit()
    print(f"Inserted {len(event_ids)} events.")
    return event_ids


def _create_seats(session, event_ids: list[int]) -> None:
    """
    Bulk-insert seats for each event.

    Seats are labelled by section: A1..A1000, B1..B1000, C1..C1000
    which gives 3,000 unique seat numbers per event.
    """
    rows: list[dict] = []
    for event_id in event_ids:
        for section in SEAT_SECTIONS:
            for n in range(1, SEATS_PER_EVENT // len(SEAT_SECTIONS) + 1):
                rows.append(
                    {
                        "event_id": event_id,
                        "seat_number": f"{section}{n}",
                        "status": "free",
                    }
                )
    session.execute(insert(Seat), rows)
    session.commit()
    print(f"Inserted {len(rows)} seats across {len(event_ids)} events.")


def _verify(session) -> None:
    events = session.scalar(select(func.count()).select_from(Event))
    seats = session.scalar(select(func.count()).select_from(Seat))
    orders = session.scalar(select(func.count()).select_from(Order))
    print()
    print("=== Database contents ===")
    print(f"events: {events}")
    print(f"seats:  {seats}")
    print(f"orders: {orders}")


def main() -> None:
    if not _guard():
        return

    session = SessionLocal()
    try:
        _wipe(session)
        event_ids = _create_events(session)
        _create_seats(session, event_ids)
        _verify(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()