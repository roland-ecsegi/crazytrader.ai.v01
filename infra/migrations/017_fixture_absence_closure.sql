BEGIN;
CREATE TABLE IF NOT EXISTS ct_fixture_timed_lookups (
 digest text PRIMARY KEY, execution_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 lookup_digest text NOT NULL REFERENCES ct_fixture_order_lookups(digest), body text NOT NULL,
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE TABLE IF NOT EXISTS ct_fixture_absence_closures (
 execution_request_id text PRIMARY KEY REFERENCES ct_execution_requests(execution_request_id),
 digest text NOT NULL UNIQUE, body text NOT NULL,
 assessment_digest text NOT NULL REFERENCES ct_fixture_absence_assessments(digest),
 bound_digest text NOT NULL REFERENCES ct_fixture_dispatch_bounds(digest),
 timed_digest text NOT NULL REFERENCES ct_fixture_timed_lookups(digest),
 release_tx_id text NOT NULL UNIQUE REFERENCES ct_ledger_transactions(transaction_id),
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE OR REPLACE FUNCTION ct_verify_timed_lookup() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE lookup_body jsonb; BEGIN
 SELECT body::jsonb INTO lookup_body FROM ct_fixture_order_lookups
 WHERE digest=NEW.lookup_digest AND execution_request_id=NEW.execution_request_id;
 IF lookup_body IS NULL OR NEW.body::jsonb->'lookup' IS DISTINCT FROM lookup_body
 OR NEW.body::jsonb->>'maximum_signature_window_ms' IS DISTINCT FROM '5000'
 OR NEW.body::jsonb->>'clock_source' IS DISTINCT FROM 'LOOPBACK_HTTP_DATE_HEADER' THEN
 RAISE EXCEPTION 'timed lookup original signed source mismatch'; END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_timed_lookup_guard ON ct_fixture_timed_lookups;
CREATE TRIGGER ct_timed_lookup_guard BEFORE INSERT ON ct_fixture_timed_lookups
 FOR EACH ROW EXECUTE FUNCTION ct_verify_timed_lookup();
CREATE OR REPLACE FUNCTION ct_verify_fixture_absence_closure() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE req text; proof record; request jsonb; original jsonb; released jsonb;
 assessment jsonb; bound jsonb; timed jsonb; current_body jsonb; current_state text;
 original_state jsonb; server_clock timestamptz; recovered_head text; BEGIN
 IF TG_TABLE_NAME='ct_fixture_absence_closures' THEN req:=NEW.execution_request_id;
 ELSE
   IF NEW.body::jsonb->>'provenance_ref' NOT LIKE 'fixture-absent:%' THEN RETURN NEW; END IF;
   req:=regexp_replace(NEW.body::jsonb->>'provenance_ref','^fixture-absent:','');
 END IF;
 SELECT * INTO proof FROM ct_fixture_absence_closures WHERE execution_request_id=req;
 SELECT r.body::jsonb,c.state,t.body::jsonb->'resulting_state' INTO request,current_state,current_body
 FROM ct_execution_requests r JOIN ct_execution_current c USING(execution_request_id)
 JOIN ct_execution_transitions t ON t.transition_id=c.transition_id WHERE r.execution_request_id=req;
 SELECT t.body::jsonb INTO original FROM ct_execution_reservations r JOIN ct_ledger_transactions t
 ON t.transaction_id=r.reservation_tx_id WHERE r.execution_request_id=req;
 SELECT body::jsonb INTO released FROM ct_ledger_transactions WHERE transaction_id=proof.release_tx_id;
 SELECT body::jsonb INTO assessment FROM ct_fixture_absence_assessments
 WHERE digest=proof.assessment_digest AND execution_request_id=req AND verdict='PROVEN';
 SELECT body::jsonb INTO bound FROM ct_fixture_dispatch_bounds
 WHERE digest=proof.bound_digest AND execution_request_id=req;
 SELECT body::jsonb INTO timed FROM ct_fixture_timed_lookups
 WHERE digest=proof.timed_digest AND execution_request_id=req;
 original_state:=assessment->'state';
 IF proof IS NULL OR request IS NULL OR original IS NULL OR released IS NULL
 OR assessment IS NULL OR bound IS NULL OR timed IS NULL
 OR proof.body::jsonb->'assessment' IS DISTINCT FROM assessment
 OR proof.body::jsonb->'dispatch_bound' IS DISTINCT FROM bound
 OR proof.body::jsonb->'timed_lookup' IS DISTINCT FROM timed
 OR proof.body::jsonb->'original_reservation' IS DISTINCT FROM original
 OR proof.body::jsonb->'release' IS DISTINCT FROM released
 OR bound->'request' IS DISTINCT FROM request
 OR original_state->'request' IS DISTINCT FROM request
 OR timed->'lookup' IS DISTINCT FROM assessment->'lookup'
 OR current_state IS DISTINCT FROM 'EXPIRED'
 OR request->>'execution_mode' IS DISTINCT FROM 'SIMULATION'
 OR request->>'side' IS DISTINCT FROM 'SELL'
 OR COALESCE(original_state->>'state','') NOT IN('UNKNOWN','RECOVERY_REQUIRED')
 OR NOT EXISTS(SELECT 1 FROM ct_execution_transitions WHERE execution_request_id=req
 AND body::jsonb->'resulting_state'=original_state)
 OR (original_state->>'filled_quantity')::numeric IS DISTINCT FROM 0::numeric
 OR original_state->>'venue_order_id' IS NOT NULL
 OR (current_body->>'filled_quantity')::numeric IS DISTINCT FROM 0::numeric
 OR current_body->>'venue_order_id' IS NOT NULL
 OR proof.body::jsonb->>'actor_id' IS DISTINCT FROM request->>'actor_id'
 OR released->>'actor_id' IS DISTINCT FROM request->>'actor_id'
 OR released->>'tenant_id' IS DISTINCT FROM request->>'tenant_id'
 OR released->>'related_order_id' IS DISTINCT FROM request->>'order_id'
 OR released->>'transaction_type' IS DISTINCT FROM 'RELEASE'
 OR released->>'provenance_ref' IS DISTINCT FROM 'fixture-absent:' || req
 OR released->>'timestamp' IS DISTINCT FROM proof.body::jsonb->>'occurred_at'
 OR timed->>'maximum_signature_window_ms' IS DISTINCT FROM '5000'
 OR timed->>'server_date' IS NULL OR timed->>'raw_server_date' IS NULL
 OR assessment->>'verdict' IS DISTINCT FROM 'PROVEN'
 OR assessment->'findings' IS DISTINCT FROM '[]'::jsonb
 OR assessment->'lookup'->>'available' IS DISTINCT FROM 'true'
 OR assessment->'lookup'->>'http_status' IS DISTINCT FROM '400'
 OR (assessment->'lookup'->>'raw_json')::jsonb->'code' IS DISTINCT FROM '-2013'::jsonb
 OR (SELECT count(*) FROM jsonb_object_keys((assessment->'lookup'->>'raw_json')::jsonb))!=2
 OR jsonb_typeof((assessment->'lookup'->>'raw_json')::jsonb->'msg') IS DISTINCT FROM 'string'
 OR assessment->'account'->>'available' IS DISTINCT FROM 'true'
 OR ((assessment->'account'->>'raw_json')::jsonb)->'before' IS DISTINCT FROM
 ((assessment->'account'->>'raw_json')::jsonb)->'after'
 OR EXISTS(SELECT 1 FROM ct_native_simulation_jobs WHERE tenant_id=request->>'tenant_id'
 AND venue_account_ref=request->>'venue_account_ref') THEN
 RAISE EXCEPTION 'absence closure requires original bounded zero-fill sources and expired custody'; END IF;
 SELECT encode(sha256(convert_to('[' || COALESCE(string_agg('"' || digest || '"',',' ORDER BY digest),'') || ']','UTF8')),'hex')
 INTO recovered_head FROM (
 SELECT digest FROM ct_ledger_transactions WHERE tenant_id=request->>'tenant_id'
 AND transaction_id!=proof.release_tx_id UNION ALL
 SELECT t.digest FROM ct_execution_current c JOIN ct_execution_transitions t ON t.transition_id=c.transition_id
 JOIN ct_execution_requests r ON r.execution_request_id=c.execution_request_id
 WHERE r.tenant_id=request->>'tenant_id' AND r.execution_request_id!=req UNION ALL
 SELECT digest FROM ct_execution_transitions WHERE execution_request_id=req
 AND body::jsonb->'resulting_state'=original_state UNION ALL
 SELECT digest FROM ct_risk_configs WHERE tenant_id=request->>'tenant_id' UNION ALL
 SELECT encode(sha256(convert_to(config_id,'UTF8')),'hex') digest
 FROM ct_risk_active_configs WHERE tenant_id=request->>'tenant_id'
 ) snapshot;
 IF recovered_head IS DISTINCT FROM assessment->>'internal_head_sha256'
 OR (current_body->>'revision')::bigint IS DISTINCT FROM
 (original_state->>'revision')::bigint + (CASE WHEN original_state->>'state'='UNKNOWN' THEN 2 ELSE 1 END)
 OR NOT EXISTS(SELECT 1 FROM ct_execution_current c JOIN ct_execution_transitions t ON t.transition_id=c.transition_id
 WHERE c.execution_request_id=req AND t.body::jsonb->>'evidence_ref'='reconciliation:fixture-absence:' || proof.digest) THEN
 RAISE EXCEPTION 'absence closure internal snapshot or atomic state proof mismatch'; END IF;
 server_clock:=(timed->>'server_date')::timestamptz;
 IF (timed->>'raw_server_date')::timestamptz IS DISTINCT FROM server_clock THEN
 RAISE EXCEPTION 'absence closure original server clock mismatch'; END IF;
 IF server_clock < (request->>'expires_at')::timestamptz + interval '6 seconds'
 OR server_clock < (timed->'lookup'->>'started_at')::timestamptz - interval '1 second'
 OR server_clock > (timed->'lookup'->>'finished_at')::timestamptz + interval '1 second'
 OR (proof.body::jsonb->>'occurred_at')::timestamptz < (assessment->>'occurred_at')::timestamptz
 OR (proof.body::jsonb->>'occurred_at')::timestamptz - (timed->'lookup'->>'started_at')::timestamptz > interval '10 seconds'
 OR NOT EXISTS(SELECT 1 FROM ct_execution_transitions WHERE execution_request_id=req
 AND body::jsonb->>'evidence_ref'='fixture-bound:' || proof.bound_digest
 AND body::jsonb->'resulting_state'->>'state'='SUBMITTING') THEN
 RAISE EXCEPTION 'absence closure elapsed original signature window unproven'; END IF;
 IF EXISTS(SELECT 1 FROM (
 SELECT value->>'asset' asset,value->>'account' account,value->>'portfolio_id' portfolio,
 sum((value->>'amount')::numeric) amount FROM jsonb_array_elements(
 (original->'postings') || (released->'postings')) GROUP BY 1,2,3
 ) combined WHERE amount!=0)
 OR (SELECT COALESCE(sum(p.amount),0) FROM ct_ledger_postings p
 JOIN ct_ledger_transactions t USING(transaction_id) WHERE p.tenant_id=request->>'tenant_id'
 AND p.portfolio_id=request->>'portfolio_id' AND p.account='RESERVED'
 AND t.related_order_id=request->>'order_id') != 0 THEN
 RAISE EXCEPTION 'absence closure must restore whole original custody exactly once'; END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_absence_closure_guard ON ct_fixture_absence_closures;
CREATE CONSTRAINT TRIGGER ct_absence_closure_guard AFTER INSERT ON ct_fixture_absence_closures
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ct_verify_fixture_absence_closure();
DROP TRIGGER IF EXISTS ct_absence_closure_ledger_guard ON ct_ledger_transactions;
CREATE CONSTRAINT TRIGGER ct_absence_closure_ledger_guard AFTER INSERT ON ct_ledger_transactions
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ct_verify_fixture_absence_closure();
DO $$ DECLARE table_name text; BEGIN
 FOREACH table_name IN ARRAY ARRAY['ct_fixture_timed_lookups','ct_fixture_absence_closures'] LOOP
 EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I',table_name || '_immutable',table_name);
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change()',table_name || '_immutable',table_name);
 END LOOP;
END; $$;
INSERT INTO ct_migrations(version) VALUES(17) ON CONFLICT DO NOTHING;
COMMIT;
