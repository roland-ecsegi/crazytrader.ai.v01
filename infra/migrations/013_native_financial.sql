BEGIN;
CREATE TABLE IF NOT EXISTS ct_native_simulation_incidents (
 incident_id text PRIMARY KEY, tenant_id text NOT NULL,
 execution_request_id text NOT NULL REFERENCES ct_native_simulation_jobs(execution_request_id),
 receipt_digest text NOT NULL REFERENCES ct_native_simulation_receipts(digest),
 body text NOT NULL, digest text NOT NULL,
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE OR REPLACE FUNCTION ct_verify_native_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE admission jsonb; claim_state text; BEGIN
 SELECT body::jsonb INTO admission FROM ct_native_simulation_jobs
 WHERE execution_request_id=NEW.execution_request_id AND job_digest=NEW.job_digest;
 SELECT state INTO claim_state FROM ct_execution_current WHERE execution_request_id=NEW.execution_request_id;
 IF admission IS NULL OR NEW.body::jsonb->'admission' IS DISTINCT FROM admission
 OR NEW.body::jsonb->'receipt'->'job' IS DISTINCT FROM admission->'job'
 OR NEW.body::jsonb->'receipt'->>'job_sha256' IS DISTINCT FROM NEW.job_digest
 OR (NEW.body::jsonb->'receipt'->>'available')::boolean IS DISTINCT FROM NEW.available
 OR (NEW.body::jsonb->'receipt'->>'observed_at')::timestamptz IS DISTINCT FROM NEW.observed_at
 OR claim_state IS NULL OR claim_state='AUTHORIZED' THEN
 RAISE EXCEPTION 'native receipt requires original owned claimed source'; END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_native_receipt_guard ON ct_native_simulation_receipts;
CREATE TRIGGER ct_native_receipt_guard BEFORE INSERT ON ct_native_simulation_receipts
 FOR EACH ROW EXECUTE FUNCTION ct_verify_native_receipt();

CREATE OR REPLACE FUNCTION ct_verify_native_completion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE req text; proof record; journal jsonb; source jsonb; job jsonb; request jsonb;
 fill jsonb; raw jsonb; state_body jsonb; remainder numeric; instrument jsonb;
 base_net numeric; quote_net numeric; fees numeric; gross numeric; fee numeric; BEGIN
 IF TG_TABLE_NAME='ct_native_simulation_postings' THEN req:=NEW.execution_request_id;
 ELSIF TG_TABLE_NAME='ct_execution_current' THEN
   req:=NEW.execution_request_id;
   IF NEW.state!='FILLED' OR NOT EXISTS(SELECT 1 FROM ct_native_simulation_jobs WHERE execution_request_id=req) THEN RETURN NEW; END IF;
 ELSE
   IF NOT (NEW.body::jsonb ? 'native_evidence') THEN RETURN NEW; END IF;
   req:=NEW.body::jsonb->'native_evidence'->'receipt'->'job'->>'execution_request_id';
 END IF;
 SELECT * INTO proof FROM ct_native_simulation_postings WHERE execution_request_id=req;
 IF proof IS NULL THEN RAISE EXCEPTION 'native completion requires atomic financial proof'; END IF;
 SELECT body::jsonb INTO source FROM ct_native_simulation_receipts
 WHERE digest=proof.receipt_digest AND execution_request_id=req AND available;
 SELECT body::jsonb INTO journal FROM ct_ledger_transactions WHERE transaction_id=proof.ledger_tx_id;
 SELECT t.body::jsonb->'resulting_state' INTO state_body FROM ct_execution_current c
 JOIN ct_execution_transitions t USING(transition_id) WHERE c.execution_request_id=req AND c.state='FILLED';
 job:=source->'receipt'->'job'; request:=source->'admission'->'request';
 fill:=journal->'native_evidence'->'fill'; raw:=(source->'receipt'->>'raw_json')::jsonb;
 IF source IS NULL OR journal IS NULL OR state_body IS NULL
 OR journal->'native_evidence'->'receipt' IS DISTINCT FROM source->'receipt'
 OR journal->>'transaction_type' IS DISTINCT FROM 'FILL'
 OR journal->>'tenant_id' IS DISTINCT FROM request->>'tenant_id'
 OR journal->>'actor_id' IS DISTINCT FROM request->>'actor_id'
 OR journal->>'related_order_id' IS DISTINCT FROM request->>'order_id'
 OR journal->>'fill_side' IS DISTINCT FROM 'SELL'
 OR journal->'fill_data' IS DISTINCT FROM fill
 OR journal->>'related_fill_id' IS DISTINCT FROM fill->>'venue_fill_id'
 OR (fill->>'quantity')::numeric IS DISTINCT FROM (job->>'quantity')::numeric
 OR (fill->>'price')::numeric IS DISTINCT FROM (raw->'fills'->0->>'last_px')::numeric
 OR (fill->>'fee_amount')::numeric IS DISTINCT FROM split_part(raw->'fills'->0->>'commission',' ',1)::numeric
 OR fill->>'fee_asset' IS DISTINCT FROM journal->>'quote_asset'
 OR state_body->'request' IS DISTINCT FROM request
 OR (state_body->>'filled_quantity')::numeric IS DISTINCT FROM (job->>'quantity')::numeric THEN
 RAISE EXCEPTION 'native completion financial/source ownership mismatch'; END IF;
 SELECT value INTO instrument FROM jsonb_array_elements(
   (job->'venue_rules'->'rules'->>'source_json')::jsonb->'symbols')
 WHERE value->>'symbol'=job->>'symbol';
 IF instrument IS NULL OR journal->>'base_asset' IS DISTINCT FROM instrument->>'baseAsset'
 OR journal->>'quote_asset' IS DISTINCT FROM instrument->>'quoteAsset'
 OR EXISTS(SELECT 1 FROM ct_ledger_postings WHERE transaction_id=proof.ledger_tx_id
 AND portfolio_id IS NOT NULL AND portfolio_id IS DISTINCT FROM request->>'portfolio_id') THEN
 RAISE EXCEPTION 'native financial asset/portfolio mismatch'; END IF;
 fee:=(fill->>'fee_amount')::numeric;
 gross:=(raw->'after'->>(instrument->>'quoteAsset'))::numeric
       -(raw->'before'->>(instrument->>'quoteAsset'))::numeric+fee;
 SELECT COALESCE(sum(amount) FILTER(WHERE asset=instrument->>'baseAsset'
 AND account IN('AVAILABLE','INVENTORY','RESERVED')),0),
 COALESCE(sum(amount) FILTER(WHERE asset=instrument->>'quoteAsset'
 AND account IN('AVAILABLE','INVENTORY','RESERVED')),0),
 COALESCE(sum(amount) FILTER(WHERE asset=instrument->>'quoteAsset' AND account='FEES'),0)
 INTO base_net,quote_net,fees FROM ct_ledger_postings WHERE transaction_id=proof.ledger_tx_id;
 IF (journal->'native_evidence'->>'quote_quantity')::numeric IS DISTINCT FROM gross
 OR base_net IS DISTINCT FROM -(job->>'quantity')::numeric
 OR quote_net IS DISTINCT FROM gross-fee OR fees IS DISTINCT FROM fee THEN
 RAISE EXCEPTION 'native posting cash/commission differs from source'; END IF;
 SELECT COALESCE(sum(p.amount),0) INTO remainder FROM ct_ledger_postings p
 JOIN ct_ledger_transactions t USING(transaction_id)
 WHERE p.tenant_id=request->>'tenant_id' AND p.portfolio_id=request->>'portfolio_id'
 AND p.account='RESERVED' AND t.related_order_id=request->>'order_id';
 IF remainder IS DISTINCT FROM 0::numeric THEN RAISE EXCEPTION 'native full fill retains reservation'; END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_native_posting_guard ON ct_native_simulation_postings;
DROP TRIGGER IF EXISTS ct_native_posting_complete ON ct_native_simulation_postings;
CREATE CONSTRAINT TRIGGER ct_native_posting_complete AFTER INSERT ON ct_native_simulation_postings
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ct_verify_native_completion();
DROP TRIGGER IF EXISTS ct_native_ledger_complete ON ct_ledger_transactions;
CREATE CONSTRAINT TRIGGER ct_native_ledger_complete AFTER INSERT ON ct_ledger_transactions
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ct_verify_native_completion();
DROP TRIGGER IF EXISTS ct_native_state_complete ON ct_execution_current;
CREATE CONSTRAINT TRIGGER ct_native_state_complete AFTER INSERT OR UPDATE ON ct_execution_current
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ct_verify_native_completion();
DROP TRIGGER IF EXISTS ct_native_incident_immutable ON ct_native_simulation_incidents;
CREATE TRIGGER ct_native_incident_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
 ON ct_native_simulation_incidents FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change();
INSERT INTO ct_migrations(version) VALUES(13) ON CONFLICT DO NOTHING;
COMMIT;
