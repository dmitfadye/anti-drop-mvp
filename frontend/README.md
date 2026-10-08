# Anti-Drop frontend foundation

Stage 1 only: an independent Russian-language workspace, overview, honest empty state and native disclosure. No bank connection, financial analysis, authentication or fake customer data. Legacy FastAPI and static UI remain unchanged on port 8000.

Requires Node >=20.9 and npm. Run from this directory:

```sh
npm ci
npm run dev
```

Open http://127.0.0.1:3000. Production: `npm run build`, then `npm start`.

Validation: `npm run lint`, `npm run typecheck`, `npm run build`, `npm run test:e2e`. Tests launch the production server on 3001 and use installed Microsoft Edge; install Edge or change the Playwright channel to your installed Chromium browser. Generated screenshots are in ignored `test-results/`. No environment variables are required.

See docs for research, design rules, font permissions and the approval workflow for future screens.
