-- Benchmark fixture: make event 1 selective for free-seat query benchmarks.
--
-- The original seed creates 12,000 seats, all with status = 'free'. That
-- state makes the status filter non-selective (it keeps every row), so the
-- composite index (event_id, status) provides no measurable advantage.
--
-- This script marks all but the first 300 seats of event 1 as 'reserved',
-- producing a realistic selective workload:
--
--     event 1 -> 300 free / 2700 reserved
--     events 2, 3, 4 -> unchanged (3000 free each)
--
-- Re-runnable: idempotent. Running it multiple times leaves event 1 in the
-- same final state.

-- Step 1: reset event 1 to all-free, so the script is idempotent.
UPDATE seats
SET status = 'free'
WHERE event_id = 1;

-- Step 2: reserve all but the first 300 seats of event 1 (by id).
UPDATE seats
SET status = 'reserved'
WHERE event_id = 1
  AND id NOT IN (
    SELECT id
    FROM seats
    WHERE event_id = 1
    ORDER BY id
    LIMIT 300
  );