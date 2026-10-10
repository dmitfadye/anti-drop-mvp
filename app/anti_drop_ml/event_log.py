"""Append-only local JSON-lines event sink. No broker, no database, no network.

Deliberately dumb: validate against the closed event contract, append one
redacted JSON object per line, never crash the request path. If no path is
configured the sink is a no-op so a fresh clone behaves like a demo.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from uuid import uuid4

from anti_drop_ml.events import ProductEventV1

_LOCK = threading.Lock()
_COUNTER = 0

REQUIRED_FIELDS = ('event_id', 'event_type', 'timestamp', 'evaluation_id', 'rule_version', 'threshold_version')


def _next_sequence() -> int:
    global _COUNTER
    with _LOCK:
        _COUNTER += 1
        return _COUNTER


def new_event_id() -> str:
    """UUID4 as a string, matching the ProductEventV1 contract."""
    return str(uuid4())


def append_event(event: dict, path: str | os.PathLike[str] | None) -> ProductEventV1 | None:
    """Validate then append. Returns the validated event, or None when disabled."""
    if not path:
        return None
    try:
        validated = ProductEventV1.model_validate(event)
    except Exception:
        # An invalid event must never break a demonstration flow, but it also
        # must not be silently dropped: surface it on stderr without the payload.
        print(f'[event_log] rejected malformed {type(event).__name__} event', flush=True)
        return None
    line = json.dumps(validated.model_dump(mode='json'), sort_keys=True, ensure_ascii=False)
    target = Path(path)
    try:
        with _LOCK:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('a', encoding='utf-8', newline='\n') as stream:
                stream.write(line + '\n')
    except OSError:
        # Sink is observability, not the request: a read-only mount or a
        # root-owned bind dir must degrade to no-op, never to HTTP 500.
        print(f'[event_log] sink unwritable ({target}); event dropped', flush=True)
        return None
    return validated


def read_events(path: str | os.PathLike[str]) -> list[dict]:
    """Read back a local sink for the operator screen and offline analysis."""
    target = Path(path)
    if not target.is_file():
        return []
    events = []
    for line in target.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # A truncated last line is expected if a run was interrupted.
            continue
    return events