# Legal / compliance text review checklist

This layer writes text that reaches a real person at a moment of stress about
their money. That makes the wording a compliance artefact, not a design detail.

**No legal review has been performed.** Both locale packs are `draft`, and
`status: approved` is unreachable until a qualified reviewer signs the rows below.

## Scope

| Artefact | What a reviewer must confirm |
|---|---|
| `locales/*.json` | every message, per language |
| `templates/*.json` | variables, forbidden phrases, review flags, version/status |
| `src/alerts.py` | the legacy P0 warning strings still exposed via `/api/analyze` |
| `src/advisory.py` | pre-transfer advisory text, specifically the "not a block" wording |
| `static/js/app.js` | UI labels, the sandbox banner, the "score is not probability" note |
| `static/operator.html` | sandbox banner, allowlisted note codes, export note |

## Per-message checklist

| # | Check | Why | Status |
|---|---|---|---|
| 1 | No claim that a transfer was blocked, frozen, declined or will be | The system performs no banking action; a false claim is a misstatement to a client | ☐ |
| 2 | No fixed penalty, article number or criminal-law characterisation | Only a court and a bank can make such statements | ☐ |
| 3 | No accusation of knowledge, intent or complicity | The rules establish a pattern, never intent | ☐ |
| 4 | No statement that identity, phone, OTP or card has been verified | No verification happens anywhere in this layer | ☐ |
| 5 | No promise of a service level, response time or outcome | Support capacity is not staffed and not owned | ☐ |
| 6 | No promise of cashback, reward, refund or compensation | Rewards are pinned to 0 in the financial model | ☐ |
| 7 | A disclaimer states the message is not a legal conclusion and the decision is the bank's | Prevents the warning from reading as a verdict | ☐ |
| 8 | A sandbox notice states that no real support case was created | The operator store is local demo state | ☐ |
| 9 | A privacy notice states that only synthetic, pseudonymous data is used | Prevents a reader from believing real data was processed | ☐ |
| 10 | Score is described as a rule score, never as a probability | A number that looks like a probability will be quoted as one | ☐ |
| 11 | The next step is an official bank channel, not a phone number in the text | Keeps the message inside the bank's contact policy | ☐ |
| 12 | Wording is short, plain and non-technical | Read once, on a phone, under stress | ☐ |

## Tone rules

Allowed and preferred:

- «Операции похожи на рискованную схему»
- «Не пересылайте деньги по просьбе незнакомцев»
- «Свяжитесь с банком через официальный канал»
- «Это демонстрационное песочное предупреждение»

Forbidden:

- any categorical blocking, freezing or refusal claim;
- any sentencing or criminal-law qualification;
- any accusation;
- any guarantee about verification, refund or compensation;
- any reference to a specific third-party service, employer or recruiter by name.

## Required disclaimers (exact intent)

Every rendered warning must carry all three, in the rendered language:

1. **Not a legal conclusion** — and the decision belongs to the bank.
2. **Sandbox notice** — this is a demonstration; support is not contacted and
   operations are not restricted.
3. **Privacy notice** — synthetic, pseudonymous data only.

`RenderedWarning` enforces their presence structurally: they are separate
contract fields, not part of the body text, so a copy edit cannot drop them.

## Regulatory checklist the bank should extend

- [ ] 115-FZ wording reviewed by the bank's compliance function
- [ ] Local advertising / consumer-protection rules for the target market
- [ ] Accessibility requirements (WCAG 2.2 AA) confirmed for the rendered language
- [ ] Recording and retention policy for warning delivery events
- [ ] Consent and legal basis for any processing of pseudonymised transaction data
- [ ] Cross-border considerations if a target market sits outside the bank's jurisdiction
- [ ] Incident path if a client disputes having received the warning

These are outside what an implementation can honestly assert. Each one is a
question for a named owner.

## Recording the review

Add to the pack and to the template:

```json
"reviewers": [
  { "role": "legal_reviewer", "reviewed_at": "ISO-8601 UTC", "review_hash_or_pseudonym": "legal-rev-01" }
]
```

then set `status: legal_reviewed`, or `approved` with `approved_at` once the bank
owner has accepted the wording. `src/localization.py` and `src/templates.py`
refuse the status change if the attestation is missing, so this file and the code
cannot drift apart silently.

## Rollback

If a legal defect is found after release: disable the layer's feature flag,
restore the standard bank warning, keep the bank's own protection running, and
record the incident. The mechanism is `docs/rollback_plan.md` and
`configs/pilot_stop_criteria.json`.