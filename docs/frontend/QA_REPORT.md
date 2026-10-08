# QA report — 2026-10-08

Branch: frontend-test-brach. Local implementation; no push or deployment.

## Automated validation

- npm run lint: passed.
- npm run typecheck: passed.
- npm run build: passed, Next.js production output.
- npm run test:e2e: 16 passed (final run 8.5s), installed Microsoft Edge.
- Backend: .venv/Scripts/python.exe -m unittest discover -s tests -v: 62 passed. No backend changes.
- git diff --check: passed.

E2E coverage: all 11 hash sections on five widths (390, 768, 1024, 1440, 1728), no document horizontal overflow, active-capsule geometry, navigation refresh, keyboard/skip link, drawer focus/Escape, reduced motion, toolbar search/notifications, applied monitoring filters, empty results, pagination, operation details, local settings persistence, searchable knowledge/FAQ, reading focus and focus return, real backend analysis, multilingual alert, retry after HTTP 503, loaded mobile content, full sequential quiz and repeat, rejected wrong codes and equivalent phone numbers, both demo confirmations and server phone result.

## Visual review

55 full-page screenshots: frontend/test-results/screens/{section}-{width}.png. Captured after document.fonts.ready with finite animations/transitions disabled for deterministic screenshots. Generated screenshots remain ignored by Git.

Desktop screens and representative mobile screens were visually inspected. Multiple iterations corrected navigation geometry, clipped branding, dense labels, font roles, and reading visibility/focus. Review assessed the supplied conversation references qualitatively. The source collages are not available as local reference images, so no numeric reference-image diff was performed. Screenshot capture is not a pixel-perfect assertion.

## Material limitations

See KNOWN_DIFFERENCES.md and FONT_SPEC.md. Missing Halvar, normal-width Asket, original illustrations and source-resolution references prevent exact reproduction. Text guides work; no video files were supplied. All bank operations, SMS and rewards remain explicitly educational.

Backend is available on 127.0.0.1:8000. Review preview is served locally on 127.0.0.1:3002; the pre-existing process on 3000 was left running.

## Small-text readability revision

The user requested a more readable main font. Switched Asket Narrow Light 300 to Segoe UI/system-ui 400 in the main UI; display headings retained. Lint, typecheck, build and all 16 E2E tests passed again (8.8s). Regenerated screenshots and inspected desktop overview/mobile monitoring.
