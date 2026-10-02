BEGIN;
CREATE TABLE IF NOT EXISTS ct_migrations(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS ct_artifacts (
    digest text PRIMARY KEY CHECK (digest ~ '^[a-f0-9]{64}$'),
    tenant_id text NOT NULL,
    schema_ref text NOT NULL,
    body text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ct_events (
    event_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    event_type text NOT NULL,
    digest text NOT NULL CHECK (digest ~ '^[a-f0-9]{64}$'),
    envelope text NOT NULL,
    payload_digest text NOT NULL REFERENCES ct_artifacts(digest),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ct_outbox (
    event_id text PRIMARY KEY REFERENCES ct_events(event_id),
    sent_at timestamptz,
    attempts integer NOT NULL DEFAULT 0 CHECK(attempts >= 0)
);
CREATE TABLE IF NOT EXISTS ct_inbox (
    consumer text NOT NULL,
    event_id text NOT NULL REFERENCES ct_events(event_id),
    digest text NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(consumer, event_id)
);
CREATE TABLE IF NOT EXISTS ct_audit (
    audit_id text PRIMARY KEY,
    event_id text NOT NULL UNIQUE REFERENCES ct_events(event_id),
    tenant_id text NOT NULL,
    actor_id text NOT NULL,
    action text NOT NULL,
    trace_id text NOT NULL,
    payload_digest text NOT NULL REFERENCES ct_artifacts(digest),
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ct_notifications (
    event_id text PRIMARY KEY REFERENCES ct_events(event_id),
    status text NOT NULL CHECK(status IN ('PENDING','DELIVERED','FAILED')),
    attempts integer NOT NULL DEFAULT 0 CHECK(attempts >= 0),
    error_category text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ct_service_health (
    service_id text PRIMARY KEY CHECK(service_id IN ('audit','outbox','notification')),
    health text NOT NULL CHECK(health IN ('HEALTHY','DEGRADED')),
    heartbeat_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION ct_forbid_history_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'append-only history'; END;
$$;
DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['ct_artifacts','ct_events','ct_inbox','ct_audit'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = table_name || '_immutable') THEN
            EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION ct_forbid_history_change()', table_name || '_immutable', table_name);
        END IF;
    END LOOP;
END;
$$;
INSERT INTO ct_migrations(version) VALUES (1) ON CONFLICT DO NOTHING;
COMMIT;
