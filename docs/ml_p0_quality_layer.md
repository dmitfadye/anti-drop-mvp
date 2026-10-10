# P0: reproducible risk quality layer

## Scope and integration

This is a synthetic rules demonstrator, not a production banking antifraud or a trained ML model. P0 adds strict contracts, a thin detector adapter, offline evaluation, privacy-constrained event contracts and an approximate A/B power helper. No new service, database, model, LLM, React migration or heavy dependency was added. Existing `/api/analyze`, static UI and Next frontend retain their behavior. New endpoint: `POST /api/v1/risk/evaluate`.

## Files

```text
anti_drop_ml/
  contracts.py               RiskSnapshotV1 / RiskDecisionV1
  adapter.py                 existing rules + stable SHA-256 identity
  metrics.py                 counts, rates, Wilson intervals, PR sweep
  events.py                  closed ProductEventV1 / metadata allowlist
  power.py                   per-arm two-proportion planning approximation
  make_labeling_template.py  deterministic synthetic fixtures
  evaluation/runner.py       JSONL/CSV CLI and report generation
fixtures/episodes/           valid examples, invalid inputs, blind template, catalog
reports/evaluation/          actual generated example artifacts
tests/test_ml_p0.py          contract, metrics, evaluation and event tests
docs/schemas/               exported versioned JSON Schemas
```

Integration modifications: `main.py` exposes the new endpoint and sanitizes its 422 responses; `src/detector.py` records exact per-rule score contributions without changing scores. Existing Russian warnings remain outside `RiskDecisionV1`; no legal accusation is returned by the new decision endpoint.

## Strict input

One snapshot is one subject. Transactions inherit the top-level subject; an optional per-transaction subject_ref must match it. Unknown fields (including language, nationality, names, phones and raw transaction text) are forbidden. References must use an opaque prefix and 8–64 lowercase hex characters, e.g. `sub_0123456789abcdef`. These are caller-issued pseudonyms, not raw identifiers; never hash low-entropy PII without an approved pseudonymization process. Syntax validation cannot prove that a value was safely generated.

All timestamps must be ISO strings with timezone or aware datetime objects and normalize to UTC. Naive dates and numeric epochs are rejected. Invalid API input produces 422, with error type and location only; raw values are not echoed on this endpoint. Duplicate event/source IDs, inconsistent subjects, negative amounts, coercible/non-integer amounts, bool-as-integer, unsupported currency and zero transfers are rejected. RUB is the only supported currency and must be explicit. `amount_minor` is kopecks. The request's typo “direction=transfer” is interpreted as `type=transfer`; direction is strictly in/out.

Future events are forbidden by default. An explicit `allow_future_events=true` permits validation for offline inspection, but the adapter still excludes future events from risk and reports the excluded count. SIM null is unknown; 0 is today, 1/2 are fresh, 3 is outside the existing two-day policy. Successful decisions have rejected-input flags false: rejected snapshots receive 422 and do not produce a fabricated GREEN decision. Empty/effectively empty snapshots return `insufficient_data`.

## Adapter and versioning

Rule version is the actual `src.policy.DEFAULT_POLICY.version` (`2026-10-08.p1`). Threshold version records RED>=50, YELLOW>=25. The adapter version is `snapshot-adapter-v1`; warning-template version is a separate provenance identifier. The runner rejects a requested rule version it cannot execute. Update these identifiers whenever behavior/templates change; no historical policy registry is claimed.

The adapter sorts by occurred_at/event_id and hashes normalized input, rule, threshold and adapter versions. Labels, dataset version and holdout metadata are excluded from scoring and identity. Input order and equivalent timezone representations do not change the decision. Score is a capped rule sum, **not probability**; raw contributions may sum above 100 while score is capped at 100. Machine reason codes have no legal conclusions.

Transfers and family collections map to existing incoming/outgoing P2P. Self-declared family purpose does not suppress rules. Salary maps to incoming_salary; `cash_withdrawal` is an additive type needed to represent the legacy cash rule. `cash_deposit` and `other` are neutral activity (legacy purchase) and do not count as P2P or salary; this mapping is a known coverage limitation, not an implemented deposit detector. RUB minor units are validated as integers; conversion to the legacy float classifier is not ledger accounting.

## Reproduce

From repository root, with project dependencies installed (Windows additionally requires tzdata):

```sh
export PYTHONPATH=app   # Python code lives in app/, run from repo root
python -m anti_drop_ml.make_labeling_template --output-dir app/fixtures/episodes
python -m anti_drop_ml.evaluation.runner --dataset app/fixtures/episodes/labeled_episodes.jsonl --output-dir reports/evaluation --positive-level RED --rule-version 2026-10-08.p1
python -m unittest discover -s app/tests -t app -v
```

Use `--positive-threshold 60` to define score>=60 instead of RED. Use `--holdout-only` only after a genuine subject-disjoint holdout exists. The supplied fixtures are all development-only synthetic placeholders. No random generation is used, so no seed is needed. Dataset bytes and ordering are deterministic. Metrics and decisions repeat; manifest timestamp/Git provenance intentionally change across runs.

## Dataset formats and safeguards

JSONL accepts an Episode envelope (episode_id, subject_ref, label, episode_class, label_source, is_holdout, payload) or a RiskSnapshotV1 whose metadata contains those labeling fields. CSV accepts episode_id/subject_ref/label/episode_class/payload_json, with label_source/is_holdout either explicit columns or in snapshot metadata. CSV booleans must be true/false. Envelope and metadata must agree. Dataset version is required and consistent. Duplicate episode IDs and subjects crossing development/holdout are rejected. Invalid episodes abort evaluation before report creation; they are not silently dropped. Invalid fixtures are kept in a separate file with expected 422 status, never mixed into metric denominators.

## Evaluation outputs

`metrics.json`, `report.md`, `confusion_matrix.csv`, `pr_curve.csv` (101 thresholds, 0–100), `segment_breakdown.csv`, `evaluation_manifest.json`, `episode_decisions.json`, and a separate `legitimate_negatives_report.md`. Rates carry numerator/denominator and Wilson 95% CI; n=0 yields null. Breakdown includes all four episode classes, label source, and holdout status. The manifest records dataset version/hash, implemented versions, positive definition, count, labels, holdout status, warnings, Git commit/dirty flag and UTC generation time.

The provided 21-episode fixture run deliberately contains a false positive: family collection followed by rent has the same observable shape as transit. It is not whitelisted. Example counts: TP=2, FP=1, TN=18, FN=0. These measure a pipeline on handcrafted placeholders; they do not estimate banking accuracy. Wide intervals and tiny risk count must remain visible. Threshold sweeps must not be used to tune on a final holdout. Wilson assumes independent observations; subject clustering requires a separate analysis plan.

## Events and A/B planning

ProductEventV1 supports all ten requested event types. It has a closed top-level schema and a typed metadata allowlist. Arbitrary free text, nested dictionaries, raw phone/name/passport/card/OTP/counterparty text/location/biometrics are rejected, not redacted into storage. No telemetry storage, SDK, assignment, outcome collection or banking action is implemented. The synthetic marker is always true. Language is a UX attribute in events, never a risk feature. Event JSON Schemas are supplied for future integration; emission of an event is not evidence of a real outcome.

`required_n_two_proportions(.20, 5, dropout_rate=.10)` returns approximate recruited participants **per arm**, equal allocation, two-sided alpha=.05 and power=.80. Uplift 5 means 5 percentage points, not 5% relative. Uses NormalDist quantiles and pooled normal approximation. It does not replace a full analysis plan: account for clustering, event rate, ITT, multiplicity, consent and guardrails. No A/B effect is demonstrated.
