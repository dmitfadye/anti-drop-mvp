# Financial model methodology

## What this is

A parameterised calculation with the inputs written down, so a reviewer can
disagree with a number instead of with a vibe. It is **not** an ROI forecast and
not a business case.

## Why the base case is not flattering

The base scenario is deliberately close to break-even and slightly negative. A
comfortable base case would have been a fabricated one. The model earns its keep
by showing which assumption would have to move, and by how much, to change the
answer — that list is the pilot's actual agenda.

## Formulas

```
FraudBenefit      = N * q * Delta * L_bank
SupportBenefit    = N * contacts_per_client_year * minutes_saved_per_contact * cost_per_minute
FalseAlertCost    = N * false_alerts_per_client_year * call_share * handling_cost
AnnualMargin      = FraudBenefit + SupportBenefit + RevenueUplift
                    - OPEX - FalseAlertCost - Rewards - Inference
Year1Net          = AnnualMargin - K
Year1ROI          = Year1Net / (K + OPEX + FalseAlertCost + Rewards + Inference)   [if denominator > 0]
SimplePayback     = 12 * K / AnnualMargin                                            [only if AnnualMargin > 0]
```

## Three rules that keep the arithmetic honest

1. **One episode, counted once.** Prevented loss, customer benefit and bank loss
   are the same event viewed from three sides. They are never summed as
   independent benefits. The model has no line for "customer benefit".
2. **Only the incremental effect counts.** `Delta` is the share of risk episodes
   prevented *because of this layer*, on top of what the bank already catches.
   Anything the existing antifraud already prevented is not ours, and
   `Delta_incremental_prevention` defaults to 0.08 for exactly that reason.
3. **Unproven money stays at zero.** `RevenueUplift`, `Rewards` and `Inference`
   are pinned to 0 (`src/finance.py::PINNED_ZERO`). No cashback, no
   cross-sell, no ML inference cost.

## Division-by-zero behaviour

| Expression | Guard |
|---|---|
| `Year1ROI` | `None` when the denominator is 0 |
| `SimplePaybackMonths` | `None` unless `AnnualMargin > 0` — a negative margin never produces a payback number |
| break-even bisection | `None` when the sign never crosses in range |
| `sensitivity` on a zero parameter | `None` swing, with a note explaining that relative sensitivity is undefined |

Undefined is reported as undefined. It is never rounded to a favourable number.

## Scenarios

| Scenario | What changes | Purpose |
|---|---|---|
| `conservative` | N ×0.8, Delta ×0.5, L_bank ×0.8, OPEX ×1.2, K ×1.2, false alerts ×1.3 | what if we are wrong in the pessimistic direction |
| `base` | parameters as written | the honest centre |
| `optimistic` | N ×1.2, Delta ×1.5, L_bank ×1.2, OPEX ×0.9, K ×0.9, false alerts ×0.7 | the upper bound of what the assumptions allow |

Multipliers, not new assumptions: the scenarios never introduce a number that is
not in `configs/financial_assumptions.json`.

## Sensitivity and break-even

`reports/finance/sensitivity.csv` sweeps each parameter ±20% and reports the
swing in `AnnualMargin`, ranked. `reports/finance/break_even.md` solves for the
multiplier on N, Delta and OPEX at which the margin reaches zero, by bisection.

Current break-even reads roughly: **+2.4% clients, or +5.9% Delta, or −2.4%
OPEX.** Those are the three conversations the pilot should have.

## Assumptions ledger

Every parameter carries `value`, `source`, `confidence` and `note`:

- `source` ∈ `assumption | interview | bank_data | evaluation | unknown`;
- `confidence` ∈ `low | medium | high`;
- anything with `source` in `assumption`/`unknown` or `confidence: low` is listed
  in `reports/finance/missing_inputs.md`.

`src/finance.py` rejects a file that omits `value`, `source` or `confidence`, uses
an unsupported `source`, or uses a non-finite number.

## Artifacts

| File | Contents |
|---|---|
| `financial_scenarios.csv` | all three scenarios, all line items, nulls preserved |
| `sensitivity.csv` | per-parameter swing, ranked, with source and confidence |
| `break_even.md` | break-even multipliers with the standard disclaimers |
| `model_assumptions.md` | the assumptions table plus the formulas |
| `missing_inputs.md` | parameters with no independent evidence |
| `pitch_one_minute.md` | the honest one-minute text |

## Tests

`tests/test_p1_finance.py` checks: negative margin is computed and printed,
payback appears only for a positive margin, division by zero is protected,
`RevenueUplift`/`Rewards` default to 0, a missing `source` is rejected, and every
generated artifact carries the disclaimers.

## What would upgrade this from assumption to evidence

1. `q` — prevalence of drop-risk episodes per client-year, from the bank's own
   labelled history.
2. `L_bank` — realised loss per prevented episode, including recovery effort.
3. `Delta` — from a powered A/B, measured as the difference between treatment and
   control, not modelled.
4. `false_alerts_per_client_year` and `call_share` — from a shadow run on
   historical data.
5. `K` and `OPEX` — real quotes for build, integration, translation review, legal
   review and run cost.

Until at least one of these is real, every output of this model is
`MODELLED ESTIMATE, NOT MEASURED ROI`.