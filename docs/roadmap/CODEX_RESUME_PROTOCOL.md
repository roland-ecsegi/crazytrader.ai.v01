# Codex Goal Resume and Usage-Limit Protocol

Codex Goals can continue across turns while active and within budget. Current Codex behavior treats budget/usage limits as a stopping condition; repository instructions cannot force the OpenAI service to automatically resume a budget-limited Goal after allowance resets.

Therefore the project implements **automatic resumability and best-effort continuation**, not a fictitious quota bypass.

## While within budget
Keep the Enterprise Local Goal active and continue automatically at safe idle boundaries.

## Durable checkpointing
At meaningful milestones and before long tests/phase gates: commit, push, update STATUS, update active ExecPlan resume checkpoint, append validation, and leave no essential state only in the VM.

## On usage/budget stop
If a final turn is available: stop starting new large work, safely finish/rollback partial migrations, run minimal consistency checks, commit/push, set STATUS=`WAITING_FOR_CODEX_USAGE_RESET`, and record last commit + exact next action. This is not completion.

## After reset
If platform auto-resumes, continue immediately. If user/system resume is required, resume the **same Goal/thread** with `/goal resume` or Resume control. Then read STATUS + active ExecPlan + Git and continue without replanning from scratch.

Do not rely on VM recovery. Git/program files are durable truth.

Do not automate UI clicking, scrape credentials, circumvent quotas, or use unofficial mechanisms to bypass usage limits.

If OpenAI later exposes a supported native auto-resume-after-reset control/API, enable and document it. Until then, one platform Resume action may be unavoidable.
