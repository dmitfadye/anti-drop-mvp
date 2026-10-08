# CI guide

## What runs

`.github/workflows/ci.yml`, on every push and pull request:

1. checkout;
2. set up Python 3.12;
3. install from the frozen lockfile;
4. lint / typecheck — only if the project has them configured;
5. unit and contract tests;
6. evaluation smoke on the small synthetic fixture set;
7. financial model smoke;
8. stop-criteria validation;
9. upload `reports/evaluation`, `reports/finance`, `reports/experiment`.

No step needs the internet at runtime beyond package installation. No step uses
real data. No step needs credentials.

## What CI deliberately does not do

- **No** Kubernetes, Helm, or cloud deploy. This is a demonstrator.
- **No** dependency audit as a blocking gate. A blocking gate with no owner and
  no remediation path is theatre. If the team adds one, it needs a policy.
- **No** e2e browser run in CI. Playwright tests live under `frontend/` and are
  run manually; adding browsers to CI doubles the run time for a demo.
- **No** secret scanning setup beyond what the platform provides.

## Local equivalent

```bash
make ci          # or: ./scripts/ci_smoke.sh
```

`scripts/ci_smoke.sh` is the same sequence with no CI-specific assumptions, and it
runs on Windows through Git Bash as well as on Linux.

## Artifacts worth reading first

| Artefact | Question it answers |
|---|---|
| `reports/evaluation/report.md` | what does the detector do and where does it fail |
| `reports/evaluation/warnings.md` | what may I not claim |
| `reports/evaluation/rule_ablation.csv` | which rule did the work |
| `reports/evaluation/legitimate_negative_report.md` | does it accuse honest clients |
| `reports/evaluation/holdout_manifest.json` | is the split honest |
| `reports/finance/financial_scenarios.csv` | is the base case positive |
| `reports/finance/missing_inputs.md` | what has no evidence |
| `reports/experiment/power_analysis.md` | is the experiment powered (answer: no) |
| `reports/experiment/blinded_scoring_template.csv` | has anything been collected (answer: no) |

## A red build

A red build is information, not an obstacle. Read the failure, decide whether it
is a real defect or an over-tight assertion, and fix the right one.

Two classes of "failure" are expected and should not be suppressed:

- `validate_stop_criteria` reporting `ready_to_start: false` — that is a truthful
  answer about the pilot plan;
- the evaluation warnings listing synthetic labels — that is the whole point.

## Reproducibility in CI

The smoke run records `git_commit`, the python version, package versions and
`git_worktree_dirty`. If a metric changes between two green builds, compare the
manifests before looking anywhere else.

See `docs/reproducibility.md`.