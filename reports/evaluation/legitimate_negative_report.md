# Legitimate negatives — synthetic fixtures only

Not validated banking accuracy. These fixtures exist to measure false-positive sensitivity on
scenarios that look superficially like the attack: family collections, salary plus cash,
recurring payments, night work, a new device, a fresh SIM, inbound-only bursts.

> No episode here was reviewed by a human analyst or a bank.
> A silent legitimate negative still produces a monitoring signal; YELLOW is not "nothing".
> A self-declared purpose (family_collection) does not override the observable flow.

## Counts

| Metric | Estimate | Wilson 95% CI |
|---|---:|---|
| legitimate_negative_alert_rate | 0.0000 | 0.0000 – 0.2425 |
| alert_rate | 0.0000 | 0.0000 – 0.2425 |

Alerted legitimate negatives: 0 of 12.

## Per-scenario behaviour

| Scenario | Class | Label | Level | Score | Reason codes |
|---|---|---|---|---:|---|
| fresh_sim_without_burst | legitimate_negative | normal | GREEN | 0 | — |
| family_collection_then_small_rent | legitimate_negative | normal | YELLOW | 45 | multiple_small_inbound |
| repeated_subject_2 | legitimate_negative | normal | YELLOW | 45 | multiple_small_inbound |
| salary_and_cash | legitimate_negative | normal | YELLOW | 25 | cashout_ratio, borderline_window |
| night_worker | legitimate_negative | normal | GREEN | 10 | night_activity |
| regular_payments | legitimate_negative | normal | GREEN | 0 | — |
| family_collection | legitimate_negative | normal | YELLOW | 45 | multiple_small_inbound |
| repeated_subject_3 | legitimate_negative | normal | YELLOW | 45 | multiple_small_inbound |
| new_device_without_sim | legitimate_negative | normal | GREEN | 10 | device_novelty_with_baseline |
| repeated_subject_1 | legitimate_negative | normal | YELLOW | 45 | multiple_small_inbound |
| outbound_before_inbound | legitimate_negative | normal | YELLOW | 25 | multiple_small_inbound |
| many_inbound_without_outbound | legitimate_negative | normal | YELLOW | 45 | multiple_small_inbound |

## Known trade-off

`family_collection_then_small_rent` and `many_inbound_without_outbound` deliberately resemble the
attack at the observable level. The detector keeps them below RED; if thresholds are lowered, these
are the fixtures that will alert first. That is the trade-off the pilot has to price, not hide.
