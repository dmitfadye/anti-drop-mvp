# Pre-transfer advisory — limitations

This is the P1-OPTIONAL block. It exists because a warning that arrives after the
money has moved is a weaker product, and because showing *how* a pre-transfer
advisory could work is honest. It is not a payment decision system.

**Status: sandbox, draft, off by default.** `ANTI_DROP_ADVISORY_ENABLED=false`.

## What it is

`POST /api/v1/risk/advisory` takes `PlannedTransferAdvisoryV1`: completed history
plus one planned outgoing transfer. It runs the same rules over a *hypothetical*
snapshot that includes the planned transaction and returns a level, the score and
the contribution the planned transfer made.

```json
{
  "status": "advisory_only",
  "banking_action": "none",
  "analysis_mode": "pre_transfer_advisory",
  "message_ru": "Есть признаки рискованной схемы. Не отправляйте деньги по просьбе незнакомцев. Свяжитесь с банком через официальный канал.",
  "advisory_notice_ru": "Это проверка перед переводом, а не блокировка."
}
```

## What it is not

- **Not a payment decision.** `banking_action` is pinned to `'none'`. No code path
  from this module can block, hold, decline or reverse a transfer.
- **Not approved.** The wording has had no legal review.
- **Not wired to a payment flow.** The planned transfer arrives in the request
  body. Nothing observes a real payment attempt.
- **Not validated.** The fixtures are synthetic; a pre-transfer signal has not
  been compared against a real outcome.
- **Not a promise that the bank would act.** A real bank must confirm the signal;
  until then this is a synthetic demonstration.

## Contract guarantees

| Rule | How it is enforced |
|---|---|
| only in advisory mode | `analysis_mode` is `Literal['pre_transfer_advisory']` |
| planned events only here | the planned id is rejected if it appears in completed history |
| completed history stays completed | `allow_future_events` is not used; any history event after `analysis_at` is a validation error |
| the planned transfer never mutates history | it is scored in a temporary snapshot and discarded |
| no blocking wording | forbidden-phrase check raises if the text ever says the transfer is blocked, frozen or declined |
| separate contract from `RiskSnapshotV1` | a planned transfer cannot be smuggled into the ordinary path |

## Observed behaviour on the synthetic fixtures

| Planned transfer over this history | Level | Note |
|---|---|---|
| 5 small inbound + 14 000 ₽ onward | `RED` | the planned transfer adds `large_outbound_after_inbound` (+25) |
| salary credited + 50 000 ₽ cash withdrawal | `YELLOW` | `cashout_ratio` only; **no false RED** |
| ordinary single transaction | `GREEN` | no rule fires |

The salary-and-cash row matters: the advisory must not alarm every cash withdrawal.

## Honest comparison with the post-event warning

| | Post-event warning | Pre-transfer advisory |
|---|---|---|
| Reaches the client before the loss | no | potentially yes |
| Is the current product | **yes** | no, sandbox only |
| False-alert cost | a confusing message | a client who is stopped from a legitimate payment |
| Needs what | nothing new | payment-flow integration, legal approval, bank sign-off on the signal |
| Evidence | synthetic fixtures | synthetic fixtures |

A half-built pre-transfer flow with false expectations is worse than a correct
post-event sandbox. That is why this block is optional and why it defaults off.

## What a real pre-transfer layer would require

1. legal sign-off on the advisory wording and on the "advisory, not a block" notice;
2. integration with the payment authorisation flow, which this repository does not
   have;
3. a real precision measurement on historical attempted transfers, including
   legitimate ones that would have been warned;
4. a product decision: does the client see the advisory before confirming, or can
   it be skipped?
5. a fraud-signal source the bank trusts — our rules are a demonstrator;
6. a rollback that restores the current authorisation path within minutes.

## Testing it

```bash
ANTI_DROP_ADVISORY_ENABLED=true uvicorn main:app --host 127.0.0.1 --port 8000
pytest tests/test_p1_advisory.py -v      # or: python -m unittest tests.test_p1_advisory -v
```

Covered: advisory mode accepts the planned event, ordinary mode still rejects
future events, the advisory does not modify completed history, legitimate planned
transfers do not produce a false RED, and the UI never says "заблокировано".