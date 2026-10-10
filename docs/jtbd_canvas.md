# JTBD canvas

**Status: NOT VALIDATED.** Every entry is a hypothesis. There are no interviews
in this repository, so the jobs below are the team's reading of the problem, not
evidence about it.

## Job statement

> When I get an unexpected transfer request and I am not sure who is behind it,
> help me decide whether to act on it — so that I do not lose my money and do not
> accuse someone who deserves trust.

## When

- a stranger or distant acquaintance asks for a transfer "just this once";
- an account receives several small amounts from different people;
- a bank message uses wording they do not fully understand;
- a family member asks them to receive and forward money;
- a phone number was recently changed.

## Want / Feel / Pains

| | Statement | Confidence |
|---|---|---|
| Want | know quickly whether the situation is legitimate | assumption |
| Want | one concrete next step, not a warning | assumption |
| Feel | calm, in control, not stupid for asking | assumption |
| Pains | cannot judge intent from a payment notification | assumption |
| Pains | bank messages in an unfamiliar language | assumption |
| Pains | fear of being accused of a crime | assumption |
| Pains | no obvious way to ask "is this normal?" without a queue | assumption |

## How it is solved today

| Alternative | Why it is chosen | Where it breaks |
|---|---|---|
| ask a relative or friend | free, fast, trusted | advice is not informed; often "just send it" |
| call the bank's hotline | authoritative | wait times, queue, sometimes no Russian |
| check in the mobile app | cheap | a normal-looking payment looks normal |
| ask the recruiter directly | they reassure you | they have an incentive to reassure |
| do nothing and see | free | the money is already gone |
| ignore the bank warning | avoids conflict | the transfer already happened |

## Pain points in our solution

1. **The warning arrives after the money left.** Without an approved pre-transfer
   mode the warning is post-event. This is the largest gap and it is stated, not
   hidden.
2. **A rule engine cannot read intent.** It sees a flow shape, not a story.
3. **A false alarm costs trust.** A family collection looks exactly like a
   recruitment until proven otherwise.
4. **One language is not enough for a whole market.** We ship one target locale
   and label the rest as not done.
5. **We cannot contact anyone.** The sandbox case creates a local record; real
   support is not involved.

## What would change the job

- If the bank already blocks or holds the transaction, the job shifts from
  "decide whether to act" to "understand why the bank acted" — a completely
  different product.
- If clients habitually ignore bank messages, the job is not "better wording",
  it is "a different channel".

## Open questions to resolve in discovery

- What is the real first action after a suspicious transfer: stop, check, ask?
- Does a warning in the client's language change the action, or only the
  comprehension score?
- What proportion of episodes involve an amount that looks normal?
- Who is trusted in the client's network when a bank is not?
- What does "не разбираюсь" mean in practice: cannot read, cannot interpret, or
  does not trust the sender?

## Evidence status

| Claim | Status |
|---|---|
| Clients face a language barrier with bank messages | `NOT_VERIFIED` — no interviews |
| A clearer warning improves the next action | `NOT_VERIFIED` — no experiment run |
| Family collections are a major false-positive source | `SYNTHETIC` — from our own fixtures |
| Support load would fall | `NOT_VERIFIED` — assumption in the financial model only |