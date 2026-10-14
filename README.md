# Ticket Sales API

A small backend service for managing events, seats, and seat reservations.  
Built with FastAPI, SQLAlchemy, and PostgreSQL, this project demonstrates relational data modelling, query performance with indexes, and safe concurrent reservations.

The system contains three related tables (`events`, `seats`, `orders`), seeds 12,000 seats for benchmarking, exposes two endpoints, and prevents two simultaneous requests from reserving the same seat.

---

## Requirements Checklist

Mapping the internship brief directly to the implementation:

| Requirement | Status | Evidence |
|---|---|---|
| 3+ related database tables | Done | `events`, `seats`, `orders` — see [`docs/database-design.md`](docs/database-design.md) |
| Foreign keys enforced by PostgreSQL | Done | `seats.event_id → events.id`, `orders.seat_id → seats.id` |
| At least 10,000 seeded seats | Done | 12,000 seats (4 events × 3,000) — see [Seeding](#seeding) |
| Free-seat listing endpoint | Done | `GET /events/{event_id}/seats/free` |
| Reservation endpoint | Done | `POST /events/{event_id}/seats/{seat_id}/reserve` |
| Free-seat endpoint under 200 ms | Done | Query runs in ~0.16 ms; endpoint ~69 ms warm — see [Performance](#performance) |
| Query plan before index | Done | [`docs/performance-baseline.md`](docs/performance-baseline.md) |
| Query plan after index | Done | [`docs/performance-after-index.md`](docs/performance-after-index.md) |
| Concurrent reservations safe | Done | Exactly one 201 and one 409 per race — see [Concurrency](#concurrency) |
| README with commands and output | Done | This document |
| Automated tests pass | Done | 16 passed in ~3 s — see [Tests](#tests) |

---

## Architecture

```text
Client
  │
  │ HTTP
  ▼
FastAPI
  │
  ▼
Service layer (reservation logic)
  │
  ▼
SQLAlchemy ORM
  │
  ▼
PostgreSQL
```

- **FastAPI** — HTTP layer, request/response validation via Pydantic.
- **Service layer** — business logic for reservations, isolated from HTTP.
- **SQLAlchemy** — ORM and Core expressions. The atomic reservation uses a Core UPDATE statement so the check and the write are one SQL call.
- **PostgreSQL** — persistence, foreign keys, constraints, transactions.
- **Alembic** — versioned migrations for reproducible schema.
- **Docker Compose** — PostgreSQL runs in a container.
- **pytest** — automated test suite.

### Data Model

```text
events (1) ──── (many) seats (1) ──── (0..1) orders
```

| Table | Purpose |
|---|---|
| `events` | A concert, show, or other ticketed event |
| `seats` | Individual seats belonging to an event, with a status of free or reserved |
| `orders` | A record created when a reservation succeeds |

Full schema and design rationale: [`docs/database-design.md`](docs/database-design.md).

### Project Structure

```text
ticket-sales-service/
├── alembic/                       Database migrations
│   └── versions/
├── app/
│   ├── api/routes/                HTTP routes
│   │   ├── events.py              Free-seat listing
│   │   └── reservations.py         Seat reservation
│   ├── db/
│   │   └── database.py            SQLAlchemy engine, session, Base
│   ├── models/                    SQLAlchemy ORM models
│   │   ├── event.py
│   │   ├── order.py
│   │   └── seat.py
│   ├── schemas/                   Pydantic request/response schemas
│   │   ├── order.py
│   │   └── seat.py
│   ├── services/
│   │   └── reservation.py          Atomic reservation logic
│   ├── config.py                  Reads .env
│   └── main.py                    FastAPI app entrypoint
├── docs/
│   ├── database-design.md
│   ├── performance-baseline.md
│   ├── performance-after-index.md
│   └── concurrency-evidence.md
├── scripts/
│   ├── seed.py                    Seed 4 events × 3,000 seats
│   ├── check_db.py
│   ├── check_models.py
│   ├── concurrency-test.ps1       Fires two simultaneous requests
│   └── queries/                   Reusable SQL files for evidence
├── tests/                         pytest suite
├── docker-compose.yml
├── requirements.txt
├── alembic.ini
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.11+
- Docker Desktop
- PowerShell (Windows) or any shell

### 1. Clone and install

```bash
git clone https://github.com/Ramsha-Anwar/ticket-sales-api.git
cd ticket-sales-api

python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/ticket_sales
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/ticket_sales_test
ALLOW_DB_WIPE=true
```

The template in `.env.example` documents each variable.

### 3. Start PostgreSQL

```bash
docker compose up -d
```

This starts a PostgreSQL 16 container named `ticket-sales-db`, mapped to host port **5433** to avoid conflicting with any native PostgreSQL installation on port 5432.

Verify the container:

```bash
docker ps
```

Expected: a `ticket-sales-db` row with `0.0.0.0:5433->5432/tcp`.

Verify connectivity:

```bash
docker exec -it ticket-sales-db psql -U postgres -d ticket_sales -c "SELECT 1;"
```

### 4. Create the test database

```bash
docker exec -it ticket-sales-db psql -U postgres -c "CREATE DATABASE ticket_sales_test;"
```

### 5. Run migrations

```bash
alembic upgrade head
```

This creates the `events`, `seats`, and `orders` tables, plus all constraints and indexes.

Verify the schema:

```bash
docker exec -it ticket-sales-db psql -U postgres -d ticket_sales -c "\dt"
```

Expected: three tables — `events`, `orders`, `seats`.

### 6. Start the API

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`, with interactive docs at `http://127.0.0.1:8000/docs`.

---

## Seeding

The seed script populates the database with 4 events and 3,000 seats each — 12,000 seats total, exceeding the 10,000-seat minimum.

```bash
python -m scripts.seed
```

Output:

```text
Wiped existing events, seats, and orders.
Inserted 4 events.
Inserted 12000 seats across 4 events.

=== Database contents ===
events: 4
seats:  12000
orders: 0
```

Verify directly in PostgreSQL:

```bash
docker exec -it ticket-sales-db psql -U postgres -d ticket_sales -c "SELECT COUNT(*) FROM seats;"
```

Output:

```text
 count
-------
 12000
(1 row)
```

The seed is **idempotent** — running it multiple times produces the same state. It is guarded by the `ALLOW_DB_WIPE` environment variable; without it set to `true`, the script refuses to run and prints a warning. This protects against accidentally wiping a real database.

---

## API Endpoints

### `GET /events/{event_id}/seats/free`

Returns all free seats for the given event.

**Request**

```bash
curl http://127.0.0.1:8000/events/1/seats/free
```

**Response — 200 OK**

```json
{
  "event_id": 1,
  "seats": [
    { "id": 1, "seat_number": "A1" },
    { "id": 2, "seat_number": "A2" }
  ]
}
```

**Error responses**

| Case | Status | Body |
|---|---|---|
| Event does not exist | `404` | `{"detail": "Event 999 not found"}` |
| Event exists, no free seats | `200` | `{"event_id": 1, "seats": []}` |

The distinction between "event missing" and "event sold out" is deliberate: a resource that exists but is empty returns `200`, while a resource that does not exist returns `404`.

---

### `POST /events/{event_id}/seats/{seat_id}/reserve`

Reserves a seat and creates an order. The reservation is atomic — see [Concurrency](#concurrency).

**Request**

```bash
curl -X POST http://127.0.0.1:8000/events/1/seats/1/reserve
```

**Response — 201 Created**

```json
{
  "order_id": 1,
  "seat_id": 1,
  "seat_number": "A1",
  "event_id": 1
}
```

**Error responses**

| Case | Status | Body |
|---|---|---|
| Event does not exist | `404` | `{"detail": "Event 999 not found"}` |
| Seat does not exist | `404` | `{"detail": "Seat 999999 not found"}` |
| Seat belongs to a different event | `404` | `{"detail": "Seat 3001 does not belong to event 1"}` |
| Seat is already reserved | `409` | `{"detail": "Seat 1 is already reserved"}` |

---

## Performance

The free-seat listing query is:

```sql
SELECT id, seat_number
FROM seats
WHERE event_id = :event_id
  AND status = 'free';
```

Benchmarks were run on the seeded dataset (12,000 seats across 4 events), using a selective fixture: event 1 was adjusted to have 300 free and 2,700 reserved seats, so the `status` filter is meaningful. Events 2–4 stayed dense (3,000 free each) as a control.

### Baseline — before the composite index

The query used the single-column index `ix_seats_event_id` and applied `status = 'free'` as a per-row filter on the heap:

```text
Bitmap Heap Scan on seats
  Recheck Cond: (event_id = 1)
  Filter: ((status)::text = 'free'::text)
  Rows Removed by Filter: 2700
  Heap Blocks: exact=23
  ->  Bitmap Index Scan on ix_seats_event_id
        Index Cond: (event_id = 1)
Execution Time: 0.614 ms (median warm 0.778 ms)
```

Full baseline: [`docs/performance-baseline.md`](docs/performance-baseline.md).

### After the composite index

Added `ix_seats_event_id_status` on `(event_id, status)` via Alembic migration `8b8017c1fef7`. Both conditions are now evaluated inside the index — no post-filter:

```text
Bitmap Heap Scan on seats
  Recheck Cond: ((event_id = 1) AND ((status)::text = 'free'::text))
  Heap Blocks: exact=3
  ->  Bitmap Index Scan on ix_seats_event_id_status
        Index Cond: ((event_id = 1) AND ((status)::text = 'free'::text))
Execution Time: 0.159 ms (median warm)
```

Full comparison: [`docs/performance-after-index.md`](docs/performance-after-index.md).

### Isolated comparison — same data, only the index differs

| Metric | No composite index | Composite index | Change |
|---|---|---|---|
| Plan | Bitmap Index Scan on `ix_seats_event_id` | Bitmap Index Scan on `ix_seats_event_id_status` | both columns in index |
| `Filter` step | Yes, on 3,000 rows | None | removed |
| `Rows Removed by Filter` | 2,700 | 0 | — |
| Heap Blocks read | 23 | 3 | ~7.7× fewer |
| Median Execution Time | 0.778 ms | 0.159 ms | ~4.9× faster |

Dense control (event 2, 3,000 free) with the composite index: median 0.675 ms — no regression versus the pre-index baseline.

### Endpoint timings

| Scenario | Response size | Warm endpoint time |
|---|---|---|
| Event 1 (300 seats) | 9,408 bytes | ~69 ms |
| Event 2 (3,000 seats) | 98,703 bytes | ~290 ms |

The query executes in **~0.16 ms**, yet the endpoint takes **~69–290 ms**. The endpoint is **not database-bound** — it is dominated by JSON serialization, ORM hydration, and HTTP/client overhead. This is reported honestly so that the effect of the index is understood to be on the query plan, not on end-to-end latency. The `< 200 ms` requirement is satisfied with margin at the query level and at the endpoint level for typical response sizes.

---

## Concurrency

Two simultaneous requests to reserve the same seat must not both succeed. This is guaranteed by performing the check and the write in a single SQL statement:

```sql
UPDATE seats
SET status = 'reserved'
WHERE id = :seat_id
  AND event_id = :event_id
  AND status = 'free';
```

PostgreSQL ensures that at most one concurrent transaction can match the `WHERE` clause. The loser observes `rowcount = 0` and returns `409 Conflict`. A unique constraint on `orders.seat_id` provides a second, database-level defence.

### Demonstration

The repo includes `scripts/concurrency-test.ps1`, which fires two simultaneous POST requests at the same seat using PowerShell `Start-Job`.

```powershell
.\scripts\concurrency-test.ps1 -EventId 1 -SeatId 5
```

Output:

```text
Firing two concurrent POST requests to:
  http://127.0.0.1:8000/events/1/seats/5/reserve

Request A:
  Status: 201
  Body:   {"order_id":5,"seat_id":5,"seat_number":"A5","event_id":1}

Request B:
  Status: 409
  Body:   {"detail":"Seat 5 is already reserved"}

===== Result =====
201 Created:     1
409 Conflict:    1

PASS: exactly one reservation succeeded and exactly one failed.
```

Verify at the database level:

```bash
docker exec -it ticket-sales-db psql -U postgres -d ticket_sales -c "SELECT COUNT(*) FROM orders WHERE seat_id = 5;"
```

Output:

```text
 count
-------
     1
(1 row)
```

Repeated on a second seat (id 6), the winner/loser order reversed — confirming the outcome is decided by the database, not by scheduling.

Full evidence: [`docs/concurrency-evidence.md`](docs/concurrency-evidence.md).

### Setup finding

During initial concurrency testing, intermittent `500` errors appeared:

```text
psycopg2.OperationalError: could not receive data from server:
    Software caused connection abort (0x00002745/10053)
```

This was a Windows socket abort under bursty concurrent load with the default SQLAlchemy connection pool. The fix was applied in `app/db/database.py`:

```python
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
```

The reservation logic itself was not changed — only the pool configuration. After this, the test passed reliably on repeated runs.

---

## Tests

The pytest suite runs against an **isolated test database** (`ticket_sales_test`) and never touches the dev database. It covers endpoint behavior, side effects, and concurrency at both the DB and HTTP layers.

```bash
pytest tests/ -v
```

Output:

```text
tests/test_concurrency_api.py::test_two_concurrent_reservations_one_succeeds PASSED
tests/test_concurrency_api.py::test_concurrent_reservations_on_multiple_seats PASSED
tests/test_concurrency_db.py::test_two_concurrent_updates_only_one_wins PASSED
tests/test_concurrency_db.py::test_repeated_concurrent_updates_are_consistent PASSED
tests/test_free_seats.py::test_returns_all_free_seats_for_event PASSED
tests/test_free_seats.py::test_excludes_reserved_seats PASSED
tests/test_free_seats.py::test_returns_empty_list_when_all_reserved PASSED
tests/test_free_seats.py::test_returns_404_for_missing_event PASSED
tests/test_free_seats.py::test_response_fields_only_include_id_and_seat_number PASSED
tests/test_reservations.py::test_reserve_free_seat_returns_201 PASSED
tests/test_reservations.py::test_reserve_creates_order_and_updates_seat PASSED
tests/test_reservations.py::test_reserve_twice_returns_409 PASSED
tests/test_reservations.py::test_reserve_unknown_seat_returns_404 PASSED
tests/test_reservations.py::test_reserve_unknown_event_returns_404 PASSED
tests/test_reservations.py::test_reserve_seat_from_other_event_returns_404 PASSED
tests/test_reservations.py::test_failed_reservation_does_not_create_order PASSED

================================================== 16 passed in ~3s ==================================================
```

### Coverage by area

| Area | Tests |
|---|---|
| Free-seat listing | 5 |
| Reservation | 7 |
| Concurrency (DB level) | 2 |
| Concurrency (API level) | 2 |

---

## Design Decisions

A few choices worth calling out explicitly:

**`status` column on `seats`, not derived from `orders`.**

Storing status on the seat enables the atomic `UPDATE ... WHERE status = 'free'` reservation, makes the free-seat listing trivially indexable, and scales to richer seat lifecycle states. The risk of "two sources of truth" is eliminated by updating both the seat and the order in one transaction.

**Unique constraint on `orders.seat_id` as a secondary defence.**

Even if application logic were ever broken by a refactor, PostgreSQL would refuse to create a second order for the same seat.

**`timestamptz` instead of `timestamp`.**

Preserves absolute instants across time zones and matches PostgreSQL's recommended default.

**Small fixture for tests, large seed for benchmarks.**

Tests seed 1 event and 10 seats so the suite runs in ~3 seconds. Benchmarks seed 12,000 seats so the query planner has to make a real choice between index and sequential scan.

**Test database isolated from the dev database.**

`ticket_sales_test` is created once and truncated between tests. This keeps the suite hermetic and prevents dev data from leaking into tests (or vice versa).

**Wipe-and-reload seed, guarded by `ALLOW_DB_WIPE`.**

Deterministic state after every run, with an explicit opt-in to prevent accidental data loss.

---

## Documentation Index

- [`docs/database-design.md`](docs/database-design.md) — schema and design rationale
- [`docs/performance-baseline.md`](docs/performance-baseline.md) — query plan before the composite index
- [`docs/performance-after-index.md`](docs/performance-after-index.md) — query plan after the composite index
- [`docs/concurrency-evidence.md`](docs/concurrency-evidence.md) — captured concurrency output
- [`scripts/queries/`](scripts/queries/) — SQL files used for measurements

---

## License

Not specified — this project was built as an internship exercise.