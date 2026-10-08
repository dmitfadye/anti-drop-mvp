# Limitations

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

## Work requiring real owners and independent review

Independent labeling and dispute adjudication; legal review of warning copy; native-speaker translation review; bank owner approval, representative data access and approved pseudonymization cannot be truthfully automated by this implementation. Product safety outcomes must be confirmed independently, not inferred from UI clicks or simulated events.
