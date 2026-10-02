# Contracts V1

Frozen Pydantic records and generated validation/serialization JSON Schemas. Financial values on the wire are decimal strings. Python callers may also use finite `Decimal`. UTC timestamps include an explicit zero offset. Namespaced identifiers support repository examples.

`TradeIntent` is a proposal; declared risk effect must be independently verified against holdings in Phase 4. Schema validity confers no permission, freshness, certification or execution authority. Immutable records alone do not provide durable uniqueness, evidence integrity or append-only storage.

Events currently carry immutable content-addressed payload references. Actual producer/consumer payload schemas, durable object resolution and replay compatibility checks are required before service integration. Event names match `docs/specs/EVENT_CATALOG.md`; consumers must expect at-least-once delivery.

Use `make schemas` for intentional schema updates, and `make check` to detect drift. Breaking changes require a new schema version. No live venue path exists.

Generated JSON Schemas document wire structure; cross-field and finite/precision/decimal range/time invariants are enforced by Python validators. Every boundary must revalidate with the versioned server contract; passing structural JSON Schema alone does not establish semantic validity.
