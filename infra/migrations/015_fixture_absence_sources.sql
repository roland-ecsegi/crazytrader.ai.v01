BEGIN;
CREATE TABLE IF NOT EXISTS ct_fixture_order_lookups (
 digest text PRIMARY KEY, execution_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 body text NOT NULL, CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE TABLE IF NOT EXISTS ct_fixture_absence_assessments (
 digest text PRIMARY KEY, execution_request_id text NOT NULL REFERENCES ct_execution_requests(execution_request_id),
 lookup_digest text NOT NULL REFERENCES ct_fixture_order_lookups(digest),
 account_digest text NOT NULL REFERENCES ct_account_read_sources(digest),
 body text NOT NULL, verdict text NOT NULL CHECK(verdict IN('PROVEN','DENIED')),
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE OR REPLACE FUNCTION ct_verify_fixture_absence_source() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE request jsonb; lookup_body jsonb; account_body jsonb; BEGIN
 SELECT body::jsonb INTO request FROM ct_execution_requests WHERE execution_request_id=NEW.execution_request_id;
 IF TG_TABLE_NAME='ct_fixture_order_lookups' THEN
   IF NEW.body::jsonb->'request' IS DISTINCT FROM request THEN
     RAISE EXCEPTION 'fixture lookup requires original request'; END IF;
 ELSE
   SELECT body::jsonb INTO lookup_body FROM ct_fixture_order_lookups WHERE digest=NEW.lookup_digest
   AND execution_request_id=NEW.execution_request_id;
   SELECT body::jsonb INTO account_body FROM ct_account_read_sources WHERE digest=NEW.account_digest
   AND anchor_request_id=NEW.execution_request_id;
   IF lookup_body IS NULL OR account_body IS NULL
   OR NEW.body::jsonb->'state'->'request' IS DISTINCT FROM request
   OR NEW.body::jsonb->'lookup' IS DISTINCT FROM lookup_body
   OR NEW.body::jsonb->'account' IS DISTINCT FROM account_body
   OR NEW.body::jsonb->>'verdict' IS DISTINCT FROM NEW.verdict THEN
     RAISE EXCEPTION 'fixture absence assessment original source mismatch'; END IF;
 END IF;
 RETURN NEW;
END; $$;
DO $$ DECLARE table_name text; BEGIN
 FOREACH table_name IN ARRAY ARRAY['ct_fixture_order_lookups','ct_fixture_absence_assessments'] LOOP
 EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I',table_name || '_guard',table_name);
 EXECUTE format('CREATE TRIGGER %I BEFORE INSERT ON %I FOR EACH ROW EXECUTE FUNCTION ct_verify_fixture_absence_source()',table_name || '_guard',table_name);
 EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I',table_name || '_immutable',table_name);
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change()',table_name || '_immutable',table_name);
 END LOOP;
END; $$;
INSERT INTO ct_migrations(version) VALUES(15) ON CONFLICT DO NOTHING;
COMMIT;
