# Phase 0 ExecPlan — Repository and contracts

## Goal
Establish reproducible tooling and immutable typed V1 domain/event foundations; pass all nine Phase 0 acceptance criteria.

## Non-goals
No exchange integration, execution authorization, infrastructure runtime or live readiness claim.

## Architecture context
AGENTS.md, ADR-0001..0005, all architecture/specifications and roadmap/program files read. Financial values use decimal strings; proposals never confer authority. L0 remains unchanged.

## Current state
Documentation-only baseline c123958 on codex/enterprise-local-autonomous.

## Proposed design
Python 3.12, uv lockfile, Pydantic frozen/extra-forbidden models and exported JSON Schema. TypeScript UI workspace reserved for Phase 13. Strict UTC, finite decimals, cross-field intent invariants; explicit enum states and versioned event registry. Event payload contracts evolve per producer phase.

## Files and ownership
packages/contracts: public domain validation; packages/domain and events: ownership guidance; apps/services/agents/policies/infra: documented boundaries. tests/contracts: negative contract evidence. scripts and CI: identical developer checks.

## Dependencies and licensing
Pydantic 2.12.3 MIT for validation/schema, pytest 8.4.2 MIT, Ruff 0.14.3 MIT, mypy 1.18.2 MIT, Hatchling 1.27.0 MIT, uv 0.12.19 MIT/Apache-2.0. Lock transitive versions; no custom validation framework. These validators support the boundary but do not authorize execution. Replace through versioned schema adapters. Vulnerability/SBOM evaluation remains required before live (Phase 14).

## Failure modes
Malformed/nonfinite/float financial values, missing sizing, contradictory direction, naive time and unknown schema fail validation. Reduction classification is a proposal only; holdings verification belongs to Hard Risk. Frozen models protect normal mutation, not malicious in-process code.

## Security and financial-risk impact
No credentials or venue calls. Untrusted extra fields denied. No bypass through owner/manual source. Schema validation does not establish current certification/permissions/expiry or verified risk direction.

## Data/event migrations
V1 initial schemas, no persisted data. Breaking changes use new versions; replay remains at-least-once. No payload dicts in financial models.

## Implementation steps
- [x] Toolchain, structure and ownership docs.
- [x] Typed contracts and deterministic schema export.
- [x] Positive/negative validation tests and CI/secret scan.
- [x] Adversarial review, repair, checkpoint and proceed Phase 0.5.

## Test plan
uv sync --locked; uv run ruff check .; uv run ruff format --check .; uv run mypy packages/contracts/src; uv run pytest; uv run python scripts/export_schemas.py --check; uv run python scripts/scan_secrets.py.

## Acceptance criteria
All Phase 0 acceptance criteria in PHASE_0_BOOTSTRAP.md; no claim of infrastructure integration or certification beyond L0.

## Rollback/recovery
Revert additive bootstrap commit; no runtime state to migrate. Preserve docs/evidence.

## Resume checkpoint
Branch codex/enterprise-local-autonomous; Phase 0 remote commit b610027 (same validated tree as local 847fdcc). Current step: Phase 0 gate passed. Next: Phase 0.5 compatibility/license ExecPlan and spikes. Uncommitted work: checkpoint documentation only. Blockers: none (network commands require platform escalation). Usage: active. Verification: make check — 43 tests, lint/format/strict types/schema drift/secret scan pass; uv build produced wheel and sdist.

## Progress log
2026-10-02: read binding specifications; selected Python contract-first tooling.

## Decisions
Do not impose UUID-only identifiers: repository examples use stable namespaced IDs. Decimal strings serialize canonically and reject binary floats. Reserve UI directory until actual UI tooling is justified.

## Completion summary
Shipped eleven V1 foundations, 22 deterministic schema files, pinned toolchain/CI and documented monorepo boundaries. Adversarial self-review repaired exponent/whitespace decimal notation, integer timestamps, zero-duration horizons and mutable event catalog construction. Model evidence references are not independently verified; actual payload schemas and transition/storage authorization are later-phase work. Phase 0 PASS; L0 unchanged; proceed Phase 0.5.
