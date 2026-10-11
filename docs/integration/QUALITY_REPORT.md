# Integration quality report — 2026-10-11

## Verified locally

- Final unified backend: **193 passed +174 subtests**, real PostgreSQL16 in an isolated `antidrop_test_unified` database. One upstream Starlette/httpx deprecation warning; no failing or skipped PostgreSQL gate in this run.
- Frontend: fresh `npm ci`, lint, TypeScript and production build passed. Full Playwright suite: **29 passed** against the real API, including BFF boundaries, legacy navigation/scenarios, learning, persistence and responsive layouts. Eight learning tests also passed after screenshot-only refinement.
- Docker: Python3.12/API, Node22/standalone Next, PostgreSQL16, separate migrations and restricted runtime DB role build and start successfully. Readiness queries actual tables.
- Real published Docker site: article -> answer -> completion -> reload; desktop1672/mobile390 without overflow/page exceptions; RED85 analysis -> persistent case -> read. Original screenshot is unavailable locally; exact pixel equivalence is not claimed. Approved shell/Onest/CSS Modules were preserved.
- Restart of PostgreSQL/API/frontend and API rebuild retained both independently-created cases and the learning profile (XP60).
- BFF: normal GREEN0/attack RED85, same-origin checks, foreign origin403, unknown route404, oversized body413, wrong content type415, conflict409, no browser credential/owner trust. Separate container with no credentials: private learning503, public catalog200; no leaked credentials.
- Learning: answer secrecy, grading, server-date streaks, replay/conflict, failed grading, subject isolation, concurrency, monthly category entitlements/history/older-period claims. Seven topics/40 truth cards/25 source test questions; adapted FAQ and draft/source-needed labels retained.
- Migration from empty DB through both revisions and Alembic metadata check passed. No SQLite or in-memory persistence fallback.
- Backup **and restore**: `pg_dump -Fc`, restore into a new isolated database, verify7 cases/1 learner. Existing DB/volumes were not reset.
- Production npm audit: **0 vulnerabilities**. Five HIGH advisories are the same development-only ESLint -> fast-glob -> micromatch -> braces chain (GHSA-vfj7-8cjw-p6xm). No compatible fixed braces release was available during verification; forced downgrade was not applied.
- P1 evaluation:81 episodes/56 primary episodes, whole-subject holdout prevents subject leakage. Localization/finance checks passed with expected draft UZ privacy fallback. Ablation is explicitly **NOT RUN**.

## Reproduction

Follow root README. Use `uv sync --frozen`, isolated `TEST_DATABASE_URL`, `pytest -q`; frontend `npm ci`, `npm run lint`, `npm run typecheck`, `npm run build`, `APP_ORIGIN=http://127.0.0.1:3001 npm run test:e2e`. Windows PowerShell environment syntax is provided in README. Never point regression tests at a shared demo database.

## Limits

This is a synthetic MVP with one shared demo profile, virtual rewards and draft educational/translations content. No bank integration, real cashback, real leaderboard percentile, production identity, streak freeze, or independently validated fraud accuracy. Optional legacy operator runtime is deferred until it has authenticated PostgreSQL storage; its source commits remain recoverable from archive tags. Vendored virtual environments and unsafe browser-supplied identity/storage were intentionally excluded.

Clean-clone deployment and GitHub publication status are recorded in the release verification section as they complete. GitHub CI is additional evidence, not implied by local success.
