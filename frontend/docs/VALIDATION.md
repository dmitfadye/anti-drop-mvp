# Validation — 8 October 2026

Node 24.19.0 / npm 11.17.0 on Windows. Registry-stable versions are pinned by package-lock.json.

- ESLint: passed.
- Strict TypeScript: passed.
- Next.js production build: passed, overview prerendered.
- Playwright / installed Edge: five tests passed, responsive widths 390/768/1024/1440, anchor destinations, overflow, keyboard skip and disclosure.
- Existing Python unittest suite: 14 tests passed, backend unchanged. pytest is not installed; repository uses unittest.
- Runtime dependency audit (`npm audit --omit=dev`): zero findings.
- Full dependency audit: five high entries in one development-only chain, eslint-config-next → Next ESLint plugin → fast-glob → micromatch → braces. Published braces 3.0.3 is affected by nested-pattern stack exhaustion (GHSA-vfj7-8cjw-p6xm); registry had no patched braces release. Do not apply npm's suggested downgrade to Next 14 tooling. Lint only trusted repository patterns. ESLint 9 emits an end-of-support warning; compatibility was prioritized over an unvalidated major upgrade.

This is a foundation smoke check, not a complete accessibility certification, penetration test or bank-integration test. Visual review covers desktop/mobile screenshots; font assets are system fallbacks. Playwright artifacts remain ignored.

## Legacy scenario migration

Eight Playwright tests passed after migration, including real backend analysis/quiz/phone scenarios, API failure/retry and loaded mobile reflow. Lint, strict typecheck and production build passed. Desktop/mobile rendered screenshots inspected. Original Python/static source unchanged.
