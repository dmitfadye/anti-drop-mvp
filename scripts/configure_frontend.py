"""Configure native Next from ignored synthetic credentials, without printing them."""
import json
from pathlib import Path

configuration = json.loads(Path('.local/demo-client.json').read_text(encoding='utf-8'))
target = Path('frontend/.env.local')
if target.exists():
    raise SystemExit('frontend/.env.local already exists; preserved unchanged')
with target.open('x', encoding='utf-8') as stream:
    stream.write('BACKEND_URL=http://127.0.0.1:8010\n')
    stream.write('SANDBOX_WEB_TOKEN=' + configuration['token'] + '\n')
    stream.write('SANDBOX_WEB_SUBJECT=' + configuration['subject_ref'] + '\n')
print('Created ignored frontend/.env.local. Credentials were not printed.')
