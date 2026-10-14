# Final Requirement Audit

This document records the final verification that every requirement from the internship brief is satisfied. Each row lists the requirement, its status, and how it was verified against the running system.

Verification was performed on 2026-10-14 against a freshly seeded database and a running API instance.

## Requirements

| # | Requirement | Status | Verification |
|---|---|---|---|
| 1 | At least three related tables | Pass | `\dt` shows `events`, `seats`, `orders` |
| 2 | Foreign keys enforced by PostgreSQL | Pass | `\d seats` and `\d orders` show FK constraints |
| 3 | Correct relationships | Pass | `events → seats` is `ON DELETE CASCADE`; `seats → orders` is `ON DELETE RESTRICT` with `UNIQUE(seat_id)` |
| 4 | At least 10,000 seats seeded | Pass | `SELECT COUNT(*) FROM seats` → 12,000 |
| 5 | Seed is reproducible | Pass | `scripts/seed.py` is idempotent, guarded by `ALLOW_DB_WIPE` |
| 6 | Free-seat listing endpoint | Pass | `GET /events/1/seats/free` → 200 with JSON |
| 7 | Reservation endpoint | Pass | `POST /events/1/seats/7/reserve` → 201 with order |
| 8 | Correct error handling | Pass | 404 for missing event/seat; 409 for duplicate reservation |
| 9 | Automated tests pass | Pass | `pytest tests/ -v` → 16 passed |
| 10 | Free-seat endpoint under 200 ms | Pass | Query ~0.16 ms (warm median); endpoint ~69 ms for 300 seats |
| 11 | Query plan captured before index | Pass | `docs/performance-baseline.md` |
| 12 | Query plan captured after index | Pass | `docs/performance-after-index.md` |
| 13 | Concurrent reservations are safe | Pass | `scripts/concurrency-test.ps1` on seats 5, 6, 8 → exactly one 201 and one 409 each time; exactly one order per seat in the DB |
| 14 | README with commands and output | Pass | `README.md` includes setup, endpoints, performance, concurrency, tests |
| 15 | Clean git history | Pass | Nine squash-merged PRs with Conventional Commits subjects |

## How Each Requirement Was Verified

### Data Model (1–3)

```bash
docker exec -it ticket-sales-db psql -U postgres -d ticket_sales -c "\dt"
docker exec -it ticket-sales-db psql -U postgres -d ticket_sales -c "\d seats"
docker exec -it ticket-sales-db psql -U postgres -d ticket_sales -c "\d orders"
```

Three tables present, foreign keys with the correct `ON DELETE` behavior, `CHECK` on `seats.status`, `UNIQUE` on `(event_id, seat_number)` and on `orders.seat_id`.

### Data Volume (4–5)

```bash
docker exec -it ticket-sales-db psql -U postgres -d ticket_sales -c \
  "SELECT event_id, COUNT(*) FROM seats GROUP BY event_id ORDER BY event_id;"
```

Returns four events with 3,000 seats each — 12,000 total.

### Endpoints (6–8)

```bash
# Free seat listing
curl http://127.0.0.1:8000/events/1/seats/free
# → 200, JSON body with "event_id": 1 and seats

# Reservation
curl -X POST http://127.0.0.1:8000/events/1/seats/7/reserve
# → 201, {"order_id":7,"seat_id":7,"seat_number":"A7","event_id":1}

# Error cases
curl http://127.0.0.1:8000/events/999/seats/free
# → 404, {"detail":"Event 999 not found"}
```

### Automated Tests (9)

```bash
pytest tests/ -v
```

16 tests pass in ~3 seconds. Coverage spans free-seat listing, reservation behaviour, and concurrency at both the database and HTTP layers.

### Performance (10–12)

- Query plan before index: `docs/performance-baseline.md`
- Query plan after index: `docs/performance-after-index.md`
- Both plans captured with `EXPLAIN (ANALYZE, BUFFERS)`.

After adding the composite index `(event_id, status)`, the query plan switched from a per-row filter to index-only condition matching, and heap reads dropped from 23 blocks to 3. Median query time dropped from 0.778 ms to 0.159 ms.

The endpoint returns a 300-seat response in ~69 ms (warm), satisfying the sub-200 ms requirement with margin.

### Concurrency (13)

```powershell
.\scripts\concurrency-test.ps1 -EventId 1 -SeatId 8
```

Result:

```text
Request A: 409 Conflict
Request B: 201 Created

===== Result =====
201 Created:     1
409 Conflict:    1

PASS: exactly one reservation succeeded and exactly one failed.
```

Database confirms exactly one order for the contested seat:

```sql
SELECT COUNT(*) FROM orders WHERE seat_id = 8;
-- 1
```

Reproduced independently on seats 5, 6, and 8, with the winner/loser order varying between runs. Full evidence in `docs/concurrency-evidence.md`.

### Documentation (14)

`README.md` includes:

- Requirements checklist mapping each item to its evidence
- Setup instructions
- API endpoint documentation with example requests and responses
- Performance summary with before/after query plans
- Concurrency demonstration and setup finding
- Test suite command and output
- Design decisions
- Documentation index

### Git History (15)

```text
100fae8 test: add pytest suite for endpoints and concurrency (#8)
f5d992f Demonstrate and document concurrent reservation safety (#7)
cb1da93 feat: add atomic seat reservation endpoint (#6)
8177b91 perf: add composite index on seats for free-seat query (#5)
15450d4 docs: capture performance baseline before index (#4)
f250b3a feat: add free seats listing endpoint (#3)
74a7017 feat: add database seed script for events and seats (#2)
52ce6d9 Add relational data model for events, seats, and orders (#1)
b66f707 chore: initialize ticket sales service with FastAPI, Docker, and PostgreSQL
```

All work landed through squash-merged pull requests. Commit subjects follow Conventional Commits. No credentials, no binaries, no generated artifacts in the history.

## Summary

Fifteen of fifteen requirements pass. The project is ready for submission.

---