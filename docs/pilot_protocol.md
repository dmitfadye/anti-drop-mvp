# Pilot protocol

**Status: NOT APPROVED.** `configs/pilot_stop_criteria.json` reports
`ready_to_start: false`. Every entry gate is pending, partial or blocked. This
document describes what a pilot would look like and what must be true first; it
is not an authorisation.

## Entry gates — none of them are signed

| Gate | Status | What "satisfied" would require |
|---|---|---|
| `owner_assigned` | pending | a named bank owner with decision authority |
| `data_legal_security_approvals` | pending | written data, legal and security approvals |
| `reviewed_templates` | **blocked** | both locales natively and legally reviewed, `status: approved` |
| `access_controls` | pending | authentication, not a loopback check |
| `data_contract` | pending | an agreed production data contract, not a synthetic one |
| `instrumented_baseline` | partial | a rerunnable baseline on real, reviewed data |
| `power_plan` | partial | required n recomputed from a measured baseline |
| `support_capacity` | pending | a staffed channel with an agreed service level |
| `stop_rollback_plan` | partial | this plan, rehearsed at least once |

Run `PYTHONPATH=app python -m scripts.validate_stop_criteria` to re-check the shape. It cannot
tell you a gate is satisfied — only a person can do that.

## Stage 1 — feasibility and usability

| | |
|---|---|
| Sample | 200–500 volunteers |
| Language | one target locale |
| Measures | comprehension, whether the message arrives at all, time to action |
| Randomisation | blinded scoring, `presentation_order` randomised |
| **Does not prove** | fraud ROI, loss reduction, detector accuracy |
| Stop | any `legal_or_privacy_incident`, any complaint about accusatory tone |

A null result here is a legitimate outcome and must be reported as such. The
question is only whether the layer is comprehensible and correctly translated.

## Stage 2 — read-only shadow

| | |
|---|---|
| Sample | approved historical or pseudonymised set |
| Compares | the layer's signal against the bank's current signal |
| Changes | nothing. No transfer is affected in any way |
| Measures | agreement, disagreement reasons, expected false-alert volume |
| Stop | any cross-subject leak, any attempt to affect a live payment |

This is where the honest accuracy conversation happens, with real data, before
anything reaches a client.

## Stage 3 — powered UX A/B

| | |
|---|---|
| Control | current bank protection and standard warning |
| Treatment | current protection plus the new communication layer |
| Primary | `safe_action_rate` uplift, with a confidence interval |
| Analysis | intention-to-treat |
| Sample | from the recomputed power plan |
| Guardrails | `felt_accused_rate`, support load, technical error rate, `translation_fallback_rate` |
| Stop | guardrail breach, harm trigger, or CI includes zero at the planned sample |

Rules, thresholds and templates are frozen for the duration. Changing the rules
and the language in the same experiment destroys the result.

## What each stage is allowed to claim

| Stage | Claimable | Not claimable |
|---|---|---|
| 1 | "the message is understood" | "fraud was prevented" |
| 2 | "the signal agrees/disagrees with the current one" | "losses fell" |
| 3 | "safe action rate differed by X, CI [a, b]" | "we prevented transfers" — prevention is not measured |

## Prerequisites that do not exist in this repository

- independent human-reviewed labels;
- an approved translation;
- a bank-agreed FPR and recall gate;
- an access control model;
- a staffed support channel;
- a rehearsed rollback;
- a data protection impact assessment;
- a real sample size computed from a real baseline.

## Rollback

`docs/rollback_plan.md`. Target: under 15 minutes from decision to the standard
bank warning, with the bank's own protection untouched.

## Communication during a pilot

Report what happened, including nulls and incidents. `reports/evaluation/warnings.md`
is the template: synthetic labels, small sample, no holdout, no bank adjudication.
Removing those lines once a pilot runs would be the first sign that the process
is being gamed.