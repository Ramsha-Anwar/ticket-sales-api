-- Find one free seat in event 1 (for testing the reservation endpoint).
SELECT id, event_id, seat_number, status
FROM seats
WHERE event_id = 1
  AND status = 'free'
ORDER BY id
LIMIT 1;