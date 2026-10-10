# P1 communication layer — what was added and how to run it

One paragraph: P0 made the detector honest, measurable and testable. P1 adds the
things a jury asks for *around* the detector — legitimate negatives, a real
localization workflow, an operator trace, experiment instrumentation,
accessibility, an honest financial model and a stop plan — without adding a
model, a broker or a database.

**Nothing in P1 performs a banking action.** No transfer is blocked, no money is
frozen, no OTP is used, no support is contacted. Every new surface is labelled
synthetic / sandbox / demo.

## Blocks

| Block | Status | Entry point |
|---|---|---|
| P1-MUST 1 legitimate negatives + edge fixtures | done | `scripts/generate_synthetic_fixtures.py`, `fixtures/episodes/*` |
| P1-MUST 2 quality evidence pack | done | `anti_drop_ml/evaluation/{runner,quality,holdout}.py` |
| P1-MUST 3 localization RU + one target locale | done | `src/localization.py`, `src/templates.py`, `locales/`, `templates/` |
| P1-MUST 4 accessibility + RTL | done | `static/css/app.css`, `static/js/app.js`, `static/operator.html` |
| P1-MUST 5 operator sandbox | done | `src/operator.py`, `src/cases.py`, `static/operator.html` |
| P1-MUST 6 experiment instrumentation | done | `src/experiments.py`, `scripts/*experiment*.py` |
| P1-SHOULD 1 discovery artifacts | templates only | `docs/{discovery_interview_guide,jtbd_canvas,alternatives_map,hypothesis_tracker,evidence_ledger}.md` |
| P1-SHOULD 2 financial model | done | `src/finance.py`, `configs/financial_assumptions.json` |
| P1-SHOULD 3 stop criteria + pilot protocol | done | `configs/pilot_stop_criteria.json`, `scripts/validate_stop_criteria.py` |
| P1-SHOULD 4 CI + container | done | `.github/workflows/ci.yml`, `deploy/Dockerfile`, `Makefile` |
| P1-OPTIONAL pre-transfer advisory | done, advisory only | `src/advisory.py` |

## Feature flags

Safe default: demo/synthetic only. Operator, experiment and advisory are off
until you ask for them. `GET /api/health` echoes the resolved state.

| Variable | Default | Effect |
|---|---|---|
| `ANTI_DROP_DEMO_MODE` | `true` | master switch for all sandbox surfaces |
| `ANTI_DROP_LOCALIZATION_ENABLED` | `true` | locale catalog and template rendering |
| `ANTI_DROP_OPERATOR_UI_ENABLED` | `false` | `/operator` page and `/api/operator/*` |
| `ANTI_DROP_OPERATOR_EXPORT_ENABLED` | `false` | `/api/operator/export` (pseudonymous) |
| `ANTI_DROP_EXPERIMENT_ENABLED` | `false` | deterministic arm assignment |
| `ANTI_DROP_EXPERIMENT_ALLOW_DRAFT_TREATMENT` | `false` | lets the demo use a not-yet-approved translation |
| `ANTI_DROP_EXPERIMENT_TREATMENT_PERCENT` | `50` | treatment share |
| `ANTI_DROP_ADVISORY_ENABLED` | `false` | `/api/v1/risk/advisory` (advisory, never a block) |
| `ANTI_DROP_OPERATOR_LOG` | *(unset)* | local JSON-lines event sink |
| `ANTI_DROP_TARGET_LOCALE` | `uz-UZ` | target language of the experiment |

The operator surface additionally requires a loopback client address. Behind a
reverse proxy that check cannot be trusted, which is why the UI and the API both
say "local demo only, no authentication".

## Commands

```bash
# tests (no network, no real data)
python -m unittest discover -s tests -v

# fixtures (deterministic, fixed seed)
python -m scripts.generate_synthetic_fixtures --output-dir fixtures/episodes

# evaluation pack
python -m anti_drop_ml.evaluation.runner \
  --dataset fixtures/episodes/all_episodes_p1.jsonl \
  --output-dir reports/evaluation \
  --cost-false-alert 650 --cost-missed-risk 45000 --prevalence 0.002

# financial model
python -m scripts.run_financial_model \
  --config configs/financial_assumptions.json --output-dir reports/finance

# experiment assignment (deterministic hash)
python -m scripts.run_experiment_assignment \
  --subjects <file with one sub_ ref per line> \
  --output reports/experiment/assignments.jsonl

# blinded scoring template + blinding map
python -m scripts.export_blinded_scoring --experiment-id exp-warning-language-2026.10

# unblind and analyse collected data
python -m scripts.analyze_experiment \
  --scored reports/experiment/collected.csv \
  --blinding-map reports/experiment/blinding_map.json \
  --declared-powered-n 400 --output-dir reports/experiment

# stop criteria gate
python -m scripts.validate_stop_criteria --config configs/pilot_stop_criteria.json

# server
uvicorn main:app --host 127.0.0.1 --port 8000
```

`make help` lists the same steps as targets (`make test`, `make eval`,
`make finance`, `make operator`, `make docker-build`).

## Integration points with P0

| P1 module | P0 module it reuses | What changed in P0 |
|---|---|---|
| `src/localization.py` | `anti_drop_ml/contracts.py` (`ClosedModel`) | none |
| `src/templates.py` | `src/alerts.py` (`TEMPLATE_VERSION` only) | none — P0 alerts stay for the legacy `/api/analyze` |
| `src/experiments.py` | `anti_drop_ml/{events,metrics,power}.py` | `events.py` event/outcome allowlists widened, `power` unchanged |
| `src/operator.py`, `src/cases.py` | `src/cases.py` P0 store | operator cases added **to the same store**; no second database |
| `src/advisory.py` | `anti_drop_ml/{adapter,contracts}.py` | `adapter.evaluate_snapshot` gained an optional `disabled_rules` pass-through |
| `anti_drop_ml/evaluation/*` | `runner.py`, `metrics.py` | `runner.py` rewritten to add artifacts; `metrics.py` untouched |
| `src/detector.py` | — | new optional `disabled_rules` parameter for ablation; default behaviour identical |

`app_stdlib.py` remains a legacy diagnostic only. It is not on the FastAPI path
and is not exercised by the CI deploy smoke.

## Integration points in `main.py` / `models.py`

`main.py` gained, in order:

1. `app.include_router(communication_router)` and `app.include_router(operator_router)`
   — both self-guarding, no extra wiring needed;
2. `GET /api/locales` — honest locale catalog;
3. `POST /api/v1/risk/advisory` — advisory-only, flag-gated;
4. `GET /operator` — static sandbox dashboard, flag- and loopback-gated;
5. `/api/health` now reports `p1_features` and the standing limitations.

`models.py` changed in one place only: `_normalize_ts` accepts a trailing `Z`
so the project really runs on its declared minimum Python (3.10). No schema
shape changed, so existing clients keep working.

## What P1 does not do

No LLM, RAG, vector DB, ML training, feature store or model registry. No Kafka,
Redis, ClickHouse, Kubernetes or microservices. No frontend framework rewrite. No
real SMS, OTP, payments, blocks, cashback or support. No raw PII. No language,
citizenship or ethnicity as a risk factor. No score presented as a probability.
No claim of a validated accuracy, an approved translation, a powered experiment
or a proven ROI.

See `docs/limitations.md` for the full list and `reports/evaluation/warnings.md`
for what this particular run measured.