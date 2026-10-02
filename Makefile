.PHONY: setup check schemas
setup:
	uv sync --locked
check:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked mypy packages/contracts/src
	uv run --locked pytest
	uv run --locked python scripts/export_schemas.py --check
	uv run --locked python scripts/scan_secrets.py
schemas:
	uv run --locked python scripts/export_schemas.py
