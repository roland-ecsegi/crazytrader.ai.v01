BEGIN;
CREATE TABLE IF NOT EXISTS ct_execution_fill_sources (
 digest text PRIMARY KEY CHECK(digest ~ '^[a-f0-9]{64}$'),
 execution_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 body text NOT NULL, observed_at timestamptz NOT NULL,
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE TABLE IF NOT EXISTS ct_execution_fills (
 tenant_id text NOT NULL, venue_account_ref text NOT NULL, symbol text NOT NULL,
 raw_trade_id bigint NOT NULL CHECK(raw_trade_id>=0),
 execution_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'), body text NOT NULL,
 ledger_tx_id text NOT NULL UNIQUE REFERENCES ct_ledger_transactions(transaction_id),
 PRIMARY KEY(tenant_id,venue_account_ref,symbol,raw_trade_id),
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE TABLE IF NOT EXISTS ct_reconciliation_incidents (
 incident_id text PRIMARY KEY, tenant_id text NOT NULL,
 execution_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 source_digest text NOT NULL REFERENCES ct_execution_fill_sources(digest),
 reason_code text NOT NULL, body text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ct_execution_suspense (
 incident_id text PRIMARY KEY REFERENCES ct_reconciliation_incidents(incident_id),
 execution_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 source_digest text NOT NULL REFERENCES ct_execution_fill_sources(digest),
 status text NOT NULL DEFAULT 'UNPOSTED_VENUE_TRUTH' CHECK(status='UNPOSTED_VENUE_TRUTH')
);
DO $$ DECLARE table_name text; BEGIN
 FOREACH table_name IN ARRAY ARRAY['ct_execution_fill_sources','ct_execution_fills','ct_reconciliation_incidents','ct_execution_suspense'] LOOP
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname=table_name || '_immutable') THEN
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change()',table_name || '_immutable',table_name);
 END IF;
 END LOOP;
END; $$;
INSERT INTO ct_migrations(version) VALUES(7) ON CONFLICT DO NOTHING;
COMMIT;
