# Synthetic detector evaluation — P1 quality evidence pack

> Rule score is not probability. Warnings are not legal conclusions. No banking actions are performed.
> Wilson intervals assume independent episodes; repeated subjects and synthetic labels do not establish bank accuracy.
> PR threshold sweeps are descriptive; do not tune on a holdout used to report performance.
> Primary metrics cover normal/risk/legitimate_negative episodes only; edge and missing-data fixtures are boundary checks.
> The warning is post-event: without an approved pre-transfer mode the client is informed after the transaction, not before.
> UNVALIDATED LABELS: synthetic_placeholder/unknown labels are pipeline fixtures, NOT validated banking accuracy.
> Not an exclusively held-out evaluation. Independent human-reviewed holdout is required.
> SMALL SAMPLE: 81 episodes. Rates move a lot with one episode; do not quote them externally.
> Adversarial fixtures present (3): adversarial_single_counterparty_split, adversarial_wait_out_the_window, adversarial_zero_padding. They probe rule evasion and are expected to appear in the false-negative list.
> NO BANK ADJUDICATION: no episode in this repository carries a bank-reviewed label.
> Score bands are the rule score mapped to levels; nothing here is a calibrated probability of fraud.

## What this report is and is not

- Score is a deterministic rule score. **It is not a probability of fraud.**
- Labels are `synthetic_placeholder`. **Synthetic labels are not validated bank accuracy.**
- **The real banking effect is not measured.** No pilot ran, no bank adjudicated anything.
- Legitimate negatives are the critical part of this report: a detector that never cries wolf on
  family collections is worth more than one with a higher recall on synthetic attacks.
- **Language is not a risk factor.** The snapshot contract has no language field at all;
  presentation language is a UX attribute only.
- The warning is **post-event**: without an approved pre-transfer mode the client is told after
  the transaction, not before it.
- A sandbox case is **not a real bank support request**: nothing is blocked, frozen or contacted.

## Run identity

- dataset: `synthetic-episodes-p1-v1` (sha256 `760c739e273fbc60…`)
- rules: `2026-10-08.p1`, thresholds: `thresholds-2026.10.08-red50-yellow25` (detector `thresholds-2026.10.08-red50-yellow25`), adapter: `snapshot-adapter-v1`
- positive definition: `level == RED`
- episodes: 81 total, 56 primary, 25 edge/missing-data
- label sources: synthetic_placeholder
- holdout status: `development_only`
- python: 3.10.5 (Windows), git commit: e1b8f37b56c92ae3b7844b136819a999ea23ef48 (dirty: True)
- generated at: 2026-10-08T15:08:42.642408+00:00

## Counts and rates (primary classes only)

| Metric | Estimate | Wilson 95% CI |
|---|---:|---|
| recall | 0.9394 | 0.8039 – 0.9832 |
| precision | 1.0000 | 0.8897 – 1.0000 |
| fpr | 0.0000 | 0.0000 – 0.1431 |
| fnr | 0.0606 | 0.0168 – 0.1961 |
| alert_rate | 0.5536 | 0.4241 – 0.6761 |
| legitimate_negative_alert_rate | 0.0000 | 0.0000 – 0.2425 |

TP=31, FP=0, TN=23, FN=2.

## Segments

| Segment type | Segment | N | TP | FP | TN | FN | FPR |
|---|---|---:|---:|---:|---:|---:|---:|
| episode_class | normal | 11 | 0 | 0 | 11 | 0 | 0.0000 |
| episode_class | risk | 33 | 31 | 0 | 0 | 2 | undefined |
| episode_class | legitimate_negative | 12 | 0 | 0 | 12 | 0 | 0.0000 |
| episode_class | edge | 25 | 3 | 0 | 8 | 14 | 0.0000 |
| label_source | synthetic_placeholder | 81 | 34 | 0 | 31 | 16 | 0.0000 |
| is_holdout | false | 81 | 34 | 0 | 31 | 16 | 0.0000 |
| is_holdout | true | 0 | 0 | 0 | 0 | 0 | undefined |
| sim_profile | absent | 1 | 0 | 0 | 1 | 0 | 0.0000 |
| sim_profile | fresh_0d | 3 | 2 | 0 | 1 | 0 | 0.0000 |
| sim_profile | fresh_1d | 1 | 1 | 0 | 0 | 0 | undefined |
| sim_profile | fresh_2d | 1 | 1 | 0 | 0 | 0 | undefined |
| sim_profile | null_only | 73 | 30 | 0 | 29 | 14 | 0.0000 |
| sim_profile | stale_30d | 1 | 0 | 0 | 0 | 1 | undefined |
| sim_profile | stale_3d | 1 | 0 | 0 | 0 | 1 | undefined |
| device_novelty | false | 79 | 33 | 0 | 30 | 16 | 0.0000 |
| device_novelty | true | 2 | 1 | 0 | 1 | 0 | 0.0000 |
| hour_bucket_local | day_12_17 | 68 | 32 | 0 | 20 | 16 | 0.0000 |
| hour_bucket_local | morning_06_11 | 5 | 0 | 0 | 5 | 0 | 0.0000 |
| hour_bucket_local | night_00_05 | 7 | 2 | 0 | 5 | 0 | 0.0000 |
| hour_bucket_local | unknown | 1 | 0 | 0 | 1 | 0 | 0.0000 |

## Edge cases and missing data

- edge/boundary episodes: 25, levels: {'GREEN': 8, 'RED': 3, 'YELLOW': 14}
- episodes flagged `borderline_window`: 3
- episodes with `insufficient_data`: 1
- missing SIM rate: 0.9012; missing device rate: 0.9630

## Error patterns

- false positives: 0, false negatives: 16
  - FN multiple_small_inbound: 11 (edge_amount_499999, edge_amount_500000, edge_count_3, edge_count_4, edge_count_5)
  - FN no_reason_code: 3 (adversarial_single_counterparty_split, adversarial_wait_out_the_window, missing_no_counterparty_ref)
  - FN borderline_window+multiple_small_inbound: 2 (edge_window_59, edge_window_60)
  - False positives on family collections are expected: a declared purpose does not change the observable flow.
  - False negatives concentrated on single-counterparty or out-of-window patterns are documented detector blind spots.
  - Both lists are synthetic fixtures; neither is a validated bank error profile.

## Language invariance

- 486 attempts to inject language/locale/nationality/ethnicity/name into a snapshot, 486 rejected, 0 accepted.

## Companion artifacts

- `legitimate_negative_report.md` — false-positive detail on legitimate scenarios
- `threshold_sensitivity.csv` — score sweep over the primary classes
- `business_thresholds.csv` / `business_thresholds.json` — cost-weighted thresholds (assumptions!)
- `rule_ablation.csv` — each rule removed in turn
- `reason_cooccurrence.csv` — which rules charge for the same pattern twice
- `holdout_manifest.json` + `holdout_development.jsonl` / `holdout_holdout.jsonl` — subject/time-disjoint split
- `warnings.md` — the same caveats as a standalone checklist
