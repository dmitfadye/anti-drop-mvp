# AntiDrop 0.4: persistent synthetic sandbox

Explainable risk education MVP. No real VTB contact, transfers, SMS or blocking. Rule points are not probabilities.

## Local demo

Prerequisites: Python3.12+, uv, Docker Desktop/Compose. From this worktree:

```powershell
uv sync --locked
uv run python scripts/init_sandbox.py
docker compose up --build -d --wait --wait-timeout 120
uv run python scripts/demo_sandbox.py
docker compose restart postgres api
docker compose up -d --wait --wait-timeout 60
uv run python scripts/demo_sandbox.py --verify-existing
```

Initializer writes ignored .env/.local credentials, refuses overwrite. Never share them. API/docs: http://127.0.0.1:8010/docs. PG has no published port. Named volume survives restart; do not use down -v if data must remain. First build needs network; evaluation has no external inference calls.

Demo persists a synthetic RED85 explanation and test case, retries the key and retrieves the same case after DB/API restart. No bank ticket is sent.

For an old volume predating the runtime role, execute `docker compose exec postgres psql -U antidrop -d antidrop -f /docker-entrypoint-initdb.d/001_runtime_role.sql` before migrations. Fresh volumes initialize automatically.

## Verification

`uv run pytest -q`. To run all nine persistence tests, set TEST_DATABASE_URL to a dedicated PostgreSQL database whose name starts with antidrop_test. Never use customer/production DB. Without it those checks explicitly skip. On2026-10-08:83 passed on PG 18; Docker demo on PG 16. One upstream Starlette/httpx deprecation warning. See [verification](docs/architecture/VERIFICATION.md).

## Integration boundary

Next.js remains intended frontend on frontend-test-brach. Backend is isolated on backend-antidrop-postgres. Approved frontend screens were not changed/merged; support buttons are not yet connected. Verified full route is HTTP CLI/Swagger. Legacy static page is not the approved Next product.

/api/analyze remains compatible analysis; /api/v1/risk/evaluate is stateless synthetic. Legacy /api/cases now410: migrate to authenticated /sandbox/evaluations and /sandbox/cases. See [contracts](docs/architecture/API_CONTRACTS.md).

## Review material

- [Scorecard](docs/competition/JURY_SCORECARD.md), [discovery](docs/competition/PRODUCT_DISCOVERY.md), [evidence](docs/competition/EVIDENCE_REGISTER.md).
- [Economics](docs/competition/FINANCIAL_MODEL.md), [pilot](docs/competition/PILOT_PROTOCOL.md), [pitch](docs/competition/PITCH_AND_DEMO.md), [roadmap](docs/competition/ROADMAP.md).
- [Database](docs/architecture/DATABASE.md), [security](docs/architecture/SECURITY.md), [limitations](docs/architecture/KNOWN_LIMITATIONS.md).

Historical competition-audit reports concern earlier revisions. No interviews, bank validation, production accuracy, public deployment, video or finished PPTX/PDF deck is claimed.
