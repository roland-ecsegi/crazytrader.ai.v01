BEGIN;
CREATE TABLE IF NOT EXISTS ct_account_read_sources (
 digest text PRIMARY KEY CHECK(digest ~ '^[a-f0-9]{64}$'),
 tenant_id text NOT NULL, venue_account_ref text NOT NULL,
 anchor_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 body text NOT NULL, observed_at timestamptz NOT NULL,
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE TABLE IF NOT EXISTS ct_account_reconciliation_reports (
 digest text PRIMARY KEY CHECK(digest ~ '^[a-f0-9]{64}$'), tenant_id text NOT NULL,
 source_digest text NOT NULL REFERENCES ct_account_read_sources(digest),
 blocks_new_risk boolean NOT NULL, body text NOT NULL,
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
DO $$ DECLARE table_name text; BEGIN
 FOREACH table_name IN ARRAY ARRAY['ct_account_read_sources','ct_account_reconciliation_reports'] LOOP
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname=table_name || '_immutable') THEN
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change()',table_name || '_immutable',table_name);
 END IF;
 END LOOP;
END; $$;
INSERT INTO ct_migrations(version) VALUES(11) ON CONFLICT DO NOTHING;
COMMIT;
