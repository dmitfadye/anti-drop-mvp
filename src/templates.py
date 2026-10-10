"""TemplateVariantV1: a warning is (decision, locale, copy) — never a new score.

Control and treatment exist to isolate one variable for the language
experiment, so this module refuses to do the two tempting things:
1. let a template influence scoring — rendering has no access to the detector
   and takes the level as an input, never as a computation;
2. let an unapproved variant masquerade as approved — every render returns the
   status and the mandatory draft badge, and the experiment layer treats a
   non-approved treatment arm as unavailable rather than used.

Placeholders are a closed allowlist and forbidden phrases are checked on both
load and render, so a later copy edit cannot bypass the guard.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from anti_drop_ml.contracts import ClosedModel
from src.localization import (
    FORBIDDEN_PHRASES,
    LocalizationPackError,
    LocalizationRegistry,
    ResolvedMessage,
    registry,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / 'templates'

TEMPLATE_SCHEMA_VERSION = 'TemplateVariantV1'
VARIABLE_PATTERN = re.compile(r'^[a-z][a-z0-9_]{0,23}$')

TemplateLevels = Literal['RED', 'YELLOW', 'GREEN']
TemplateStatuses = Literal['draft', 'native_reviewed', 'legal_reviewed', 'approved', 'deprecated']
TemplateArms = Literal['control', 'treatment']

MESSAGE_KEYS_BY_LEVEL = {
    'RED': ('alert.red.title', 'alert.red.body'),
    'YELLOW': ('alert.yellow.title', 'alert.yellow.body'),
    'GREEN': ('alert.yellow.title', 'alert.yellow.body'),
}

CONTROL_TEMPLATE_ID = 'warning_ru_control_v1'
CONTROL_TEMPLATE_ID_YELLOW = 'warning_ru_control_yellow_v1'
TREATMENT_TEMPLATE_ID = 'warning_uz_treatment_v1'
TREATMENT_TEMPLATE_ID_YELLOW = 'warning_uz_treatment_yellow_v1'
CONTROL_LOCALE = 'ru-RU'
TREATMENT_LOCALE = 'uz-UZ'


class TemplateError(ValueError):
    """A template file or render request violated the template contract."""


class TemplateReviewerV1(ClosedModel):
    role: Literal['native_reviewer', 'legal_reviewer', 'product_reviewer']
    reviewed_at: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$')
    # Attestation pseudonym or content hash only — reviewer identity is not PII here.
    review_hash_or_pseudonym: str | None = Field(default=None, max_length=128, pattern=r'^[a-zA-Z0-9._:/-]+$')


class TemplateVariantV1(ClosedModel):
    schema_version: Literal['TemplateVariantV1'] = TEMPLATE_SCHEMA_VERSION
    template_id: str = Field(pattern=r'^[a-z0-9_]{3,64}$')
    version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,40}$')
    locale: str = Field(pattern=r'^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$')
    risk_level: TemplateLevels
    status: TemplateStatuses
    arm: TemplateArms = 'control'
    experiment_id: str | None = Field(default=None, pattern=r'^exp-[a-z0-9.-]{1,60}$')
    title_key: str = Field(pattern=r'^alert\.[a-z]+\.title$')
    body_key: str = Field(pattern=r'^alert\.[a-z]+\.body$')
    cta_key: Literal['cta.help', 'cta.sandbox_notice']
    legal_review_required: bool = True
    native_review_required: bool = True
    variables_allowed: list[str] = Field(default_factory=list, max_length=16)
    forbidden_phrases: list[str] = Field(default_factory=list, max_length=64)
    reviewers: list[TemplateReviewerV1] = Field(default_factory=list, max_length=32)
    created_at: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$')
    approved_at: str | None = Field(default=None, pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$')

    @field_validator('variables_allowed')
    @classmethod
    def _variables_are_safe(cls, value: list[str]) -> list[str]:
        for name in value:
            if not VARIABLE_PATTERN.match(name):
                raise ValueError(f'unsafe variable name: {name}')
        return value

    @model_validator(mode='after')
    def _status_matches_review_trail(self):
        roles = {reviewer.role for reviewer in self.reviewers}
        if self.status in ('native_reviewed', 'legal_reviewed', 'approved'):
            if self.native_review_required and 'native_reviewer' not in roles:
                raise ValueError('status claims native review but no native_reviewer is recorded')
        if self.status in ('legal_reviewed', 'approved'):
            if self.legal_review_required and 'legal_reviewer' not in roles:
                raise ValueError('status claims legal review but no legal_reviewer is recorded')
        if self.status == 'approved':
            if not self.approved_at:
                raise ValueError('approved templates require approved_at')
            if not all(reviewer.review_hash_or_pseudonym for reviewer in self.reviewers):
                raise ValueError('approved templates need a pseudonymised review attestation')
        elif self.approved_at:
            raise ValueError('approved_at is only allowed for approved templates')
        return self

    @property
    def is_approved(self) -> bool:
        return self.status == 'approved'


class RenderedWarning(ClosedModel):
    """Everything the UI needs, including the honesty markers."""

    schema_version: Literal['RenderedWarningV1'] = 'RenderedWarningV1'
    template_id: str
    template_version: str
    template_status: TemplateStatuses
    arm: TemplateArms
    experiment_id: str | None = None
    locale: str
    language_name: str
    direction: Literal['ltr', 'rtl'] = 'ltr'
    risk_level: TemplateLevels
    title: str
    body: str
    cta: str
    sandbox_notice: str
    legal_disclaimer: str
    privacy_notice: str
    used_fallback_keys: list[str] = Field(default_factory=list)
    draft_badge: str | None = None
    score_is_not_probability: Literal[True] = True
    localization_version: str | None = None

    def as_dict(self) -> dict:
        return self.model_dump(mode='json')


class TemplateRegistry:
    """Loads versioned templates from disk; used by the API and by scripts."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._dir = Path(templates_dir) if templates_dir else TEMPLATES_DIR
        self._templates: dict[str, TemplateVariantV1] = {}
        self._load_errors: dict[str, str] = {}

    def refresh(self) -> 'TemplateRegistry':
        self._templates.clear()
        self._load_errors.clear()
        if not self._dir.is_dir():
            return self
        for path in sorted(self._dir.glob('*.json')):
            try:
                template = TemplateVariantV1.model_validate(json.loads(path.read_text(encoding='utf-8')))
            except (OSError, ValidationError, json.JSONDecodeError) as exc:
                self._load_errors[path.name] = _short_reason(exc)
                continue
            if template.template_id in self._templates:
                self._load_errors[path.name] = f'duplicate template_id {template.template_id}'
                continue
            self._templates[template.template_id] = template
        return self

    @property
    def load_errors(self) -> dict[str, str]:
        return dict(self._load_errors)

    def get(self, template_id: str) -> TemplateVariantV1:
        template = self._templates.get(template_id)
        if template is None:
            raise TemplateError(f'unknown template_id: {template_id}')
        return template

    def describe(self) -> list[dict]:
        return [
            {'template_id': t.template_id, 'version': t.version, 'locale': t.locale, 'risk_level': t.risk_level,
             'status': t.status, 'arm': t.arm, 'experiment_id': t.experiment_id, 'is_approved': t.is_approved,
             'legal_review_required': t.legal_review_required, 'native_review_required': t.native_review_required,
             'variables_allowed': t.variables_allowed, 'approved_at': t.approved_at,
             'reviewers': [{'role': r.role, 'reviewed_at': r.reviewed_at} for r in t.reviewers]}
            for t in sorted(self._templates.values(), key=lambda t: t.template_id)
        ]


def load_template(path: Path) -> TemplateVariantV1:
    try:
        return TemplateVariantV1.model_validate(json.loads(Path(path).read_text(encoding='utf-8')))
    except ValidationError as exc:
        raise TemplateError(f'{Path(path).name}: {_short_reason(exc)}') from None
    except (OSError, json.JSONDecodeError):
        raise TemplateError(f'{Path(path).name}: unreadable template file') from None


def validate_templates(templates_dir: Path | str | None = None) -> list[dict]:
    directory = Path(templates_dir) if templates_dir else TEMPLATES_DIR
    if not directory.is_dir():
        return [{'file': None, 'template_id': None, 'ok': False, 'reason': 'templates directory missing'}]
    rows: list[dict] = []
    for path in sorted(directory.glob('*.json')):
        try:
            template = load_template(path)
        except TemplateError as exc:
            rows.append({'file': path.name, 'template_id': None, 'ok': False, 'reason': str(exc)})
            continue
        rows.append({'file': path.name, 'template_id': template.template_id, 'ok': True, 'reason': None,
                     'status': template.status, 'locale': template.locale, 'arm': template.arm})
    return rows


def template_id_for(locale: str, level: str) -> str:
    """Deterministic control/treatment mapping used by both arms of the experiment."""
    if locale == CONTROL_LOCALE:
        return CONTROL_TEMPLATE_ID if level == 'RED' else CONTROL_TEMPLATE_ID_YELLOW
    if locale == TREATMENT_LOCALE:
        return TREATMENT_TEMPLATE_ID if level == 'RED' else TREATMENT_TEMPLATE_ID_YELLOW
    raise TemplateError(f'no template variant bound to locale {locale}')


def render_warning(
    template_id: str,
    risk_level: str,
    values: dict[str, str] | None = None,
    localization_registry: LocalizationRegistry | None = None,
    templates_registry: TemplateRegistry | None = None,
) -> RenderedWarning:
    """Render a warning for an already-made decision. Never reads rules or scores."""
    templates = (templates_registry or TemplateRegistry().refresh()).get(template_id)
    if risk_level not in MESSAGE_KEYS_BY_LEVEL:
        raise TemplateError(f'unsupported risk_level: {risk_level}')
    if templates.risk_level != risk_level:
        raise TemplateError(f'template {template_id} is bound to {templates.risk_level}, decision level is {risk_level}')
    localization = localization_registry or registry()
    pack = localization.pack(templates.locale)
    if pack is None:
        raise LocalizationPackError(f'no localization pack for template locale {templates.locale}')
    if templates.title_key not in pack.messages and templates.body_key not in pack.messages:
        raise TemplateError(f'template {template_id} has no keys in pack {pack.locale}')

    resolved: list[ResolvedMessage] = [
        localization.render(templates.locale, templates.title_key, values, pack.fallback_locale),
        localization.render(templates.locale, templates.body_key, values, pack.fallback_locale),
        localization.render(templates.locale, templates.cta_key, values, pack.fallback_locale),
        localization.render(templates.locale, 'cta.sandbox_notice', values, pack.fallback_locale),
        localization.render(templates.locale, 'legal.disclaimer', values, pack.fallback_locale),
        localization.render(templates.locale, 'privacy.notice', values, pack.fallback_locale),
    ]
    for item in resolved:
        _assert_render_safe(item.text)
    title, body, cta, sandbox_notice, legal_disclaimer, privacy_notice = (item.text for item in resolved)
    return RenderedWarning(
        template_id=templates.template_id, template_version=templates.version, template_status=templates.status,
        arm=templates.arm, experiment_id=templates.experiment_id, locale=pack.locale,
        language_name=pack.display_name_native, direction=pack.direction, risk_level=risk_level,
        title=title, body=body, cta=cta, sandbox_notice=sandbox_notice,
        legal_disclaimer=legal_disclaimer, privacy_notice=privacy_notice,
        used_fallback_keys=sorted({item.key for item in resolved if item.used_fallback}),
        draft_badge=pack.draft_badge(), localization_version=pack.version,
    )


def _assert_render_safe(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            raise TemplateError(f'rendered text contains forbidden claim: {phrase}')


@dataclass(frozen=True)
class TemplatePair:
    """Control/treatment pair for one experiment; both pinned to one rule set."""

    experiment_id: str
    control_template_id: str
    treatment_template_id: str
    treatment_available: bool
    blocked_reason: str | None

    def as_dict(self) -> dict:
        return {
            'experiment_id': self.experiment_id,
            'control_template_id': self.control_template_id,
            'treatment_template_id': self.treatment_template_id,
            'treatment_available': self.treatment_available,
            'blocked_reason': self.blocked_reason,
        }


def resolve_pair(experiment_id: str, control_template_id: str, treatment_template_id: str) -> TemplatePair:
    """A treatment arm whose template is not approved is unavailable, not silently used."""
    templates = TemplateRegistry().refresh()
    treatment = templates.get(treatment_template_id)
    control = templates.get(control_template_id)
    if not treatment.is_approved:
        return TemplatePair(experiment_id, control.template_id, treatment.template_id, False,
                            f'treatment template status is "{treatment.status}", not "approved"')
    if treatment.locale == control.locale:
        return TemplatePair(experiment_id, control.template_id, treatment.template_id, False,
                            'treatment locale equals control locale; the experiment would isolate nothing')
    return TemplatePair(experiment_id, control.template_id, treatment.template_id, True, None)


def _short_reason(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        if errors:
            location = '.'.join(str(part) for part in errors[0].get('loc', ()))
            return f'{location}: {errors[0].get("msg", "invalid")}'
    return 'unreadable template file'