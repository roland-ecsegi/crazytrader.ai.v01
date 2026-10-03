BEGIN;
CREATE TABLE IF NOT EXISTS ct_fixture_dispatch_bounds (
 execution_request_id text PRIMARY KEY REFERENCES ct_execution_requests(execution_request_id),
 digest text NOT NULL UNIQUE, body text NOT NULL,
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE OR REPLACE FUNCTION ct_verify_fixture_dispatch_bound() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE request jsonb; request_digest text; current_state text; BEGIN
 SELECT r.body::jsonb,r.digest,c.state INTO request,request_digest,current_state
 FROM ct_execution_requests r JOIN ct_execution_current c USING(execution_request_id)
 WHERE r.execution_request_id=NEW.execution_request_id;
 PERFORM pg_advisory_xact_lock(hashtextextended('ledger:' || (request->>'tenant_id'),0));
 SELECT state INTO current_state FROM ct_execution_current WHERE execution_request_id=NEW.execution_request_id;
 IF current_state IS DISTINCT FROM 'AUTHORIZED'
 OR NEW.body::jsonb->'request' IS DISTINCT FROM request
 OR NEW.body::jsonb->>'request_sha256' IS DISTINCT FROM request_digest
 OR request->>'execution_mode' IS DISTINCT FROM 'SIMULATION'
 OR request->>'side' IS DISTINCT FROM 'SELL'
 OR EXISTS(SELECT 1 FROM ct_native_simulation_jobs WHERE tenant_id=request->>'tenant_id'
 AND venue_account_ref=request->>'venue_account_ref')
 OR NEW.body::jsonb->>'bound_at' IS NULL
 OR (NEW.body::jsonb->>'bound_at')::timestamptz < (request->>'created_at')::timestamptz
 OR (NEW.body::jsonb->>'bound_at')::timestamptz >= (request->>'expires_at')::timestamptz
 OR NEW.body::jsonb->>'protocol' IS DISTINCT FROM 'LOOPBACK_DEADLINE_GUARD_V1'
 OR NEW.body::jsonb->>'maximum_signature_window_ms' IS DISTINCT FROM '5000'
 OR NEW.body::jsonb->>'sdk_version' IS DISTINCT FROM '3.0.0'
 OR NEW.body::jsonb->>'child_source_sha256' IS DISTINCT FROM '113680db83443dacad4b124b407a298f75a1579ebdc0cf5d188833c2f937530b' THEN
 RAISE EXCEPTION 'fixture dispatch bound requires original authorized simulation request'; END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_fixture_bound_guard ON ct_fixture_dispatch_bounds;
CREATE TRIGGER ct_fixture_bound_guard BEFORE INSERT ON ct_fixture_dispatch_bounds
 FOR EACH ROW EXECUTE FUNCTION ct_verify_fixture_dispatch_bound();
DROP TRIGGER IF EXISTS ct_fixture_bound_immutable ON ct_fixture_dispatch_bounds;
CREATE TRIGGER ct_fixture_bound_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
 ON ct_fixture_dispatch_bounds FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change();
CREATE OR REPLACE FUNCTION ct_verify_fixture_guarded_claim() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE bound_digest text; transition_body jsonb; BEGIN
 IF NEW.state!='SUBMITTING' THEN RETURN NEW; END IF;
 SELECT digest INTO bound_digest FROM ct_fixture_dispatch_bounds WHERE execution_request_id=NEW.execution_request_id;
 IF bound_digest IS NULL THEN RETURN NEW; END IF;
 SELECT body::jsonb INTO transition_body FROM ct_execution_transitions WHERE transition_id=NEW.transition_id;
 IF transition_body->>'evidence_ref' IS DISTINCT FROM 'fixture-bound:' || bound_digest THEN
 RAISE EXCEPTION 'guarded fixture claim requires bound protocol evidence'; END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_fixture_guarded_claim ON ct_execution_current;
CREATE TRIGGER ct_fixture_guarded_claim BEFORE INSERT OR UPDATE ON ct_execution_current
 FOR EACH ROW EXECUTE FUNCTION ct_verify_fixture_guarded_claim();
CREATE OR REPLACE FUNCTION ct_verify_native_sdk_choice() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended('ledger:' || NEW.tenant_id,0));
 IF NOT EXISTS(SELECT 1 FROM ct_execution_current WHERE execution_request_id=NEW.execution_request_id
 AND state='AUTHORIZED') THEN RAISE EXCEPTION 'native choice requires original unsent authorization'; END IF;
 IF EXISTS(SELECT 1 FROM ct_fixture_dispatch_bounds d JOIN ct_execution_requests r USING(execution_request_id)
 WHERE r.tenant_id=NEW.tenant_id AND r.venue_account_ref=NEW.venue_account_ref) THEN
 RAISE EXCEPTION 'simulation account already bound to SDK fixture backend'; END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_native_sdk_choice ON ct_native_simulation_jobs;
CREATE TRIGGER ct_native_sdk_choice BEFORE INSERT ON ct_native_simulation_jobs
 FOR EACH ROW EXECUTE FUNCTION ct_verify_native_sdk_choice();
INSERT INTO ct_migrations(version) VALUES(16) ON CONFLICT DO NOTHING;
COMMIT;
