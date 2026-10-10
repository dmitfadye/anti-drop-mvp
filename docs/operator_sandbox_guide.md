# Operator sandbox guide

## What this is

A local observation screen so a jury or a bank reviewer can see that a warning
leaves a trace: a case, a status, an event timeline, counters, and a redacted
export.

## What this is not

- **Not** a bank back office, a CRM, an anti-fraud console or a ticket queue.
- **No authentication.** Anyone who can reach the port can read and change it.
- **No real personal data**, ever. See the redaction section.
- **No banking action.** Nothing is blocked, frozen, escalated or paid out.
- **No audit guarantee.** The action log is append-only JSON lines in a local
  file, not a compliance-grade store.

## Turning it on

```bash
export PYTHONPATH=app   # Python code lives in app/, run from repo root
export ANTI_DROP_DEMO_MODE=true
export ANTI_DROP_OPERATOR_UI_ENABLED=true
export ANTI_DROP_OPERATOR_EXPORT_ENABLED=true      # optional, for /export
export ANTI_DROP_OPERATOR_LOG=.local/operator_events.jsonl   # optional, event sink
uvicorn main:app --host 127.0.0.1 --port 8000
open http://127.0.0.1:8000/operator
```

Two gates must both pass: the flags above, and a loopback client address. A
request from a non-loopback address gets `403` with the reason. Behind a reverse
proxy the address cannot be trusted, which is exactly why the banner says the
surface has no authentication — do not put it behind a proxy and call it secure.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/operator/cases` | list with filters: `level`, `status`, `locale`, `experiment_arm`, `episode_class`, `created_from`, `created_to` |
| `GET` | `/api/operator/cases/{case_id}` | detail plus event timeline and the status machine |
| `POST` | `/api/operator/cases` | create one sandbox case (needs `Idempotency-Key`) |
| `POST` | `/api/operator/cases/{case_id}/status` | apply one transition (needs `Idempotency-Key`) |
| `GET` | `/api/operator/metrics` | counters, rates, fallback count, assignment count |
| `GET` | `/api/operator/status-machine` | statuses, transitions, allowlists, forbidden notes |
| `GET` | `/api/operator/export?format=json\|csv` | pseudonymous export, flag-gated |

## Creating a case

```bash
curl -X POST http://127.0.0.1:8000/api/operator/cases \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $RANDOM" \
  -d '{
    "subject_pseudonym": "sub_00000000cafe0001",
    "scenario_code": "demo_attack",
    "level": "RED", "score": 70,
    "locale": "ru-RU", "locale_status": "draft",
    "template_id": "warning_ru_control_v1",
    "evaluation_id": "<64 hex>",
    "rule_version": "2026-10-08.p1",
    "threshold_version": "thresholds-2026.10.08-red50-yellow25",
    "experiment_id": "exp-warning-language-2026.10",
    "experiment_arm": "control",
    "episode_class": "risk",
    "reason_codes": ["multiple_small_inbound"]
  }'
```

There is **no free text**. `scenario_code` and `note_code` come from allowlists
(`src/cases.py`), so an operator cannot accidentally write a phone number or a
client name into a record.

## Status updates

```bash
curl -X POST http://127.0.0.1:8000/api/operator/cases/case_.../status \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $RANDOM" \
  -d '{"status":"case_confirmed","actor_role":"demo_operator","note_code":"sandbox_confirmation"}'
```

Response:

```json
{
  "case_id": "case_8944ca03f147e533",
  "status": "case_confirmed",
  "updated_at": "2026-10-08T12:10:00Z",
  "idempotent_replay": false,
  "note_code": "sandbox_confirmation",
  "sandbox_notice": "Локальная песочница. Синтетические данные. Не банковская система поддержки."
}
```

- repeat the same key with the same payload → `200`, `idempotent_replay: true`, no second transition;
- reuse the key with a different payload → `409`;
- illegal transition → `409` with the pair that was rejected;
- missing `Idempotency-Key` → `400`;
- unknown `status`, `actor_role` or `note_code` → `422`.

See `docs/operator_status_machine.md`.

## Metrics

`GET /api/operator/metrics` returns total cases, cases by level / status /
locale / arm / episode class, alert rate, legitimate-negative alert rate,
`translation_fallback` count, experiment assignment count, error/rejection count
from the event sink, and the number of logged operator actions.

Rates whose denominator is empty are `null`, never `0`. A screen showing
"legitimate negative alert rate: 0%" when nothing has been labelled would be
worse than no screen at all.

## Export and redaction

Export is off unless `ANTI_DROP_OPERATOR_EXPORT_ENABLED=true`. It is redacted
twice:

1. **Structurally** — cases only ever hold opaque `sub_` refs, reason codes,
   allowlisted note codes and version strings. There is no field that could hold
   a phone number or a name.
2. **At export time** — `redact_row` keeps an allowlist of columns, drops any
   column whose name looks PII-shaped, and masks digit runs that could be a phone
   or a card number.

## Event sink

With `ANTI_DROP_OPERATOR_LOG` set, communication events and `experiment_assigned`
records are appended to that JSON-lines file. Each line is validated against the
closed `ProductEventV1` contract before it is written, so a malformed event is
dropped with a stderr note instead of landing in the log. There is no broker and
no database; the file grows and is rotated by whoever owns the machine.

## Resetting

```bash
python -c "from src.cases import reset_operator_store; reset_operator_store()"
```

Cases live in process memory, so a restart clears them. That is intentional for a
demo and would be unacceptable for a pilot: the pilot needs a real store with
retention and access control.

## What a pilot would still need

- authentication and authorisation, not a loopback check;
- a real case store with retention, access control and audit;
- a real escalation path to support, with a staffed service level;
- an approval gate on which statuses an operator may set;
- monitored logging with alerting on the error counters;
- a documented, rehearsed rollback (`docs/rollback_plan.md`).