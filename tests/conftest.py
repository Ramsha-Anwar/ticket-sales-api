"""
Pytest fixtures for the Ticket Sales API test suite.

Design:
    - Session-scoped fixture creates the schema once (via Base.metadata).
    - Function-scoped fixtures truncate tables and install a small, deterministic
      fixture dataset before each test.
    - The FastAPI TestClient uses a request-scoped session (via a get_db
      override) so commits made by the API are visible to the test's own
      independent session.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, text
from sqlalchemy.orm import Session, sessionmaker

# Ensure the project root is importable when pytest runs from any directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import TEST_DATABASE_URL  # noqa: E402
from app.db.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Event, Seat  # noqa: E402

# Small, deterministic dataset for tests — 1 event, 10 seats.
TEST_EVENT_NAME = "Test Concert"
TEST_SEAT_COUNT = 10
TEST_EVENT_ID = 1  # guaranteed by TRUNCATE ... RESTART IDENTITY


@pytest.fixture(scope="session")
def test_engine():
    """Create a single engine for the test database, and create the schema."""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not set — skipping DB-backed tests.")

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield engine

    engine.dispose()


@pytest.fixture(scope="session")
def TestSessionLocal(test_engine):
    """Session factory bound to the test engine."""
    return sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="function")
def db_session(test_engine, TestSessionLocal) -> Iterator[Session]:
    """Truncate tables and install the minimal fixture before each test.

    Yields a session the test can use for direct DB inspection. This session
    is independent from the one the API uses, so it sees committed changes.
    """
    session = TestSessionLocal()
    try:
        _truncate_all(session)
        _seed_minimal_fixture(session)
        session.commit()
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session, TestSessionLocal) -> Iterator[TestClient]:
    """FastAPI TestClient whose get_db dependency returns a fresh test session.

    The override creates a new request-scoped session per call, mirroring
    production behaviour. This ensures the API's commits are visible to the
    test's own `db_session`.
    """
    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate_all(session: Session) -> None:
    """Wipe all tables and reset id sequences."""
    session.execute(
        text("TRUNCATE TABLE orders, seats, events RESTART IDENTITY CASCADE")
    )


def _seed_minimal_fixture(session: Session) -> None:
    """Insert a small, known dataset: 1 event with 10 seats, all free."""
    starts_at = datetime.now(timezone.utc) + timedelta(days=30)
    result = session.execute(
        insert(Event).returning(Event.id),
        [{"name": TEST_EVENT_NAME, "starts_at": starts_at}],
    )
    event_id = result.scalar_one()

    rows = [
        {"event_id": event_id, "seat_number": f"A{i}", "status": "free"}
        for i in range(1, TEST_SEAT_COUNT + 1)
    ]
    session.execute(insert(Seat), rows)