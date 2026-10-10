"""Parameterised financial model. Honest arithmetic about uncertain inputs.

Design rules that keep this from becoming a pitch deck generator:
- every parameter carries a `source` and a `confidence`; `unknown` sources are
  reported as missing evidence rather than quietly treated as facts;
- RevenueUplift, Rewards and Inference are pinned to 0 unless a caller supplies
  evidence, because none exists in this repository;
- avoided-loss, customer benefit and bank loss are NOT summed together — the
  model counts one incremental prevented episode, once;
- a negative base case is printed as negative, and payback appears only when the
  annual margin is positive.

Stdlib only, no Excel, no external service.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ParameterSource = Literal['assumption', 'interview', 'bank_data', 'evaluation', 'unknown']
Confidence = Literal['low', 'medium', 'high']

PARAMETER_NAMES = (
    'n_clients', 'q_risk_episodes_per_client_year', 'delta_incremental_prevention',
    'l_bank_rubles_per_episode', 'contacts_per_client_year', 'minutes_saved_per_contact',
    'cost_per_minute_rubles', 'false_alerts_per_client_year', 'call_share_after_false_alert',
    'handling_cost_per_contact_rubles', 'k_initial_cost', 'opex_annual',
)

# Never add money we cannot attribute to this layer.
PINNED_ZERO = ('revenue_uplift', 'rewards', 'inference_cost')

SCENARIO_ORDER = ('conservative', 'base', 'optimistic')


class FinancialModelError(ValueError):
    """Invalid assumptions file or parameter set."""


@dataclass(frozen=True)
class Assumption:
    value: float
    source: ParameterSource
    confidence: Confidence
    note: str = ''

    def as_dict(self) -> dict:
        return {'value': self.value, 'source': self.source, 'confidence': self.confidence, 'note': self.note}


@dataclass(frozen=True)
class Scenario:
    name: str
    multipliers: dict[str, float] = field(default_factory=dict)


SCENARIOS: tuple[Scenario, ...] = (
    Scenario('conservative', {
        'delta_incremental_prevention': 0.5, 'l_bank_rubles_per_episode': 0.8, 'opex_annual': 1.2,
        'k_initial_cost': 1.2, 'n_clients': 0.8, 'false_alerts_per_client_year': 1.3,
    }),
    Scenario('base', {}),
    Scenario('optimistic', {
        'delta_incremental_prevention': 1.5, 'l_bank_rubles_per_episode': 1.2, 'opex_annual': 0.9,
        'k_initial_cost': 0.9, 'n_clients': 1.2, 'false_alerts_per_client_year': 0.7,
    }),
)


def load_assumptions(path: Path | str) -> dict[str, Assumption]:
    """Read configs/financial_assumptions.json into validated assumptions."""
    target = Path(path)
    try:
        raw = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise FinancialModelError(f'{target.name}: unreadable assumptions file') from exc
    if not isinstance(raw, dict) or 'parameters' not in raw or not isinstance(raw['parameters'], dict):
        raise FinancialModelError(f'{target.name}: expected an object with a "parameters" mapping')
    assumptions: dict[str, Assumption] = {}
    for name, entry in raw['parameters'].items():
        if name not in PARAMETER_NAMES and name not in PINNED_ZERO:
            raise FinancialModelError(f'{target.name}: unknown parameter {name}')
        if not isinstance(entry, dict) or 'value' not in entry or 'source' not in entry or 'confidence' not in entry:
            raise FinancialModelError(f'{target.name}: parameter {name} needs value, source and confidence')
        if entry['source'] not in ('assumption', 'interview', 'bank_data', 'evaluation', 'unknown'):
            raise FinancialModelError(f'{target.name}: parameter {name} has an unsupported source')
        if entry['confidence'] not in ('low', 'medium', 'high'):
            raise FinancialModelError(f'{target.name}: parameter {name} has an unsupported confidence')
        value = entry['value']
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value != value or value in (float('inf'), float('-inf')):
            raise FinancialModelError(f'{target.name}: parameter {name} must be a finite number')
        assumptions[name] = Assumption(float(value), entry['source'], entry['confidence'], str(entry.get('note', ''))[:300])
    missing = [name for name in PARAMETER_NAMES if name not in assumptions]
    if missing:
        raise FinancialModelError(f'{target.name}: missing required parameters: {", ".join(missing)}')
    return assumptions


def get(assumptions: dict[str, Assumption], name: str, multipliers: dict[str, float] | None = None) -> float:
    base = assumptions[name].value
    return base * (multipliers or {}).get(name, 1.0)


def compute(assumptions: dict[str, Assumption], multipliers: dict[str, float] | None = None) -> dict[str, Any]:
    """Annual margin for one parameter set. Division-by-zero paths stay None."""
    multipliers = multipliers or {}
    n_clients = get(assumptions, 'n_clients', multipliers)
    q = get(assumptions, 'q_risk_episodes_per_client_year', multipliers)
    delta = get(assumptions, 'delta_incremental_prevention', multipliers)
    l_bank = get(assumptions, 'l_bank_rubles_per_episode', multipliers)
    contacts = get(assumptions, 'contacts_per_client_year', multipliers)
    minutes_saved = get(assumptions, 'minutes_saved_per_contact', multipliers)
    cost_per_minute = get(assumptions, 'cost_per_minute_rubles', multipliers)
    false_alerts = get(assumptions, 'false_alerts_per_client_year', multipliers)
    call_share = get(assumptions, 'call_share_after_false_alert', multipliers)
    handling_cost = get(assumptions, 'handling_cost_per_contact_rubles', multipliers)
    k_initial = get(assumptions, 'k_initial_cost', multipliers)
    opex = get(assumptions, 'opex_annual', multipliers)
    revenue_uplift = get(assumptions, 'revenue_uplift', multipliers) if 'revenue_uplift' in assumptions else 0.0
    rewards = get(assumptions, 'rewards', multipliers) if 'rewards' in assumptions else 0.0
    inference = get(assumptions, 'inference_cost', multipliers) if 'inference_cost' in assumptions else 0.0

    fraud_benefit = n_clients * q * delta * l_bank
    support_benefit = n_clients * contacts * minutes_saved * cost_per_minute
    false_alert_cost = n_clients * false_alerts * call_share * handling_cost
    annual_margin = fraud_benefit + support_benefit + revenue_uplift - opex - false_alert_cost - rewards - inference
    year1_net = annual_margin - k_initial
    denominator = k_initial + opex + false_alert_cost + rewards + inference
    year1_roi = year1_net / denominator if denominator > 0 else None
    payback_months = 12 * k_initial / annual_margin if annual_margin > 0 else None
    return {
        'fraud_benefit': fraud_benefit,
        'support_benefit': support_benefit,
        'revenue_uplift': revenue_uplift,
        'false_alert_cost': false_alert_cost,
        'rewards': rewards,
        'inference_cost': inference,
        'opex_annual': opex,
        'k_initial_cost': k_initial,
        'annual_margin': annual_margin,
        'year1_net': year1_net,
        'year1_roi': year1_roi,
        'simple_payback_months': payback_months,
    }


def scenario_table(assumptions: dict[str, Assumption]) -> list[dict]:
    rows = []
    for scenario in SCENARIOS:
        result = compute(assumptions, scenario.multipliers)
        rows.append({
            'scenario': scenario.name,
            'multipliers': json.dumps(scenario.multipliers, sort_keys=True) if scenario.multipliers else '{}',
            **{key: (None if value is None else round(value, 2)) for key, value in result.items()},
        })
    return rows


def sensitivity(assumptions: dict[str, Assumption], base_multipliers: dict[str, float] | None = None) -> list[dict]:
    """One-at-a-time ±20% sweep, ranked by swing in annual margin."""
    base = compute(assumptions, base_multipliers)['annual_margin']
    rows = []
    for name in PARAMETER_NAMES:
        entry = assumptions[name]
        if entry.value == 0:
            rows.append({'parameter': name, 'base_value': entry.value, 'margin_low': None, 'margin_high': None,
                         'swing_rubles': None, 'source': entry.source, 'confidence': entry.confidence,
                         'note': 'parameter is zero; relative sensitivity is undefined'})
            continue
        low = compute(assumptions, {**(base_multipliers or {}), name: (base_multipliers or {}).get(name, 1.0) * 0.8})['annual_margin']
        high = compute(assumptions, {**(base_multipliers or {}), name: (base_multipliers or {}).get(name, 1.0) * 1.2})['annual_margin']
        rows.append({
            'parameter': name, 'base_value': entry.value,
            'margin_low': round(low, 2), 'margin_high': round(high, 2),
            'swing_rubles': round(abs(high - low), 2),
            'swing_pct_of_margin': round(abs(high - low) / abs(base), 4) if base else None,
            'source': entry.source, 'confidence': entry.confidence,
        })
    return sorted(rows, key=lambda row: (-(row['swing_rubles'] or 0), row['parameter']))


def _solve(parameter: str, target: str, assumptions: dict[str, Assumption], low: float, high: float, iterations: int = 80) -> float | None:
    """Bisection on one multiplier. Returns None when the sign never changes."""
    def margin(multiplier: float) -> float:
        return compute(assumptions, {parameter: multiplier})[target]

    low_margin, high_margin = margin(low), margin(high)
    if low_margin == high_margin or (low_margin > 0) == (high_margin > 0):
        return None
    for _ in range(iterations):
        middle = (low + high) / 2
        value = margin(middle)
        if (value > 0) == (low_margin > 0):
            low, low_margin = middle, value
        else:
            high, high_margin = middle, value
    return (low + high) / 2


def break_even(assumptions: dict[str, Assumption]) -> dict:
    return {
        'break_even_n_clients_multiplier': _solve('n_clients', 'annual_margin', assumptions, 0.01, 200.0),
        'break_even_delta_multiplier': _solve('delta_incremental_prevention', 'annual_margin', assumptions, 0.0001, 200.0),
        'break_even_opex_multiplier': _solve('opex_annual', 'annual_margin', assumptions, 0.01, 200.0),
        'n_clients_base': assumptions['n_clients'].value,
        'delta_base': assumptions['delta_incremental_prevention'].value,
        'opex_base': assumptions['opex_annual'].value,
    }


def missing_evidence(assumptions: dict[str, Assumption]) -> list[str]:
    return [
        f'{name}: source is "{entry.source}"/"{entry.confidence}" — no independent evidence in this repository'
        for name, entry in sorted(assumptions.items())
        if entry.source in ('assumption', 'unknown') or entry.confidence == 'low'
    ]


DISCLAIMERS = [
    'MODELLED ESTIMATE, NOT MEASURED ROI. Inputs are assumptions unless marked bank_data.',
    'Counts only incremental prevention on top of existing bank protection; existing protection is not claimed as a benefit.',
    'Prevalence (q) and unit loss (L_bank) are assumptions; no bank data was available.',
    'RevenueUplift = 0, Rewards = 0, Inference = 0 until proven; no cashback is modelled.',
    'A positive payback in the optimistic scenario is not a promise, only a condition to be tested in a pilot.',
]


def write_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    columns = columns or (list(rows[0]) if rows else [])
    with target.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return '_no rows_\n'
    lines = ['| ' + ' | '.join(columns) + ' |', '|' + '---|' * len(columns)]
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column)
            cells.append('n/a' if value is None else (f'{value:.2f}' if isinstance(value, float) else str(value)))
        lines.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines) + '\n'


def write_reports(assumptions: dict[str, Assumption], output_dir: Path | str) -> dict[str, Path]:
    """Emit the full P1 finance artifact set."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    scenarios = scenario_table(assumptions)
    sensitivity_rows = sensitivity(assumptions)
    break_even_row = break_even(assumptions)
    missing = missing_evidence(assumptions)

    written: dict[str, Path] = {}
    write_csv(directory / 'financial_scenarios.csv', scenarios)
    written['financial_scenarios.csv'] = directory / 'financial_scenarios.csv'
    write_csv(directory / 'sensitivity.csv', sensitivity_rows)
    written['sensitivity.csv'] = directory / 'sensitivity.csv'

    break_even_md = ['# Break-even (assumptions, not forecasts)', '', *[f'> {line}' for line in DISCLAIMERS], '',
                    '## Break-even multipliers', '', markdown_table(
                        [{'parameter': key, 'value': value} for key, value in break_even_row.items()], ['parameter', 'value']),
                    '', 'A multiplier of 1.0 means the base parameter already breaks even. Values far from 1.0 mean',
                    'the base case depends on an unproven input.', '']
    (directory / 'break_even.md').write_text('\n'.join(break_even_md), encoding='utf-8')
    written['break_even.md'] = directory / 'break_even.md'

    assumptions_md = ['# Model assumptions', '', *[f'> {line}' for line in DISCLAIMERS], '',
                      markdown_table([{'parameter': name, **entry.as_dict()} for name, entry in sorted(assumptions.items())],
                                     ['parameter', 'value', 'source', 'confidence', 'note']), '',
                      '## Formulas', '',
                      '- FraudBenefit = N * q * Delta * L_bank',
                      '- SupportBenefit = N * contacts_per_client_year * minutes_saved_per_contact * cost_per_minute',
                      '- FalseAlertCost = N * false_alerts_per_client_year * call_share * handling_cost',
                      '- AnnualMargin = FraudBenefit + SupportBenefit + RevenueUplift - OPEX - FalseAlertCost - Rewards - Inference',
                      '- Year1Net = AnnualMargin - K',
                      '- Year1ROI = Year1Net / (K + OPEX + FalseAlertCost + Rewards + Inference) when denominator > 0',
                      '- SimplePaybackMonths = 12*K / AnnualMargin only when AnnualMargin > 0', '',
                      'Avoided loss, customer benefit and bank loss are one and the same episode counted once.',
                      'They are never added as independent benefits.', '']
    (directory / 'model_assumptions.md').write_text('\n'.join(assumptions_md), encoding='utf-8')
    written['model_assumptions.md'] = directory / 'model_assumptions.md'

    missing_md = ['# Missing inputs', '', 'These parameters have no independent evidence in this repository.',
                  'Every one of them is a pilot question, not a known quantity.', '']
    missing_md += [f'- {item}' for item in missing] or ['- none']
    missing_md += ['', *[f'> {line}' for line in DISCLAIMERS], '']
    (directory / 'missing_inputs.md').write_text('\n'.join(missing_md), encoding='utf-8')
    written['missing_inputs.md'] = directory / 'missing_inputs.md'

    base = next(row for row in scenarios if row['scenario'] == 'base')
    conservative = next(row for row in scenarios if row['scenario'] == 'conservative')
    optimistic = next(row for row in scenarios if row['scenario'] == 'optimistic')

    def money(value: float | None) -> str:
        return 'не окупается' if value is None else f'{value:.1f} мес.'

    if base['annual_margin'] < 0:
        verdict = ('Иллюстративная база **убыточна**: годовая маржа отрицательна. Это не повод прятать '
                   'цифру — это точный список условий, которые пилот должен подтвердить или опровергнуть.')
    elif base['simple_payback_months'] is None:
        verdict = ('Иллюстративная база выходит около нуля, но не окупается: годовая маржа недостаточна, '
                   'простая окупаемость не считается.')
    else:
        verdict = (f'Иллюстративная база положительна: простая окупаемость '
                   f'{base["simple_payback_months"]:.1f} мес. Это сценарий, а не обещание.')

    pitch = [
        '# One minute, honestly', '',
        *[f'> {line}' for line in DISCLAIMERS], '',
        'Считаем только дополнительный эффект поверх текущей защиты банка: тот же перевод, который',
        'существующий антифрод уже частично перехватывает, мы не считаем своей победой дважды.', '',
        f'Иллюстративная база: годовая маржа {base["annual_margin"]:,.0f} ₽,'
        f' net первого года {base["year1_net"]:,.0f} ₽, простая окупаемость {money(base["simple_payback_months"])}.',
        f'Консервативная база: маржа {conservative["annual_margin"]:,.0f} ₽,'
        f' окупаемость {money(conservative["simple_payback_months"])}.', '',
        f'Оптимистичная база (множители {optimistic["multipliers"]}) даёт'
        f' {optimistic["annual_margin"]:,.0f} ₽ — это верхняя граница допущений, а не обещание.', '',
        verdict, '',
        'Что именно должен проверить пилот: Delta (дополнительный эффект), OPEX и K, долю ложных',
        'обращений и подтверждённый охват клиентов.', '',
        'Это не ROI пилота. Это условия, которые пилот должен подтвердить или опровергнуть.', '',
    ]
    (directory / 'pitch_one_minute.md').write_text('\n'.join(pitch), encoding='utf-8')
    written['pitch_one_minute.md'] = directory / 'pitch_one_minute.md'
    return written