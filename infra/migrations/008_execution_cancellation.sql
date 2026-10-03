BEGIN;
CREATE TABLE IF NOT EXISTS ct_cancellation_evaluations (
 request_id text PRIMARY KEY,
 execution_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 request_digest text NOT NULL,
 digest text NOT NULL UNIQUE CHECK(digest ~ '^[a-f0-9]{64}$'),
 body text NOT NULL,
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE TABLE IF NOT EXISTS ct_cancellation_receipts (
 digest text PRIMARY KEY CHECK(digest ~ '^[a-f0-9]{64}$'),
 request_id text NOT NULL REFERENCES ct_cancellation_evaluations(request_id),
 body text NOT NULL,
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
DROP TRIGGER IF EXISTS ct_cancellation_evaluations_immutable ON ct_cancellation_evaluations;
CREATE TRIGGER ct_cancellation_evaluations_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
 ON ct_cancellation_evaluations FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change();
DROP TRIGGER IF EXISTS ct_cancellation_receipts_immutable ON ct_cancellation_receipts;
CREATE TRIGGER ct_cancellation_receipts_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
 ON ct_cancellation_receipts FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change();
INSERT INTO ct_migrations(version) VALUES(8) ON CONFLICT DO NOTHING;
COMMIT;
