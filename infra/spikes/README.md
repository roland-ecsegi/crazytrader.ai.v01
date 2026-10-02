# Reproducible compatibility spikes

Run `uv sync --project infra/spikes/python --locked`, then `uv run --project infra/spikes/python --locked python infra/spikes/python/compatibility.py` for offline trading-library checks. No exchange requests are made.

With the managed local Docker socket available, run `python infra/spikes/platform_probe.py`. Exact digest-pinned images are recorded in the script; pull them first when offline. It creates a unique internal network, no published ports, disposable containers/data and cleans up. PostgreSQL trust authentication and anonymous S3 are solely disposable fixtures on that isolated network. OpenBao is never initialized/unsealed. Do not use spike configuration in deployment.

`python infra/spikes/license_probe.py` verifies exact-tag upstream license documents with inherited proxy/CA trust. Generated JSON records are evidence artifacts. See [adoption decisions](../../docs/evidence/spikes/ADOPTION.md) for limitations and later required tests.
