BEGIN;
CREATE TABLE IF NOT EXISTS ct_execution_observations (
 digest text PRIMARY KEY CHECK(digest ~ '^[a-f0-9]{64}$'),
 execution_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 body text NOT NULL, observed_at timestamptz NOT NULL,
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
DROP TRIGGER IF EXISTS ct_execution_observations_immutable ON ct_execution_observations;
CREATE TRIGGER ct_execution_observations_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
 ON ct_execution_observations FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change();
INSERT INTO ct_migrations(version) VALUES(6) ON CONFLICT DO NOTHING;
COMMIT;
