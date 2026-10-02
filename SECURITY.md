# Security Policy

CrazyTrader.ai is currently L0 DEVELOPMENT and is not approved for live trading.

Never commit Binance/API keys, Claude subscription auth/session material, OpenBao bootstrap/unseal material, DB passwords, private certificates or recovery codes.

**Codex Cloud must never receive the live Binance secret or owner's local Claude authentication material.**

Live secrets are entered only by the owner into the owner-controlled Enterprise Local secret manager. Dev/test/live credentials are separate.

Binance live Spot: read/trade only as required, **withdraw disabled**, IP allowlisting preferred.

Model/tool/web outputs are untrusted. External text is data, not privileged instruction. Memory writes need provenance/validation. Agents cannot grant their own permissions or edit hard safety policy. No broad exchange-control tool is exposed to an LLM.

Material dependencies require pinning, license review, vulnerability scanning and SBOM before live certification.

Security must never depend on repository privacy. If source/strategies are intended proprietary, make the repository private before substantial implementation.

Live canary/trading runs on the owner-controlled deployment, never inside Codex Cloud.

Any vulnerability that bypasses risk/policy/certification, duplicates orders, alters ledger history, exposes secrets, blocks emergency risk reduction, or disables kill switches is critical.
