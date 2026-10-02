# Permanent Agents and Skill Registry V1

## Permanent-agent rule

A permanent agent is a persistent software entity.

It is not merely a prompt or a temporary model invocation.

Identity must survive provider/model changes.

## Agent record

Each agent has:

- agent_id
- stable role
- responsibilities
- permissions
- tools
- skills
- working memory
- long-term memory
- experience history
- performance history
- provider/model configuration
- audit history

## Baseline agents

### Chief Orchestrator

Purpose:

- coordinate work;
- route tasks;
- handle dependencies;
- request reviews;
- escalate incidents.

No direct trading authority.

### Math Research Agent

Purpose:

- generate quantitative hypotheses;
- create features;
- run experiments;
- interpret statistical results;
- create model candidates.

No live deployment authority.

### Strategy Research Agent

Purpose:

- generate and compare strategies;
- research regime-specific behavior;
- optimize parameters;
- register strategy candidates.

No live deployment authority.

### Market Regime Agent

Purpose:

- classify regime;
- detect regime transition;
- publish advisory regime metadata.

Advisory only.

### Portfolio Agent

Purpose:

- propose capital allocation;
- analyze concentration and correlation;
- propose capital increases/decreases.

Proposal only.

### Risk Analyst Agent

Purpose:

- analyze emerging risk;
- detect degradation;
- recommend tighter limits;
- review unusual drawdown.

This agent is not the Hard Risk Engine.

### Execution Supervisor Agent

Purpose:

- inspect slippage;
- inspect rejection patterns;
- detect execution anomalies;
- escalate reconciliation problems.

It may not submit exchange orders itself.

### Learning Agent

Purpose:

- convert outcomes into experience;
- identify repeated success/failure;
- propose new hypotheses;
- maintain learning summaries.

### Auditor Agent

Purpose:

- inspect decision chains;
- identify missing evidence;
- detect unauthorized paths;
- verify lifecycle rules.

### Security Agent

Purpose:

- review configuration;
- detect permission drift;
- review security alerts;
- recommend secret rotation;
- escalate security incidents.

It never receives raw secrets.

## Skill contract

A skill is executable capability, not descriptive prose.

Every skill has:

- skill_id
- semantic version
- input schema
- output schema
- implementation reference
- allowed agents
- required permissions
- resource limits
- audit category
- test suite

## Initial skill examples

### backtest_strategy

Inputs:

- strategy_version
- dataset_version
- timeframe
- fee_model
- slippage_model

Outputs:

- trade_count
- CAGR
- max_drawdown
- Sharpe
- Sortino
- profit_factor
- expectancy
- regime_breakdown
- failure_reasons

### compare_strategy_versions

Inputs:

- candidate versions
- validation windows
- cost model

Outputs:

- comparable metric set
- statistically relevant differences
- degradation flags

### quantitative_edge_analysis

Inputs:

- feature snapshot
- model version
- cost model
- horizon

Outputs:

- expected_return
- expected_cost
- expected_net_edge
- downside_distribution
- confidence_quality

### inspect_execution_quality

Inputs:

- fills
- expected prices
- latency
- market state

Outputs:

- realized slippage
- abnormality flags
- execution-quality report

### propose_capital_allocation

Inputs:

- strategy performance
- drawdown
- correlations
- risk budget
- market regime

Outputs:

- proposed allocation
- rationale
- constraints

The output remains a proposal subject to hard policy.

## Permission principle

Research agents can research.

Execution services can execute.

No agent receives a tool that combines unrestricted reasoning with raw exchange authority.
