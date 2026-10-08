# Limitations

## P0 (unchanged)

- Data and labels shipped with P0 are synthetic placeholders, not real customer records or bank adjudication.
- Score is a deterministic rule score, **not a probability of fraud**. Rules are heuristic; device novelty and night work can be legitimate.
- Warnings and reason codes are not legal conclusions or evidence that someone committed an offence.
- No transfer is blocked, money frozen, SMS/OTP verified, cashback paid or real support case created. Existing interactions are explicitly sandbox/mock. P0 emits no banking action and stores no telemetry.
- Real accuracy is unconfirmed without an independently human-reviewed, representative, subject-disjoint holdout. The supplied set has only two synthetic risk episodes. Recall=1 on this set is not a real-world performance claim.
- Legitimate negatives are critical to FPR. Family funds followed by rent can be observationally indistinguishable from transit; the example intentionally exposes a false positive. Self-declared purpose does not override rules.
- Language, citizenship, ethnicity, names and origin are not risk factors. Language is only a UX event attribute.
- A/B effects are unproven until a real, preplanned experiment. Power helper is approximate and does not replace an analysis plan accounting for clustering, event rate, ITT and guardrails.
- Opaque-reference regex and closed schemas reject common raw-PII submissions but cannot prove de-identification or legal access. Use approved caller-issued pseudonyms; do not supply or log real PII. P0 risk validation errors do not echo raw values.
- Contracts and events schemas prepare integration; they are not authentication, authorization, consent, production ingestion controls, audit storage or delivery guarantees.
- Only RUB is supported. Existing float classifier is not a ledger. Deposit/other mapping is neutral activity, not a cash-deposit risk model. Missing counterparties/devices/SIM can reduce rule sensitivity.
- Future events are rejected by default and always excluded from risk even when explicitly allowed for offline inspection. Invalid inputs are not included in accuracy denominators.
- Wilson intervals assume independent episodes. Correlated subjects or related accounts require a cluster-aware statistical design; pseudonym split checks do not detect all leakage.
- Dataset generation is deterministic and handcrafted. Manifests record time/commit/dirty state, but there is no external registry, model training or historical rule-execution service.

## P1 additions

### Localization and templates

- Exactly one target locale (`uz-UZ`) exists beyond the Russian control, and it is `draft`: **no native-speaker review, no legal review, not approved.** The P0 claim of seven languages is not repeated here.
- The `uz-UZ` pack is intentionally missing `privacy.notice`. That key resolves through the Russian fallback and is reported as `translation_fallback`; a reader who does not read Russian sees that sentence in Russian. This is a quality gap, not a feature.
- The machine draft of the Uzbek copy has not been read aloud by anyone. It is a starting point for a reviewer, not a translation.
- Forbidden-phrase checks are keyword-based and cover the languages present in this repository. They are a backstop against the worst wording, not a proof that the copy is legally safe.
- A missing key falls back silently in meaning: the text is correct for the control locale but may be hard for the target-locale reader. Fallback is logged and surfaced, and must still be fixed rather than relied on.
- `rtl` support exists in the CSS and contracts but is **unexercised**: no RTL locale ships, so it has not been tested against a real right-to-left script.
- Accessibility work is markup-level and unit-checked. No screen reader (NVDA/JAWS/VoiceOver) has been used and no axe/Lighthouse audit has been run. Contrast ratios were computed by hand. Keyboard behaviour was reasoned about, not session-tested.

### Operator sandbox

- The operator surface has **no authentication and no authorisation**. The only guard is a double feature flag plus a loopback client-address check. Behind a reverse proxy that check is meaningless. This is a local demo, not production security.
- Cases live in process memory. A restart clears them. There is no store, no retention policy, no audit guarantee and no recovery.
- Operator notes cannot be free text — only an allowlisted `note_code`. That protects privacy but means the case record cannot carry the nuance a real support case needs.
- Metrics describe a local synthetic sandbox. Rates with an empty denominator are `null`, never `0`, and no volume here resembles production.
- Exports are pseudonymous by construction and additionally masked. Masking is a backstop, not a proof of anonymisation.
- `operator_actions_logged` counts in-process actions only. The append-only JSON-lines sink is a local file with no rotation, integrity protection or audit guarantee.
- The sandbox creates **no real support case**: no queue, no ticket, no human is notified.

### Experiment

- `blinded_scoring_template.csv` ships with **zero filled rows**. No participant data exists in this repository.
- No experiment has been run. Every analysis output carries `claim_permitted: false` by construction.
- The treatment arm is refused by default because the target translation is `draft`. Running with `--allow-draft-treatment` demonstrates the split and is recorded in the artifact; it is a demo, not an experiment.
- The power figure is a planning number from assumed baseline and uplift rates. It does not model clustering, event-rate multiplicity, interim looks or guardrails.
- Wilson intervals assume independent participants. Repeated sessions per participant would invalidate them, and the code does not prevent that from happening.
- `analysis` is descriptive. It does not correct for attrition, does not verify randomisation integrity, and cannot detect a failed assignment.
- Sample sizes here are far below any powered requirement; `NOT POWERED` appears in the output for that reason.

### Evaluation evidence

- Primary metrics are computed on `normal`, `risk` and `legitimate_negative` episodes only. Edge and missing-data fixtures are boundary checks and are excluded from the confusion matrix. Their behaviour is reported separately instead.
- All labels are `synthetic_placeholder`. Recall and FPR are pipeline behaviour, not validated accuracy.
- The shipped dataset is small (≈80 episodes). Rates move noticeably with one episode; `SMALL SAMPLE` is reported for this reason.
- The ablation result that four rules contribute nothing to recall is a fact **about this fixture set**, not about the rules on real traffic.
- The two documented false negatives (single-counterparty splitting, waiting out the window) are real blind spots and are not fixed.
- `missing_no_counterparty_ref` scores GREEN: without counterparties the sender-diversity rule cannot fire. That is a data-contract gap, not a decision to trust.
- The holdout split is subject- and time-disjoint bookkeeping. Rules are not trained, so this is about honest reporting, not about generalisation.
- Business-threshold tables use caller-supplied costs and prevalence. They are `ASSUMPTION_DRIVEN` and are labelled as such in the artifact.
- Business thresholds are computed at the fixture prevalence and are not re-weighted to the assumed market prevalence.

### Financial model

- Every parameter is an assumption. Prevalence, unit loss, OPEX, K, contact volume, minutes saved and handling cost have no measured source.
- `L_bank_rubles_per_episode` is `source: unknown`. It scales the entire benefit side.
- The base case is negative by design. That is a statement about the assumptions, not a prediction.
- Break-even multipliers are computed against those assumptions; they are the questions for the pilot, not forecasts.
- Revenue uplift, rewards and inference cost are pinned to 0. No cashback, cross-sell or ML cost is modelled.
- Support benefit is modelled as a single line and assumes saved minutes; the reduction in contact length has never been measured.

### Pre-transfer advisory (optional)

- Advisory only: `banking_action: 'none'`. There is no code path that can block, hold, decline or reverse a transfer.
- It is `draft`, off by default (`ANTI_DROP_ADVISORY_ENABLED=false`), and has had no legal review.
- The signal is synthetic: no payment-flow integration exists, so nothing observes a real transfer attempt.
- The score contribution of a planned transfer is a what-if on the same rules; it is not calibrated and not validated against outcomes.
- The UI never says "blocked"; the advisory notice says the opposite. This is asserted by test, not proven against real copy review.

### Infrastructure

- CI runs on GitHub Actions and has not been executed in this environment; the local equivalent is `scripts/ci_smoke.sh`.
- The Dockerfile has not been built here. `USER sandbox`, the healthcheck and the `cap_drop: ALL` compose profile are unverified.
- `app_stdlib.py` remains a legacy diagnostic and is not on the FastAPI path. It is not exercised by the CI deploy smoke.
- No dependency audit is configured, and none is enforced. A blocking gate with no owner is worse than a documented gap.
- `requirements-lock.txt` exists but was not regenerated by P1; no new dependency was added.

## Work requiring real owners and independent review

Independent labeling and dispute adjudication; legal review of warning copy; native-speaker translation review; bank owner approval, representative data access and approved pseudonymization; a production case store with retention and access control; authentication for the operator surface; a rehearsed rollback; a measured `safe_action_rate` baseline; a signed set of FPR/recall gates; and a real pilot with real participants. None of these can be truthfully automated by this implementation. Product safety outcomes must be confirmed independently, not inferred from UI clicks or simulated events.