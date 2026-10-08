# Evaluation report template

## Provenance and scope

Dataset version/hash: …; rule/adapter/threshold/template versions: …; Git commit and dirty state: …; execution time: …; episode count: …; label sources: …; holdout status and split ownership: ….

Explicitly state synthetic/unknown labels and that they do not establish validated banking accuracy. Describe selection bias, missing classes, repeated subjects and unknown data coverage.

## Positive definition and results

State RED or score>=threshold. Include TP/FP/TN/FN; recall, precision, FPR, FNR, alert rate, legitimate-negative alert rate; each denominator and Wilson 95% interval. Undefined denominators must be null, not zero. Link confusion_matrix.csv and PR curve. Do not select a threshold on the reported final holdout.

## Segment analysis

Report normal/risk/legitimate_negative/edge, label source and development/holdout separately. Review legitimate-negative false alerts in their own report, especially family collections, rent, salary/cash, night work and device changes. Explain missed risks and missing information without asserting criminal intent.

## Limitations and next decision

Score is not probability; a warning is not a legal conclusion; no bank operation is performed. State whether independent adjudication exists, who owns bank data access, necessary human reviews, remaining sampling/CI limitations, and whether an experiment has actually run. A/B effects are unproven until the experiment and analysis are complete.
