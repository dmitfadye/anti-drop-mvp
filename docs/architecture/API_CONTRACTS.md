# API contracts and frontend handoff

Version 0.4.0; source of truth: `docs/schemas/openapi.json` and model schemas. All `/sandbox/*` routes require `Authorization: Bearer <server-provisioned token>`. Never expose credentials in URLs, logs or committed code. Local identities are not bank IAM.

| Endpoint | Behavior |
|---|---|
| POST /sandbox/evaluations | 200 after decision commit; subject must match token |
| GET /sandbox/evaluations/{id} | Owned decision, otherwise404 |
| POST /sandbox/cases | 201 committed case; required Idempotency-Key |
| GET /sandbox/cases/{id} | Owned case, otherwise404 |
| GET /sandbox/cases | Owned pagination, limit1..100, offset0..10000 |
| POST /api/v1/risk/evaluate | Stateless synthetic evaluation, no identity/persistence |
| POST /api/analyze | Legacy analysis with safer validation and insufficient-data result |
| POST /api/cases; GET /api/cases/{id} | 410: unsafe unowned memory implementation retired |

RiskSnapshotV1 uses opaque refs, explicit aware analysis_at, integer minor units and bounded events. Duplicate `(source,event_id)` or `(source,source_event_id)` is rejected; different sources may reuse local IDs. Mixed subjects, invalid dates and boolean SIM coercion are rejected. Source type is synthetic/sandbox, never bank_trusted. Times normalize to UTC. Future/zero events do not score; empty/all-excluded input returns INSUFFICIENT_DATA. evaluation_id hashes canonical scoring inputs/version, excluding transport metadata.

Decision exposes rule version, score/level, reason contributions, warnings and sandbox:true. Explicit identical inputs/version replay deterministically. Points are uncalibrated, not fraud probabilities.

Case body: `{evaluation_id, selected_language, contact_reason, client_comment?}`. Reasons: explain_risk, suspicious_request, need_assistance. Comment <=500 characters, synthetic only, fingerprinted but not retained. Key:1..128 permitted ASCII characters. Scope: subject/operation/key digest. Same key/body returns identical case and201; changed body409. Concurrent replay creates one case/event. Evaluation must belong to authenticated subject; absent/foreign404. UUID is not authorization.

Errors: `{error_code,field,detail,request_id,errors[]}`. 401 credential,403 mismatched snapshot subject,404 hidden foreign/absent resource,409 conflict,410 retired/expired resource,413 body>2MiB including chunked upload,422 validation,503 storage/identity unavailable. Raw inputs and unknown field names are redacted. Server generates X-Request-ID, including errors. No success on failed commit.

Pending frontend sequence: authenticated evaluation -> show actual explanation/synthetic label -> create case with a fresh intent key -> retain key on retry -> show success only after201 -> GET on revisit. 503 keeps retryable pending state. Do not silently replace conflicting409 keys. Show INSUFFICIENT_DATA explicitly. Trusted bank gateway identity is required before real deployment; client subject headers/local browser-embedded tokens are not bank authentication. This is a handoff, not completed Next integration.

Legacy differences: naive dates still mean Moscow time; strict V1 rejects them. Omitted legacy analysis_at is capped at current UTC to exclude future events. Internal historical helpers may anchor to latest event; strict public replay uses explicit time. Callers expecting GREEN for empty input or legacy case success must migrate. Stdlib fallback is diagnostic only.
