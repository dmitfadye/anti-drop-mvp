# Experiment design — warning language

## Question

Does showing the same risk warning in the client's own language, instead of
Russian, change what the client does next?

**Not**: does the detector work, does the warning reduce fraud loss. Those are
different questions with different data requirements.

## Why it is shaped this way

| Design choice | Reason |
|---|---|
| Randomisation unit is `subject_pseudonym` | One decision per person. Sessions within a person would be correlated and the interval would be a lie. |
| Both arms see the **same** `RiskDecisionV1` | The experiment must isolate one variable. Rules, thresholds and score are identical across arms. |
| Only template + locale differ | If the rules changed at the same time, no result would be attributable. |
| Language never touches the detector | `RiskSnapshotV1` has no language field. A `language_invariance` check in the evaluation report proves injection attempts are rejected. |
| Treatment refused while unapproved | Running a pilot arm with an unreviewed translation would test a translation nobody stands behind. |
| Blinded scoring | Participants cannot infer the arm from the interface, and the analyst cannot unblind before collection ends. |

## Arms

| Arm | Locale | Template | Status |
|---|---|---|---|
| `control` | `ru-RU` | `warning_ru_control_v1`, `warning_ru_control_yellow_v1` | `draft` |
| `treatment` | `uz-UZ` | `warning_uz_treatment_v1`, `warning_uz_treatment_yellow_v1` | `draft` |

Both are `draft`, so `resolve_pair` returns `treatment_available: false` and every
subject is assigned to `control`. `--allow-draft-treatment` exists to demonstrate
the split in a demo; it is written into the artifact so nobody mistakes a demo
split for an experiment.

## Assignment

Deterministic hash, no state store:

```
bucket = int(sha256(f"{salt_version}|{experiment_id}|{subject_pseudonym}"), 16) % 100
arm    = "treatment" if bucket < treatment_percent else "control"
```

Properties: sticky per subject, reproducible across reruns and machines, and
independent of arrival order. `assignment_salt_version` is recorded so a future
salt change is visible in the data rather than silent.

## Metrics

**Primary:** `safe_action_rate` — proportion of participants choosing a safe next
step (`safe_action_chosen`, `accepted_advisory`) over all exposed.

**Secondary:**

- `understanding_rate` — `understood_next_step` answered yes;
- `time_to_action_ms` median and p90;
- `felt_accused_rate` — guardrail, expected to *fall* with better language;
- `translation_fallback_rate` — how often a key had to fall back to Russian.

**Guardrails:** support load, complaints, technical error rate, fallback rate.

## Analysis

- intention-to-treat: every assigned participant counts in their assigned arm;
- Wilson 95% intervals on every rate;
- a null result is reported as a null result;
- `claim_permitted` is hard-coded `false` in `src/experiments.py`. The analysis
  code has no branch that can produce an uplift claim.

## Power

```
required_n_two_proportions(baseline_rate, expected_uplift_pp, alpha, power, dropout)
```

With the default assumptions (`baseline 0.30`, `uplift 8pp`, `alpha 0.05`,
`power 0.80`, `dropout 0.10`) the helper returns a required n per arm. That n is
a **planning figure**: the inputs are assumptions from this repository, and the
helper does not model clustering, event-rate multiplicity, interim looks or
guardrails. Recompute it on pilot baseline data before the pilot starts.

## Events

`experiment_assigned`, `alert_delivered`, `alert_viewed`, `template_rendered`,
`language_selected`, `translation_fallback`, `help_started`, `case_created`,
`case_confirmed`, `safe_action_confirmed`, `understanding_survey_submitted`,
`scoring_recorded`, `request_failed`.

Every event carries `evaluation_id`, `rule_version` and `threshold_version` from
the decision, so an event can always be traced back to the exact risk output.
PII-shaped fields are not in the vocabulary and are rejected by the closed model.

## Blinding

- participants see `display_template_id` (`blin_<hash>`) only;
- `blinding_map.json` maps display id → template / arm / locale and is stored
  separately;
- `scripts/analyze_experiment.py` unblinds only after collection and writes
  `unblinded_analysis_template.csv`;
- `comments_no_pii` is validated against phone-shaped digit runs.

## Stopping

Early stop for harm only: an increase in `felt_accused_rate`, a support-load
breach, or any legal/compliance trigger. Stopping early for "it looks like it is
working" invalidates the result and is forbidden.

Full criteria: `configs/pilot_stop_criteria.json`.

## What would make this publishable

1. an approved `uz-UZ` translation (native + legal review);
2. a baseline `safe_action_rate` measured in a real usability session;
3. a recomputed power plan against that baseline;
4. preregistered analysis code with a commit hash;
5. a fixed analysis date and no interim looks.

Until then every output from this module is labelled
`EXPLORATORY_NO_UPLIFT_CLAIM` / `NOT POWERED`, and that label is the honest one.