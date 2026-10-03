BEGIN;
CREATE TABLE IF NOT EXISTS ct_market_sources (
 digest text PRIMARY KEY CHECK(digest ~ '^[a-f0-9]{64}$'),
 tenant_id text NOT NULL, environment text NOT NULL CHECK(environment IN ('PUBLIC','SANDBOX')),
 symbol text NOT NULL, metadata_version text NOT NULL, parser_version text NOT NULL,
 object_key text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ct_market_records (
 tenant_id text NOT NULL, environment text NOT NULL, symbol text NOT NULL,
 trade_id bigint NOT NULL CHECK(trade_id >= 0), digest text NOT NULL,
 source_digest text NOT NULL REFERENCES ct_market_sources(digest), body text NOT NULL,
 PRIMARY KEY(tenant_id,environment,symbol,trade_id)
);
CREATE TABLE IF NOT EXISTS ct_market_batches (
 source_digest text PRIMARY KEY REFERENCES ct_market_sources(digest),
 status text NOT NULL CHECK(status IN ('PENDING','COMMITTED','FAILED')),
 error_category text, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ct_market_watermarks (
 tenant_id text NOT NULL, environment text NOT NULL, symbol text NOT NULL,
 last_trade_id bigint NOT NULL, source_digest text NOT NULL REFERENCES ct_market_sources(digest),
 PRIMARY KEY(tenant_id,environment,symbol)
);
CREATE TABLE IF NOT EXISTS ct_market_checkpoints (
 tenant_id text NOT NULL, environment text NOT NULL, symbol text NOT NULL,
 body text NOT NULL, health text NOT NULL CHECK(health IN ('UNKNOWN','DEGRADED','HEALTHY')),
 heartbeat_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,environment,symbol)
);
DO $$ DECLARE table_name text; BEGIN
 FOREACH table_name IN ARRAY ARRAY['ct_market_sources','ct_market_records'] LOOP
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname=table_name || '_immutable') THEN
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change()',table_name || '_immutable',table_name);
 END IF;
 END LOOP;
END; $$;
INSERT INTO ct_migrations(version) VALUES(2) ON CONFLICT DO NOTHING;
COMMIT;
