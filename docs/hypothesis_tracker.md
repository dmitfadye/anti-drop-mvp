# Hypothesis tracker

Every hypothesis starts `untested`. Status changes require the named evidence in
the "evidence" column — not a feeling, not a demo, not a screenshot.

| id | Hypothesis | Status | Method | Sample | Confirm if | Refute if | Current evidence | Missing evidence | Owner | By |
|---|---|---|---|---|---|---|---|---|---|---|
| **H1** | A language barrier prevents a safe action on bank messages | `untested` | semi-structured interviews, 12–15 participants | clients using bank messages in a non-Russian language | ≥ 8 describe not understanding or reading word-by-word, and ≥ 5 would change their action if it were clear | most describe full comprehension and unchanged behaviour | none | interviews, verbatim recall of real messages | research owner | before any pilot |
| **H2** | A warning in a contextual native language improves understanding | `untested` | powered A/B, `safe_action_rate` primary | power-plan n per arm | difference positive with CI excluding zero | CI includes zero after the planned sample | none | approved `uz-UZ` translation; baseline rate; power plan | experiment owner | stage 3 |
| **H3** | The rules give acceptable precision at an acceptable recall | `PARTIALLY_SUPPORTED (SYNTHETIC)` | fixture evaluation + ablation + holdout split | 81 synthetic episodes, `synthetic_placeholder` labels | FPR gate met on human-reviewed holdout | FPR or recall below the agreed gate on adjudicated data | `reports/evaluation/*`: recall 0.94, FPR 0.00 on synthetic fixtures; 4 rules contribute nothing on this set | independent human-reviewed labels; a real holdout; bank-agreed gates | ML owner | before pilot |
| **H4** | A clear warning increases the intention to seek help | `untested` | usability study with blinded scoring | 20–30 participants, exploratory | `help_started` and safe-action rates clearly higher, with no rise in `felt_accused_rate` | no change, or higher `felt_accused_rate` | none | conducted study; blinded export filled in | product owner | before pilot |
| **H5** | The bank needs a communication layer separate from the existing antifraud | `untested` | structured conversation with the bank risk/fraud owner | n/a | bank confirms a gap between "flagged" and "client understands next step" | bank confirms existing channels already cover it | none | the conversation | business owner | before pilot |
| **H6** | The economics are positive | `REFUTED ON CURRENT ASSUMPTIONS` | parameterised model + sensitivity + break-even | assumptions only | base `AnnualMargin > 0` | base `AnnualMargin <= 0` | `reports/finance/*`: base margin ≈ −0.2M ₽/yr; break-even needs +2.4% clients, +5.9% delta, or −2.4% OPEX | prevalence, unit loss, OPEX, K, false-alert rate from bank data | finance owner | before pilot |

## Notes per hypothesis

**H1** — the cheapest to test and the one most often asserted without evidence. The
guide exists (`docs/discovery_interview_guide.md`); the interviews have not
happened.

**H2** — cannot start today: the treatment translation is `draft`. Running it would
test a translation no one has reviewed.

**H3** — the only hypothesis with any numbers, and every number is synthetic.
`reports/evaluation/rule_ablation.csv` also shows that `cashout_ratio`,
`night_activity`, `sim_changed_recently` and `device_novelty_with_baseline`
contribute nothing to recall on this fixture set, which is a real finding about
the fixture set, not about the rules.

**H4** — the sandbox case counters (`case_created`, `help_started`) are
instrumented, but no data has been collected.

**H5** — this is the assumption the whole project rests on. If the bank already
sends a clear in-language warning, there is no product.

**H6** — deliberately close to break-even. A comfortable base case would have
been a fabricated base case. The falsification condition is documented so the
model can be wrong in public.

## Rules for this file

- status values are `untested`, `partially_supported`, `refuted`, `validated`;
- `validated` requires evidence a third party could check;
- an `owner` and a `by` date are mandatory; an empty cell is a blocker;
- a hypothesis that has been refuted stays in the file with its refutation.
  Deleting it would be the dishonest option.