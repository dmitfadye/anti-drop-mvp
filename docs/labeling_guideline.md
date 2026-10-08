# Independent labeling workflow

The supplied synthetic labels are handcrafted intent placeholders, not adjudication. Their purpose is exercising the measurement pipeline. Never label using the detector's score, level, reasons or selected threshold.

## Labels and classes

- **risk**: independent scenario evidence/adjudication supports a risky receive-and-forward or related pattern. This is an episode label for evaluation, not a legal accusation or a judgment about a person.
- **normal**: documented ordinary activity, e.g. salary or ordinary transfer, without independent evidence of risky intent.
- **legitimate_negative**: label normal, but observable behavior resembles rules: family collection, salary plus cash, recurring transfers, night work, new device without SIM change. Include family collection followed by rent; it can trigger a false alert.
- **edge**: boundary/control episode (59/60/61 minutes, one kopeck, threshold amounts, ordering). Label from independently specified scenario intent. Invalid inputs are contract tests, not normal negatives.

If ambiguous, leave label null in labeling_template.jsonl and route to adjudication. Evaluation rejects unresolved labels. Do not guess normal or risk to inflate denominators. Real reviewers should label independently; preserve disagreement and resolution in a controlled review register outside the runtime dataset. A second reviewer/adjudicator must resolve disputed labels. Set human_reviewed only after actual review; bank_adjudicated requires the bank's actual owner/process.

## Procedure

1. Run `python -m anti_drop_ml.make_labeling_template`. `labeling_template.jsonl` has null labels and unknown source, while labeled_episodes.jsonl is explicitly synthetic_placeholder.
2. Provide reviewers the scenario context under controlled access; hide scores, detector predictions and current thresholds. The separate synthetic fixture catalog describes scenario intent and must not be used as independent adjudication.
3. Review inclusion/exclusion criteria, sufficient context, chronology and legitimate purpose. Language/citizenship/ethnicity/name are not risk labels or features. Use pseudonyms only; no real PII in this repository.
4. Record label and provenance consistently in envelope and payload metadata. Retain ambiguous cases for separate adjudication, rather than silently discard them.
5. Split by subject before threshold work. Reserve a bank-owned human-reviewed holdout, locked before iteration. Avoid temporal, duplicate-event, household and related-subject leakage; software only enforces subject split consistency.
6. Freeze dataset version/hash and policy/threshold versions; evaluate once on the held-out set. Threshold selection uses development data only. Review false positives by legitimate-negative subtype, not only aggregate FPR.

`synthetic_placeholder` must never be renamed human_reviewed just because an engineer ran tests or inspected output. The example set is small, curated, unrepresentative and entirely development-only. It cannot validate accuracy or be sold as a bank benchmark.
