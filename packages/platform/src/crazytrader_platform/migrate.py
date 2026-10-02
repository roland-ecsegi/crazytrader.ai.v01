"""Explicit schema administration entrypoint, separate from service workers."""

from pathlib import Path

from crazytrader_platform.runtime import required
from crazytrader_platform.storage import EventStore


def main() -> None:
    try:
        EventStore(required("CT_DATABASE_DSN")).migrate(Path(required("CT_MIGRATION_PATH")))
    except Exception:
        raise SystemExit("platform migration failed; inspect owner-local database health") from None
    print("platform migration applied")


if __name__ == "__main__":
    main()
