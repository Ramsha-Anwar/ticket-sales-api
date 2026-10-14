# Concurrency Evidence — Reservation Endpoint

This document captures the empirical proof that the reservation endpoint prevents two concurrent requests from reserving the same seat. It is the direct evidence for the brief's requirement:

> Two concurrent requests targeting the same seat must never both succeed.

## Summary

- **Two simultaneous POST requests were sent to the same seat.** Exactly one returned `201 Created`; exactly one returned `409 Conflict`.
- **The database contains exactly one order** for each contested seat.
- The result **reproduces across multiple seats**, with the winner/loser order varying between runs — confirming a genuine race, not a deterministic shortcut.

## Setup

- PostgreSQL 16 in Docker Desktop (Windows)
- FastAPI served by Uvicorn (local development)
- Test driver: `scripts/concurrency-test.ps1`, using PowerShell `Start-Job` to fire two requests simultaneously.
- Both requests target the same URL: `POST /events/1/seats/{seat_id}/reserve`

## Test Script

`scripts/concurrency-test.ps1` starts two background jobs at the same time. Each job issues a single `Invoke-WebRequest` POST to the same reservation URL. The script then collects both responses and reports the counts of each status code.

```powershell
$job1 = Start-Job -ScriptBlock $scriptBlock -ArgumentList $url
$job2 = Start-Job -ScriptBlock $scriptBlock -ArgumentList $url

$result1 = Receive-Job -Job $job1 -Wait
$result2 = Receive-Job -Job $job2 -Wait
```

## Run 1 — Seat 5

**Command:**

```powershell
.\scripts\concurrency-test.ps1 -EventId 1 -SeatId 5
```

**Output:**

```text
Firing two concurrent POST requests to:
  http://127.0.0.1:8000/events/1/seats/5/reserve

Request A:
  Status: 201
  Body:
  {"order_id":5,"seat_id":5,"seat_number":"A5","event_id":1}

Request B:
  Status: 409
  Body:
  {"detail":"Seat 5 is already reserved"}

===== Result =====
201 Created:     1
409 Conflict:    1
PASS: exactly one reservation succeeded and exactly one failed.
```

**Database verification:**

```sql
SELECT COUNT(*) FROM orders WHERE seat_id = 5;
-- count = 1

SELECT id, status FROM seats WHERE id = 5;
-- id = 5, status = reserved
```

## Run 2 — Seat 6

**Command:**

```powershell
.\scripts\concurrency-test.ps1 -EventId 1 -SeatId 6
```

**Output:**

```text
Firing two concurrent POST requests to:
  http://127.0.0.1:8000/events/1/seats/6/reserve

Request A:
  Status: 409

Request B:
  Status: 201
  Body:
  {"order_id":6,"seat_id":6,"seat_number":"A6","event_id":1}

===== Result =====
201 Created:     1
409 Conflict:    1
PASS: exactly one reservation succeeded and exactly one failed.
```

**Note:** this time Request A received the 409 and Request B received the 201 — the opposite of Run 1. This variability confirms the requests are genuinely racing, and the atomic database update decides the winner.

**Database verification:**

```sql
SELECT COUNT(*) FROM orders WHERE seat_id = 6;
-- count = 1
```

## Why This Proves the Requirement

The two requests were sent **simultaneously** (via `Start-Job`), not sequentially. A naive implementation — `SELECT` → check → `UPDATE` — would allow both requests to read `status = 'free'` before either one writes `reserved`, and both would succeed.

The actual implementation instead performs the check and the write in a single SQL statement:

```sql
UPDATE seats
SET status = 'reserved'
WHERE id = :seat_id
  AND event_id = :event_id
  AND status = 'free';
```

PostgreSQL guarantees that at most one concurrent transaction can match this WHERE clause and change the row. The other transaction observes `rowcount = 0` and returns `409 Conflict`. The unique constraint on `orders.seat_id` provides a second, database-level defence: even if the application logic were bypassed, PostgreSQL would refuse a second order for the same seat.

## Setup Finding — Connection Pool Sizing Under Concurrency

The first concurrency attempts produced intermittent HTTP 500 errors:

```text
psycopg2.OperationalError: could not receive data from server:
    Software caused connection abort (0x00002745/10053)
```

This is a Windows socket abort (`WSAECONNABORTED`) that occurred on ordinary queries, not on the atomic UPDATE. The root cause was connection instability under bursty concurrent load with the default SQLAlchemy pool configuration.

The fix was applied in `app/db/database.py`:

```python
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
```

- `pool_pre_ping=True` validates pooled connections with a lightweight `SELECT 1` before use and replaces dead connections transparently.
- `pool_size=10` keeps up to 10 connections warm.
- `max_overflow=20` allows short bursts beyond the pool size.

After this change, the same test passed on repeated runs with no 500 errors. The atomic reservation logic itself was not changed — only the connection pool configuration.

## Files

- `scripts/concurrency-test.ps1` — the test driver.
- `app/db/database.py` — connection pool configuration.
- `app/services/reservation.py` — the atomic reservation implementation.
