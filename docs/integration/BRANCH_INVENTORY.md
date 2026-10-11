# Инвентаризация веток AntiDrop

Дата проверки: 11 октября 2026, Europe/Moscow. Статус: discovery; интеграция и удаление веток не выполнены.

## Область и доказательства

`D:\FintechPSD\anti-drop-mvp` и `D:\FintechPSD\anti-drop-backend` — связанные worktree одного Git repository (`anti-drop-mvp/.git`), а не независимые клоны. Оба tracked/untracked short status были пустыми до записи этого отчёта. Ignored: локальные `.venv`, `.local`, caches, frontend/node_modules, .next и test-results; их наличие не доказывает воспроизводимость чистой установки. Содержимое секретных env-файлов не выводилось.

Выполнены `git fetch origin` без prune, `git ls-remote --symref origin HEAD`, `git ls-remote --heads --tags origin`, `git worktree list --porcelain`, `git log --all --graph`, `git merge-base`, `git rev-list --left-right --count`, `git cherry` и файловые сравнения. GitHub connector подтвердил default `master`, публичность и push permission текущего подключения. `gh` отсутствует. GitHub REST дал четыре remote branches, все `protected: false`, пустые releases/tags/open PR и `actions/workflows.total_count=0`. Детальный endpoint protection вернул HTTP 401: rulesets/required checks не подтверждены, отсутствие protection flag не заменяет admin-аудит.

Полный список обнаруженных branch refs приведён ниже. `origin/HEAD` — alias `origin/master`, не самостоятельная ветка. PR search вернул три PR; все проверены отдельно. Единственный обнаруженный fork из PR — `filipp880/anti-drop-mvp`, его `master` проверен через ls-remote и совпадает с merged PR #3. Другие неизвестные/private forks не объявляются проверенными.

## Сравнение с актуальным remote default

База счётчиков — `origin/master` `f6c6c7c80558f9c451ef0307a62c430dbf0c8456`. «Уникальные» — commits справа в `origin/master...ref`; это ancestry, не доказательство сохранённого поведения. `git cherry` дополнительно подтвердил отсутствие patch-equivalent commits для четырёх frontend commits и двух backend commits. В таблице SHA сокращены для чтения; полные tips далее.

| Ветка/reference | Tip | Merge-base | Только default / только ref | Изменения и ценность | Конфликт / рекомендация |
|---|---|---|---:|---|---|
| local `master` | 565c720 | 565c720 | 30 / 0 | Исходный MVP; вся история достижима из default | `ALREADY MERGED`; local устарела, удаление не разрешено |
| `origin/master` | f6c6c7c | f6c6c7c | 0 / 0 | P1, sandbox SQLite/PG, Compose, users/SIM, layout app/ | `KEEP`; текущий default; не брать целиком без устранения рисков |
| local `frontend-test-brach` | 8bdec6c | e1b8f37 | 21 / 4 | Четыре commits утверждённого Next.js shell/screens/fonts/Playwright | `INTEGRATE`; предлагаемая база; default содержит более старый frontend |
| `origin/frontend-test-brach` | 8bdec6c | e1b8f37 | 21 / 4 | Совпадает с local frontend | `INTEGRATE`; один источник, не двойная интеграция |
| local `backend-antidrop-postgres` | 0fb475f | e1b8f37 | 21 / 2 | Alembic/psycopg3, durable evaluations/cases, trusted sessions, domain fixes, tests и jury docs | `PARTIALLY INTEGRATE`; перенос backend без замещения frontend |
| `origin/zima` | 19162ec | 19162ec | 20 / 0 | P1 evaluation, fixtures, neutral localization, operator/advisory/experiments, docs | `ALREADY MERGED` в default; selective reuse quality/evidence; operator/API conflicts требуют отдельного решения |
| `origin/my-branch` | 11d78b2 | 11d78b2 | 11 / 0 | SQLite sandbox и dual PG storage, one-command Compose; P1 merge | `ALREADY MERGED`; не дублировать конкурирующее storage; useful API/error/idempotency evidence сохранить |
| fork `filipp880/anti-drop-mvp:master` | 131bc61 | 131bc61 | 1 / 0 | users/SIM persistence; также accidental venv и CI deletion | `PARTIALLY INTEGRATE` только доменный замысел, без доверия browser header; весь tip уже в default |

Полные tips:

```text
master                      565c72017c1be04e0734998b435d9db508940de9
origin/master               f6c6c7c80558f9c451ef0307a62c430dbf0c8456
frontend-test-brach          8bdec6c9b404555d9b8197ff48789f554b73faec
origin/frontend-test-brach   8bdec6c9b404555d9b8197ff48789f554b73faec
backend-antidrop-postgres    0fb475f813d547749562837f4a3d57db9b4bb715
origin/zima                 19162eca333bfc05ddfbfe642675b87a53076d47
origin/my-branch            11d78b20d4935264603e873f1851c8a537754554
filipp880:master            131bc6170a12bb648f09283ce752beaf00e30133
shared comparison base      e1b8f37b56c92ae3b7844b136819a999ea23ef48
```

## PR и история

| PR | Состояние | Head / merge SHA | Значение |
|---|---|---|---|
| [#1](https://github.com/dmitfadye/anti-drop-mvp/pull/1) | closed, merged | fc598f0 / 7853cee | Persistent SQLite cases, per-subject idempotency, error envelope; legacy cases отключены |
| [#2](https://github.com/dmitfadye/anti-drop-mvp/pull/2) | closed, merged | 09185e6 / 314990f | Dual SQLite/Postgres + P1 zima; psycopg2 lock fix и frontend support endpoint |
| [#3](https://github.com/dmitfadye/anti-drop-mvp/pull/3) | closed, merged | 131bc61 / f6c6c7c | Fork users/SIM; удаление CI и tracked virtualenv, вопреки узкому заголовку PR |

Дополнительный merge `eb8663e` включает Compose commit `11d78b2`. `9df11e2` переносит backend в `app/`, `4b6b336` исправляет demo Ref и ошибки event sink, `ab914bb` добавляет UID/GID контейнера. `131bc61` добавил **2129 tracked файлов `app/.venv310/`** и удалил 102-строчный `.github/workflows/ci.yml`. Это vendor/runtime мусор, не полезная реализация. Требуется убрать из интеграционного дерева, историю не переписывать. В default tracked только `.env.example` среди проверенных env/db/secret имён; это не полный secret scan истории.

## Источники для выборочной интеграции

1. **Frontend 8bdec6c:** `frontend/components/{AppShell,Overview,Dashboard,Transactions,Learning,Monitoring,PhoneChange,ContentScreens,DemoWorkspace,Icon}.tsx`, соответствующие CSS Modules, `education.ts`, `api.ts`, preferences/useSection, app routes, `frontend/tests`, `docs/frontend` и разрешённые font assets. Новые ranks/streak/cards расширяют эту основу.
2. **Backend 37f6b82 → 0fb475f:** `src/{database,sandbox,http_boundary}.py`, domain `{detector,alerts,quiz,sim_security,policy}.py`, `models.py`, `main.py`, `anti_drop_ml/{contracts,adapter}.py`, `migrations`, `alembic.ini`, `infra/001_runtime_role.sql`, `scripts/{migrate,init_sandbox,demo_sandbox,retention}.py`, `tests/{test_postgres,test_domain_p2,test_audit,test_detector}.py`, `compose.yaml`, Dockerfile, manifests/locks, `docs/architecture`, competition evidence. Shared contracts/manifests/Compose интегрировать последовательно.
3. **P1 19162ec:** потенциально переиспользуемые `anti_drop_ml/evaluation/{holdout,quality,runner}.py`, synthetic fixture catalogs, scripts генерации/финансовой модели, полезные methodology/localization docs. `adapter.py`, `events.py`, `event_log.py`, `src/detector.py` конфликтуют с contract/domain fixes backend; нельзя копировать весь package без reconciliation. `src/{advisory,operator,communication,experiments,flags,finance,localization,templates}.py` образуют связанную подсистему; не заявлять сохранение до явного выбора и тестов.
4. **my-branch/default:** сохранить доказанные требования case error envelope/replay/subject isolation, полезный restart smoke и Compose health/start order. Не дублировать `src/db.py` + SQLite/psycopg2 рядом с Alembic/psycopg3. SIM users из `5e2b2ba` требуют адаптации к trusted server identity и synthetic phone boundary; browser `X-Sandbox-Subject` не является auth.

## Локальный patch

`D:\FintechPSD\anti-drop-ml-p0.patch`: 198499 bytes, LastWriteTime 8 октября 2026 16:13:07 (host display). Это deterministic P0 contracts/evaluation/fixtures/docs/tests, не обученная ML pipeline. Read-only `git apply --reverse --check` на текущем frontend worktree завершился **exit 0**: все изменения patch уже присутствуют в рабочем дереве. Patch не применялся, отдельной уникальной интеграции не требует. Полезный P0 уже в общем предке e1b8f37 и истории default.

## Предлагаемый порядок и ограничения

Checkpoint A: создать отдельную `integration/antidrop-unified` от frontend 8bdec6c; последовательно перенести backend domain/contracts, Alembic/DB/session, Compose и тесты; затем совместимые P1 quality modules и обучение. Существующие worktrees/ветки/patch сохранить. Это proposal, не зарегистрированное approval.

Узкие конфликты: два storage API и auth модели; root Python против app/; legacy `/api/cases` retirement против совместимости; P1 detector/adapter против strict backend contracts; устаревший frontend default против approved shell; удалённый CI; cached virtualenv; competing lockfiles и psycopg2/3. Решения и функциональные retirements должны быть явно согласованы в плане. Для будущего merge в master понадобится отдельный review полного итогового diff: отказ от случайных venv файлов не разрешает потерю полезных P1 возможностей.

Приложение и refs, кроме разрешённого fetch, не изменялись. Recovery refs ещё не создавались; ветки не удалялись; проверки приложения в рамках Git inventory не запускались. Ни ancestry, ни closed PR не являются основанием безопасного удаления ветки.

## Generated during integration

Local feature/learning-cards (6806023), feature/learning-server (b032ae4), and integration/antidrop-unified were created after the initial inventory. Their useful changes were selectively integrated and tested; final tips are archived before branch cleanup. User subsequently authorized a sole master branch and deletion of the other local/remote branches.
