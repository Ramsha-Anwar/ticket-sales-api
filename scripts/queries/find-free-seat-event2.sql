-- Find one free seat in event 2 (for the "seat does not belong to event" test).
SELECT id, event_id, seat_number, status
FROM seats
WHERE event_id = 2
  AND status = 'free'
ORDER BY id
LIMIT 1;