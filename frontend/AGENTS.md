# Frontend scope

- This directory is an independent App Router frontend with demo MVP scenarios.
- Preserve the legacy Python backend and static application.
- Use strict TypeScript and Server Components by default.
- Add client boundaries only for real interactive requirements.
- Use native CSS and CSS Modules; no Tailwind or UI kits.
- Follow strict BEM and bracket-based module access.
- Combine base classes with modifiers explicitly.
- Keep global CSS limited to tokens and resets.
- Reuse semantic tokens for color, spacing and surfaces.
- Avoid speculative abstractions and dependencies.
- Product copy is Russian; code and technical docs are English.
- Never invent balances, customer data or integration status.
- Keep prototype limitations visible and understandable.
- Link only to implemented destinations.
- Maintain keyboard access, skip links and visible focus.
- Respect reduced-motion preferences.
- Check 390, 768, 1024 and 1440px layouts.
- Run lint, typecheck, build and Playwright after meaningful changes.
- Inspect screenshots before delivering visual changes.
- Keep generated artifacts and secrets out of Git.
- Version the npm lockfile; use npm ci for reproduction.
- Stage explicit paths only and inspect the staged diff.
- Follow docs/SCREEN_WORKFLOW.md for future screens.
- Obtain visual concept approval before coding a new screen.

- Keep one shared sidebar capsule; remeasure after hash, size, font and drawer changes.
- Toolbar search covers supported sections only; preserve demo and affiliation disclosures.

# Approved implementation (2026-10-08)
- Latest reference is the single overview screenshot in the user conversation, approximately 1672 x 941. It supersedes the earlier collages.
- User explicitly authorized proceeding from the inline image without a source file or further questions.
- See ../docs/frontend/APPROVED_VISUAL_SPEC.md; do not redesign other screens.
- Work exclusively in frontend-test-brach; preserve hash navigation and backend contracts.
- Use locally hosted Onest with its SIL OFL license, strict TypeScript and BEM CSS Modules.
- Verify actual browser screenshots at reference size and 1440, 1024, 768, 390px; run typecheck, lint, build and Playwright.
