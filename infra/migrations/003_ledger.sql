BEGIN;
CREATE TABLE IF NOT EXISTS ct_portfolios (
 portfolio_id text PRIMARY KEY, tenant_id text NOT NULL, mode text NOT NULL CHECK(mode IN ('MATH','STRATEGY','RESERVE')),
 digest text NOT NULL, body text NOT NULL, UNIQUE(tenant_id,portfolio_id)
);
CREATE TABLE IF NOT EXISTS ct_ledger_transactions (
 transaction_id text PRIMARY KEY, tenant_id text NOT NULL, source_event_id text NOT NULL,
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'), body text NOT NULL,
 transaction_type text NOT NULL CHECK(transaction_type IN ('FUNDING','ALLOCATION','RESERVATION','RELEASE','FILL','FEE','TRANSFER','CORRECTION')),
 related_order_id text, related_fill_id text,
 correction_of_id text REFERENCES ct_ledger_transactions(transaction_id),
 writer_xid bigint NOT NULL DEFAULT txid_current(),
 recorded_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,source_event_id), UNIQUE(tenant_id,transaction_id),
 CHECK((transaction_type='CORRECTION') = (correction_of_id IS NOT NULL)),
 CHECK(correction_of_id IS DISTINCT FROM transaction_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ct_ledger_compensation_identity ON ct_ledger_transactions(tenant_id,correction_of_id) WHERE transaction_type='CORRECTION';
CREATE UNIQUE INDEX IF NOT EXISTS ct_ledger_fill_identity ON ct_ledger_transactions(tenant_id,related_fill_id) WHERE transaction_type='FILL';
CREATE UNIQUE INDEX IF NOT EXISTS ct_ledger_reservation_identity ON ct_ledger_transactions(tenant_id,related_order_id) WHERE transaction_type='RESERVATION';
CREATE TABLE IF NOT EXISTS ct_ledger_postings (
 posting_id text PRIMARY KEY, transaction_id text NOT NULL, tenant_id text NOT NULL,
 portfolio_id text, account text NOT NULL CHECK(account IN ('AVAILABLE','RESERVED','INVENTORY','EXTERNAL','FEES','CAPITAL','REALIZED_PNL')),
 asset text NOT NULL, amount numeric(74,18) NOT NULL, valuation_ref text,
 FOREIGN KEY(tenant_id,transaction_id) REFERENCES ct_ledger_transactions(tenant_id,transaction_id),
 FOREIGN KEY(tenant_id,portfolio_id) REFERENCES ct_portfolios(tenant_id,portfolio_id),
 CHECK(amount <> 0 AND amount <> 'NaN'::numeric AND abs(amount) < power(10::numeric,56)),
 CHECK((account='EXTERNAL') = (portfolio_id IS NULL))
);
CREATE INDEX IF NOT EXISTS ct_ledger_account_history ON ct_ledger_postings(tenant_id,portfolio_id,account,asset);
CREATE OR REPLACE FUNCTION ct_check_ledger_balance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tx text; count_postings integer; payload jsonb;
BEGIN
 tx := NEW.transaction_id;
 SELECT count(*) INTO count_postings FROM ct_ledger_postings WHERE transaction_id=tx;
 IF count_postings < 2 OR count_postings > 100 THEN RAISE EXCEPTION 'bounded balanced postings required'; END IF;
 IF EXISTS(SELECT asset FROM ct_ledger_postings WHERE transaction_id=tx GROUP BY asset HAVING sum(amount) <> 0) THEN
 RAISE EXCEPTION 'unbalanced ledger asset'; END IF;
 IF EXISTS(SELECT 1 FROM ct_ledger_transactions a JOIN ct_ledger_transactions b ON b.transaction_id=a.correction_of_id
           WHERE a.transaction_id=tx AND a.tenant_id <> b.tenant_id) THEN RAISE EXCEPTION 'correction tenant mismatch'; END IF;
 IF EXISTS(
 SELECT 1 FROM ct_ledger_postings all_p JOIN
 (SELECT DISTINCT tenant_id,portfolio_id,account,asset FROM ct_ledger_postings WHERE transaction_id=tx
  AND account IN ('AVAILABLE','RESERVED','INVENTORY')) affected
 ON all_p.tenant_id=affected.tenant_id AND all_p.portfolio_id=affected.portfolio_id
 AND all_p.account=affected.account AND all_p.asset=affected.asset
 GROUP BY all_p.tenant_id,all_p.portfolio_id,all_p.account,all_p.asset HAVING sum(all_p.amount) < 0
 ) THEN RAISE EXCEPTION 'negative controlled funds'; END IF;
 IF EXISTS(
 SELECT 1 FROM ct_ledger_postings p JOIN ct_ledger_transactions t USING(transaction_id)
 WHERE p.tenant_id=NEW.tenant_id AND p.account='RESERVED'
 GROUP BY p.portfolio_id,p.asset,t.related_order_id
 HAVING sum(p.amount) < 0 OR t.related_order_id IS NULL
 ) THEN RAISE EXCEPTION 'negative or unattributed order reservation'; END IF;
 IF NEW.transaction_id IS NOT NULL AND EXISTS(
 SELECT 1 FROM ct_ledger_transactions t JOIN ct_ledger_postings p
 ON p.transaction_id IN (t.transaction_id,t.correction_of_id)
 WHERE t.transaction_id=tx AND t.transaction_type='CORRECTION'
 GROUP BY p.portfolio_id,p.account,p.asset HAVING sum(p.amount)<>0
 ) THEN RAISE EXCEPTION 'correction must fully compensate original attribution'; END IF;
 SELECT body::jsonb INTO payload FROM ct_ledger_transactions WHERE transaction_id=tx;
 IF EXISTS(SELECT 1 FROM ct_ledger_transactions t WHERE t.transaction_id=tx AND (
 t.digest IS DISTINCT FROM encode(sha256(convert_to(t.body,'UTF8')),'hex')
 OR t.transaction_id IS DISTINCT FROM payload->>'transaction_id'
 OR t.tenant_id IS DISTINCT FROM payload->>'tenant_id'
 OR t.source_event_id IS DISTINCT FROM payload->>'source_event_id'
 OR t.transaction_type IS DISTINCT FROM payload->>'transaction_type'
 OR t.related_order_id IS DISTINCT FROM payload->>'related_order_id'
 OR t.related_fill_id IS DISTINCT FROM payload->>'related_fill_id'
 OR t.correction_of_id IS DISTINCT FROM payload->>'correction_of_id')) THEN
 RAISE EXCEPTION 'journal immutable body/hash/provenance mismatch'; END IF;
 IF jsonb_array_length(payload->'postings') IS DISTINCT FROM count_postings THEN
 RAISE EXCEPTION 'journal body/posting count mismatch'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(payload->'postings') item
 LEFT JOIN ct_ledger_postings p ON p.posting_id=item->>'posting_id' AND p.transaction_id=tx
 WHERE p.posting_id IS NULL OR p.amount IS DISTINCT FROM (item->>'amount')::numeric
 OR p.portfolio_id IS DISTINCT FROM item->>'portfolio_id' OR p.account IS DISTINCT FROM item->>'account'
 OR p.asset IS DISTINCT FROM item->>'asset' OR p.valuation_ref IS DISTINCT FROM item->>'valuation_ref') THEN
 RAISE EXCEPTION 'journal body/posting content mismatch'; END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION ct_forbid_late_posting() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM ct_ledger_transactions WHERE transaction_id=NEW.transaction_id AND writer_xid=txid_current()) THEN
 RAISE EXCEPTION 'committed journal cannot gain postings'; END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION ct_lock_ledger_tenant() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended('ledger:' || NEW.tenant_id,0));
 RETURN NEW;
END; $$;
DO $$ DECLARE table_name text; BEGIN
 FOREACH table_name IN ARRAY ARRAY['ct_portfolios','ct_ledger_transactions','ct_ledger_postings'] LOOP
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname=table_name || '_immutable') THEN
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change()',table_name || '_immutable',table_name);
 END IF;
 END LOOP;
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='ct_ledger_transaction_balanced') THEN
 CREATE TRIGGER ct_ledger_same_transaction_postings BEFORE INSERT ON ct_ledger_postings FOR EACH ROW EXECUTE FUNCTION ct_forbid_late_posting();
 CREATE TRIGGER ct_ledger_tenant_serialized BEFORE INSERT ON ct_ledger_transactions FOR EACH ROW EXECUTE FUNCTION ct_lock_ledger_tenant();
 CREATE CONSTRAINT TRIGGER ct_ledger_transaction_balanced AFTER INSERT ON ct_ledger_transactions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ct_check_ledger_balance();
 CREATE CONSTRAINT TRIGGER ct_ledger_posting_balanced AFTER INSERT ON ct_ledger_postings DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ct_check_ledger_balance();
 END IF;
END; $$;
INSERT INTO ct_migrations(version) VALUES(3) ON CONFLICT DO NOTHING;
COMMIT;
