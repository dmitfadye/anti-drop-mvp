# Synthetic detector evaluation

> Rule score is not probability. Warnings are not legal conclusions. No banking actions are performed.
> Wilson intervals assume independent episodes; repeated subjects and synthetic labels do not establish bank accuracy.
> PR threshold sweeps are descriptive; do not tune on a holdout used to report performance.
> UNVALIDATED LABELS: synthetic_placeholder/unknown labels are pipeline fixtures, NOT validated banking accuracy.
> Not an exclusively held-out evaluation. Independent human-reviewed holdout is required.

Dataset: synthetic-episodes-v2; rules: 2026-10-08.p2; thresholds: thresholds-2026.10.08-red50-yellow25.
Positive definition: level == RED. Episodes: 24.

| Metric | Estimate | Wilson 95% CI |
|---|---:|---|
| recall | 1.0000 | 0.3424 – 1.0000 |
| precision | 0.6667 | 0.2077 – 0.9385 |
| fpr | 0.0455 | 0.0081 – 0.2180 |
| fnr | 0.0000 | 0.0000 – 0.6576 |
| alert_rate | 0.1250 | 0.0434 – 0.3100 |
| legitimate_negative_alert_rate | 0.0909 | 0.0162 – 0.3774 |

TP=2, FP=1, TN=21, FN=0.

## Legitimate negatives

See legitimate_negatives_report.md for separate counts and alerted fixture IDs.

## Segments

| Class | N | FP | FN |
|---|---:|---:|---:|
| normal | 2 | 0 | 0 |
| risk | 2 | 0 | 0 |
| legitimate_negative | 11 | 1 | 0 |
| edge | 9 | 0 | 0 |
