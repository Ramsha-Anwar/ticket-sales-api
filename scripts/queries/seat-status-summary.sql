SELECT event_id, status, COUNT(*) AS count
FROM seats
GROUP BY event_id, status
ORDER BY event_id, status;