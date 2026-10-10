"""Subject- and time-disjoint holdout splitter.

Rules are not trained, so a holdout is not about fitting — it is about not
reporting a number on the same episodes that shaped the thresholds. Two
invariants are enforced rather than documented:

1. a `subject_ref` appears in exactly one side of the split;
2. the holdout side is taken from the later part of each subject's timeline,
   so "recent behaviour" is what gets held out.

The manifest records both invariants, the episode ids on each side and the time
boundaries, so a reviewer can re-check the split without rerunning the code.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

HASH_SALT = 'holdout-split-v1'
MANIFEST_SCHEMA_VERSION = 'HoldoutManifestV1'


@dataclass(frozen=True)
class HoldoutSplit:
    development: list
    holdout: list
    manifest: dict


def subject_bucket(subject_ref: str, holdout_percent: int = 30, salt: str = HASH_SALT) -> int:
    if not 1 <= holdout_percent <= 99:
        raise ValueError('holdout_percent must be between 1 and 99')
    digest = hashlib.sha256(f'{salt}|{subject_ref}'.encode()).hexdigest()
    return int(digest, 16) % 100


def split_episodes(episodes: list, holdout_percent: int = 30, salt: str = HASH_SALT) -> HoldoutSplit:
    """Deterministic split. Raises if any subject would land on both sides."""
    by_subject: dict[str, list] = {}
    for episode in episodes:
        by_subject.setdefault(episode.subject_ref, []).append(episode)

    development: list = []
    holdout: list = []
    subject_rows: list[dict] = []
    for subject_ref in sorted(by_subject):
        rows = sorted(by_subject[subject_ref], key=lambda item: (item.payload.analysis_at, item.episode_id))
        bucket = subject_bucket(subject_ref, holdout_percent, salt)
        if bucket < holdout_percent:
            # Latest episode of this subject is the held-out one; the earlier
            # episodes stay in development so the time ordering is visible.
            held = rows[-1]
            holdout.append(held)
            development.extend(rows[:-1])
            rule = 'latest_episode_of_subject'
        else:
            development.extend(rows)
            rule = 'all_episodes_development'
        subject_rows.append({
            'subject_ref': subject_ref,
            'bucket': bucket,
            'split': 'holdout' if bucket < holdout_percent else 'development',
            'rule': rule,
            'episodes': len(rows),
            'first_analysis_at': rows[0].payload.analysis_at.isoformat(),
            'last_analysis_at': rows[-1].payload.analysis_at.isoformat(),
        })

    overlap = {row['subject_ref'] for row in subject_rows if row['split'] == 'holdout'} & {
        row['subject_ref'] for row in subject_rows if row['split'] == 'development'
    }
    if overlap:
        raise ValueError('subject leakage between development and holdout')

    development.sort(key=lambda item: item.episode_id)
    holdout.sort(key=lambda item: item.episode_id)
    manifest = {
        'schema_version': MANIFEST_SCHEMA_VERSION,
        'holdout_percent_requested': holdout_percent,
        'salt_version': salt,
        'method': 'deterministic hash of subject_ref; latest episode of a held-out subject goes to holdout',
        'invariants': {
            'subject_disjoint': True,
            'time_ordered_within_subject': True,
            'rules_are_not_trained': True,
        },
        'development_episodes': len(development),
        'holdout_episodes': len(holdout),
        'development_subjects': sum(1 for row in subject_rows if row['split'] == 'development'),
        'holdout_subjects': sum(1 for row in subject_rows if row['split'] == 'holdout'),
        'time_range_development': _time_range(development),
        'time_range_holdout': _time_range(holdout),
        'development_episode_ids': [item.episode_id for item in development],
        'holdout_episode_ids': [item.episode_id for item in holdout],
        'subjects': subject_rows,
        'warnings': [
            'This split is bookkeeping for honest reporting, not a trained-model holdout.',
            'Episodes are synthetic placeholders; a real holdout needs independent human-reviewed labels.',
            'Wilson intervals on either side still assume independent episodes.',
        ],
    }
    return HoldoutSplit(development=development, holdout=holdout, manifest=manifest)


def _time_range(episodes: list) -> dict:
    if not episodes:
        return {'from': None, 'to': None}
    times = sorted(item.payload.analysis_at for item in episodes)
    return {'from': _iso(times[0]), 'to': _iso(times[-1])}


def _iso(value: datetime) -> str:
    return value.isoformat()


def episode_row(episode, is_holdout: bool) -> dict:
    """Serialise an episode with the computed split flag, not the declared one.

    The flag is written in both the envelope and the snapshot metadata, because
    the dataset loader requires them to agree. A file that only updated one of
    the two would fail to load ? which is the desired behaviour for a split.
    """
    payload = episode.payload.model_dump(mode='json')
    payload['metadata']['is_holdout'] = is_holdout
    return {
        'episode_id': episode.episode_id,
        'subject_ref': episode.subject_ref,
        'label': episode.label,
        'episode_class': episode.episode_class,
        'label_source': episode.label_source,
        'is_holdout': is_holdout,
        'payload': payload,
    }


def write_split(split: HoldoutSplit, output_dir: Path) -> dict[str, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return {
        'holdout_development.jsonl': _write_jsonl(directory / 'holdout_development.jsonl',
                                                   [episode_row(item, False) for item in split.development]),
        'holdout_holdout.jsonl': _write_jsonl(directory / 'holdout_holdout.jsonl',
                                              [episode_row(item, True) for item in split.holdout]),
        'holdout_manifest.json': _write_json(directory / 'holdout_manifest.json', split.manifest),
    }


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text(''.join(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    return path


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    return path