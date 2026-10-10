# Анти-Дроп P1 — команды проекта.
# Один поддерживаемый серверный путь: FastAPI (uvicorn main:app).
# app_stdlib.py — legacy диагностика, в deploy-путь не входит.

# Python-код живёт в app/ (импорты main/src/anti_drop_ml/scripts), запуск из корня.
# PYRUN добавляет app/ в sys.path; относительные пути данных — от корня.
PYTHON ?= python
PYRUN = PYTHONPATH=app $(PYTHON)
HOST ?= 127.0.0.1
PORT ?= 8000
DATASET ?= app/fixtures/episodes/all_episodes_p1.jsonl
EVAL_DIR ?= reports/evaluation
FINANCE_DIR ?= reports/finance
FINANCE_CONFIG ?= app/configs/financial_assumptions.json

.DEFAULT_GOAL := help
.PHONY: help install test eval fixtures finance experiment stop-criteria demo operator \
        docker-build docker-run clean-reports clean-local lint ci

help: ## Показать доступные цели
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Установить зависимости
	$(PYTHON) -m pip install -r app/requirements.txt

test: ## Прогнать все тесты (без сети, без реальных данных)
	$(PYTHON) -m unittest discover -s app/tests -t app -v

fixtures: ## Перегенерировать синтетические fixtures (детерминированно, fixed seed)
	$(PYRUN) -m scripts.generate_synthetic_fixtures --output-dir app/fixtures/episodes

eval: ## Полный evaluation pack P1
	$(PYRUN) -m anti_drop_ml.evaluation.runner \
		--dataset $(DATASET) --output-dir $(EVAL_DIR) \
		--cost-false-alert 650 --cost-missed-risk 45000 --prevalence 0.002

finance: ## Финансовая модель (conservative/base/optimistic + sensitivity + break-even)
	$(PYRUN) -m scripts.run_financial_model --config $(FINANCE_CONFIG) --output-dir $(FINANCE_DIR)

experiment: ## Шаблон blinded scoring + карта раскрытия (без данных)
	$(PYRUN) -m scripts.export_blinded_scoring --experiment-id exp-warning-language-2026.10

stop-criteria: ## Проверить план остановки пилота
	$(PYRUN) -m scripts.validate_stop_criteria --config app/configs/pilot_stop_criteria.json

demo: ## Запустить локальный демо (FastAPI, только синтетика)
	$(PYRUN) -m uvicorn main:app --host $(HOST) --port $(PORT)

operator: ## Запустить демо с включённым экраном оператора
	ANTI_DROP_DEMO_MODE=true \
	ANTI_DROP_OPERATOR_UI_ENABLED=true \
	ANTI_DROP_OPERATOR_EXPORT_ENABLED=true \
	ANTI_DROP_OPERATOR_LOG=.local/operator_events.jsonl \
	$(PYRUN) -m uvicorn main:app --host $(HOST) --port $(PORT)

lint: ## Линт/типизация, если настроены в проекте
	@if command -v ruff >/dev/null 2>&1; then ruff check app/src app/anti_drop_ml app/scripts app/tests; \
	elif $(PYTHON) -c "import mypy" >/dev/null 2>&1; then $(PYTHON) -m mypy app/src app/anti_drop_ml; \
	else echo "ruff/mypy не установлены — пропускаю (проект не требует отдельного линтера)."; fi

ci: ## Локальный эквивалент CI
	./app/scripts/ci_smoke.sh

docker-build: ## Собрать образ демонстратора (non-root)
	docker build -f deploy/Dockerfile -t anti-drop-p1:demo .

docker-run: ## Запустить контейнер на 127.0.0.1:8000
	docker run --rm -p 127.0.0.1:8000:8000 anti-drop-p1:demo

clean-reports: ## Удалить сгенерированные отчёты
	rm -rf $(EVAL_DIR) $(FINANCE_DIR) reports/experiment

clean-local: ## Удалить локальные артефакты (логи, sqlite-демо, кеш)
	rm -rf .local .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +