# Сохранение полезных возможностей P1

Источники: `origin/zima` `19162eca333bfc05ddfbfe642675b87a53076d47`; исправление event sink из `origin/master` `f6c6c7c80558f9c451ef0307a62c430dbf0c8456`. Интеграция сохраняет текущие строгие backend contracts, Decimal, PostgreSQL, server-side sandbox identity и утверждённый frontend.

Сохранены: локализация RU/UZ с честными draft badges и fallback, шаблоны предупреждений, воспроизводимое распределение synthetic language experiments, exploratory analysis/blinding, финансовая модель с неподтверждёнными допущениями, optional advisory без банковских действий и P1 quality evaluation на 81 synthetic episodes. Исходные P0 fixtures не заменены; P1 dataset — `fixtures/episodes/all_episodes_p1.jsonl`.

API подключается через `src.p1.router`. Communication evaluate и advisory требуют configured sandbox bearer identity и совпадения subject. Язык не влияет на score. Client events требуют identity и принадлежащий ей сохранённый evaluation. Недоступная запись event sink даёт 503. Case-linked event schema старого P1 не совместима с PostgreSQL UUID case IDs: такие события отвергаются 422. JSONL events не являются банковским аудитом, не обеспечивают идемпотентность и не заменяют PostgreSQL case events. Response явно сообщает `idempotency_supported: false`.

Optional capabilities задаются `ANTI_DROP_DEMO_MODE`, `ANTI_DROP_LOCALIZATION_ENABLED`, `ANTI_DROP_EXPERIMENT_ENABLED`, `ANTI_DROP_EXPERIMENT_ALLOW_DRAFT_TREATMENT`, `ANTI_DROP_ADVISORY_ENABLED`, `ANTI_DROP_OPERATOR_LOG` и experiment/localization settings из `src/flags.py`. Events sink по умолчанию выключен. Advisory/experiment по умолчанию выключены. Draft translations нельзя представлять как проверенные носителем или банком.

## Evaluation и исправленный holdout

```powershell
python -m anti_drop_ml.evaluation.runner --dataset fixtures/episodes/all_episodes_p1.jsonl --output-dir .local/p1-evaluation
python -m scripts.run_financial_model --config configs/financial_assumptions.json --output-dir .local/finance
python -m scripts.validate_localization
python -m unittest tests.test_p1_unified tests.test_templates tests.test_localization tests.test_financial_model tests.test_experiment_assignment tests.test_blinding_export tests.test_event_schema_pii -v
```

Primary metrics относятся только к normal/risk/legitimate-negative; edge/missing-data — отдельные boundary checks. Все shipped labels — synthetic placeholders, банковская accuracy не подтверждена. Составные subject groups теперь целиком попадают в одну сторону hash split. Исправлена утечка repeated-subject episodes из исходного holdout; manifest больше не заявляет глобальную временную независимость.

**Rule ablation: NOT RUN.** Текущий detector не предоставляет поддержанный offline disabled-rule contract. Runner сохраняет threshold/co-occurrence/legitimate-negative/cost reports и явно записывает этот пробел в manifest/warnings; `rule_ablation.csv` не создаётся. Вычитание score contribution не выдаётся за повторный запуск выключенного правила. Исторические reports P1 нельзя представлять как результаты нового detector.

## Отложенная адаптация operator

Operator state machine, redaction и UI/API сохранены в исходных refs, но unsafe runtime не переносится: старый `src/cases.py` использует память/JSONL, operator разрешает synthetic loopback без auth. Для сохранения полноценного operator flow нужны authenticated PostgreSQL adapter, новая Alembic revision, расширение case status constraint/response и transactional idempotency tests. Это явное отложенное ограничение, а не заявление, что возможность уже реализована или не представляла ценности. Legacy storage/auth не восстановлены.

## Фактическая проверка

Windows, Python 3.12.10; использовано существующее backend venv, поэтому это не проверка clean installation. Targeted pure suites: 89 tests PASS. Новые integration regressions: 5 tests PASS. Evaluation CLI: 81 episodes, 56 primary, PASS. `unittest discover -s tests -v`: 156 tests PASS на момент записи; PostgreSQL pytest functions не входят в unittest discovery и проверяются отдельно оркестратором. Наблюдались Starlette httpx deprecation и ResourceWarning socket в общем suite; отсутствие утечек не заявляется.
