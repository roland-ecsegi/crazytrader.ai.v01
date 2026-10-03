BEGIN;
CREATE TABLE IF NOT EXISTS ct_venue_rule_receipts (
 digest text PRIMARY KEY CHECK(digest ~ '^[a-f0-9]{64}$'),
 tenant_id text NOT NULL, environment text NOT NULL CHECK(environment IN ('SANDBOX','PUBLIC')),
 symbol text NOT NULL, metadata_version text NOT NULL, source_digest text NOT NULL,
 body text NOT NULL, observed_at timestamptz NOT NULL,
 UNIQUE(tenant_id,environment,symbol,observed_at),
 CHECK(encode(sha256(convert_to(body,'UTF8')),'hex')=digest)
);
CREATE INDEX IF NOT EXISTS ct_venue_rule_receipts_lookup
 ON ct_venue_rule_receipts(tenant_id,environment,symbol,observed_at DESC);
DROP TRIGGER IF EXISTS ct_venue_rule_receipts_immutable ON ct_venue_rule_receipts;
CREATE TRIGGER ct_venue_rule_receipts_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
 ON ct_venue_rule_receipts FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change();
INSERT INTO ct_migrations(version) VALUES(9) ON CONFLICT DO NOTHING;
COMMIT;
