# Rollback plan

## Principle

The adaptive layer is additive. Rolling it back must restore exactly the previous
client experience and must **not** weaken the bank's own protection.

## Decision authority

| Trigger class | Who decides | Target time |
|---|---|---|
| Immediate stop (`configs/pilot_stop_criteria.json#immediate_stop`) | any on-call owner, unilaterally | ≤ 15 minutes |
| Pause and review | pilot owner with one metric named | ≤ 1 working day |
| Planned rollback | pilot owner | next scheduled window |

Nobody needs permission to stop. Re-enabling requires the entry gates again.

## Steps

1. **Kill the feature flag.**

   ```bash
   ANTI_DROP_LOCALIZATION_ENABLED=false
   ANTI_DROP_EXPERIMENT_ENABLED=false
   ANTI_DROP_OPERATOR_UI_ENABLED=false
   ANTI_DROP_ADVISORY_ENABLED=false
   # demo_mode stays true: the base demonstrator must keep working
   ```

2. **Confirm the layer is inert.**

   ```bash
   curl -s localhost:8000/api/health | jq '.p1_features'
   curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/api/operator/cases   # expect 503
   curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/api/v1/risk/advisory  # expect 503
   ```

3. **Confirm the base protection is untouched.** The rules engine, thresholds,
   `POST /api/v1/risk/evaluate` and `POST /api/analyze` are unchanged by any P1
   flag. Verify a known snapshot still returns the same `evaluation_id` and
   score as before the change.

4. **Return clients to the standard bank warning.** In this repository that means
   the legacy `src/alerts.py` text served by `/api/analyze`. In a pilot it means
   the bank's own notification path — which this repository does not own and
   does not touch.

5. **Preserve evidence.** Copy the local JSON-lines event sink and the operator
   action log before any cleanup. Do not delete incident evidence.

6. **Tell people.** A short incident note: what was observed, when, what was
   changed, what is still unknown. Include the null or negative result.

7. **Re-open only after review.** Every entry gate returns to pending or blocked;
   the rollback gets written up before anything is enabled again.

## Never do this

- disable or weaken the bank's existing antifraud to "isolate" our effect;
- delete logs, exports or fixtures during an incident;
- re-enable with a partial rollback to "test whether it was really the cause";
- change thresholds and re-enable in one step;
- announce the layer externally before the copy has been reviewed.

## Rehearsal

Not yet done. A rollback that has never been exercised is a wish. Before a pilot:

1. run the steps above against the demo, timing each one;
2. verify the base snapshot check in step 3 passes;
3. record the measured time;
4. set `rollback.tested: true` in `configs/pilot_stop_criteria.json` with the date
   and the person who ran it.

Until that record exists, `rollback.tested` stays `false` and this plan is
`NOT VERIFIED`.

## In this repository

Flipping the flags is instant and reversible; the base protection genuinely does
not depend on them. That is the one part that *is* verified, and it was made true
by construction: no P1 module is imported by the risk path.