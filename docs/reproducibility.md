# Reproducibility

A claim is only as good as the command that regenerates it. This file lists
those commands and the versions they record.

## Golden rule

Every report records: `dataset_version`, `rule_version`, `threshold_version`,
`template_version`, `experiment_id`, `code_commit`, `python_version`, package
versions, `random_seed`, `generated_at`, and SHA-256 hashes of inputs and
outputs. A report without those fields is not evidence.

## Full regeneration from a clean clone

```bash
python -m venv app/.venv && app/.venv/bin/pip install -r app/requirements-lock.txt
export PYTHONPATH=app   # Python code lives in app/, run from repo root

# 1. fixtures — deterministic, fixed seed, no randomness at import time
python -m scripts.generate_synthetic_fixtures --output-dir app/fixtures/episodes

# 2. evaluation pack
python -m anti_drop_ml.evaluation.runner \
  --dataset app/fixtures/episodes/all_episodes_p1.jsonl \
  --output-dir reports/evaluation \
  --cost-false-alert 650 --cost-missed-risk 45000 --prevalence 0.002

# 3. financial model
python -m scripts.run_financial_model \
  --config app/configs/financial_assumptions.json --output-dir reports/finance

# 4. blinded scoring template (empty by design)
python -m scripts.export_blinded_scoring --experiment-id exp-warning-language-2026.10

# 5. stop criteria gate
python -m scripts.validate_stop_criteria --config app/configs/pilot_stop_criteria.json

# 6. tests
python -m unittest discover -s app/tests -t app -v
```

`scripts/ci_smoke.sh` runs exactly this sequence.

## What is deterministic

| Artefact | Guarantee |
|---|---|
| fixtures | byte-identical on rerun; `provenance.json` records `random_seed: 20261008` |
| `evaluation_id` | SHA-256 over the canonical snapshot + rule + threshold + adapter version; metadata, ordering and input timezone do not change it |
| decision | pure function of the snapshot; no clock, no randomness |
| assignment | `sha256(salt|experiment_id|subject) % 100`; no state store |
| holdout split | hash-based; identical on any machine |
| blinding map | hash-based; stable across runs |
| financial model | pure arithmetic; no sampling |

## What is not deterministic, and why

| Field | Why |
|---|---|
| `generated_at`, `timestamp` | wall clock; the point of the manifest |
| `git_worktree_dirty` | changes as soon as you edit anything |
| `file_hashes` over output reports | depend on the timestamp above |
| `python_version`, package versions | environment |

Everything else should be byte-identical given the same inputs. If a metric
changes, the cause is an input, the code, or a genuine bug — not the clock.

## Environment

| Component | Version |
|---|---|
| Python | `>=3.10`, CI on 3.12 |
| FastAPI | `>=0.115` |
| Pydantic | `>=2.0` (v2 required) |
| httpx | `>=0.27` (TestClient) |
| tzdata | required on Windows for `zoneinfo` |

`anti_drop_ml/evaluation/quality.py::environment_fingerprint` records the actual
versions of each into `evaluation_manifest.json`.

## One supported server path

`uvicorn main:app` with FastAPI. `app_stdlib.py` is a legacy diagnostic from P0
and is not on the deploy path; CI does not smoke it. Do not deploy both.

## Reruns and diffs

```bash
python -m anti_drop_ml.evaluation.runner --dataset ... --output-dir /tmp/run-a
python -m anti_drop_ml.evaluation.runner --dataset ... --output-dir /tmp/run-b
diff <(jq 'del(.timestamp, .environment, .git_worktree_dirty)' /tmp/run-a/metrics.json) \
     <(jq 'del(.timestamp, .environment, .git_worktree_dirty)' /tmp/run-b/metrics.json)
```

An empty diff means the pipeline is reproducible.

## What a report is not

- synthetic labels are not validated accuracy;
- a holdout split here is bookkeeping, not a trained-model holdout;
- `ready_to_start: false` is the honest state of the pilot plan;
- the financial base case is modelled from assumptions, not measured.

The scripts print those states rather than hiding them, and
`reports/evaluation/warnings.md` restates them in prose.