# Known Issues / External Constraints

## Codex usage-limit auto-resume
Current Codex Goals can stop at a budget/usage limit. Repository code cannot force the OpenAI service to resume after allowance resets. The project implements durable automatic resumability; a product Resume action may still be required. See `CODEX_RESUME_PROTOCOL.md`.

## Repository visibility
Repository is currently public. Security must not depend on privacy, but if proprietary implementation/strategies are intended, the owner should switch it to private before substantial code is added.

## Future live validation
Codex Cloud will not receive live Binance secrets. L5/L6 require owner-controlled local setup/activation.

No current external blocker prevents independent implementation.

## Future live/canary authority conflict
AGENTS invariant10 forbids real money before L6; certification requires actual L5
canary trades to achieve L6. Phase4 preserves the stronger invariant and denies LIVE
before L6. An accepted owner ADR is needed at the owner-local live boundary; finish
independent engineering before requesting that material decision. No credentials
or live activation are requested by this checkpoint.

## Phase5 financial/venue scope still being closed
Current dispatch supports protective SIMULATION SELL through literal-loopback SDK
fixtures. Real venue five-minute notional averages/account order counts require sourced
proof, never last-price substitution or zero defaults. Published Fill/Ledger V1 assumes
quantity*price; rounded actual quoteQty needs additive accounting evidence/contracts.
Owner/system cap currencies need explicit binding/FX proof before future increasing
authority; production remains L0 and rejects increasing authority. These are engineering
dependencies, not external blockers or certification completion.
