# PostgreSQL persistence

SQLAlchemy2, psycopg3, Alembic revision832fa12ce83f. PostgreSQL-only URLs; missing storage503, no memory/SQLite fallback. Tested native PG 18 and Docker PG 16. Migration-owner credentials are separate from API runtime credentials.

| Table | Retained data/constraints |
|---|---|
| risk_evaluations | SHA256 ID, subject, aware times, rule/status/source, bounded decision JSONB; evaluation+subject unique and score/source checks |
| sandbox_cases | UUID, composite evaluation+subject FK, language/reason, registered-sandbox status/time |
| case_events | Event ID, case FK, type/time; creation atomic with case |
| idempotency_records | Unique subject+operation+key digest, request fingerprint, case FK |

No raw snapshots, names, phones, account numbers, tokens or comments are retained. Opaque refs/reason metadata still require retention/access controls. Subjects are server configuration, not a bank directory table.

Transaction: advisory lock(subject/action/key) -> replay/conflict check -> owned evaluation row lock -> insert case/event/key -> commit -> response. Unique constraint is final duplicate guard. Composite FK prevents foreign linkage. Audit/storage failure rolls back all inserts. Reads include owner. Advisory hash collision only serializes unrelated requests.

Runtime role has SELECT/INSERT/UPDATE on four tables; no schema creation/DELETE. PG has no published host port. API binds loopback, nonroot, read-only root filesystem and dropped capabilities. Named volume is persistence, not tested backup/DR.

Proposed retention:30 days. `python -m scripts.retention --days 30` dry-runs; `--apply` explicitly deletes expired evaluations and cascades dependents. Requires operator/owner credentials. Scheduling, bank-approved retention and deletion audit remain pending. Idempotency expires with retained data. Never enter real customer data.
