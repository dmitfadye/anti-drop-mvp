# Существенные решения интеграции

| Конфликт | Решение и доказательство | Ограничение / проверка |
|---|---|---|
| Approved frontend против старого frontend в master/backend | Сохранён `8bdec6c`, расширяется только обучение и persistent demo flow; Onest/BEM/light shell | Исходный approved raster недоступен; Playwright/screenshots и сохранённый spec, без pixel-equivalence claim |
| Root Python против `app/` и tracked virtualenv в master | Root layout; `app/.venv310` не переносится, история сохраняется | 2129 vendor files не являются функциональным исходником; clean install/Compose |
| SQLite/psycopg2/header identity против owned PostgreSQL | `0fb475f`: psycopg3, SQLAlchemy, Alembic, server token→subject, scoped FK/locks | PG ownership, concurrency, mismatch409, rollback и restart tests |
| Legacy case API и новый durable API | Старый unscoped `/api/cases` даёт410; Next BFF использует `/sandbox/evaluations` и `/sandbox/cases` | Legacy clients обязаны перейти; интерфейс показывает только подтверждённый case ID |
| Frontend bearer и browser subject | Token хранится только сервером Next; exact API allowlist; shared demo profile явно подписан | Это локальный демо-профиль, не персональная банковская identity |
| Internal Docker hostname против browser Origin | Explicit `APP_ORIGIN`, проверка точного origin, нет доверия browser subject/auth headers | В README используется127.0.0.1; другой host/port требует env update |
| P1 detector/adapter против строгих domain fixes | Сохранён Decimal/backend adapter; P1 runner адаптирован без неподдержанного disabled-rule shim | Ablation NOT RUN; остальные quality reports воспроизводимы |
| P1 holdout repeated subjects | Split целыми subject groups; исправлен ложный subject_disjoint guard | Новый multi-episode regression, temporal independence не заявляется |
| P1 operator storage/status и текущий sandbox constraint | Unsafe runtime не активируется; источник сохранён в refs, адаптация явно отложена | Нужны auth/PostgreSQL adapter/новая migration; поддержанный case workflow остаётся registered-sandbox |
| Старые учебные призы и новая gamification | Legacy quiz compatibility сохранён; новый server-graded course из PDF, draft/source flags | 3/7/14/30 rewards virtual, category раз в заработанный месяц, no real cash/percentile |
| 14-day choice в PDF и явное требование пользователя «месяц» | Дополнительная категория после30 дней подряд | Инструкции PDF — содержание документа; текущий user request приоритетен |
| Пакеты и locks | npm/package-lock и uv/uv.lock; runtime requirements export из frozen lock | 5 связанных HIGH dev advisories без совместимого patch; runtime audit отдельно |
| Исторические font/docs claims | Onest authoritative; старые QA помечены историческими; Asket licenses сохранены | Не обещается точное соответствие отсутствующему исходному растру |

Все выбранные файлы переносились выборочно, а не автоматическим принятием newest commit. SHA источников и recovery references — BRANCH_INVENTORY.md и BRANCH_CLEANUP_PLAN.md. Изменения entrypoints/contracts/Compose проверяются совместно перед контрольной точкой B.
