# Blinded scoring rubric

Used by whoever collects usability data. The participant never sees which arm
they are in; the analyst does not know either until collection is closed.

## Why blinded

If a participant can tell they got the "new" version, they rate it differently.
If the analyst can unblind early, they will quietly change the questions. Both
biases are expensive and both are cheap to prevent: a `blin_<hash>` display id
plus a map stored in a different place.

## Collection rules

- `display_template_id` comes from `blinding_map.json`. Never type a real
  template id into a participant record.
- `presentation_order` is randomised per participant so order effects do not
  attach to one arm.
- One session per participant. A repeat visit is a second observation, not a
  second participant, and breaks the independence assumption behind the intervals.
- Record what the participant **did**, not what you think they meant.
- `comments_no_pii`: no names, no phone numbers, no card digits, no employer
  names, no screenshots of real statements. The field rejects phone-shaped digit
  runs; that is a backstop, not a licence.

## Fields

| Field | Type | Meaning | Allowed values |
|---|---|---|---|
| `participant_pseudonym` | string | pseudonymous id | `sub_participant0001` style, never a phone |
| `scenario_id` | string | which situation was shown | `transit_red`, `salary_cash_yellow` |
| `presentation_order` | int | order within the session | 1..N |
| `display_template_id` | string | blinded template | `blin_<16 hex>` |
| `risk_level` | enum | level shown | `RED`, `YELLOW`, `GREEN` |
| `action_choice` | enum | what the participant chose to do next | `safe_action_chosen`, `accepted_advisory`, `unsafe_action_chosen`, `declined_advisory` |
| `time_to_action_ms` | int | from render to first action | ms, 0..3 600 000 |
| `confidence` | int 1..5 | how sure they were | 1 = guessing |
| `felt_accused` | bool | did the wording feel like blame | |
| `understood_next_step` | bool | could they state the next step | |
| `comments_no_pii` | string | free text, PII-free | ≤ 280 chars |

## Grading the action choice

The rubric depends on the scenario, so the safe choice differs:

| Scenario | Safe | Unsafe |
|---|---|---|
| `transit_red` | stop forwarding, contact the bank through an official channel, ask the bank to check the account | continue forwarding, send the money "just this once", share card or codes with anyone, wait for the problem to pass |
| `salary_cash_yellow` | check with the bank, ask questions before acting | panic-close the account, send money "to be safe", hand over the card |

`declined_advisory` is **not** automatically unsafe. A participant who read the
warning and decided the situation did not apply has understood it correctly. It
is coded separately so the analysis can distinguish "ignored" from "did not
apply".

## The three questions

| Id | Question | Probes |
|---|---|---|
| `q1` | «Что сейчас произошло с моими операциями?» | comprehension of the risk explanation |
| `q2` | «Что банк предлагает сделать дальше?» | whether the next step is clear |
| `q3` | «Будет ли банк блокировать мои деньги?» | false-promise check — **the correct answer is "нет"** |

`q3` is the safety question. If a participant answers "yes, they will block my
money", the wording failed regardless of how good the comprehension score is.

## Analysis rules

- unblind only after collection is closed and the data is frozen;
- report intention-to-treat: every assigned participant counts in their arm;
- Wilson intervals on every rate;
- report `felt_accused_rate` as a guardrail even when it moves the "wrong" way;
- report `translation_fallback_rate` — a high rate means the treatment copy is
  incomplete and the comparison is unfair;
- no uplift claim without a powered sample.

## Honest statement

`reports/experiment/blinded_scoring_template.csv` ships with **zero filled
rows**. No participant answers exist in this repository. Any analysis run before
real collection would describe invented data, and `src/experiments.py` refuses to
set `claim_permitted: true` in any case.