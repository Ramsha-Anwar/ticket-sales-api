EXPLAIN (ANALYZE, BUFFERS)
SELECT id, seat_number
FROM seats
WHERE event_id = 1
  AND status = 'free';