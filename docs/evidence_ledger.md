# Evidence ledger

One row per claim. Status is the point of the file:

| Status | Meaning |
|---|---|
| `VERIFIED` | checked in this repository, reproducible by a third party |
| `PARTIAL` | checked, but on synthetic data or with a known gap |
| `NOT_VERIFIED` | asserted somewhere, no evidence yet |
| `ASSUMPTION` | a number chosen so the model could run |

| # | Claim | Evidence | Source | Status | Link / file | Owner | Date |
|---|---|---|---|---|---|---|---|
| 1 | The rules engine is deterministic and reproducible | Same snapshot → identical `evaluation_id` and score; timezone mixing normalises | code + tests | `VERIFIED` | `tests/test_ml_p0.py::TestStrictSnapshots`; `anti_drop_ml/adapter.py` | ML owner | 2026-10-08 |
| 2 | Invalid contracts are rejected, not crashed | 24 invalid payloads all return 422, never 500 | fixtures + tests | `VERIFIED` | `fixtures/episodes/invalid_contract/invalid.jsonl`; `tests/test_p1_fixtures.py` | ML owner | 2026-10-08 |
| 3 | The detector does not accuse family collections | 12 legitimate negatives, 0 RED on the P1 fixture set | synthetic evaluation | `PARTIAL` | `reports/evaluation/legitimate_negative_report.md` | ML owner | 2026-10-08 |
| 4 | Recall is 0.94 with FPR 0.00 | 33 synthetic risk episodes, 31 TP | synthetic evaluation | `PARTIAL` — labels are `synthetic_placeholder`, n=33 | `reports/evaluation/metrics.json` | ML owner | 2026-10-08 |
| 5 | Four rules contribute nothing to recall on this fixture set | ablation deltas are exactly 0 | synthetic ablation | `PARTIAL` | `reports/evaluation/rule_ablation.csv` | ML owner | 2026-10-08 |
| 6 | Language cannot influence the score | 486 injection attempts, all rejected by the closed contract | contract + report | `VERIFIED` | `reports/evaluation/report.md#Language invariance`; `anti_drop_ml/contracts.py` | ML owner | 2026-10-08 |
| 7 | The score is not a probability | `score_interpretation` is pinned in every response | contract + UI copy | `VERIFIED` | `anti_drop_ml/contracts.py::RiskDecisionV1`; `static/js/app.js` | product owner | 2026-10-08 |
| 8 | Exactly one target locale is shipped, as a draft | one pack, `status: draft`, mandatory badge | repo | `VERIFIED` | `locales/uz-UZ.json`; `src/localization.py` | product owner | 2026-10-08 |
| 9 | The target translation is native-reviewed | — | — | `NOT_VERIFIED` | — | native reviewer | — |
| 10 | The target translation is legally approved | — | — | `NOT_VERIFIED` | — | legal reviewer | — |
| 11 | A warning in the client's language changes the next action | — | — | `NOT_VERIFIED` | `docs/experiment_design.md` | experiment owner | — |
| 12 | The experiment is powered | n=0 collected; baseline rate is an assumption | — | `NOT_VERIFIED` | `reports/experiment/power_analysis.md` | experiment owner | — |
| 13 | False-alert handling cost is 650 ₽ per contact | assumed | — | `ASSUMPTION` | `configs/financial_assumptions.json` | finance owner | — |
| 14 | Drop-episode prevalence is 0.002 per client-year | assumed | — | `ASSUMPTION` | `configs/financial_assumptions.json` | finance owner | — |
| 15 | Bank loss per prevented episode is 45 000 ₽ | no bank data available | — | `ASSUMPTION` (`source: unknown`) | `configs/financial_assumptions.json` | bank owner | — |
| 16 | The base financial case is not positive | model output | model | `PARTIAL` — computed from assumptions 13–15 | `reports/finance/financial_scenarios.csv` | finance owner | 2026-10-08 |
| 17 | Break-even needs ≈ +2.4% clients or +5.9% delta | model output | model | `PARTIAL` — same assumptions | `reports/finance/break_even.md` | finance owner | 2026-10-08 |
| 18 | Revenue uplift is zero | pinned, no evidence for anything else | — | `VERIFIED` | `src/finance.py::PINNED_ZERO` | finance owner | 2026-10-08 |
| 19 | Cashback / rewards are not part of this layer | pinned to 0 | — | `VERIFIED` | `src/finance.py`; `docs/financial_model_methodology.md` | finance owner | 2026-10-08 |
| 20 | The bank needs a communication layer | — | — | `NOT_VERIFIED` | `docs/hypothesis_tracker.md#H5` | business owner | — |
| 21 | No real banking action is possible from this code | no payment, block, freeze, OTP or payout code path exists | code review | `VERIFIED` | `src/operator.py`, `src/advisory.py`, `docs/limitations.md` | engineering | 2026-10-08 |
| 22 | The operator surface is local-only | loopback check + double flags; non-loopback returns 403 | tests | `VERIFIED` | `tests/test_p1_operator.py` | engineering | 2026-10-08 |
| 23 | The operator surface is production-secure | there is no authentication | — | `NOT_VERIFIED` | `docs/operator_sandbox_guide.md` | security owner | — |
| 24 | Exports contain no raw PII | structural allowlist + digit masking, tested | tests | `VERIFIED` | `src/operator.py::redact_row`; `tests/test_p1_operator.py` | security owner | 2026-10-08 |
| 25 | The UI is accessible to screen-reader users | markup follows the rules; no screen reader has been used | manual review only | `NOT_VERIFIED` | `docs/accessibility_checklist.md` | frontend owner | — |
| 26 | The warning reaches the client before the money moves | post-event only; advisory sandbox is unapproved and off by default | — | `NOT_VERIFIED` | `src/advisory.py`; `docs/pre_transfer_advisory_limitations.md` | product owner | — |
| 27 | The holdout split is subject-disjoint | asserted by construction and re-checked before writing | code + manifest | `VERIFIED` | `anti_drop_ml/evaluation/holdout.py`; `reports/evaluation/holdout_manifest.json` | ML owner | 2026-10-08 |
| 28 | Rules need a real holdout | the shipped split is bookkeeping, not a trained-model holdout | — | `PARTIAL` | `reports/evaluation/warnings.md` | ML owner | 2026-10-08 |
| 29 | Independent human-reviewed labels exist | none in this repository | — | `NOT_VERIFIED` | — | ML owner | — |
| 30 | A pilot is ready to start | entry gates are pending/partial/blocked | config | `VERIFIED` — the validator reports `ready_to_start: false` | `configs/pilot_stop_criteria.json` | pilot owner | 2026-10-08 |

## What a jury should read first

Rows 3–5 are the only measured results, and they are synthetic. Rows 9, 11, 12,
20, 23, 25, 26, 29 are the honest gaps. Rows 13–15 are the numbers the financial
model rests on, and all three are assumptions. Row 30 is the closest thing to a
"no" in this repository, and it is deliberate.