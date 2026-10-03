.PHONY: setup check schemas
setup:
	uv sync --locked
	uv sync --locked --project services/market-data/sdk
check:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked mypy packages/contracts/src packages/platform/src packages/market/src packages/ledger/src
	uv run --locked pytest
	uv run --locked python scripts/export_schemas.py --check
	uv run --locked python scripts/scan_secrets.py
	uv run --locked --project services/market-data/sdk python services/market-data/sdk/verify_offline.py
schemas:
	uv run --locked python scripts/export_schemas.py

integration:
	uv run --locked python scripts/platform_integration.py
	uv run --locked python scripts/market_integration.py
