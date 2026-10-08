# AntiDrop frontend

Russian-language application implementing the approved AntiDrop screen references: overview, monitoring, how it works, protection scenarios, learning/quiz, educational phone-change wizard, knowledge base, text guides, examples, settings and FAQ support. One visible screen at a time, with the existing hash links retained.

No bank connection or real financial operations. Legacy FastAPI and static UI remain unchanged on port 8000. Analysis, multilingual warnings, educational content, quiz checking and phone simulation use the existing API.

Requires Node >=20.9 and npm. From this directory:

```sh
npm ci
npm run dev
```

Open http://127.0.0.1:3000. Production: `npm run build`, then `npm start`. Start the existing backend from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Next proxies /api/* to the backend. Optional server-only BACKEND_URL overrides it (set before build).

Validation: `npm run lint`, `npm run typecheck`, `npm run build`, `npm run test:e2e`. E2E tests require the existing backend on 8000, launch production frontend on 3001 and use installed Microsoft Edge. Screenshots are saved in ignored `test-results/screens/` for all eleven screens at 390, 768, 1024, 1440 and 1728px widths.

Local Asket fonts are included; Halvar and normal-width Asket Light/Regular are missing. Original 3D illustrations have not been supplied. See ../docs/frontend/ for visual specification, component map, font mapping, QA and known differences. The result is not claimed pixel-perfect.
