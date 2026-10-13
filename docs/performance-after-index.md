# Performance After Index — Composite `(event_id, status)`

This document records the effect of the composite index `ix_seats_event_id_status` on the free-seat listing query. It is the "after" counterpart to [`performance-baseline.md`](performance-baseline.md).

## Summary

The composite index changes the query plan and reduces heap reads by **~87%**, producing a **~4.9× faster query** on the same data. Endpoint latency is unchanged in practical terms, because the endpoint is not database-bound — it is dominated by serialization and HTTP overhead.

## Environment

- PostgreSQL 16 in Docker Desktop (Windows)
- FastAPI served by Uvicorn (local development, no `--workers`)
- Same dataset as the baseline: **4 events × 3,000 seats = 12,000 seats**
- Measurements taken on 2026-10-13

## Fixture Adjustment

The original seed created 12,000 seats, all with `status = 'free'`. In that state the `status = 'free'` predicate is **non-selective** — it keeps every row it examines — so the composite index provides no advantage over the single-column `event_id` index.

To produce a realistic and selective workload for the benchmark, event 1 was modified to:

| Event | Free | Reserved |
|---|---:|---:|
| 1 | 300 | 2,700 |
| 2 | 3,000 | 0 |
| 3 | 3,000 | 0 |
| 4 | 3,000 | 0 |

Events 2–4 were left untouched as a control (still 3,000 free each). The fixture is reproducible via `scripts/queries/setup-benchmark-fixture.sql`.

## Query Under Test

```sql
SELECT id, seat_number
FROM seats
WHERE event_id = 1
  AND status = 'free';
```

## Scenario A — Selective Data, No Composite Index

`ix_seats_event_id_status` dropped via `alembic downgrade -1`.

### Query Plan

```text
Bitmap Heap Scan on seats  (cost=39.37..192.37 rows=2325 width=8) (actual time=0.124..0.554 rows=300 loops=1)
  Recheck Cond: (event_id = 1)
  Filter: ((status)::text = 'free'::text)
  Rows Removed by Filter: 2700
  Heap Blocks: exact=23
  Buffers: shared hit=28
  ->  Bitmap Index Scan on ix_seats_event_id  (cost=0.00..38.78 rows=3000 width=0)
        Index Cond: (event_id = 1)
        Buffers: shared hit=5
Execution Time: 0.614 ms
```

### Three Runs

| Run | Execution Time |
|---|---:|
| 1 | 1.133 ms |
| 2 | 0.614 ms |
| 3 | 0.778 ms |
| **Median** | **0.778 ms** |

### Analysis

- The single-column index locates all 3,000 rows for `event_id = 1`.
- All 3,000 rows are fetched from the heap.
- `Rows Removed by Filter: 2700` — 2,700 fetched rows are then discarded because they are reserved, not free.
- Heap Blocks read: 23.

## Scenario B — Selective Data, With Composite Index

`ix_seats_event_id_status` restored via `alembic upgrade head`.

### Query Plan

```text
Bitmap Heap Scan on seats  (cost=36.12..178.99 rows=2325 width=8) (actual time=0.062..0.098 rows=300 loops=1)
  Recheck Cond: ((event_id = 1) AND ((status)::text = 'free'::text))
  Heap Blocks: exact=3
  Buffers: shared hit=3 read=2
  ->  Bitmap Index Scan on ix_seats_event_id_status  (cost=0.00..35.53 rows=2325 width=0)
        Index Cond: ((event_id = 1) AND ((status)::text = 'free'::text))
        Buffers: shared read=2
Execution Time: 0.159 ms
```

### Three Runs

| Run | Execution Time |
|---|---:|
| 1 | 0.159 ms |
| 2 | 0.138 ms |
| 3 | 0.161 ms |
| **Median** | **0.159 ms** |

### Analysis

- The composite index satisfies both `event_id` and `status` directly in the index — see `Index Cond` containing both columns.
- There is no `Filter` step in the plan. Every row returned by the index already matches both conditions.
- Heap Blocks read: 3 (down from 23).
- Buffer usage is minimal — the index alone answers the query.

## Isolated Comparison — Same Data, Only the Index Differs

| Metric | Scenario A (no composite) | Scenario B (composite) | Improvement |
|---|---|---|---|
| Plan node | Bitmap Index Scan on `ix_seats_event_id` | Bitmap Index Scan on `ix_seats_event_id_status` | — |
| Index Cond columns | `event_id` only | `event_id` AND `status` | Both in index |
| Filter step | Yes, on 3,000 rows | None | Removed |
| Rows Removed by Filter | 2,700 | 0 | — |
| Heap Blocks read | 23 | 3 | ~7.7× fewer |
| Median Execution Time | 0.778 ms | 0.159 ms | ~4.9× faster |

This is the apples-to-apples comparison: same data, same query, only the index definition differs. The entire time difference is attributable to the composite index.

## Scenario C — Dense Data Control (Event 2)

Event 2 remains dense (3,000 free out of 3,000). The composite index is still used, and there is no regression relative to the pre-index baseline.

### Query Plan

```text
Bitmap Heap Scan on seats  (cost=36.12..178.99 rows=2325 width=8) (actual time=0.106..0.492 rows=3000 loops=1)
  Recheck Cond: ((event_id = 2) AND ((status)::text = 'free'::text))
  Heap Blocks: exact=23
  Buffers: shared hit=28
  ->  Bitmap Index Scan on ix_seats_event_id_status
        Index Cond: ((event_id = 2) AND ((status)::text = 'free'::text))
Execution Time: 0.675 ms
```

### Three Runs

| Run | Execution Time |
|---|---:|
| 1 | 0.758 ms |
| 2 | 0.675 ms |
| 3 | 0.650 ms |
| **Median** | **0.675 ms** |

### Analysis

The composite index is not harmful on dense data. It is still preferred by the planner and produces a plan of similar cost to the single-column index. No regression.

## Endpoint Timings

Measured with PowerShell `Measure-Command`. The server was kept warm between runs; the first call after a cold start is excluded.

### Event 1 — Selective (300 Free Seats, 9,408-Byte Response)

| Run | Time |
|---|---:|
| 1 | 285.47 ms |
| 2 | 69.12 ms |
| 3 | 75.60 ms |

**Fastest warm:** ~69 ms

### Event 2 — Dense (3,000 Free Seats, 98,703-Byte Response)

| Run | Time |
|---|---:|
| 1 | 292.35 ms |
| 2 | 288.66 ms |
| 3 | 443.61 ms |

**Typical warm:** ~290 ms

### Interpretation

The endpoint is not database-bound:

- The query executes in ~0.16 ms, yet the endpoint takes ~69–290 ms.
- The database is responsible for well under 1% of the endpoint latency.
- Endpoint latency scales with response size (300 seats → ~9 KB → ~69 ms; 3,000 seats → ~96 KB → ~290 ms), confirming that JSON serialization and payload size dominate.

The composite index improves the query plan — as required by the brief — but the endpoint latency is bounded by serialization and HTTP overhead, not the database. This is documented honestly so that any future reader understands what the index does and does not change.

## What the Index Actually Buys

- **Fewer heap reads (23 → 3 blocks):** less I/O, better cache behavior.
- **No per-row filter:** the planner does not have to post-process index results to check status.
- **Better scaling:** as more seats become reserved over the life of an event, the selectivity of `status = 'free'` increases, and the index advantage grows. The dense-data control (event 2) shows the index is never worse.
- **Leftmost-prefix coverage:** queries filtering on `event_id` alone are still served efficiently by the composite index, making `ix_seats_event_id` partially redundant.

## Notes

The composite index is created by Alembic migration `8b8017c1fef7_add_composite_index_on_seats_event_id_.py`. This document does not modify the schema — it only measures the effect.

`ix_seats_event_id` (single-column) is now largely redundant given the composite index. It is retained for now to keep the diff minimal; a future migration could drop it if desired.