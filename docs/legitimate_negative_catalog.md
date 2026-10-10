# Legitimate negative catalogue

Every scenario here exists to answer one question: **does the detector accuse a
client who did nothing wrong?** A rules engine that only knows the attack shape
will always have perfect recall and be useless in production.

All fixtures are synthetic. `label_source` is `synthetic_placeholder` for every
row in `fixtures/episodes/`. No episode has been reviewed by a human analyst or
a bank. Rates computed on this set are pipeline behaviour, **not validated
banking accuracy**.

## Why this matters more than recall

- Recall on synthetic attacks is easy: you wrote the attack.
- False positives on legitimate patterns are what cost a bank customer trust and
  support capacity — and they are invisible without deliberately built fixtures.
- A warning that fires on a family collection teaches clients to ignore the next
  warning. That is the failure mode this catalogue exists to prevent.

## Catalog

| # | Scenario | Group | Why a bank would call it legitimate | Expected outcome |
|---|---|---|---|---|
| 1 | `family_collection` | legitimate_negative | Several people pay back a shared expense | YELLOW/GREEN, never RED |
| 2 | `family_collection_then_small_rent` | legitimate_negative | Collection followed by a small, purpose-stated payment | not RED |
| 3 | `salary_and_cash` | legitimate_negative | Salary credited, then withdrawn in cash | YELLOW at most |
| 4 | `regular_payments` | legitimate_negative | Rent, utilities, subscriptions on a schedule | GREEN |
| 5 | `night_worker` | legitimate_negative | Shift work, operations between 00:00 and 06:00 | not RED for time alone |
| 6 | `new_device_without_sim` | legitimate_negative | New phone, SIM change unknown | YELLOW at most |
| 7 | `fresh_sim_without_burst` | legitimate_negative | SIM replaced today, no burst | GREEN |
| 8 | `many_inbound_without_outbound` | legitimate_negative | 6 small inbound payments, no onward transfer | YELLOW monitoring |
| 9 | `outbound_before_inbound` | legitimate_negative | Large outgoing happens *before* the burst | no flow-through |
| 10 | `generated_quiet_*` | normal | Ordinary activity with no transit shape | GREEN |

Note on #1 vs the attack: at the observable level they are nearly identical. A
self-declared `family_collection` type does **not** override the flow, because
anyone can label a transfer that way. The detector stays below RED; the
limitation is documented rather than hidden.

## Boundary fixtures

Edge fixtures test behaviour, not accuracy. They are excluded from the primary
confusion matrix and reported under `edge_case_behavior_summary`.

| Group | Coverage |
|---|---|
| `edge_window_*` | 59 / 60 / 61 minutes, midnight crossing, previous calendar day |
| `edge_amount_*` | 1 minor unit, threshold − 1, exactly threshold, threshold + 1 |
| `edge_count_*` | 1, 2, 3, 4, 5 small inbound payments |
| `edge_sim_*` | `null`, 0, 1, 2, 3, 30 days |
| `missing_data` | no device, no counterparty, no SIM, all three, empty history |
| `invalid_contract` | duplicate ids, future/naive/invalid dates, zero and negative amounts, mixed subjects, foreign currency, raw PII fields |

`sim_changed_days_ago = null` means *unknown*, not *zero days*. The detector must
not treat unknown as fresh.

## Missing data behaviour contract

- Missing counterparty → sender-diversity signal degrades; the system must not
  invent a counterparty. `missing_no_counterparty_ref` is a documented false
  negative.
- Missing device/SIM → the corresponding rule cannot fire; `data_quality` records
  `has_missing_device` / `has_missing_sim` and confidence drops.
- Empty history → `status = insufficient_data`, score 0, never a fabricated level.

## Invalid contracts

`fixtures/episodes/invalid_contract/invalid.jsonl` holds 24 payloads that must be
rejected with `422`. A `500` on any of them is a defect. The catalogue also
proves the closed schema refuses `phone`, `full_name` and other raw-PII shapes
instead of storing them.

## How to regenerate and re-measure

```bash
python -m scripts.generate_synthetic_fixtures --output-dir fixtures/episodes
python -m anti_drop_ml.evaluation.runner \
  --dataset fixtures/episodes/all_episodes_p1.jsonl --output-dir reports/evaluation
```

Then read `reports/evaluation/legitimate_negative_report.md` for the per-scenario
table and `reports/evaluation/rule_ablation.csv` for which rules the legitimate
negatives actually exercise.

## What would replace these fixtures

Synthetic fixtures can only prove the pipeline is wired correctly. A pilot needs:

1. independently human-reviewed labels from analysts who did not build the rules;
2. a representative population, including the customers who complain;
3. subject-disjoint holdout with a real time split;
4. adjudication of disagreements, not a majority vote;
5. documented thresholds for acceptable false-alert rate agreed with the bank.

Until those exist, every number here is `SYNTHETIC PLACEHOLDER / NOT VERIFIED`.