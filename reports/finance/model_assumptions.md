# Model assumptions

> MODELLED ESTIMATE, NOT MEASURED ROI. Inputs are assumptions unless marked bank_data.
> Counts only incremental prevention on top of existing bank protection; existing protection is not claimed as a benefit.
> Prevalence (q) and unit loss (L_bank) are assumptions; no bank data was available.
> RevenueUplift = 0, Rewards = 0, Inference = 0 until proven; no cashback is modelled.
> A positive payback in the optimistic scenario is not a promise, only a condition to be tested in a pilot.

| parameter | value | source | confidence | note |
|---|---|---|---|---|
| call_share_after_false_alert | 0.25 | assumption | low | Share of false alerts that trigger a support call. |
| contacts_per_client_year | 0.01 | assumption | low | Client-initiated support contacts per client per year across the pilot population. |
| cost_per_minute_rubles | 400.00 | assumption | low | Fully loaded agent cost per minute. |
| delta_incremental_prevention | 0.08 | assumption | low | Share of risk episodes prevented ONLY because of the new communication layer, on top of existing protection. Requires an approved treatment template and a powered A/B to confirm. |
| false_alerts_per_client_year | 0.01 | evaluation | low | Derived from SYNTHETIC fixture false-alert rates only. NOT validated bank precision. |
| handling_cost_per_contact_rubles | 650.00 | assumption | low | Cost of handling one false-alert contact. |
| k_initial_cost | 18000000.00 | assumption | low | One-off cost: build, bank integration, translation review, legal review, security review, pilot setup. |
| l_bank_rubles_per_episode | 45000.00 | unknown | low | Bank loss per prevented drop episode. No bank data available; bundles recovery effort, fraud handling and write-off assumptions. |
| minutes_saved_per_contact | 3.00 | assumption | low | Agent minutes saved because a structured sandbox case arrives with context. UNVERIFIED. |
| n_clients | 500000.00 | assumption | low | Illustrative pilot reach for one language. NOT a confirmed bank population. |
| opex_annual | 9000000.00 | assumption | low | Annual run cost: maintenance, template re-review, monitoring, data-contract upkeep, evaluation reruns. |
| q_risk_episodes_per_client_year | 0.00 | assumption | low | Prevalence assumption: share of clients with a drop-risk episode in a year. Deliberately conservative and NOT measured; it scales the entire benefit side. |


## Formulas

- FraudBenefit = N * q * Delta * L_bank
- SupportBenefit = N * contacts_per_client_year * minutes_saved_per_contact * cost_per_minute
- FalseAlertCost = N * false_alerts_per_client_year * call_share * handling_cost
- AnnualMargin = FraudBenefit + SupportBenefit + RevenueUplift - OPEX - FalseAlertCost - Rewards - Inference
- Year1Net = AnnualMargin - K
- Year1ROI = Year1Net / (K + OPEX + FalseAlertCost + Rewards + Inference) when denominator > 0
- SimplePaybackMonths = 12*K / AnnualMargin only when AnnualMargin > 0

Avoided loss, customer benefit and bank loss are one and the same episode counted once.
They are never added as independent benefits.
