BEGIN;
CREATE TABLE IF NOT EXISTS ct_risk_configs (
 config_id text PRIMARY KEY, tenant_id text NOT NULL, actor_id text NOT NULL,
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'), body text NOT NULL,
 installed_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,actor_id,config_id)
);
CREATE TABLE IF NOT EXISTS ct_risk_active_configs (
 tenant_id text NOT NULL, actor_id text NOT NULL, config_id text NOT NULL,
 PRIMARY KEY(tenant_id,actor_id),
 FOREIGN KEY(tenant_id,actor_id,config_id) REFERENCES ct_risk_configs(tenant_id,actor_id,config_id)
);
CREATE TABLE IF NOT EXISTS ct_owner_config_activations (
 activation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id text NOT NULL, actor_id text NOT NULL,
 previous_config_id text REFERENCES ct_risk_configs(config_id),
 config_id text NOT NULL REFERENCES ct_risk_configs(config_id),
 activated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE OR REPLACE FUNCTION ct_audit_config_activation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='INSERT' THEN
 INSERT INTO ct_owner_config_activations(tenant_id,actor_id,config_id)
 VALUES(NEW.tenant_id,NEW.actor_id,NEW.config_id);
 ELSIF NEW.config_id IS DISTINCT FROM OLD.config_id THEN
 INSERT INTO ct_owner_config_activations(tenant_id,actor_id,previous_config_id,config_id)
 VALUES(NEW.tenant_id,NEW.actor_id,OLD.config_id,NEW.config_id);
 END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS ct_config_activation_audit ON ct_risk_active_configs;
CREATE TRIGGER ct_config_activation_audit AFTER INSERT OR UPDATE ON ct_risk_active_configs
 FOR EACH ROW EXECUTE FUNCTION ct_audit_config_activation();
DROP TRIGGER IF EXISTS ct_active_config_no_delete ON ct_risk_active_configs;
CREATE TRIGGER ct_active_config_no_delete BEFORE DELETE OR TRUNCATE ON ct_risk_active_configs
 FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change();
CREATE TABLE IF NOT EXISTS ct_venue_safety_facts (
 digest text PRIMARY KEY CHECK(digest ~ '^[a-f0-9]{64}$'), tenant_id text NOT NULL,
 environment text NOT NULL, execution_mode text NOT NULL, body text NOT NULL,
 observed_at timestamptz NOT NULL, UNIQUE(tenant_id,digest),
 UNIQUE(tenant_id,environment,execution_mode,observed_at)
);
CREATE TABLE IF NOT EXISTS ct_risk_source_facts (
 digest text PRIMARY KEY CHECK(digest ~ '^[a-f0-9]{64}$'),
 tenant_id text NOT NULL, resource_id text NOT NULL, source_service text NOT NULL,
 schema_ref text NOT NULL, body text NOT NULL, observed_at timestamptz NOT NULL,
 UNIQUE(tenant_id,resource_id,schema_ref,observed_at)
);
CREATE TABLE IF NOT EXISTS ct_risk_contexts (
 context_id text PRIMARY KEY, tenant_id text NOT NULL, intent_digest text NOT NULL,
 digest text NOT NULL UNIQUE CHECK(digest ~ '^[a-f0-9]{64}$'), body text NOT NULL,
 config_id text NOT NULL REFERENCES ct_risk_configs(config_id),
 observed_at timestamptz NOT NULL, UNIQUE(tenant_id,digest)
);
CREATE TABLE IF NOT EXISTS ct_trade_intents (
 intent_id text PRIMARY KEY, tenant_id text NOT NULL, digest text NOT NULL,
 body text NOT NULL, created_at timestamptz NOT NULL, UNIQUE(tenant_id,intent_id)
);
CREATE TABLE IF NOT EXISTS ct_risk_evaluations (
 record_digest text PRIMARY KEY CHECK(record_digest ~ '^[a-f0-9]{64}$'),
 tenant_id text NOT NULL, intent_id text NOT NULL, context_digest text NOT NULL,
 risk_decision_id text NOT NULL, body text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,intent_id),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES ct_trade_intents(tenant_id,intent_id),
 FOREIGN KEY(tenant_id,context_digest) REFERENCES ct_risk_contexts(tenant_id,digest)
);
DO $$ DECLARE table_name text; BEGIN
 FOREACH table_name IN ARRAY ARRAY['ct_owner_config_activations','ct_risk_configs','ct_venue_safety_facts','ct_risk_source_facts','ct_risk_contexts','ct_trade_intents','ct_risk_evaluations'] LOOP
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname=table_name || '_immutable') THEN
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change()',table_name || '_immutable',table_name);
 END IF;
 END LOOP;
END; $$;
INSERT INTO ct_migrations(version) VALUES(4) ON CONFLICT DO NOTHING;
COMMIT;
