"""LocalizationPackV1: one honest locale at a time, with a review trail.

The P0 demo claimed seven languages. P1 replaces that claim with a workflow:
every pack declares its own `status`, the UI must badge anything below
`approved`, and a missing key falls back to the control locale with a logged
`translation_fallback` instead of silently changing meaning.

Rules enforced here, not by convention:
- messages are plain text: no HTML, no markup, no style attributes;
- interpolation is limited to a fixed placeholder allowlist;
- forbidden phrases (categorical legal/blocking claims) are rejected on load;
- a pack without an `approved` status can never be presented as approved.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from anti_drop_ml.contracts import ClosedModel

LOCALES_DIR = Path(__file__).resolve().parent.parent / 'locales'

LocaleStatus = Literal['draft', 'native_reviewed', 'legal_reviewed', 'approved', 'deprecated']
Direction = Literal['ltr', 'rtl']
Script = Literal['Latn', 'Cyrl', 'Arab', 'other']

# Only these tokens may be interpolated, and only these message keys exist.
ALLOWED_VARIABLES = ('amount', 'currency', 'reason_short', 'next_step', 'lang_name')

REQUIRED_MESSAGE_KEYS = (
    'alert.red.title',
    'alert.red.body',
    'alert.yellow.title',
    'alert.yellow.body',
    'cta.help',
    'cta.sandbox_notice',
    'legal.disclaimer',
    'privacy.notice',
)

_PLACEHOLDER = re.compile(r'\{([a-z_]{1,24})\}')
_HTML_MARKUP = re.compile(r'<[a-zA-Z/!][^>]*>|&[a-z]+;|javascript:', re.IGNORECASE)

# Categorical legal/blocking claims. Present in several languages so a pack
# cannot smuggle a promise through in the target locale.
FORBIDDEN_PHRASES = (
    'заблокирован', 'заблокирована', 'заблокированы', 'заморажив', 'заморожено',
    'заморожены', 'деньги заморожены', '6 лет', 'шесть лет', 'вы соучастник',
    'соучастник', 'otp', 'otp подтверждён', 'кешбэк начислен', 'кэшбэк начислен',
    'вернули деньги', 'support will answer within', 'ответит за 2 минуты',
)


class LocalizationPackError(ValueError):
    """A pack file violated the pack contract; refuses to load."""


class LocalizationReviewerV1(ClosedModel):
    role: Literal['native_reviewer', 'legal_reviewer', 'product_reviewer']
    reviewed_at: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$')
    # Pseudonym or content hash only: reviewer identity is not published as PII.
    review_hash_or_pseudonym: str | None = Field(default=None, max_length=128, pattern=r'^[a-zA-Z0-9._:/-]+$')


class LocalizationPackV1(ClosedModel):
    schema_version: Literal['LocalizationPackV1']
    locale: str = Field(pattern=r'^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$')
    language_code: str = Field(pattern=r'^[a-z]{2,3}$')
    display_name_native: str = Field(min_length=1, max_length=64)
    display_name_en: str = Field(min_length=1, max_length=64)
    direction: Direction
    script: Script
    status: LocaleStatus
    reviewers: list[LocalizationReviewerV1] = Field(default_factory=list, max_length=32)
    messages: dict[str, str]
    template_ids: list[str] = Field(default_factory=list, max_length=32)
    fallback_locale: str = Field(pattern=r'^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$')
    version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    synthetic: bool = True
    notes: str | None = Field(default=None, max_length=400)

    @field_validator('messages')
    @classmethod
    def _messages_are_plain_safe_text(cls, value: dict[str, str]) -> dict[str, str]:
        for key, text in value.items():
            if key not in REQUIRED_MESSAGE_KEYS:
                raise ValueError(f'unknown message key: {key}')
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f'message {key} must be non-empty plain text')
            if _HTML_MARKUP.search(text):
                raise ValueError(f'message {key} must not contain HTML or entities')
            for token in _PLACEHOLDER.findall(text):
                if token not in ALLOWED_VARIABLES:
                    raise ValueError(f'message {key} uses forbidden placeholder {{{token}}}')
            lowered = text.lower()
            for phrase in FORBIDDEN_PHRASES:
                if phrase in lowered:
                    raise ValueError(f'message {key} contains forbidden claim: {phrase}')
        return value

    @model_validator(mode='after')
    def _review_trail_matches_status(self):
        roles = {reviewer.role for reviewer in self.reviewers}
        if self.status in ('native_reviewed', 'legal_reviewed', 'approved') and 'native_reviewer' not in roles:
            raise ValueError('status claims native review but no native_reviewer is recorded')
        if self.status in ('legal_reviewed', 'approved') and 'legal_reviewer' not in roles:
            raise ValueError('status claims legal review but no legal_reviewer is recorded')
        if self.status == 'approved' and self.reviewers:
            for reviewer in self.reviewers:
                if not reviewer.review_hash_or_pseudonym:
                    raise ValueError('approved packs need a pseudonymised review attestation')
        return self

    @property
    def is_approved(self) -> bool:
        return self.status == 'approved'

    def draft_badge(self) -> str | None:
        """Mandatory UI marker whenever the pack is not approved."""
        return None if self.is_approved else _STATUS_BADGE[self.status]


_STATUS_BADGE = {
    'draft': 'черновой перевод • не проверен носителем • experimental template',
    'native_reviewed': 'перевод проверен носителем, но не юридически • draft for pilot',
    'legal_reviewed': 'юридически проверен, но статус approved ещё не подтверждён банком',
    'deprecated': 'перевод выведен из оборота • deprecated',
}


@dataclass(frozen=True)
class ResolvedMessage:
    locale: str
    key: str
    text: str
    used_fallback: bool
    pack_status: LocaleStatus
    draft_badge: str | None

    def as_dict(self) -> dict:
        return {
            'locale': self.locale,
            'key': self.key,
            'text': self.text,
            'used_fallback': self.used_fallback,
            'pack_status': self.pack_status,
            'draft_badge': self.draft_badge,
        }


class LocalizationRegistry:
    """Loads packs from disk once and resolves keys with an explicit fallback.

    A fallback is reported, never silent: callers get `used_fallback=True` so
    the event stream can record `translation_fallback`.
    """

    def __init__(self, locales_dir: Path | None = None) -> None:
        self._dir = Path(locales_dir) if locales_dir else LOCALES_DIR
        self._packs: dict[str, LocalizationPackV1] = {}
        self._load_errors: dict[str, str] = {}

    def _load_dir(self) -> None:
        if not self._dir.is_dir():
            return
        for path in sorted(self._dir.glob('*.json')):
            try:
                pack = LocalizationPackV1.model_validate(json.loads(path.read_text(encoding='utf-8')))
            except (OSError, ValidationError, json.JSONDecodeError) as exc:
                self._load_errors[path.name] = _first_message(exc)
                continue
            if pack.locale in self._packs:
                self._load_errors[path.name] = f'duplicate locale {pack.locale}'
                continue
            self._packs[pack.locale] = pack

    def refresh(self) -> 'LocalizationRegistry':
        self._packs.clear()
        self._load_errors.clear()
        self._load_dir()
        return self

    @property
    def locales(self) -> list[str]:
        return sorted(self._packs)

    @property
    def load_errors(self) -> dict[str, str]:
        return dict(self._load_errors)

    def pack(self, locale: str) -> LocalizationPackV1 | None:
        return self._packs.get(locale)

    def describe(self) -> list[dict]:
        return [
            {
                'locale': pack.locale,
                'language_code': pack.language_code,
                'display_name_native': pack.display_name_native,
                'display_name_en': pack.display_name_en,
                'direction': pack.direction,
                'script': pack.script,
                'status': pack.status,
                'version': pack.version,
                'synthetic': pack.synthetic,
                'draft_badge': pack.draft_badge(),
                'reviewers': [{'role': r.role, 'reviewed_at': r.reviewed_at} for r in pack.reviewers],
                'missing_keys': sorted(set(REQUIRED_MESSAGE_KEYS) - set(pack.messages)),
            }
            for pack in sorted(self._packs.values(), key=lambda p: p.locale)
        ]

    def resolve(self, locale: str, key: str, fallback_locale: str = 'ru-RU') -> ResolvedMessage:
        if key not in REQUIRED_MESSAGE_KEYS:
            raise LocalizationPackError(f'unknown message key: {key}')
        pack = self._packs.get(locale)
        if pack is None:
            raise LocalizationPackError(f'unknown locale: {locale}')
        if key in pack.messages:
            return ResolvedMessage(pack.locale, key, pack.messages[key], False, pack.status, pack.draft_badge())
        fallback = self._packs.get(fallback_locale) or self._packs.get(pack.fallback_locale)
        if fallback is None or key not in fallback.messages:
            raise LocalizationPackError(f'no text for {key} in {locale} or {fallback_locale}')
        return ResolvedMessage(pack.locale, key, fallback.messages[key], True, pack.status, pack.draft_badge())

    def render(self, locale: str, key: str, values: dict[str, str] | None = None, fallback_locale: str = 'ru-RU') -> ResolvedMessage:
        """Interpolate with the allowlist only; unknown variables are dropped."""
        resolved = self.resolve(locale, key, fallback_locale)
        # Fill every allowed placeholder: a missing value must not abort the
        # interpolation and leave raw braces in front of the client.
        safe = {name: str(value) for name, value in (values or {}).items() if name in ALLOWED_VARIABLES}
        safe.update({name: '?' for name in ALLOWED_VARIABLES if name not in safe})
        try:
            text = resolved.text.format(**safe)
        except (KeyError, IndexError, ValueError):
            # Defensive only: with the allowlist filled in, format cannot fail on
            # a missing placeholder. Never surface a raw KeyError to the UI.
            text = resolved.text
        return ResolvedMessage(resolved.locale, key, text, resolved.used_fallback, resolved.pack_status, resolved.draft_badge)

    def locale_options(self, include_deprecated: bool = False) -> list[dict]:
        return [
            {'locale': entry['locale'], 'display_name_native': entry['display_name_native'],
             'display_name_en': entry['display_name_en'], 'direction': entry['direction'],
             'status': entry['status'], 'draft_badge': entry['draft_badge']}
            for entry in self.describe()
            if include_deprecated or entry['status'] != 'deprecated'
        ]


def _first_message(exc: Exception) -> str:
    """Short, payload-free reason for a broken pack file."""
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        if errors:
            location = '.'.join(str(part) for part in errors[0].get('loc', ()))
            return f'{location}: {errors[0].get("msg", "invalid")}'
        return 'invalid pack'
    return 'unreadable pack file'


def load_pack(path: Path) -> LocalizationPackV1:
    """Load a single pack from an explicit path, raising on any contract breach."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    try:
        return LocalizationPackV1.model_validate(data)
    except ValidationError as exc:
        raise LocalizationPackError(f'{Path(path).name}: {_first_message(exc)}') from None


def validate_packs(locales_dir: Path | str | None = None) -> list[dict]:
    """Return one row per pack file with ok/missing keys/bad status reason."""
    directory = Path(locales_dir) if locales_dir else LOCALES_DIR
    rows: list[dict] = []
    if not directory.is_dir():
        return [{'file': None, 'locale': None, 'ok': False, 'reason': 'locales directory missing', 'missing_keys': []}]
    for path in sorted(directory.glob('*.json')):
        try:
            pack = load_pack(path)
        except (LocalizationPackError, OSError, json.JSONDecodeError) as exc:
            rows.append({'file': path.name, 'locale': None, 'ok': False, 'reason': str(exc), 'missing_keys': []})
            continue
        missing = sorted(set(REQUIRED_MESSAGE_KEYS) - set(pack.messages))
        rows.append({'file': path.name, 'locale': pack.locale, 'ok': True, 'reason': None, 'missing_keys': missing,
                     'status': pack.status, 'direction': pack.direction, 'draft_badge': pack.draft_badge()})
    return rows


def known_locales(locales_dir: Path | str | None = None) -> Iterable[str]:
    for row in validate_packs(locales_dir):
        if row['ok'] and row['locale']:
            yield row['locale']


_REGISTRY = LocalizationRegistry()


def registry() -> LocalizationRegistry:
    return _REGISTRY.refresh()