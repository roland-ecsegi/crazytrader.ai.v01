# Known Issues / External Constraints

## Codex usage-limit auto-resume
Current Codex Goals can stop at a budget/usage limit. Repository code cannot force the OpenAI service to resume after allowance resets. The project implements durable automatic resumability; a product Resume action may still be required. See `CODEX_RESUME_PROTOCOL.md`.

## Repository visibility
Repository is currently public. Security must not depend on privacy, but if proprietary implementation/strategies are intended, the owner should switch it to private before substantial code is added.

## Future live validation
Codex Cloud will not receive live Binance secrets. L5/L6 require owner-controlled local setup/activation.

No current blocker prevents Phase 0 implementation.
