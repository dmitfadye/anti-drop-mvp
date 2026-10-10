"""Deterministic synthetic fixture generator for the P1 legitimate-negative work.

Run from the repository root:
    python -m scripts.generate_synthetic_fixtures --output-dir fixtures/episodes

Everything here is hand-built intent plus a fixed-seed generator for volume.
There is no random sampling from real data and no real personal data: every
ref is a hash of a scenario name, every amount is chosen to sit on or off a
declared detector threshold.

Label honesty is a hard rule of this file:
- `label_source` is always `synthetic_placeholder`;
- each episode records `label_basis`, which says *why* it is labelled risk or
  normal (scenario intent, or "detector is expected to miss this" for the
  documented blind spots);
- a fixture is never promoted to human_reviewed or bank_adjudicated here,
  because no such labelling exists in this repository.

Provenance (seed, generator version, threshold constants) is written to
`fixtures/episodes/provenance.json` so a report can quote it.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_SEED = 20261008
GENERATOR_VERSION = 'generate-synthetic-fixtures-v1'
DATASET_VERSION = 'synthetic-episodes-p1-v1'
BASE_AT = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)

# Detector thresholds these fixtures are built around (src/policy.py).
SMALL_TXN_MAX_MINOR = 500_000          # 5 000 ₽
TRANSIT_WINDOW_MIN = 60
RED_TRANSIT_COUNT = 5
RED_TRANSIT_SENDERS = 3

GROUPS = ('normal', 'risk', 'legitimate_negative', 'edge', 'missing_data')
INVALID_GROUP = 'invalid_contract'
EPISODE_CLASS_BY_GROUP = {
    'normal': 'normal',
    'risk': 'risk',
    'legitimate_negative': 'legitimate_negative',
    'edge': 'edge',
    # Missing-data episodes are boundary cases for the detector, so they are
    # labelled with the edge class; the group is preserved in the catalog.
    'missing_data': 'edge',
}


def ref(prefix: str, value: str) -> str:
    import hashlib

    return prefix + '_' + hashlib.sha256(value.encode()).hexdigest()[:16]


def transaction(index: int = 0, minutes: int = 10, direction: str = 'in', kind: str = 'transfer',
                amount: int = 300_000, sim: int | None = None, device: str | None = None,
                counterparty: str | None = None, at: datetime | None = None) -> dict:
    moment = at or (BASE_AT - timedelta(minutes=minutes))
    return {
        'event_id': ref('evt', f'{index}-{moment.isoformat()}'),
        'occurred_at': moment.isoformat(),
        'direction': direction,
        'type': kind,
        'amount_minor': amount,
        'currency': 'RUB',
        'counterparty_ref': counterparty if counterparty is not None else ref('cp', str(index)),
        'device_id': device,
        'sim_changed_days_ago': sim,
    }


def snapshot(transactions: list[dict], subject_key: str, *, analysis_at: datetime | None = None,
             label: str = 'normal', episode_class: str = 'normal', is_holdout: bool = False) -> dict:
    return {
        'schema_version': 'RiskSnapshotV1',
        'subject_ref': ref('sub', subject_key),
        'analysis_at': (analysis_at or BASE_AT).isoformat(),
        'timezone_policy': 'normalize_to_utc',
        'allow_future_events': False,
        'transactions': transactions,
        'metadata': {
            'dataset_version': DATASET_VERSION,
            'label_source': 'synthetic_placeholder',
            'is_holdout': is_holdout,
            'episode_class': episode_class,
        },
    }


def episode(name: str, group: str, transactions: list[dict], label: str, label_basis: str,
            expectations: str, *, subject_key: str | None = None, analysis_at: datetime | None = None,
            adversarial: bool = False) -> tuple[dict, dict]:
    subject = subject_key or name
    episode_class = EPISODE_CLASS_BY_GROUP[group]
    payload = snapshot(transactions, subject, analysis_at=analysis_at, label=label,
                       episode_class=episode_class, is_holdout=bool(HOLDOUT_SCENARIOS & {name}))
    row = {
        'episode_id': ref('ep', name),
        'subject_ref': payload['subject_ref'],
        'label': label,
        'episode_class': episode_class,
        'label_source': 'synthetic_placeholder',
        'is_holdout': payload['metadata']['is_holdout'],
        'payload': payload,
    }
    catalog_row = {
        'episode_id': row['episode_id'],
        'scenario': name,
        'group': group,
        'episode_class': episode_class,
        'label': label,
        'label_source': 'synthetic_placeholder',
        'label_basis': label_basis,
        'adversarial': adversarial,
        'expected_behavior': expectations,
        'is_holdout': row['is_holdout'],
        'subject_ref': row['subject_ref'],
    }
    return row, catalog_row


# is_holdout is never hand-declared in fixtures. Hand-declared holdouts are how
# subject leakage sneaks in; the split is computed by
# `anti_drop_ml.evaluation.holdout.split_episodes` instead, which owns the flag.


HOLDOUT_SCENARIOS: frozenset[str] = frozenset()


def _small_inbound(count: int, *, sim: int | None = None, amount: int = 300_000,
                   device: str | None = None, start_minutes: int = 45, step: int = 5,
                   kind: str = 'transfer') -> list[dict]:
    return [transaction(i, minutes=start_minutes - i * step, kind=kind, amount=amount, sim=sim, device=device)
            for i in range(count)]


def build_episodes() -> tuple[list[dict], list[dict]]:
    episodes: list[dict] = []
    catalog: list[dict] = []
    rng = Random(FIXTURE_SEED)

    def add(*args, **kwargs):
        row, catalog_row = episode(*args, **kwargs)
        episodes.append(row)
        catalog.append(catalog_row)

    # ---------------------------------------------------------------- normal
    add('ordinary_transfer', 'normal',
        [transaction(0, minutes=180, amount=120_000), transaction(1, minutes=170, direction='out', kind='other', amount=80_000)],
        'normal', 'ordinary peer-to-peer activity, no transit shape', 'GREEN expected')
    add('salary_only', 'normal', [transaction(0, minutes=240, kind='salary', amount=6_000_000)],
        'normal', 'single salary credit', 'GREEN expected')
    add('salary_and_spend', 'normal', [
        transaction(0, minutes=600, kind='salary', amount=5_500_000),
        transaction(1, minutes=590, direction='out', kind='other', amount=90_000),
        transaction(2, minutes=580, direction='out', kind='other', amount=45_000),
    ], 'normal', 'salary plus ordinary spending', 'GREEN expected')
    add('relatives_transfer', 'normal', [transaction(0, minutes=120, direction='out', amount=1_000_000)],
        'normal', 'one large outgoing transfer to a known counterparty', 'GREEN expected')
    add('stable_monthly_spend', 'normal', [
        transaction(i, minutes=60 + i * 1440, direction='out', kind='other', amount=100_000) for i in range(6)
    ], 'normal', 'regular monthly spending, no inbound burst', 'GREEN expected')

    # ---------------------------------------------------- legitimate_negative
    add('family_collection', 'legitimate_negative', _small_inbound(5, kind='family_collection'),
        'normal', 'family/friends paying back a shared expense; no onward transfer',
        'YELLOW or GREEN, never RED from the transit shape alone')
    add('family_collection_then_small_rent', 'legitimate_negative',
        _small_inbound(5, kind='family_collection') + [transaction(9, minutes=2, direction='out', amount=300_000)],
        'normal', 'family collection followed by a small, purpose-stated outgoing payment',
        'must not be RED; small outgoing is not cashout')
    add('salary_and_cash', 'legitimate_negative', [
        transaction(0, minutes=100, kind='salary', amount=6_000_000),
        transaction(1, minutes=60, direction='out', kind='cash_withdrawal', amount=5_000_000),
    ], 'normal', 'salary withdrawn in cash the same day', 'YELLOW at most; cashout alone is not dроp evidence')
    add('regular_payments', 'legitimate_negative',
        [transaction(i, minutes=30 + i * 1440, direction='out', amount=100_000) for i in range(4)],
        'normal', 'rent/utilities/subscriptions on a fixed schedule', 'GREEN expected')
    night = [transaction(i, kind='other', direction='out', amount=10_000) for i in range(3)]
    for item in night:
        item['occurred_at'] = '2026-10-08T00:10:00+03:00'
    add('night_worker', 'legitimate_negative', night, 'normal',
        'shift worker operating at night, no inbound transit', 'not RED because of time alone',
        analysis_at=datetime(2026, 10, 8, 0, 30, tzinfo=timezone(timedelta(hours=3))))
    add('new_device_without_sim', 'legitimate_negative',
        [transaction(i, minutes=200 if i == 0 else 40 - i * 5, kind='other',
                     device=ref('dev', 'legacy') if i == 0 else ref('dev', 'fresh')) for i in range(4)],
        'normal', 'new device, SIM change unknown', 'YELLOW at most; device novelty alone must not be RED')
    add('fresh_sim_without_burst', 'legitimate_negative', [transaction(0, minutes=30, sim=0)],
        'normal', 'SIM replaced today, no transfer burst', 'GREEN; fresh SIM alone must not be RED')
    add('many_inbound_without_outbound', 'legitimate_negative', _small_inbound(6),
        'normal', 'several small inbound payments and no onward transfer',
        'YELLOW monitoring, not RED')
    add('outbound_before_inbound', 'legitimate_negative',
        [transaction(9, minutes=58, direction='out', amount=1_400_000)] + _small_inbound(4, start_minutes=45),
        'normal', 'large outgoing happens before the inbound burst',
        'outbound must not count as flow-through')

    # P0 holdout replicas, kept so both splits stay populated.
    # ------------------------------------------------------------------ risk
    add('inbound_and_large_outbound', 'risk',
        _small_inbound(5) + [transaction(9, minutes=2, direction='out', amount=1_400_000)],
        'risk', 'classic transit: five small inbound from five senders, then one large onward transfer',
        'RED expected')
    add('fresh_sim_and_transit', 'risk',
        [{**item, 'sim_changed_days_ago': 0} for item in _small_inbound(5)]
        + [transaction(9, minutes=2, direction='out', amount=1_400_000, sim=0)],
        'risk', 'fresh SIM plus transit burst plus onward transfer', 'RED expected')
    add('transit_plus_fanout', 'risk',
        _small_inbound(5) + [transaction(20 + i, minutes=6 - i, direction='out', amount=200_000) for i in range(4)],
        'risk', 'inbound burst followed by four different recipients',
        'RED expected; two rules contribute, reason co-occurrence is reported')
    add('cashout_after_inbound', 'risk',
        _small_inbound(5) + [transaction(9, minutes=3, direction='out', kind='cash_withdrawal', amount=1_600_000)],
        'risk', 'inbound burst followed by a large cash withdrawal', 'RED expected')
    add('transit_with_new_device', 'risk',
        [transaction(0, minutes=600, kind='other', device=ref('dev', 'legacy')),
         transaction(1, minutes=500, kind='other', device=ref('dev', 'legacy')),
         *[{**item, 'device_id': ref('dev', 'fresh')} for item in _small_inbound(5)],
         transaction(9, minutes=2, direction='out', amount=1_400_000, device=ref('dev', 'fresh'))],
        'risk', 'device change plus SIM change plus transit', 'RED expected')
    add('adversarial_single_counterparty_split', 'risk',
        [transaction(i, minutes=45 - i * 5, counterparty=ref('cp', 'single-relay')) for i in range(6)],
        'risk', 'adversarial: one relay splits the transit into six inbound pieces',
        'documented blind spot: sender-diversity rule cannot see a single relay, expect a miss', adversarial=True)
    add('adversarial_zero_padding', 'risk',
        _small_inbound(4) + [transaction(7, minutes=8, kind='other', amount=0, counterparty=ref('cp', 'padding'))]
        + [transaction(8, minutes=2, direction='out', amount=1_400_000)],
        'risk', 'adversarial: zero-amount noise mixed into a real transit',
        'zero amounts are excluded by contract, so only the real inbounds drive the transit rule', adversarial=True)
    add('adversarial_wait_out_the_window', 'risk',
        _small_inbound(5, start_minutes=85, step=5) + [transaction(9, minutes=62, direction='out', amount=1_400_000)],
        'risk', 'adversarial: inbound burst and onward transfer both placed outside the 60-minute window',
        'documented blind spot: waiting out the window defeats the short rule, expect a miss', adversarial=True)
    night_at = datetime(2026, 10, 8, 1, 15, tzinfo=timezone.utc)
    add('night_transit', 'risk',
        [{**item, 'occurred_at': (night_at - timedelta(minutes=10 + i * 5)).isoformat()}
         for i, item in enumerate(_small_inbound(5))]
        + [{**transaction(9, direction='out', amount=1_400_000), 'occurred_at': (night_at - timedelta(minutes=5)).isoformat()}],
        'risk', 'transit performed at night', 'RED expected', analysis_at=night_at)

    # ------------------------------------------------------------------ edge
    for minutes in (59, 60, 61):
        add(f'edge_window_{minutes}', 'edge', _small_inbound(5, start_minutes=minutes, step=0),
            'risk' if minutes <= TRANSIT_WINDOW_MIN else 'normal',
            f'exact window boundary: all inbound {minutes} minutes before analysis_at',
            f'inbound at {minutes} min is {"inside" if minutes <= TRANSIT_WINDOW_MIN else "outside"} the 60-minute window')
    midnight = [transaction(i, minutes=0, kind='other', amount=20_000) for i in range(3)]
    for index, item in enumerate(midnight):
        item['occurred_at'] = f'2026-10-07T23:{58 - index * 2:02d}:00+00:00'
    add('edge_midnight_cross', 'edge', midnight, 'normal',
        'activity crosses the UTC date boundary', 'window maths must not wrap around midnight')
    day_one = [transaction(0, minutes=300, kind='other', amount=30_000),
               transaction(1, minutes=290, kind='other', amount=30_000)]
    for item in day_one:
        item['occurred_at'] = '2026-10-06T12:00:00+00:00'
    add('edge_date_boundary', 'edge', day_one, 'normal', 'episodes on a previous calendar day',
        'previous-day activity must not be treated as inside the current window')
    for amount, label, note in [
        (1, 'normal', 'one kopeck'),
        (SMALL_TXN_MAX_MINOR - 1, 'risk', 'one minor unit below the small-transaction threshold'),
        (SMALL_TXN_MAX_MINOR, 'risk', 'exactly on the small-transaction threshold, inclusive by contract'),
        (SMALL_TXN_MAX_MINOR + 1, 'normal', 'one minor unit above the threshold'),
    ]:
        add(f'edge_amount_{amount}', 'edge', _small_inbound(5, amount=amount), label,
            f'amount boundary: {note}', f'{amount} minor units vs threshold {SMALL_TXN_MAX_MINOR}')
    for count in (1, 2, 3, 4, 5):
        add(f'edge_count_{count}', 'edge', _small_inbound(count), 'risk' if count >= 3 else 'normal',
            f'count boundary: {count} small inbound payments',
            f'{count} inbounds vs YELLOW count 3 and RED count {RED_TRANSIT_COUNT}')
    for sim in (None, 0, 1, 2, 3, 30):
        add(f'edge_sim_{"null" if sim is None else sim}', 'edge', _small_inbound(5, sim=sim),
            'risk', f'SIM freshness boundary: sim_changed_days_ago={sim}',
            'sim=null means unknown, sim 0-2 is fresh, sim 3+ is stale')

    # ----------------------------------------------------------- missing data
    add('missing_no_device_id', 'missing_data',
        [{**item, 'device_id': None} for item in _small_inbound(5)],
        'risk', 'no device id on any transaction', 'reduced confidence, reason codes still reported')
    add('missing_no_counterparty_ref', 'missing_data',
        [{**item, 'counterparty_ref': None} for item in _small_inbound(5)],
        'risk', 'no counterparty pseudonym on any transaction',
        'sender-diversity signal degrades; must not invent a counterparty')
    add('missing_no_sim_field', 'missing_data', _small_inbound(5, sim=None),
        'risk', 'sim_changed_days_ago absent', 'SIM rule must not fire on unknown values')
    add('missing_no_device_no_sim', 'missing_data',
        [{**item, 'device_id': None, 'sim_changed_days_ago': None} for item in _small_inbound(5)],
        'risk', 'neither device nor SIM available', 'degraded data quality, no fabricated risk')
    add('missing_empty_history', 'missing_data', [],
        'normal', 'no transactions at all', 'insufficient_data status, score 0, never a fabricated level')

    # ------------------------------------------------- repeated subject (leak)
    for day in (1, 2, 3):
        add(f'repeated_subject_{day}', 'legitimate_negative',
            _small_inbound(5, kind='family_collection', start_minutes=45 + (3 - day) * 5),
            'normal', f'third episode of the same synthetic subject, day {day}',
            'same subject across time; the splitter must keep every episode on one side',
            subject_key='repeated-subject')

    # Pseudo-random volume split across normal and risk so rate estimates have a
    # denominator, generated with a fixed seed so reruns are byte-identical.
    for index in range(rng.randint(28, 34)):
        if index % 5 != 0:
            amount = rng.choice([50_000, 300_000])
            transactions = _small_inbound(5, amount=amount, start_minutes=45)
            transactions += [transaction(90 + index, minutes=2, direction='out', amount=1_400_000)]
            add(f'generated_transit_{index:03d}', 'risk', transactions, 'risk',
                'fixed-seed generated transit episode: five small inbound plus one large onward transfer',
                f'amount {amount} minor units per inbound; RED expected; seed {FIXTURE_SEED}')
        else:
            quiet = [transaction(900 + index * 10 + slot, minutes=rng.choice([120, 180, 300, 600]),
                                 kind=rng.choice(['transfer', 'other', 'salary']),
                                 amount=rng.choice([60_000, 150_000, 900_000, 4_500_000]))
                     for slot in range(rng.randint(1, 3))]
            add(f'generated_quiet_{index:03d}', 'normal', quiet, 'normal',
                'fixed-seed generated ordinary activity without transit shape',
                f'GREEN expected; seed {FIXTURE_SEED}')

    episodes.sort(key=lambda row: row['episode_id'])
    catalog.sort(key=lambda row: row['episode_id'])
    return episodes, catalog


def build_invalid() -> list[dict]:
    """Contracts that must be rejected with 422, never with a 500."""
    base = snapshot([transaction(0, minutes=30), transaction(1, minutes=25)], 'invalid-base')
    cases: list[tuple[str, dict]] = []

    def variant(name: str, mutate) -> None:
        payload = json.loads(json.dumps(base))
        mutate(payload)
        cases.append((name, payload))

    def first(payload):
        return payload['transactions'][0]

    def second(payload):
        return payload['transactions'][1]

    variant('duplicate_event_id', lambda p: second(p).update(event_id=first(p)['event_id']))
    variant('duplicate_source_event_id', lambda p: (first(p).update(source_event_id=ref('src', 'dup')),
                                                    second(p).update(source_event_id=ref('src', 'dup'))))
    variant('future_occurred_at', lambda p: first(p).update(occurred_at=(BASE_AT + timedelta(minutes=5)).isoformat()))
    variant('zero_amount_transfer', lambda p: first(p).update(amount_minor=0))
    variant('negative_amount', lambda p: first(p).update(amount_minor=-1))
    variant('mixed_subject_ref', lambda p: second(p).update(subject_ref=ref('sub', 'someone-else')))
    variant('naive_occurred_at', lambda p: first(p).update(occurred_at='2026-10-08T11:00:00'))
    variant('invalid_timezone', lambda p: first(p).update(occurred_at='2026-10-08T11:00:00+99:00'))
    variant('invalid_occurred_at', lambda p: first(p).update(occurred_at='not-a-date'))
    variant('amount_not_integer', lambda p: first(p).update(amount_minor=100.5))
    variant('amount_as_string', lambda p: first(p).update(amount_minor='100'))
    variant('float_amount', lambda p: first(p).update(amount_minor=100.0))
    variant('foreign_currency', lambda p: first(p).update(currency='USD'))
    variant('bool_amount', lambda p: first(p).update(amount_minor=True))
    variant('sim_as_bool', lambda p: first(p).update(sim_changed_days_ago=False))
    variant('raw_pii_field', lambda p: first(p).update(phone='+79990000000'))
    variant('raw_pii_top_level', lambda p: p.update(full_name='SYNTHETIC-NOT-A-PERSON'))
    variant('salary_outbound', lambda p: first(p).update(direction='out', type='salary'))
    variant('cash_withdrawal_inbound', lambda p: first(p).update(direction='in', type='cash_withdrawal'))
    variant('naive_analysis_at', lambda p: p.update(analysis_at='2026-10-08T12:00:00'))
    variant('unknown_top_level_field', lambda p: p.update(risk_factor='language'))
    variant('unknown_episode_class', lambda p: p['metadata'].update(episode_class='maybe'))
    variant('invalid_device_ref', lambda p: first(p).update(device_id='my-laptop'))
    variant('analysis_at_not_datetime', lambda p: p.update(analysis_at=1764000000))
    return [{'scenario': name, 'expected_status': 422, 'expected_detail': 'contract validation', 'payload': payload}
            for name, payload in cases]


def provenance() -> dict:
    return {
        'schema_version': 'FixtureProvenanceV1',
        'generator': GENERATOR_VERSION,
        'dataset_version': DATASET_VERSION,
        'random_seed': FIXTURE_SEED,
        'generated_at': BASE_AT.isoformat(),
        'deterministic': True,
        'label_sources': ['synthetic_placeholder'],
        'human_reviewed_count': 0,
        'bank_adjudicated_count': 0,
        'detector_thresholds_used_to_build_fixtures': {
            'small_txn_max_minor': SMALL_TXN_MAX_MINOR,
            'transit_window_min': TRANSIT_WINDOW_MIN,
            'red_transit_count': RED_TRANSIT_COUNT,
            'red_transit_senders': RED_TRANSIT_SENDERS,
        },
        'statement': (
            'All episodes are synthetic. label_source is synthetic_placeholder for every row. '
            'No human review, no bank adjudication and no real customer data was used. '
            'Metrics computed on this set are pipeline behaviour, NOT validated banking accuracy.'
        ),
        'adversarial_cases': [
            'adversarial_single_counterparty_split', 'adversarial_zero_padding',
            'adversarial_staggered_out_of_window',
        ],
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


def write_fixtures(output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    episodes, catalog = build_episodes()
    written: list[str] = []
    for group in GROUPS:
        rows = [row for row, entry in zip(episodes, catalog) if entry['group'] == group]
        if not rows:
            continue
        path = output_dir / group / 'episodes.jsonl'
        write_jsonl(path, rows)
        written.append(str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path))
        catalog_rows = [entry for entry in catalog if entry['group'] == group]
        (output_dir / group / 'catalog.json').write_text(
            json.dumps({'schema_version': 'FixtureGroupCatalogV1', 'group': group,
                        'dataset_version': DATASET_VERSION, 'label_sources': ['synthetic_placeholder'],
                        'count': len(catalog_rows), 'episodes': catalog_rows}, indent=2, ensure_ascii=False) + '\n',
            encoding='utf-8')
    invalid = build_invalid()
    write_jsonl(output_dir / INVALID_GROUP / 'invalid.jsonl', invalid)
    (output_dir / INVALID_GROUP / 'catalog.json').write_text(
        json.dumps({'schema_version': 'InvalidContractCatalogV1', 'count': len(invalid),
                    'expected_status': 422, 'scenarios': [row['scenario'] for row in invalid]}, indent=2) + '\n',
        encoding='utf-8')
    write_jsonl(output_dir / 'all_episodes_p1.jsonl', episodes)
    (output_dir / 'fixture_catalog_p1.json').write_text(
        json.dumps({'schema_version': 'FixtureCatalogV1', 'dataset_version': DATASET_VERSION,
                    'count': len(catalog), 'episodes': catalog}, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8')
    (output_dir / 'provenance.json').write_text(json.dumps(provenance(), indent=2, ensure_ascii=False) + '\n',
                                                encoding='utf-8')
    return {'episodes': len(episodes), 'invalid': len(invalid), 'written': written}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=REPO_ROOT / 'fixtures' / 'episodes')
    args = parser.parse_args()
    result = write_fixtures(args.output_dir)
    print(f"Wrote {result['episodes']} synthetic episodes and {result['invalid']} invalid-contract cases "
          f"to {args.output_dir}. Labels are synthetic_placeholder only.")


if __name__ == '__main__':
    main()