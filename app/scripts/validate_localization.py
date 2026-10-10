"""Validate the localization packs and warning templates.

    python -m scripts.validate_localization

Exits non-zero when a pack or template violates its contract, when a required
message key is missing, or when the target locale is not present at all. A
`draft` status is reported, not treated as a failure: an unreviewed translation
is a known state, and the UI badges it. What this script refuses is a pack that
*claims* a review that is not recorded, and text that promises a banking action.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.localization import LocalizationRegistry, validate_packs  # noqa: E402
from src.templates import validate_templates  # noqa: E402

BLOCKING_KEYWORDS = ('заблокирован', 'заморажив', '6 лет', 'otp', 'кешбэк', 'поддержка ответит')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--locales-dir', type=Path, default=None)
    parser.add_argument('--templates-dir', type=Path, default=None)
    parser.add_argument('--require-locale', action='append', default=[],
                        help='locale that must exist, e.g. --require-locale uz-UZ')
    parser.add_argument('--fallback-locale', default='ru-RU',
                        help='locale that supplies missing keys; named in the warnings')
    parser.add_argument('--strict', action='store_true',
                        help='treat incomplete packs as blocking instead of warning')
    args = parser.parse_args()

    # A contract breach blocks; an incomplete pack only warns, because the
    # fallback path handles it safely and is logged as translation_fallback.
    problems: list[str] = []
    warnings: list[str] = []
    pack_rows = validate_packs(args.locales_dir)
    template_rows = validate_templates(args.templates_dir)

    for row in pack_rows:
        if not row['ok']:
            problems.append(f'locale pack {row["file"]}: {row["reason"]}')
            continue
        if row['missing_keys']:
            warnings.append(f'locale {row["locale"]} is missing keys: {", ".join(row["missing_keys"])} '
                            f'(they fall back to {args.fallback_locale} and are logged as translation_fallback)')
    for row in template_rows:
        if not row['ok']:
            problems.append(f'template {row["file"]}: {row["reason"]}')

    registry = LocalizationRegistry(args.locales_dir).refresh()
    for locale in args.require_locale:
        if registry.pack(locale) is None:
            problems.append(f'required locale is absent: {locale}')

    if not pack_rows:
        problems.append('no locale packs found')
    if not template_rows:
        problems.append('no warning templates found')
    if args.strict:
        problems.extend(warnings)
        warnings = []

    statuses = {row['locale']: row.get('status') for row in pack_rows if row['ok']}
    template_statuses = {row['template_id']: row.get('status') for row in template_rows if row['ok']}

    print(json.dumps({
        'locales': pack_rows,
        'templates': template_rows,
        'locale_statuses': statuses,
        'template_statuses': template_statuses,
        'approved_locales': sorted(locale for locale, status in statuses.items() if status == 'approved'),
        'approved_templates': sorted(name for name, status in template_statuses.items() if status == 'approved'),
        'experiment_treatment_available': bool(template_statuses) and all(
            status == 'approved' for name, status in template_statuses.items() if 'treatment' in name),
        'problems': problems,
        'warnings': warnings,
        'ok': not problems,
        'note': ('draft is a valid state and must stay badged in the UI. This gate blocks on contract '
                 'breaches and unreviewed claims; incomplete packs are warnings because the fallback '
                 'path is logged. Use --strict to make them blocking.'),
    }, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())