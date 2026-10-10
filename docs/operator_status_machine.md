# Operator case status machine

The state machine lives in `src/cases.py` (`OPERATOR_STATUSES`,
`ALLOWED_TRANSITIONS`) and is served at `GET /api/operator/status-machine`.

## States

| Status | Meaning | Terminal |
|---|---|---|
| `created` | sandbox case exists, nobody has looked at it yet | no |
| `viewed` | an operator opened the case | no |
| `help_started` | the client asked for help in the demo flow | no |
| `case_confirmed` | the client confirmed they understand the situation | no |
| `safe_action_confirmed` | the client confirmed they will not forward the money | no |
| `closed_demo` | demonstration finished | **yes** |
| `failed` | the attempt did not complete | no |
| `unknown` | the state could not be determined | no |

## Transitions

```
created            -> viewed | help_started | failed | unknown | closed_demo
viewed             -> help_started | case_confirmed | failed | unknown | closed_demo
help_started       -> case_confirmed | safe_action_confirmed | failed | unknown | closed_demo
case_confirmed     -> safe_action_confirmed | failed | unknown | closed_demo
safe_action_confirmed -> closed_demo | failed | unknown
failed             -> closed_demo | unknown
unknown            -> viewed | help_started | case_confirmed | closed_demo | failed
closed_demo        -> (terminal)
```

Two rules the code enforces rather than documents:

1. **No skipping.** `created -> safe_action_confirmed` is `409`. The sequence is
   the observation: a case that jumps to a confirmed safe action implies the
   intermediate conversation happened, which the sandbox cannot show.
2. **No resurrection.** `closed_demo` is terminal.

Two pragmatic exceptions:

- requesting the **current** status is a no-op reported as `idempotent_replay: true`
  rather than an error, so a double click is harmless;
- reusing an `Idempotency-Key` with a **different** payload is `409`, not a silent
  overwrite.

## Allowlists

| List | Values |
|---|---|
| `actor_role` | `demo_operator`, `demo_observer`, `demo_reviewer` |
| `note_code` | `sandbox_confirmation`, `help_path_explained`, `translation_fallback_seen`, `client_will_hold_transfer`, `client_asked_official_channel`, `client_unreachable`, `duplicate_report`, `simulator_test`, `demo_no_response` |
| `scenario_code` | `demo_normal`, `demo_attack`, `demo_edge`, `demo_missing_data`, `demo_family_collection`, `demo_salary_cash`, `demo_night_worker`, `demo_regular_payments`, `demo_manual` |

**Free text is not accepted anywhere.** This is the main privacy control: an
operator cannot write "client said his wife asked to transfer 200k to card
4276…" into a record, because there is no field for it.

Explicitly rejected notes: "money returned", "account frozen", "client accused",
"OTP verified", cashback granted, anything containing personal data.

## Timeline

Every transition appends to the case timeline:

```json
{"status": "case_confirmed", "at": "2026-10-08T12:10:00Z",
 "actor_role": "demo_operator", "note_code": "sandbox_confirmation"}
```

Timestamps are UTC ISO-8601 with a `Z` suffix. The timeline is append-only: no
update path rewrites or deletes an entry.

## Idempotency

| Situation | Result |
|---|---|
| first request with key `K` | transition applied, `idempotent_replay: false` |
| repeat with key `K`, same payload | no second transition, `idempotent_replay: true` |
| repeat with key `K`, different payload | `409` |
| no `Idempotency-Key` header | `400` |
| unknown case id | `404` |

Case creation is idempotent on `(subject_pseudonym, scenario_code,
Idempotency-Key)`, so a retrying client never creates a duplicate case.

## What the states do not mean

`case_confirmed` and `safe_action_confirmed` record what a **synthetic
participant in a demonstration** clicked. They are not evidence about a real
client, and they must never be used to support a claim that the product changed
client behaviour. The experiment analysis labels them `exploratory` for exactly
that reason.

## Testing a transition

```bash
curl http://127.0.0.1:8000/api/operator/status-machine
curl -X POST http://127.0.0.1:8000/api/operator/cases/case_XXX/status \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: t1' \
  -d '{"status":"safe_action_confirmed","actor_role":"demo_operator"}'
# -> 409 viewed -> safe_action_confirmed is not an allowed operator transition
```