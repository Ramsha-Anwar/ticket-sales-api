# Performance Baseline — Before Index

This document captures the pre-optimization performance of the free-seat listing query and endpoint. It is the baseline for comparison with the post-index measurements.

## Environment

- **Database:** PostgreSQL 16 in Docker Desktop on Windows
- **Dataset:** 4 events × 3,000 seats = **12,000 seats**
- **API server:** FastAPI served by Uvicorn locally, without `--workers`
- **Measurement date:** 2026-10-12

## Query Under Test

```sql
SELECT id, seat_number
FROM seats
WHERE event_id = 1
  AND status = 'free';
```

## Baseline `EXPLAIN ANALYZE`

### Run 1 — Cold

```text
QUERY PLAN
---------------------------------------------------------------------------------------------------------------------------------
Index Scan using ix_seats_event_id on seats  (cost=0.29..102.28 rows=3000 width=8) (actual time=... rows=3000 loops=1)
  Index Cond: (event_id = 1)
  Filter: ((status)::text = 'free'::text)
Planning Time: 3.975 ms
Execution Time: 3.237 ms
```

### Run 2 — Warm

```text
QUERY PLAN
---------------------------------------------------------------------------------------------------------------------------------
Index Scan using ix_seats_event_id on seats  (cost=0.29..102.28 rows=3000 width=8) (actual time=0.029..0.697 rows=3000 loops=1)
  Index Cond: (event_id = 1)
  Filter: ((status)::text = 'free'::text)
Planning Time: 0.506 ms
Execution Time: 0.879 ms
```

### Run 3 — Warm

```text
QUERY PLAN
---------------------------------------------------------------------------------------------------------------------------------
Index Scan using ix_seats_event_id on seats  (cost=0.29..102.28 rows=3000 width=8) (actual time=0.040..1.168 rows=3000 loops=1)
  Index Cond: (event_id = 1)
  Filter: ((status)::text = 'free'::text)
Planning Time: 0.766 ms
Execution Time: 1.348 ms
```

## Query Plan Analysis

The plan uses the existing `ix_seats_event_id` index, created by setting `index=True` on the `event_id` column.

- **Index condition:** `event_id = 1` — PostgreSQL uses the index to find candidate rows for the event.
- **Filter:** `status = 'free'` — PostgreSQL applies the status condition after finding those rows, checking the 3,000 candidate rows.
- **Warm query execution time:** approximately **0.9–1.3 ms** across the two warm runs.

## Endpoint Timings

**Endpoint:** `GET http://127.0.0.1:8000/events/1/seats/free`

Measurements were taken using PowerShell's `Measure-Command`.

| Run | Time |
|---:|---:|
| 1 | 755.72 ms |
| 2 | 501.32 ms |
| 3 | 285.95 ms |

- **Response size:** 97,596 bytes
- **Seats returned:** 3,000
- **Fastest observed endpoint time:** 285.95 ms

### Endpoint Timing Analysis

The fastest observed endpoint request took approximately **286 ms**, while the database query itself took roughly **1 ms** in warm runs. The endpoint is therefore much slower than the query alone.

Potential contributors to the difference include:

- SQLAlchemy ORM hydration of 3,000 `Seat` objects
- Pydantic response-model processing and JSON serialization for 3,000 objects
- HTTP request/response overhead
- PowerShell `Invoke-WebRequest` client overhead

These are plausible contributors; the measurements do not isolate the exact time spent in each one.

## Observations to Test at M9

The current query plan uses an index scan and then applies a separate status filter:

```text
Index Cond: (event_id = 1)
Filter: ((status)::text = 'free'::text)
```

A composite index on `(event_id, status)` should allow PostgreSQL to use both conditions as index conditions, potentially removing the separate status filter from the plan.

The post-index measurements will test these expectations:

1. **Query plan:** `status = 'free'` may appear in the `Index Cond`, rather than as a separate `Filter`.
2. **Query execution time:** query execution may improve, although the improvement could be modest for this dataset.
3. **Endpoint response time:** endpoint latency may change little because the database query is only a small part of the measured request time.

The post-index document will compare the actual query plan and timings against this baseline. These are expectations to verify, not assumed results.
