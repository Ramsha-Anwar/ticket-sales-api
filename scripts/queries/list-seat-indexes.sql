SELECT indexname
FROM pg_indexes
WHERE tablename = 'seats'
ORDER BY indexname;