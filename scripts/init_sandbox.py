"""Create ignored local credentials and a synthetic sample; never overwrite existing configuration."""
import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anti_drop_ml.make_labeling_template import make_snapshot, transaction


def main():
    target = Path('.env')
    if target.exists():
        raise SystemExit('.env already exists; preserved unchanged')
    token = secrets.token_hex(32)
    subject = 'sub_' + secrets.token_hex(16)
    password = secrets.token_hex(24)
    tokens = json.dumps({token: subject}, separators=(',', ':'))
    with target.open('x', encoding='utf-8') as stream:
        stream.write(f"POSTGRES_PASSWORD={password}\nAPI_DATABASE_PASSWORD={secrets.token_hex(24)}\nSANDBOX_TOKENS='{tokens}'\n")
    local = Path('.local')
    local.mkdir(exist_ok=True)
    (local/'demo-client.json').write_text(json.dumps({'token': token, 'subject_ref': subject}), encoding='utf-8')
    snapshot = make_snapshot([transaction(i, minutes=40-i*5, sim=0) for i in range(5)] + [transaction(9, minutes=1, direction='out', amount=1400000)])
    snapshot['subject_ref'] = subject
    (local/'demo-snapshot.json').write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
    print('Created ignored .env and .local demo configuration. Credentials were not printed.')


if __name__ == '__main__':
    main()
