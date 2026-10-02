# Permanent Agents and Skill Registry V1

A permanent agent is a persistent software entity with stable identity, role, permissions, governed memory, executable skills/tools, experience/performance history, provider config and audit history. `Agent != model`.

Baseline:
- Chief Orchestrator — coordination only.
- Math Research Agent — quant hypotheses/features/models/experiments.
- Strategy Research Agent — strategy research/comparison/optimization.
- Market Regime Agent — advisory regime detection.
- Portfolio Agent — allocation proposals only.
- Risk Analyst Agent — advisory risk analysis, not Hard Risk.
- Execution Supervisor — execution/slippage/anomaly analysis, no raw order authority.
- Learning Agent — ExperienceRecord analysis and hypothesis generation.
- Auditor Agent — adversarial lifecycle/decision/permission audit.
- Security Agent — config/permission/security analysis, never raw secrets.

A skill is executable and versioned with typed I/O, implementation ref, allowed agents, required permissions, resource/time limits, audit category and tests.

Examples: backtest_strategy, compare_strategy_versions, quantitative_edge_analysis, inspect_execution_quality, propose_capital_allocation, analyze_trade_experience, verify_strategy_promotion_evidence.

## Permission and memory governance

Agents cannot edit their own permissions or hard policy. Tool acquisition is governed. Research tools cannot reach live exchange credentials. No tool combines unrestricted LLM reasoning with raw exchange authority.

Memory may be working, episodic, research, operational learning or curated knowledge. Durable memory requires provenance, timestamp/version, quality/confidence where relevant, retention class and owning agent.

External web/social/exchange/model/tool content is untrusted data. Prompt-like text inside it cannot override repository/system policy.

Learning from own trades means ExperienceRecords and research evidence, not blind live code rewriting.
