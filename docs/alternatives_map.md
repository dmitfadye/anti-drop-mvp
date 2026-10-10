# Alternatives map

What the client does today instead of using this layer, and what a bank could do
instead of buying it. Being honest about the second list is the point.

**Status: assessment by the team. No user research, no vendor comparison, no
measured figures.**

## What a client does instead

| Alternative | Cost to client | Why it wins | Where it fails | Our layer's advantage | Our layer's disadvantage |
|---|---|---|---|---|---|
| **do nothing** | high if wrong | zero effort, no confrontation | money is already gone | explains before the loss | post-event only |
| **ask a friend or relative** | free | trusted, human | uninformed; "just send it once" | bank-grade explanation | colder, slower |
| **call the hotline** | time | authoritative answer | queue, language, hours | asynchronous, written, in-language | no real support behind it |
| **ask the recruiter** | free | they reassure you | conflict of interest | neutral | nothing we can add here |
| **check the app history** | free | concrete data | a normal-looking payment looks normal | explains the pattern, not just the list | pattern ≠ intent |
| **ask another bank** | time | comparison | inconsistent answers | consistent, versioned wording | no real service level |
| **transfer to another card** | time | feels like a workaround | destroys the trail and can be a mule step itself | keeps the trail intact | we cannot enforce it |
| **block the sender** | free | immediate | does not help if the sender is a real acquaintance | reframes the risk | none |

## What the bank could do instead of this layer

| Bank-side option | What it does | Relative cost | Why we are not claiming it |
|---|---|---|---|
| **hold or block the transaction** | stops the loss | operational and legal cost; customer friction | not our scope; requires bank infrastructure and compliance approval |
| **existing antifraud score / rule engine** | already scores transactions | already paid for | this layer explicitly counts only *incremental* effect on top of it |
| **SMS / push notification in the client's language** | simpler channel | low | a notification is not an explanation; can be ignored |
| **in-app flow before the transfer** | warns *before* the money moves | requires payment-flow integration | we have an advisory sandbox only, and it is not approved |
| **transaction cool-down for new recipients** | mechanical prevention | friction for legitimate cases | would create exactly the false positives this catalogue documents |
| **callback verification with the client** | human confirmation | expensive | no capacity, no ownership |
| **post-event SMS about the episode** | warns after the fact | low | this is the category our layer sits in, and its value is unproven |
| **nothing; rely on existing protection** | status quo | zero | the honest baseline our financial model measures against |

## Why not more automation

| Option not built | Why |
|---|---|
| ML model instead of rules | needs labelled bank data, model governance and monitoring we cannot provide; a rules engine is explainable to a client and to compliance |
| LLM-generated warning text | no verified translator path, no review trail, unprovable tone, and it would break the "no accusation" guarantee |
| real-time scoring on every transaction | the payment integration does not exist here; a half-built pre-transfer flow creates false expectations |
| automated case creation into the bank's CRM | needs access control, retention policy and an owner — none exist |

## Honest conclusion

The alternatives table is symmetric, and that is the finding. This layer competes
with "ask a friend" and with the bank's existing protection, not with nothing. Its
entire value is the incremental effect of *explaining the risk in the client's
language at the moment of risk*, and that effect is currently
`NOT_VERIFIED / ASSUMPTION` in every document in this repository.