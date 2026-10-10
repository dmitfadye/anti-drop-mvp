# Anti-Drop frontend foundation

Independent Russian-language workspace with the legacy MVP scenarios restyled: synthetic-transaction monitoring, multilingual risk alerts, educational stories/quiz and phone-change simulation. No bank connection or real financial operations. Legacy FastAPI and static UI remain unchanged on port 8000.

Requires Node >=20.9 and npm. Run from this directory:

```sh
npm ci
npm run dev
```

Open http://127.0.0.1:3000. Production: `npm run build`, then `npm start`. Start the existing FastAPI backend on 127.0.0.1:8000 before using the scenarios. Next proxies /api/* to that backend; optional server-only BACKEND_URL can override the destination (set before build). No browser CORS configuration is needed.

Validation: `npm run lint`, `npm run typecheck`, `npm run build`, `npm run test:e2e`. Tests require the existing backend on 8000, launch the production frontend on 3001 and use installed Microsoft Edge; install Edge or change the Playwright channel to your installed Chromium browser. Generated screenshots are in ignored `test-results/`. No environment variables are required for the default local setup.

See docs for research, design rules, font permissions and the approval workflow for future screens.
