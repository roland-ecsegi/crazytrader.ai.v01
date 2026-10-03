BEGIN;
CREATE TABLE IF NOT EXISTS ct_execution_requests (
 execution_request_id text PRIMARY KEY, tenant_id text NOT NULL,
 intent_id text NOT NULL, order_id text NOT NULL UNIQUE,
 venue_account_ref text NOT NULL, client_order_id text NOT NULL,
 risk_record_digest text NOT NULL REFERENCES ct_risk_evaluations(record_digest),
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'), body text NOT NULL,
 UNIQUE(tenant_id,intent_id), UNIQUE(tenant_id,venue_account_ref,client_order_id),
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE TABLE IF NOT EXISTS ct_execution_transitions (
 transition_id text PRIMARY KEY,
 execution_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 revision bigint NOT NULL CHECK(revision>=0),
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'), body text NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(execution_request_id,revision), CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE TABLE IF NOT EXISTS ct_execution_current (
 execution_request_id text PRIMARY KEY REFERENCES ct_execution_requests(execution_request_id),
 transition_id text NOT NULL UNIQUE REFERENCES ct_execution_transitions(transition_id),
 revision bigint NOT NULL CHECK(revision>=0), state text NOT NULL,
 CHECK(state IN ('CREATED','RISK_PENDING','AUTHORIZED','SUBMITTING','SUBMITTED','ACKNOWLEDGED',
 'PARTIALLY_FILLED','FILLED','DENIED','REJECTED','CANCEL_PENDING','CANCELLED','EXPIRED',
 'UNKNOWN','RECOVERY_REQUIRED'))
);
CREATE TABLE IF NOT EXISTS ct_execution_reservations (
 execution_request_id text PRIMARY KEY REFERENCES ct_execution_requests(execution_request_id),
 reservation_tx_id text NOT NULL UNIQUE REFERENCES ct_ledger_transactions(transaction_id),
 reserve_asset text NOT NULL, reserve_account text NOT NULL CHECK(reserve_account IN('AVAILABLE','INVENTORY')),
 reserve_amount numeric(74,18) NOT NULL CHECK(reserve_amount>0),
 ledger_head_sha256 text NOT NULL, safety_sha256 text NOT NULL, checkpoint_sha256 text NOT NULL
);
CREATE OR REPLACE FUNCTION ct_verify_execution_pointer() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE transition_body jsonb; request_body jsonb; BEGIN
 SELECT body::jsonb INTO transition_body FROM ct_execution_transitions
 WHERE transition_id=NEW.transition_id AND execution_request_id=NEW.execution_request_id
 AND revision=NEW.revision;
 IF transition_body IS NULL OR transition_body->'resulting_state'->>'state' != NEW.state THEN
 RAISE EXCEPTION 'execution pointer does not match immutable transition'; END IF;
 IF TG_OP='UPDATE' AND (NEW.execution_request_id != OLD.execution_request_id OR NEW.revision != OLD.revision+1) THEN
 RAISE EXCEPTION 'execution pointer revision must advance exactly once'; END IF;
 IF TG_OP='UPDATE' AND (transition_body->>'previous_state' != OLD.state OR
 (transition_body->>'previous_revision')::bigint != OLD.revision) THEN
 RAISE EXCEPTION 'execution transition predecessor mismatch'; END IF;
 IF NEW.state IN('AUTHORIZED','SUBMITTING') AND NOT EXISTS(SELECT 1 FROM ct_execution_reservations
 WHERE execution_request_id=NEW.execution_request_id) THEN
 RAISE EXCEPTION 'execution requires durable reservation'; END IF;
 IF TG_OP='INSERT' AND (NEW.revision!=0 OR NEW.state!='CREATED') THEN
 RAISE EXCEPTION 'execution pointer must start CREATED'; END IF;
 SELECT body::jsonb INTO request_body FROM ct_execution_requests WHERE execution_request_id=NEW.execution_request_id;
 IF transition_body->'resulting_state'->'request' != request_body THEN
 RAISE EXCEPTION 'execution request identity changed'; END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_execution_pointer_guard ON ct_execution_current;
CREATE TRIGGER ct_execution_pointer_guard BEFORE INSERT OR UPDATE ON ct_execution_current
 FOR EACH ROW EXECUTE FUNCTION ct_verify_execution_pointer();
DROP TRIGGER IF EXISTS ct_execution_pointer_no_delete ON ct_execution_current;
CREATE TRIGGER ct_execution_pointer_no_delete BEFORE DELETE OR TRUNCATE ON ct_execution_current
 FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change();
DO $$ DECLARE table_name text; BEGIN
 FOREACH table_name IN ARRAY ARRAY['ct_execution_requests','ct_execution_transitions','ct_execution_reservations'] LOOP
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname=table_name || '_immutable') THEN
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change()',table_name || '_immutable',table_name);
 END IF;
 END LOOP;
END; $$;
INSERT INTO ct_migrations(version) VALUES(5) ON CONFLICT DO NOTHING;
COMMIT;
