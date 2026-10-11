# Latest changes — 2026-10-11

## Unified application

- Combined the approved Next.js frontend, authenticated FastAPI/PostgreSQL backend and compatible P1 tools in one root project. Preserved Onest, shared navigation and existing MVP screens.
- Added a Next server BFF with a route allowlist, server credentials, origin/body/timeout checks and redacted failures. Monitoring now creates and reads durable owned cases; repeated requests do not duplicate them.
- Added PostgreSQL migrations, separate runtime database role, readiness checks, Docker Compose, locked dependencies and GitHub CI. Removed reliance on unsafe unscoped cases, client-supplied identity and vendored virtual environments.

## Learning cards and progress

- Imported seven course topics,40 truth cards and25 test questions from supplied quizData.pdf, preserving draft/source-needed labels.
- Added a choice of quiz, mini-lesson with cards and final quiz, or article with a comprehension question. Answers are graded on the server; progress survives reloads and service restarts.
- Added server-date streaks,3/7/14/30-day virtual bonuses, XP ranks and progress toward the next rank. After30 consecutive days, earn one additional demo cashback category choice per eligible calendar month, with retained choice history.
- Added retry/error states, keyboard/mobile support and browser/backend tests. No invented percentile or actual bank bonus is displayed.

## Documentation and history

- Root README covers first deployment, local development, configuration, API, demo steps, tests, backup and troubleshooting.
- Integration documents explain branch audit, conflict decisions, preserved/deferred behavior, test evidence and archive tags. The sole maintained branch is master; historical commits remain available through recovery tags.
- Known limitation: five linked HIGH advisories in development lint tooling; runtime npm audit is clean. Course/translation review, production identity and the operator runtime remain future work.
