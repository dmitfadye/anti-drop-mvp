"""Demonstrate real HTTP evaluation -> explanation -> durable case -> retrieval."""
import argparse
import json
import sys
from pathlib import Path

import httpx


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8010')
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    configuration = json.loads(Path('.local/demo-client.json').read_text(encoding='utf-8'))
    headers = {'Authorization': 'Bearer ' + configuration['token']}
    output = Path('.local/demo-result.json')
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=10) as client:
        if args.verify_existing:
            result = json.loads(output.read_text(encoding='utf-8'))
            response = client.get('/sandbox/cases/' + result['case_id'])
            response.raise_for_status()
            assert response.json() == result
            print('Persisted case verified after restart:', result['case_id'])
            return
        payload = json.loads(Path('.local/demo-snapshot.json').read_text(encoding='utf-8'))
        response = client.post('/sandbox/evaluations', json=payload)
        response.raise_for_status()
        decision = response.json()
        print('Synthetic evaluation:', decision['level'], 'rule score', decision['score'])
        print('Not a probability. Reasons:', ', '.join(decision['reason_codes']))
        for warning in decision['warnings']:
            print(warning)
        body = {'evaluation_id': decision['evaluation_id'], 'selected_language': 'ru', 'contact_reason': 'need_assistance'}
        response = client.post('/sandbox/cases', json=body, headers={'Idempotency-Key': 'jury-demo-v1'})
        response.raise_for_status()
        case = response.json()
        replay = client.post('/sandbox/cases', json=body, headers={'Idempotency-Key': 'jury-demo-v1'})
        replay.raise_for_status()
        assert replay.json() == case
        response = client.get('/sandbox/cases/' + case['case_id'])
        response.raise_for_status()
        assert response.json() == case
        output.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding='utf-8')
        print('Durable case:', case['case_id'])
        print(case['next_step'])


if __name__ == '__main__':
    main()
