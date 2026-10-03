BEGIN;
CREATE TABLE IF NOT EXISTS ct_unsent_execution_expiries (
 execution_request_id text PRIMARY KEY REFERENCES ct_execution_requests(execution_request_id),
 digest text NOT NULL UNIQUE, body text NOT NULL,
 release_tx_id text NOT NULL UNIQUE REFERENCES ct_ledger_transactions(transaction_id),
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE OR REPLACE FUNCTION ct_verify_unsent_expiry() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE req text; proof record; original jsonb; released jsonb; request jsonb; current_state text; BEGIN
 IF TG_TABLE_NAME='ct_unsent_execution_expiries' THEN req:=NEW.execution_request_id;
 ELSE
   IF NEW.body::jsonb->>'provenance_ref' NOT LIKE 'unsent-expiry:%' THEN RETURN NEW; END IF;
   req:=regexp_replace(NEW.body::jsonb->>'provenance_ref','^unsent-expiry:','');
 END IF;
 SELECT * INTO proof FROM ct_unsent_execution_expiries WHERE execution_request_id=req;
 SELECT r.body::jsonb,c.state INTO request,current_state FROM ct_execution_requests r
 JOIN ct_execution_current c USING(execution_request_id) WHERE r.execution_request_id=req;
 SELECT t.body::jsonb INTO original FROM ct_execution_reservations r JOIN ct_ledger_transactions t
 ON t.transaction_id=r.reservation_tx_id WHERE r.execution_request_id=req;
 SELECT body::jsonb INTO released FROM ct_ledger_transactions WHERE transaction_id=proof.release_tx_id;
 IF proof IS NULL OR original IS NULL OR released IS NULL
 OR proof.body::jsonb->>'occurred_at' IS NULL OR current_state IS DISTINCT FROM 'EXPIRED'
 OR request->>'execution_mode' IS DISTINCT FROM 'SIMULATION'
 OR request->>'side' IS DISTINCT FROM 'SELL'
 OR proof.body::jsonb->'request' IS DISTINCT FROM request
 OR proof.body::jsonb->'original_reservation' IS DISTINCT FROM original
 OR proof.body::jsonb->'release' IS DISTINCT FROM released
 OR proof.body::jsonb->>'actor_id' IS DISTINCT FROM request->>'actor_id'
 OR (proof.body::jsonb->>'occurred_at')::timestamptz < (request->>'expires_at')::timestamptz
 OR released->>'transaction_type' IS DISTINCT FROM 'RELEASE'
 OR released->>'tenant_id' IS DISTINCT FROM request->>'tenant_id'
 OR released->>'actor_id' IS DISTINCT FROM request->>'actor_id'
 OR released->>'provenance_ref' IS DISTINCT FROM 'unsent-expiry:' || req
 OR released->>'related_order_id' IS DISTINCT FROM request->>'order_id'
 OR EXISTS(SELECT 1 FROM ct_execution_transitions WHERE execution_request_id=req
 AND body::jsonb->'resulting_state'->>'state' NOT IN('CREATED','RISK_PENDING','AUTHORIZED','EXPIRED'))
 OR EXISTS(SELECT 1 FROM ct_execution_observations WHERE execution_request_id=req)
 OR EXISTS(SELECT 1 FROM ct_native_simulation_receipts WHERE execution_request_id=req) THEN
 RAISE EXCEPTION 'unsent expiry requires expired original undispatched request and custody'; END IF;
 IF EXISTS(SELECT 1 FROM (
   SELECT value->>'asset' asset,value->>'account' account,value->>'portfolio_id' portfolio,
   sum((value->>'amount')::numeric) amount FROM jsonb_array_elements(
     (original->'postings') || (released->'postings')) GROUP BY 1,2,3
 ) combined WHERE amount!=0) THEN
 RAISE EXCEPTION 'unsent expiry must restore exact original custody'; END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_unsent_expiry_guard ON ct_unsent_execution_expiries;
CREATE CONSTRAINT TRIGGER ct_unsent_expiry_guard AFTER INSERT ON ct_unsent_execution_expiries
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ct_verify_unsent_expiry();
DROP TRIGGER IF EXISTS ct_unsent_expiry_ledger_guard ON ct_ledger_transactions;
CREATE CONSTRAINT TRIGGER ct_unsent_expiry_ledger_guard AFTER INSERT ON ct_ledger_transactions
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ct_verify_unsent_expiry();
DROP TRIGGER IF EXISTS ct_unsent_expiry_immutable ON ct_unsent_execution_expiries;
CREATE TRIGGER ct_unsent_expiry_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
 ON ct_unsent_execution_expiries FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change();
INSERT INTO ct_migrations(version) VALUES(14) ON CONFLICT DO NOTHING;
COMMIT;
