# Permanent Agents and Skill Registry V1

## Permanent-agent rule

A permanent agent is a persistent software entity, not merely a prompt or temporary model invocation. Its identity survives provider/model changes.

Each agent has:
- stable agent_id and role;
- responsibilities;
- permission profile;
- executable skills/tools;
- working and long-term memory;
- experience/performance history;
- AI provider/model config;
- audit history.

## Baseline agents

### Chief Orchestrator
Coordinates tasks/dependencies, requests reviews, handles escalation. No direct trading authority.

### Math Research Agent
Generates quantitative hypotheses, features, model proposals and experiments; interprets statistical evidence. No live deployment authority.

### Strategy Research Agent
Generates/compares strategies, regime-specific ideas and parameter studies; registers candidates. No live deployment authority.

### Market Regime Agent
Classifies trend/range/volatility/liquidity regimes and transitions. Advisory only.

### Portfolio Agent
Analyzes capital efficiency/correlation and proposes allocation changes. Cannot exceed owner hard caps.

### Risk Analyst Agent
Analyzes emerging/degrading risk and recommends tighter limits. It is not the deterministic Hard Risk Engine.

### Execution Supervisor Agent
Inspects slippage, rejections, latency and execution anomalies; escalates reconciliation issues. Cannot directly submit raw exchange orders.

### Learning Agent
Turns ExperienceRecords into reusable lessons, detects repeated patterns and creates research hypotheses.

### Auditor Agent
Performs adversarial review of decision chains, permissions, promotion evidence and architecture invariants.

### Security Agent
Reviews config, permission drift, dependency/security findings and incidents. Never receives raw secrets.

## Skill contract

Every skill has:
- skill_id and semantic version;
- typed input schema;
- typed output schema;
- implementation reference;
- allowed_agents;
- required_permissions;
- resource/time limits;
- audit category;
- test suite.

### backtest_strategy
Inputs: strategy_version, dataset_version, timeframe, fee/slippage models.
Outputs: trade count, return metrics, max drawdown, Sharpe/Sortino, profit factor, expectancy, regime breakdown, failure reasons, reproducibility ref.

### compare_strategy_versions
Inputs: candidate versions, validation windows, cost model.
Outputs: normalized comparison, uncertainty/statistical relevance, degradation flags.

### quantitative_edge_analysis
Inputs: feature snapshot, model version, cost model, horizon.
Outputs: expected gross/net return, cost estimate, downside distribution, edge quality/confidence.

### inspect_execution_quality
Inputs: expected/actual fills, latency, venue/market state.
Outputs: slippage, reject/latency anomalies, execution-quality report.

### propose_capital_allocation
Inputs: performance quality, drawdown, correlations, liquidity, risk budget, regime.
Outputs: proposal, rationale, constraints. Never hard-cap authority.

### analyze_trade_experience
Inputs: ExperienceRecord set.
Outputs: clustered success/failure patterns, drift signals, research hypotheses.

### verify_strategy_promotion_evidence
Inputs: candidate lifecycle state and evidence refs.
Outputs: pass/fail gaps; never self-authorizes promotion.

## Permission governance

- Least privilege.
- Agents cannot change their own permission profiles.
- Tool acquisition/change is governed and audited.
- Research agents cannot access live exchange credentials.
- No unrestricted reasoning tool has raw exchange authority.
- Security/risk agents cannot disclose secrets to themselves.

## Memory governance

Memory types may include working, episodic, research, operational learning and curated knowledge.

Durable memory requires:
- provenance/source;
- timestamp/version;
- confidence/quality where relevant;
- owning agent;
- retention class;
- validation status.

External web/social/exchange/model/tool output is untrusted data. Embedded prompt-like instructions cannot override repository/system policy.

Learning from executed trades means ExperienceRecords, derived evidence and candidate research; it does not mean blind mutation/deployment of live code.
