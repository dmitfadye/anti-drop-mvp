#!/usr/bin/env bash
# One-shot ML/финансовая оценка для docker compose service `eval`.
# Та же последовательность, что `make eval` + `make finance`.
# Только синтетика, пишет артефакты в reports/ (смонтирован из корня репозитория).
set -euo pipefail

python -m anti_drop_ml.evaluation.runner \
  --dataset fixtures/episodes/all_episodes_p1.jsonl \
  --output-dir reports/evaluation \
  --cost-false-alert 650 --cost-missed-risk 45000 --prevalence 0.002

python -m scripts.run_financial_model \
  --config configs/financial_assumptions.json \
  --output-dir reports/finance

echo "OK: reports/evaluation/report.md, reports/finance/financial_scenarios.csv"
