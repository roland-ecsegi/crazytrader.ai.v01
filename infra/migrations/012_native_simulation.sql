BEGIN;
CREATE TABLE IF NOT EXISTS ct_native_simulation_jobs (
 execution_request_id text PRIMARY KEY REFERENCES ct_execution_requests(execution_request_id),
 tenant_id text NOT NULL, venue_account_ref text NOT NULL,
 digest text NOT NULL UNIQUE CHECK(digest ~ '^[a-f0-9]{64}$'),
 job_digest text NOT NULL UNIQUE CHECK(job_digest ~ '^[a-f0-9]{64}$'),
 body text NOT NULL, UNIQUE(execution_request_id,job_digest),
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE TABLE IF NOT EXISTS ct_native_simulation_receipts (
 digest text PRIMARY KEY CHECK(digest ~ '^[a-f0-9]{64}$'),
 execution_request_id text NOT NULL REFERENCES ct_native_simulation_jobs(execution_request_id),
 job_digest text NOT NULL REFERENCES ct_native_simulation_jobs(job_digest),
 body text NOT NULL, available boolean NOT NULL, observed_at timestamptz NOT NULL,
 FOREIGN KEY(execution_request_id,job_digest) REFERENCES ct_native_simulation_jobs(execution_request_id,job_digest),
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE TABLE IF NOT EXISTS ct_native_simulation_postings (
 execution_request_id text PRIMARY KEY REFERENCES ct_native_simulation_jobs(execution_request_id),
 receipt_digest text NOT NULL UNIQUE REFERENCES ct_native_simulation_receipts(digest),
 ledger_tx_id text NOT NULL UNIQUE REFERENCES ct_ledger_transactions(transaction_id)
);
CREATE OR REPLACE FUNCTION ct_verify_native_job() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE original_body jsonb; original_digest text; current_state text; BEGIN
 SELECT r.body::jsonb,r.digest,c.state INTO original_body,original_digest,current_state
 FROM ct_execution_requests r JOIN ct_execution_current c USING(execution_request_id)
 WHERE r.execution_request_id=NEW.execution_request_id;
 IF current_state IS DISTINCT FROM 'AUTHORIZED' OR NEW.body::jsonb->'request' IS DISTINCT FROM original_body
 OR NEW.body::jsonb->'job'->>'request_sha256' IS DISTINCT FROM original_digest
 OR NEW.body::jsonb->'job'->>'execution_request_id' IS DISTINCT FROM NEW.execution_request_id
 OR original_body->>'tenant_id' IS DISTINCT FROM NEW.tenant_id
 OR original_body->>'venue_account_ref' IS DISTINCT FROM NEW.venue_account_ref
 OR original_body->>'execution_mode' IS DISTINCT FROM 'SIMULATION' OR original_body->>'side' IS DISTINCT FROM 'SELL' THEN
 RAISE EXCEPTION 'native admission requires original authorized simulation request'; END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_native_job_guard ON ct_native_simulation_jobs;
CREATE TRIGGER ct_native_job_guard BEFORE INSERT ON ct_native_simulation_jobs
 FOR EACH ROW EXECUTE FUNCTION ct_verify_native_job();
DO $$ DECLARE table_name text; BEGIN
 FOREACH table_name IN ARRAY ARRAY['ct_native_simulation_jobs','ct_native_simulation_receipts','ct_native_simulation_postings'] LOOP
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname=table_name || '_immutable') THEN
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change()',table_name || '_immutable',table_name);
 END IF;
 END LOOP;
END; $$;

-- Source admission alone cannot be forged into completed financial proof.
CREATE OR REPLACE FUNCTION ct_native_financial_adapter_pending() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
 RAISE EXCEPTION 'native financial adapter proof not implemented';
END; $$;
DROP TRIGGER IF EXISTS ct_native_posting_guard ON ct_native_simulation_postings;
CREATE TRIGGER ct_native_posting_guard BEFORE INSERT ON ct_native_simulation_postings
 FOR EACH ROW EXECUTE FUNCTION ct_native_financial_adapter_pending();

INSERT INTO ct_migrations(version) VALUES(12) ON CONFLICT DO NOTHING;
COMMIT;
