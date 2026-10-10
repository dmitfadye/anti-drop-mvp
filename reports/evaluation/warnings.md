# Evaluation warnings

Read this before quoting any number from `metrics.json`.

## Sample

- episodes: 81 (primary 56, edge 25)
- label sources: synthetic_placeholder
- holdout status: `development_only`

## Generated warnings

- Rule score is not probability. Warnings are not legal conclusions. No banking actions are performed.
- Wilson intervals assume independent episodes; repeated subjects and synthetic labels do not establish bank accuracy.
- PR threshold sweeps are descriptive; do not tune on a holdout used to report performance.
- Primary metrics cover normal/risk/legitimate_negative episodes only; edge and missing-data fixtures are boundary checks.
- The warning is post-event: without an approved pre-transfer mode the client is informed after the transaction, not before.
- UNVALIDATED LABELS: synthetic_placeholder/unknown labels are pipeline fixtures, NOT validated banking accuracy.
- Not an exclusively held-out evaluation. Independent human-reviewed holdout is required.
- SMALL SAMPLE: 81 episodes. Rates move a lot with one episode; do not quote them externally.
- Adversarial fixtures present (3): adversarial_single_counterparty_split, adversarial_wait_out_the_window, adversarial_zero_padding. They probe rule evasion and are expected to appear in the false-negative list.
- NO BANK ADJUDICATION: no episode in this repository carries a bank-reviewed label.
- Score bands are the rule score mapped to levels; nothing here is a calibrated probability of fraud.

## Claims this repository does NOT support

- "recall 1.0" or "recall 90%" as a bank accuracy figure — labels are synthetic.
- "we prevented a transfer" — the data already contains the outgoing transfer.
- "works in 7 languages" — one target locale pack exists and it is a draft.
- "ROI positive" — the base financial case is close to or below break-even by construction.
- "supports real clients" — there is no authentication, no real data path and no bank integration.
