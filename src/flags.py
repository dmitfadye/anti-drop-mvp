"""Feature flags for the P1 layer. Safe default state is demo/synthetic only.

Every P1 capability is opt-in through the environment. Nothing here grants a
banking action: the flags unlock demonstration paths (operator sandbox screen,
experiment instrumentation, pre-transfer advisory), never real transfers,
blocks, freezes, OTP, cashback or support tickets.

Reading the environment through one module keeps the default state auditable:
`current_flags()` is echoed by /api/health so a jury can see what is on.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass

TRUTHY = frozenset({'1', 'true', 'yes', 'on', 'enable', 'enabled'})
FALSY = frozenset({'0', 'false', 'no', 'off', 'disable', 'disabled'})


class FlagError(ValueError):
    """Raised for an unparsable flag value instead of silently defaulting."""


def env_flag(name: str, default: bool = False) -> bool:
    """Explicit env parsing. Unknown values fail loudly rather than lying."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == '':
        return default
    value = raw.strip().lower()
    if value in TRUTHY:
        return True
    if value in FALSY:
        return False
    raise FlagError(f'{name} must be one of true/false, got {raw!r}')


def env_int(name: str, default: int, minimum: int = 0, maximum: int = 1_000_000) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == '':
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise FlagError(f'{name} must be an integer, got {raw!r}') from None
    if not minimum <= value <= maximum:
        raise FlagError(f'{name} must be between {minimum} and {maximum}, got {value}')
    return value


@dataclass(frozen=True)
class Flags:
    """Resolved P1 state. Defaults keep the widest surface switched off."""

    demo_mode: bool = True
    localization_enabled: bool = True
    operator_ui_enabled: bool = False
    operator_export_enabled: bool = False
    experiment_enabled: bool = False
    experiment_allow_draft_treatment: bool = False
    advisory_enabled: bool = False
    treatment_percent: int = 50
    experiment_id: str = 'exp-warning-language-2026.10'
    target_locale: str = 'uz-UZ'
    control_locale: str = 'ru-RU'
    case_store_path: str = ''
    operator_log_path: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


def current_flags() -> Flags:
    """Resolve flags from the environment. Called per request, never cached."""
    return Flags(
        demo_mode=env_flag('ANTI_DROP_DEMO_MODE', True),
        localization_enabled=env_flag('ANTI_DROP_LOCALIZATION_ENABLED', True),
        operator_ui_enabled=env_flag('ANTI_DROP_OPERATOR_UI_ENABLED', False),
        operator_export_enabled=env_flag('ANTI_DROP_OPERATOR_EXPORT_ENABLED', False),
        experiment_enabled=env_flag('ANTI_DROP_EXPERIMENT_ENABLED', False),
        experiment_allow_draft_treatment=env_flag('ANTI_DROP_EXPERIMENT_ALLOW_DRAFT_TREATMENT', False),
        advisory_enabled=env_flag('ANTI_DROP_ADVISORY_ENABLED', False),
        treatment_percent=env_int('ANTI_DROP_EXPERIMENT_TREATMENT_PERCENT', 50, 1, 99),
        experiment_id=os.environ.get('ANTI_DROP_EXPERIMENT_ID', 'exp-warning-language-2026.10').strip() or 'exp-warning-language-2026.10',
        target_locale=os.environ.get('ANTI_DROP_TARGET_LOCALE', 'uz-UZ').strip() or 'uz-UZ',
        control_locale=os.environ.get('ANTI_DROP_CONTROL_LOCALE', 'ru-RU').strip() or 'ru-RU',
        case_store_path=os.environ.get('ANTI_DROP_OPERATOR_CASE_STORE', '').strip(),
        operator_log_path=os.environ.get('ANTI_DROP_OPERATOR_LOG', '').strip(),
    )


SANDBOX_BANNER = 'Локальная песочница. Синтетические данные. Не банковская система поддержки.'
SANDBOX_BANNER_EN = 'Local sandbox. Synthetic data. Not a bank support system.'