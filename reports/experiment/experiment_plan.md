# Experiment plan ? warning language (exp-warning-language-2026.10)

**Status: PLANNING DOCUMENT. Nothing has been run. `treatment_available: false`
because the `uz-UZ` translation is `draft` and no native or legal reviewer has
signed it.**

## Question

Does the same risk warning, shown in the client's own language instead of
Russian, change what the client does next?

Not: does the detector work, does the warning reduce fraud loss. Those need
different data and are not what this experiment measures.

## Design

| Field | Value |
|---|---|
| randomization unit | `subject_pseudonym` |
| assignment | deterministic hash of salt + experiment_id + subject |
| treatment share | 50% (`ANTI_DROP_EXPERIMENT_TREATMENT_PERCENT`) |
| control | `ru-RU`, `warning_ru_control_v1` / `warning_ru_control_yellow_v1` |
| treatment | `uz-UZ`, `warning_uz_treatment_v1` / `warning_uz_treatment_yellow_v1` |
| shared | one `RiskDecisionV1`, one `rule_version`, one `threshold_version` per subject |
| variable changed | template + locale only |
| scoring | blinded, `display_template_id` = `blin_<hash>` |
| analysis | intention-to-treat |

## Metrics

**Primary:** `safe_action_rate` uplift (`safe_action_chosen`, `accepted_advisory`).

**Secondary:** `understanding_rate`, `time_to_action_ms` (median and p90),
completion of the help flow.

**Guardrails:** `felt_accused_rate`, support contacts per 1000 warnings,
technical error rate, `translation_fallback_rate`, complaints.

## Gates before the pilot may start

- [ ] `uz-UZ` pack is `approved` (native review + legal review recorded)
- [ ] control copy is `approved` as well
- [ ] baseline `safe_action_rate` measured in a real usability session
- [ ] power plan recomputed from that baseline
- [ ] analysis code preregistered with a commit hash
- [ ] fixed analysis date, no interim looks

## Sample size

`required_n_two_proportions(baseline_rate, expected_uplift_pp, alpha, power, dropout)`
? an approximate planning figure for independent individuals, equal allocation.
It does not model clustering, event-rate multiplicity or interim looks. Run:

```
python -m scripts.analyze_experiment --scored <collected.csv>   --blinding-map reports/experiment/blinding_map.json --declared-powered-n 400
```

## Stopping

Stop for harm only: `felt_accused_rate` rising, support load over capacity, a
legal or privacy trigger, or a technical error rate above 2%. Stopping early
because the numbers look good destroys the result and is forbidden.

Full criteria: `configs/pilot_stop_criteria.json`.

## Claims this plan does not license

- "the language experiment showed uplift" ? nothing has been collected;
- "safe action rate improved by X pp" ? no data exists;
- "the treatment is production-ready" ? the translation is a machine draft.

Every analysis output carries `claim_permitted: false` until a powered sample
exists. `reports/experiment/blinded_scoring_template.csv` ships with zero filled
rows on purpose.
