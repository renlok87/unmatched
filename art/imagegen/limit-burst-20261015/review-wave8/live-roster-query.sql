BEGIN TRANSACTION READ ONLY;
SELECT jsonb_build_object('captured_at_utc', to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'), 'database', current_database(), 'server_version', current_setting('server_version'), 'transaction_read_only', current_setting('transaction_read_only'), 'rows', (SELECT jsonb_agg(row_to_json(h) ORDER BY h."nameEn") FROM (SELECT id,name,"nameEn","nameRu",set,health,"fighterType",movement,properties,sidekicks,"updatedAt" FROM "Hero" WHERE "nameEn" IN ('Black Panther','Black Widow','Doctor Strange','Elektra')) h));
COMMIT;
