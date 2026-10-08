# Verification — 2026-10-08

Backend worktree D:/FintechPSD/anti-drop-backend, branch backend-antidrop-postgres, base origin/zima e1b8f37. Evidence concerns local working code, not bank certification.

- `uv sync --locked` installs pinned environment.
- TEST_DATABASE_URL=<isolated native PG 18 antidrop_test> with `uv run pytest -q`:83 passed,21 subtests; one upstream Starlette/httpx deprecation warning.
- Nine real PG tests cover migrations/constraints, owned reads, foreign access, same-key replay/conflict,16 concurrent requests/8 workers, injected audit failure atomic rollback, separate-process retrieval, missing/unavailable storage503. Not SQLite substitutes.
- `docker compose up --build -d --wait`: PG 16, migration, unprivileged API, loopback8010, no PG port.
- Separate `antidrop-freshcheck` Compose project with a new empty volume and loopback8011 also bootstrapped roles/schema automatically. Evaluation, case, replay and retrieval passed; temporary containers stopped afterward. Original demo volume was untouched.
- Runtime-role SQL checks: not superuser, no CREATEDB/CREATEROLE, DML allowed, DELETE/schema CREATE denied.
- `scripts/demo_sandbox.py`: RED85/three reasons; committed case, same-key replay, owned GET match. No bank dispatch.
- Restart both PG/API, wait, `--verify-existing`: exact saved response survives named-volume restart.
- 24-fixture evaluation:TP2 FP1 TN21 FN0. Recall2/2 Wilson95%34.2..100%; precision2/3 20.8..93.9%; FPR1/22 .8..21.8%. All synthetic_placeholder, no holdout. Legitimate rent collection false positive remains. These are not production estimates.

Domain regression: SIM0 preserved/boolean rejected; exact money/extremes; aware/bounded dates; mixed subjects and composite duplicate IDs rejected; empty/zero/future insufficient; legacy future2099 excluded without explicit time; equivalent phone normalization; neutral warnings; body cap/redaction/request IDs.

UTC year-boundary offsets are rejected after normalization rather than producing an adapter revalidation500.

Legacy-case tests now assert deliberate410; persistent replacement tested separately. Prior frontend Playwright belongs to separate branch. Unverified: connected Next flow, production load/IAM/feed, restore, TLS/rate limits, user efficacy, reviewed translations/economic effect. Without TEST_DATABASE_URL nine PG tests explicitly skip.
