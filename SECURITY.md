# Security Policy

## Current stage

CrazyTrader.ai is in architecture/bootstrap and is not yet approved for live trading.

## Reporting

Do not publish secrets, API keys, account identifiers, or exploitable security details in public issues.

Use private owner communication for sensitive findings until a private security-reporting channel is configured.

## Secret policy

Never commit:

- Binance API keys;
- Anthropic/OpenAI API keys;
- secret-store bootstrap tokens;
- database passwords;
- private certificates;
- recovery codes.

## Live trading

Live exchange credentials and live order submission are prohibited until the repository reaches the relevant certification phases.

## Dependency policy

Security-relevant dependencies must be pinned through the project's chosen dependency-management mechanism and reviewed for license/security implications.

## Financial safety

A vulnerability that can:

- bypass risk;
- bypass OPA;
- create duplicate orders;
- alter the ledger;
- expose secrets;
- bypass certification;
- disable kill switches;

is considered critical.
