# Synthetic detector evaluation

> Rule score is not probability. Warnings are not legal conclusions. No banking actions are performed.
> Wilson intervals assume independent episodes; repeated subjects and synthetic labels do not establish bank accuracy.
> PR threshold sweeps are descriptive; do not tune on a holdout used to report performance.
> UNVALIDATED LABELS: synthetic_placeholder/unknown labels are pipeline fixtures, NOT validated banking accuracy.
> Not an exclusively held-out evaluation. Independent human-reviewed holdout is required.

Dataset: synthetic-episodes-v1; rules: 2026-10-08.p1; thresholds: thresholds-2026.10.08-red50-yellow25.
Positive definition: level == RED. Episodes: 21.

| Metric | Estimate | Wilson 95% CI |
|---|---:|---|
| recall | 1.0000 | 0.3424 – 1.0000 |
| precision | 0.6667 | 0.2077 – 0.9385 |
| fpr | 0.0526 | 0.0094 – 0.2464 |
| fnr | 0.0000 | 0.0000 – 0.6576 |
| alert_rate | 0.1429 | 0.0498 – 0.3464 |
| legitimate_negative_alert_rate | 0.1111 | 0.0199 – 0.4350 |

TP=2, FP=1, TN=18, FN=0.

## Legitimate negatives

See legitimate_negatives_report.md for separate counts and alerted fixture IDs.

## Segments

| Class | N | FP | FN |
|---|---:|---:|---:|
| normal | 2 | 0 | 0 |
| risk | 2 | 0 | 0 |
| legitimate_negative | 9 | 1 | 0 |
| edge | 8 | 0 | 0 |
