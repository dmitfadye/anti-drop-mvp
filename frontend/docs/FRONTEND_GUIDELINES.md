# Frontend guidelines

Use App Router and Server Components by default. Add a narrow client boundary only for actual state, events or browser APIs. Strict TypeScript, native CSS and CSS Modules only. No Tailwind, UI kits, state frameworks or speculative API abstraction. Keep the independent Python backend unchanged unless a later task explicitly requires integration.

Every class follows block__element--modifier (a block alone is valid). Access modules with styles['block__element']; combine base and modifier explicitly. No utility naming, styling IDs, inline static styles or !important. Use semantic tokens. Extract a component when it is reused or has clear independent behavior, not to create a library prematurely.

Russian product copy; English code, documentation and commit descriptions. Use semantic landmarks, one h1, ordered headings, explicit labels, visible focus and truthful loading/error states. Do not imply accounts are connected, safety has been assessed or bank operations performed when they have not.

Run lint, typecheck, production build and Playwright before committing. Test user behavior through roles and stable labels, responsive layouts, overflow, keyboard operation and real links. Review screenshots at 390/768/1024/1440px. Ignore generated artifacts and secrets; version npm package-lock.json. Explicit staging only.
