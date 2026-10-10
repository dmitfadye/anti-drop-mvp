# Security and privacy gate checklist

A gate list for a pilot discussion. **Nothing here has been signed by a security
owner.** Items marked `PARTIAL` describe what this repository actually does;
items marked `NOT VERIFIED` are claims nobody has checked yet.

## Identity and access

| # | Item | Status | Note |
|---|---|---|---|
| 1 | Authentication on every non-public route | `NOT VERIFIED` — none exists | the operator surface has no auth at all, only a loopback check |
| 2 | Authorisation per role | `NOT VERIFIED` | `actor_role` is an allowlist label, not an identity |
| 3 | Loopback-only for the operator surface | `PARTIAL` — implemented, tested | trivially bypassed behind a proxy |
| 4 | Secret management | `NOT VERIFIED` | there are no secrets in this repository; a deployment must introduce them properly |
| 5 | Session handling | n/a | no sessions, no cookies, no tokens |

## Data protection

| # | Item | Status | Note |
|---|---|---|---|
| 6 | Pseudonymous refs only | `PARTIAL` — enforced by regex + closed models | `sub_`, `cp_`, `evt_`, `case_`, `tpl_`, `dev_`, `ep_`, `src_` |
| 7 | Raw PII rejected, not stored | `PARTIAL` — 24 invalid-contract cases prove rejection | rejection is not the same as detection |
| 8 | Validation errors do not echo raw input | `VERIFIED` | `POST /api/v1/risk/evaluate` returns `type` and `loc` only |
| 9 | Logs redacted | `PARTIAL` — events are allowlist-validated before writing | file permissions and rotation are the operator's job |
| 10 | Exports redacted | `PARTIAL` — column allowlist plus digit masking | no independent review has been performed |
| 11 | Data minimisation | `PARTIAL` | only `label`, `level`, `score`, `reason_codes`, versions are needed; nothing else is stored |
| 12 | Retention policy | `NOT VERIFIED` | none defined; the demo files grow until deleted |
| 13 | Legal basis / DPIA | `NOT VERIFIED` | belongs to a data protection owner |
| 14 | Subject access and deletion | `NOT VERIFIED` | no store, no process |

## The three data classes

| Class | Examples | Handling |
|---|---|---|
| Synthetic | all fixtures, demo scenarios, operator cases | allowed everywhere, labelled in code and in the UI |
| Pseudonymous | `sub_<hash>`, `cp_<hash>`, `case_<hash>` | allowed in logs and exports; re-identification risk must be assessed by the owner |
| Raw PII | phone, name, passport, card, OTP, address | never accepted; refused by the contracts; must never be entered, even in a demo |

If a real customer's data reaches any of these surfaces, that is an
`immediate_stop` event with code `real_pii_exposure`.

## Network and runtime

| # | Item | Status | Note |
|---|---|---|---|
| 15 | No outbound network calls | `VERIFIED` — no HTTP client in `src/` | only `TestClient` in tests |
| 16 | No CDN or third-party asset | `VERIFIED` — asserted by tests | Swagger and CSS are local |
| 17 | CORS | `VERIFIED` — no wildcard | same-origin only |
| 18 | Dependency pinning | `PARTIAL` — `uv.lock` + `requirements-lock.txt` exist | no automated dependency audit in CI |
| 19 | Container runs non-root | see `Dockerfile` | verify the image, do not assume |
| 20 | No secrets in the image | `VERIFIED` — none exist; keep it true | |
| 21 | Dependency scanning | `NOT VERIFIED` | suggested in CI, non-blocking by design |
| 22 | Rate limiting | `NOT VERIFIED` | a demo on loopback does not need it; a pilot does |

## Availability and abuse

| # | Item | Status | Note |
|---|---|---|---|
| 23 | The layer cannot block or freeze a payment | `VERIFIED` by design | no payment code path exists; advisory returns `banking_action: 'none'` |
| 24 | The layer cannot create a real support case | `VERIFIED` by design | the sandbox store is local process memory |
| 25 | No OTP or SMS is sent | `VERIFIED` | the SIM trainer only simulates |
| 26 | No reward or cashback is granted | `VERIFIED` | `Rewards` pinned to 0; quiz `reward_status: simulated` |
| 27 | Graceful failure | `PARTIAL` | the UI shows errors and keeps form state; there is no circuit breaker |
| 28 | Monitoring and alerting | `NOT VERIFIED` | counters exist on a screen; nobody is paged |

## Threat notes

| Threat | Current state |
|---|---|
| Prompt injection through a transaction field | fields are typed and length-bounded; free text exists only in the quiz and the SIM trainer, both inert |
| XSS through reason codes or translations | `textContent`/`createElement` only; no `innerHTML` in `static/js/*.js`; asserted by tests |
| Refusal-of-service through a huge snapshot | `transactions` is capped at 5000; string lengths bounded |
| Log forging | events are JSON-validated before writing |
| Enumeration through error messages | errors give `type` and `loc`, not values |
| Re-identification from an export | pseudonymous by construction; masking is a backstop, not a guarantee |
| Treating the loopback check as security | **it is not.** Documented in `docs/operator_sandbox_guide.md` |

## What a security owner must do

1. Replace the loopback check with real authentication and authorisation.
2. Define retention, deletion and access logging for the case store.
3. Run a dependency audit and decide what is blocking.
4. Approve the data contract for pseudonymised transaction data.
5. Review `redact_row` and the export format independently.
6. Sign the DPIA and the legal basis.
7. Confirm the image runs non-root with no secrets, by inspection.
8. Decide the alerting policy for the operator counters.

Until those are done, this project is a demonstrator and should be described as
one.