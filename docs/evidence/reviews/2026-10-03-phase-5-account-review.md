# Independent adversarial root pass: account reconciliation

Separate root review after implementation, not human/separate-model approval.
Reviewed raw-source ownership/strict financial strings, duplicate assets/IDs/JSON
keys, history completion/caps, account flags, before/after consistency, internal
head changes, original order/fee/time/quote identity, total vs reserved balances,
unknown cost attribution and notification/audit fail-closed behavior.

Repairs: source commits before comparison; comparison failures emit unavailable
blocking reports; partial SDK truth retained after later endpoint failure; timestamps
and stored-fill hashes verified; active config changes included in head; per-order
reservation verified independently of equal aggregate balance. Two first-run test
failures were unsupported audit batch size10000; corrected to bounded1000. Full50
actual cases pass; final nine account cases pass, including full-page SDK pagination.

No bounded-fixture blocking defect found. Reports have no certification effect and
cannot resolve historical incidents. Real venue retention/discovery, multi-account
attribution, sourced BUY buffers, initial cost and controlled recovery remain work.
Automatic review rejected process-environment diagnostic extraction; it did not run.
The supported harness provided all diagnostics and now accepts validated test paths
inside tests/market, preserving its default full suite. No credential extraction.

Final partial-source10 cases PASS (53.17s). Alert review found repeated-fault
notification duplication; distinct per-read Checked audit and stable financial
fault identity repair implemented. Ten unchanged account cases PASS; repaired
notification case PASS (7.76s), preserving two receipts and one critical alert.
Final150 unit/type/schema/build checks PASS. No certification/gate assertion.
