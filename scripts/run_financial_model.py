"""Run from repository root:

    python -m scripts.run_financial_model --config configs/financial_assumptions.json \
        --output-dir reports/finance

Writes financial_scenarios.csv, sensitivity.csv, break_even.md,
model_assumptions.md, missing_inputs.md and pitch_one_minute.md. Every artifact
carries the disclaimers; the base case is printed even when it is negative.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.finance import FinancialModelError, DISCLAIMERS, load_assumptions, write_reports  # noqa: E402

DEFAULT_CONFIG = Path('configs/financial_assumptions.json')
DEFAULT_OUTPUT = Path('reports/finance')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        assumptions = load_assumptions(args.config)
    except FinancialModelError as exc:
        print(f'Financial model rejected: {exc}', file=sys.stderr)
        return 2
    written = write_reports(assumptions, args.output_dir)
    summary = {
        'artifacts': sorted(written),
        'disclaimers': DISCLAIMERS,
        'status': 'MODELLED_ESTIMATE_NOT_MEASURED_ROI',
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())