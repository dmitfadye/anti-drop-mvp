"""Deterministic handcrafted fixtures, no random generation and no personal data."""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATASET_VERSION = 'synthetic-episodes-v1'
AT = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def ref(prefix: str, value: str) -> str:
    return prefix+'_'+hashlib.sha256(value.encode()).hexdigest()[:16]


def transaction(index: int = 0, minutes: int = 10, direction: str = 'in', kind: str = 'transfer', amount: int = 300000, sim: int | None = None, device: str | None = None) -> dict:
    return {'event_id': ref('evt', str(index)), 'occurred_at': (AT-timedelta(minutes=minutes)).isoformat(), 'direction': direction, 'type': kind, 'amount_minor': amount, 'currency': 'RUB', 'counterparty_ref': ref('cp', str(index)), 'device_id': device, 'sim_changed_days_ago': sim}


def make_snapshot(transactions: list[dict], subject: str = 'subject') -> dict:
    return {'schema_version': 'RiskSnapshotV1', 'subject_ref': ref('sub', subject), 'analysis_at': AT.isoformat(), 'timezone_policy': 'normalize_to_utc', 'transactions': transactions, 'metadata': {'dataset_version': DATASET_VERSION, 'label_source': 'synthetic_placeholder', 'is_holdout': False, 'episode_class': 'normal'}}


def build_fixtures() -> tuple[list[dict], list[dict], list[dict]]:
    episodes, invalid, catalog = [], [], []

    def add(name, txns, label='normal', category='legitimate_negative'):
        snapshot = make_snapshot(txns, name)
        snapshot['metadata']['episode_class'] = category
        episode = {'episode_id': ref('ep', name), 'subject_ref': snapshot['subject_ref'], 'label': label, 'episode_class': category, 'label_source': 'synthetic_placeholder', 'is_holdout': False, 'payload': snapshot}
        episodes.append(episode)
        catalog.append({'episode_id': episode['episode_id'], 'scenario': name, 'label_basis': 'handcrafted synthetic scenario intent, not detector output'})

    inbound = [transaction(i, minutes=40-i*5) for i in range(5)]
    add('ordinary_transfer', [transaction()], category='normal')
    add('salary', [transaction(kind='salary', amount=6000000)], category='normal')
    add('family_collection', [transaction(i, minutes=40-i*5, kind='family_collection') for i in range(5)])
    # A benign purpose can have the same observable flow as risk: expose the false positive.
    add('family_collection_then_rent', [transaction(i, minutes=40-i*5, kind='family_collection') for i in range(5)]+[transaction(9, minutes=1, direction='out', amount=1400000)])
    add('relatives_transfer', [transaction(direction='out', amount=1000000)])
    add('regular_payments', [transaction(i, minutes=10+i*1440, direction='out', amount=100000) for i in range(4)])
    add('salary_and_cash', [transaction(0, minutes=100, kind='salary', amount=6000000), transaction(1, kind='cash_withdrawal', direction='out', amount=5000000)])
    night = [transaction(i, minutes=20-i*5, kind='other', direction='out', amount=10000) for i in range(3)]
    for t in night:
        t['occurred_at'] = '2026-10-08T00:10:00+03:00'
    add('night_worker', night)
    episodes[-1]['payload']['analysis_at'] = '2026-10-08T00:30:00+03:00'
    add('new_device_without_sim', [transaction(i, minutes=80 if i == 0 else 30-i*5, kind='other', device=ref('dev', 'old' if i == 0 else 'new')) for i in range(4)])
    add('fresh_sim_without_burst', [transaction(sim=0)])
    add('many_inbound_without_outbound', inbound)
    add('inbound_and_large_outbound', inbound+[transaction(9, minutes=1, direction='out', amount=1400000)], 'risk', 'risk')
    add('fresh_sim_and_transit', [{**t, 'sim_changed_days_ago': 0} for t in inbound]+[transaction(9, minutes=1, direction='out', amount=1400000, sim=0)], 'risk', 'risk')
    add('outbound_before_inbound', [transaction(9, minutes=55, direction='out', amount=1400000)]+inbound, category='edge')
    for minutes in (59, 60, 61):
        add(f'window_{minutes}', [transaction(i, minutes=minutes) for i in range(5)], category='edge')
    for amount in (1, 499999, 500000, 500001):
        add(f'amount_{amount}', [transaction(i, amount=amount) for i in range(5)], category='edge')
    for name in ('duplicate_event_id', 'duplicate_source_event_id', 'future_event', 'zero_transfer', 'negative_amount', 'mixed_subjects', 'invalid_date', 'naive_date'):
        snapshot = make_snapshot([transaction(0), transaction(1)], name)
        first, second = snapshot['transactions']
        if name == 'duplicate_event_id': second['event_id'] = first['event_id']
        elif name == 'duplicate_source_event_id': first['source_event_id'] = second['source_event_id'] = ref('src', 'duplicate')
        elif name == 'future_event': first['occurred_at'] = (AT+timedelta(seconds=1)).isoformat()
        elif name == 'zero_transfer': first['amount_minor'] = 0
        elif name == 'negative_amount': first['amount_minor'] = -1
        elif name == 'mixed_subjects': second['subject_ref'] = ref('sub', 'different')
        elif name == 'invalid_date': first['occurred_at'] = 'not-a-date'
        elif name == 'naive_date': first['occurred_at'] = '2026-10-08T11:00:00'
        invalid.append({'scenario': name, 'expected_status': 422, 'payload': snapshot})
    return sorted(episodes, key=lambda e: e['episode_id']), invalid, catalog


def write_fixtures(output_dir: Path):
    episodes, invalid, catalog = build_fixtures()
    output_dir.mkdir(parents=True, exist_ok=True)
    def jsonl(name, rows):
        (output_dir/name).write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows), encoding='utf-8')
    jsonl('labeled_episodes.jsonl', episodes)
    jsonl('invalid_snapshots.jsonl', invalid)
    template = copy.deepcopy(episodes)
    for row in template:
        row['label'] = None
        row['label_source'] = row['payload']['metadata']['label_source'] = 'unknown'
    jsonl('labeling_template.jsonl', template)
    (output_dir/'fixture_catalog.json').write_text(json.dumps(catalog, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('fixtures/episodes'))
    write_fixtures(parser.parse_args().output_dir)
