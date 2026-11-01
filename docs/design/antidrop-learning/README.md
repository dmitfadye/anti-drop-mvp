# AntiDrop Scenario Learning

Implemented on `feat/scenario-learning`, starting from `c5db44e`. The existing banking shell, seven original topics, backend persistence, authentication and reward contracts are preserved. A new eighth topic, «Звонок под давлением», adds six practice scenarios and one independent final question.

Follow-up: [thematic cards for all eight topics and encoding repair](THEMES.md). Four more generated illustrations now complement phone/shield art; all questions use themed cards. Content integrity guards prevent question-mark corruption from being shown as valid teaching material.

## Visual evidence

Three built-in ImageGen reference boards: [iOS Learning](concept-1-ios.png), [Swipe Cards](concept-2-swipe.png), [Scenario Simulator](concept-3-simulator.png). Each includes desktop/mobile and correct/incorrect/result states. The selected direction combines simulator context with calm iOS controls; see [DESIGN.md](DESIGN.md). These generated images are references, not screenshots of implemented software.

Actual production-app captures, using the real FastAPI/PostgreSQL QA stack:

- [Desktop catalog](screenshots/catalog-1440.png), [scenario](screenshots/idle-1440.png), [incorrect answer](screenshots/incorrect-1440.png), [correct answer](screenshots/correct-1440.png), [result](screenshots/result-1440.png).
- [Mobile catalog](screenshots/catalog-390.png), [scenario](screenshots/idle-390.png), [restored session](screenshots/resumed-390.png), [result](screenshots/result-390.png).
- The same eight states are captured at 390, 768, 1024 and 1440 px: catalog, intro, idle, selected, incorrect, correct, resumed and result. There are 32 screenshots. Baseline files are historical: the original production build was stale compared with source, which is why it displayed the older linear onboarding screen.

## Implementation

- `frontend/components/Learning.tsx`: catalog, formats, pause/resume, practice/final workflow, results, local attempt history and mistakes review.
- `ScenarioCard.tsx`: situation, native radio choices, server feedback, source links and feedback focus.
- `learning-session.ts`: versioned local draft and bounded local history (20 attempts), validation of restored values.
- `learning-api.ts`: public types and actionable errors.
- `src/learning.py`: stateless `POST /api/v1/learning/practice`, version checks, replay before current-content lookup, independent assessment gate.
- `data/learning/course.json`: single runtime content source. Sources and editorial limits: [CONTENT.md](CONTENT.md).
- Next.js and matching ESLint configuration patched from 16.4.0 to 16.4.3 after npm audit identified upstream vulnerabilities. No new UI/state library was added.
- `frontend/public/images/learning/scenario-phone.png` and `safety-shield.png`: built-in ImageGen assets derived from the selected references, subsequently requested explicitly by the user. They are actually rendered through Next Image, not replaced by CSS icons. The phone screen text remains accessible live HTML. Exact asset prompts are recorded in DESIGN.md.

Practice accepts `{module_id, question_id, answer, course_version}` and only checks `cards`; it returns feedback without XP or persistence. Quiz keys are not exposed by this endpoint. Completion still validates the complete answer set on the server and atomically records progress and replay. `course_version` is optional for legacy callers; new UI always supplies it. Old idempotent replies survive later catalog edits.

For modules with `assessment_independent: true`, lesson success depends on at least 80% correct **quiz** answers, not the combined practice score. Thus six correct practice answers cannot compensate for a wrong final answer in the new topic. Passing article mode still means acquaintance with the topic, not independent assessment; UI makes this distinction explicit.

## Adding a scenario

Add a module or card to `data/learning/course.json` instead of copying pages. Keep IDs stable and unique within a module. Cards use `id`, `prompt`, `options`, integer `correct`, `explanation`; scenarios additionally use `scenario_type`, `scenario_text`, `learning_goal`, `danger_sign`, `safe_action`, `difficulty`, verified `source_url` and `content_version`. Public catalog omits answer keys, explanations and danger/safe-action hints. Add independent final situations under `quiz`. Bump catalog and content versions when wording or scoring changes. Mark unverified claims `source_needed: true`.

## Storage and limits

The draft key is `antidrop-learning-session-v1`; attempt history is `antidrop-learning-attempts-v1`. They contain no credentials. The draft preserves format, module, step, answers, feedback display cache and the idempotency key, including retry after a failed submission and F5. Incompatible drafts are not applied. A denied storage API leaves the in-memory workflow usable with a visible warning. Only server-confirmed results affect XP.

Drafts/history are browser-local, not cross-device. Feedback in browser storage is only a display cache, never a trusted grading input. Server progress still belongs to one shared synthetic demo profile. Review awards no additional XP. Current practice reviews repeat the mistaken card; independent final assessment can be retaken separately. New paraphrased review items, scheduled repetition and personalized identity remain future work. Keyboard focus and automated accessibility checks passed for implemented paths; a full assistive-technology/WCAG audit is not claimed.

## Verification

Standard commands from the repository README remain valid: `npm run lint`, `npm run typecheck`, `npm run build`, `npm run test:e2e`; backend `pytest -q` with a dedicated disposable `TEST_DATABASE_URL`. Never run PostgreSQL regression tests against shared/user data. Playwright starts production Next on 3001; set `APP_ORIGIN=http://127.0.0.1:3001` for that process.

This session used a new isolated PostgreSQL container on loopback 5544 with tmpfs and random credentials in ignored `.local/learning2-env.json`, plus native backend8010 and frontend3000. Existing database volumes/configuration were not changed. The QA database is deliberately ephemeral; it is not the normal persistence deployment. Root Compose remains the normal durable deployment path.

Latest results after the encoding/theme follow-up: backend **218 passed +174 subtests**, no PostgreSQL skips; frontend lint/types/production build passed; **65 Playwright tests passed**. Real scenario walkthrough at all four widths verified F5 restoration, successful final result, exact idempotent replay, saved completion after reload, mistakes review, readable cards 4/5 and text inside the phone. All eight actual API quiz views were also checked at all four widths (32 view checks), with no horizontal overflow, damaged text or page exceptions. Production `npm audit --omit=dev` reported **0 vulnerabilities** after the dependency patch. Development dependency audit is not clean; no forced unrelated dependency changes were applied. Starlette/httpx deprecation and existing Next standalone-start warning remain.

The follow-up used two bounded GPT-6.1 Sol/medium agents for backend/content repair and frontend regression review; the coordinator implemented the shared thematic UI and generated assets. Tests do not establish that every possible defect or accessibility issue is absent.

The original Playwright catalog expectation was updated from seven modules to the exact eight module IDs; answer secrecy and credential checks remain intact. Added scenario tests cover practice gating/focus, reload/retry UUID, independent pass/fail, review, incompatible drafts, denied storage, 503 recovery, stale GET race and removed modules.
