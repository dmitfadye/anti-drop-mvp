#!/usr/bin/env bash
# Локальный эквивалент CI: тот же порядок, что в .github/workflows/ci.yml.
# Только синтетика. Без сети во время выполнения, без реальных данных, без секретов.
# Запуск из КОРНЯ репозитория (цель `make ci`); Python-код живёт в app/,
# поэтому модули вызываются через PYTHONPATH=app, а пути данных — от корня.
set -euo pipefail

# An explicit PYTHON wins, including a Windows path under Git Bash/MSYS.
if [ -n "${PYTHON:-}" ] && "$PYTHON" -c 'import sys' >/dev/null 2>&1; then
  PY="$PYTHON"
elif [ -x app/.venv/bin/python ] && app/.venv/bin/python -c 'import pydantic' >/dev/null 2>&1; then
  PY=app/.venv/bin/python
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import pydantic' >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1 && python -c 'import pydantic' >/dev/null 2>&1; then
  PY=python
else
  echo "No interpreter with the project dependencies found. Run 'make install' first." >&2
  exit 2
fi
PYTHON="$PY"
export PYTHONPATH="${PYTHONPATH:-}:app"

echo "==> 1/6 unit and contract tests"
"$PYTHON" -m unittest discover -s app/tests -t app -q

echo "==> 2/6 regenerate synthetic fixtures (deterministic)"
"$PYTHON" -m scripts.generate_synthetic_fixtures --output-dir app/fixtures/episodes

echo "==> 3/6 evaluation pack"
"$PYTHON" -m anti_drop_ml.evaluation.runner \
  --dataset app/fixtures/episodes/all_episodes_p1.jsonl \
  --output-dir reports/evaluation \
  --cost-false-alert 650 --cost-missed-risk 45000 --prevalence 0.002

echo "==> 4/6 financial model"
"$PYTHON" -m scripts.run_financial_model \
  --config app/configs/financial_assumptions.json --output-dir reports/finance

echo "==> 5/6 blinded scoring template (empty by design)"
"$PYTHON" -m scripts.export_blinded_scoring --experiment-id exp-warning-language-2026.10

echo "==> 6/6 pilot stop criteria gate"
"$PYTHON" -m scripts.validate_stop_criteria --config app/configs/pilot_stop_criteria.json || true

echo
echo "OK. Артефакты:"
echo "  reports/evaluation/report.md      — что делает детектор и где ошибается"
echo "  reports/evaluation/warnings.md     — что нельзя заявлять"
echo "  reports/finance/financial_scenarios.csv — экономика (база близка к нулю)"
echo "  reports/experiment/                — blinded шаблон, данных НЕТ"