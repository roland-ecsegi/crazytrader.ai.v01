BEGIN;
-- Legacy prepared rows remain NULL and fail dispatch; never retrospectively grant authority.
ALTER TABLE ct_execution_reservations ADD COLUMN IF NOT EXISTS venue_rules_digest text
 REFERENCES ct_venue_rule_receipts(digest);
INSERT INTO ct_migrations(version) VALUES(10) ON CONFLICT DO NOTHING;
COMMIT;
