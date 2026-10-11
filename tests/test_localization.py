"""LocalizationPackV1 contract tests: honest statuses, safe text, visible fallback."""
import json
import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.localization import (  # noqa: E402
    ALLOWED_VARIABLES,
    FORBIDDEN_PHRASES,
    REQUIRED_MESSAGE_KEYS,
    LocalizationPackError,
    LocalizationPackV1,
    LocalizationRegistry,
    LocalizationReviewerV1,
    load_pack,
    registry,
    validate_packs,
)

LOCALES_DIR = Path(__file__).resolve().parent.parent / 'locales'


def base_pack(**overrides) -> dict:
    pack = {
        'schema_version': 'LocalizationPackV1',
        'locale': 'zz-ZZ', 'language_code': 'zz',
        'display_name_native': 'Test', 'display_name_en': 'Test',
        'direction': 'ltr', 'script': 'Latn', 'status': 'draft',
        'reviewers': [],
        'messages': {key: f'text for {key}' for key in REQUIRED_MESSAGE_KEYS},
        'template_ids': [], 'fallback_locale': 'ru-RU', 'version': 'loc-zz-v1',
    }
    pack.update(overrides)
    return pack


class TestPackContract(unittest.TestCase):
    def test_shipped_packs_are_valid_and_draft(self):
        rows = validate_packs(LOCALES_DIR)
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(row['file']):
                self.assertTrue(row['ok'], row['reason'])
                self.assertIn(row['status'], ('draft', 'native_reviewed', 'legal_reviewed', 'approved'))
        statuses = {row['locale']: row['status'] for row in rows}
        self.assertEqual(statuses.get('ru-RU'), 'draft')
        self.assertEqual(statuses.get('uz-UZ'), 'draft')
        self.assertEqual(len(statuses), 2, 'exactly two packs: control + one target language')

    def test_draft_pack_requires_a_badge(self):
        pack = load_pack(LOCALES_DIR / 'uz-UZ.json')
        self.assertFalse(pack.is_approved)
        self.assertIsNotNone(pack.draft_badge())
        self.assertIn('не проверен носителем', pack.draft_badge())

    def test_status_cannot_outrun_the_review_trail(self):
        for status in ('native_reviewed', 'legal_reviewed', 'approved'):
            with self.subTest(status=status):
                with self.assertRaises(ValidationError):
                    LocalizationPackV1.model_validate(base_pack(status=status))
        approved = base_pack(status='approved', reviewers=[
            LocalizationReviewerV1(role='native_reviewer', reviewed_at='2026-10-20T09:00:00Z',
                                   review_hash_or_pseudonym='n1').model_dump(),
            LocalizationReviewerV1(role='legal_reviewer', reviewed_at='2026-10-21T09:00:00Z',
                                   review_hash_or_pseudonym='l1').model_dump()])
        LocalizationPackV1.model_validate(approved)  # now allowed
        approved['reviewers'][0]['review_hash_or_pseudonym'] = None
        with self.assertRaises(ValidationError):
            LocalizationPackV1.model_validate(approved)

    def test_html_entities_and_markup_are_refused(self):
        for text in ('<b>bold</b>', 'нажмите &laquo;сюда&raquo;', 'javascript:alert(1)', '<img src=x>'):
            with self.subTest(text=text):
                messages = {key: f'text for {key}' for key in REQUIRED_MESSAGE_KEYS}
                messages['alert.red.body'] = text
                with self.assertRaises(ValidationError):
                    LocalizationPackV1.model_validate(base_pack(messages=messages))

    def test_forbidden_claims_are_refused(self):
        for phrase in FORBIDDEN_PHRASES:
            with self.subTest(phrase=phrase):
                messages = {key: f'text for {key}' for key in REQUIRED_MESSAGE_KEYS}
                messages['cta.help'] = f'Ваш счёт {phrase} в банке'
                with self.assertRaises(ValidationError):
                    LocalizationPackV1.model_validate(base_pack(messages=messages))

    def test_placeholders_are_restricted(self):
        messages = {key: f'text for {key}' for key in REQUIRED_MESSAGE_KEYS}
        messages['alert.red.body'] = 'сумма {amount}, причина {internal_rule_id}'
        with self.assertRaises(ValidationError):
            LocalizationPackV1.model_validate(base_pack(messages=messages))
        messages['alert.red.body'] = 'сумма {amount} {currency} причина {reason_short} шаг {next_step}'
        LocalizationPackV1.model_validate(base_pack(messages=messages))

    def test_unknown_message_key_and_empty_message(self):
        messages = {key: f'text for {key}' for key in REQUIRED_MESSAGE_KEYS}
        messages['alert.secret'] = 'x'
        with self.assertRaises(ValidationError):
            LocalizationPackV1.model_validate(base_pack(messages=messages))
        messages = {key: f'text for {key}' for key in REQUIRED_MESSAGE_KEYS}
        messages['cta.help'] = '   '
        with self.assertRaises(ValidationError):
            LocalizationPackV1.model_validate(base_pack(messages=messages))

    def test_unknown_locale_and_key_raise_not_silently_fall_back(self):
        local = registry()
        with self.assertRaises(LocalizationPackError):
            local.resolve('xx-XX', 'alert.red.title')
        with self.assertRaises(LocalizationPackError):
            local.resolve('ru-RU', 'alert.magenta.title')

    def test_allowed_variables_are_exactly_the_documented_set(self):
        self.assertEqual(set(ALLOWED_VARIABLES), {'amount', 'currency', 'reason_short', 'next_step', 'lang_name'})

    def test_reviewed_at_must_be_iso_utc(self):
        with self.assertRaises(ValidationError):
            LocalizationReviewerV1(role='native_reviewer', reviewed_at='20.10.2026')
        LocalizationReviewerV1(role='native_reviewer', reviewed_at='2026-10-20T09:00:00+03:00')

    def test_reviewer_pseudonym_rejects_pii_shapes(self):
        for value in ('Ivan Ivanov', 'ivan@example.com', '+79990000000'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    LocalizationReviewerV1(role='native_reviewer', reviewed_at='2026-10-20T09:00:00Z',
                                           review_hash_or_pseudonym=value)


class TestFallbackIsVisible(unittest.TestCase):
    def setUp(self):
        self.registry = LocalizationRegistry(LOCALES_DIR).refresh()

    def test_target_locale_falls_back_and_reports_it(self):
        # uz-UZ deliberately lacks privacy.notice so this path is observable.
        pack = self.registry.pack('uz-UZ')
        self.assertNotIn('privacy.notice', pack.messages)
        resolved = self.registry.resolve('uz-UZ', 'privacy.notice')
        self.assertTrue(resolved.used_fallback)
        self.assertEqual(resolved.locale, 'uz-UZ')
        self.assertIsNotNone(resolved.draft_badge)
        native = self.registry.resolve('uz-UZ', 'alert.red.title')
        self.assertFalse(native.used_fallback)

    def test_describe_lists_missing_keys(self):
        described = {row['locale']: row for row in self.registry.describe()}
        self.assertEqual(described['uz-UZ']['missing_keys'], ['privacy.notice'])
        self.assertEqual(described['ru-RU']['missing_keys'], [])

    def test_render_ignores_unknown_variables(self):
        rendered = self.registry.render('ru-RU', 'alert.red.body',
                                       {'amount': '15000', 'currency': 'RUB', 'secret': 'DO_NOT_LEAK'})
        self.assertIn('15000', rendered.text)
        self.assertNotIn('DO_NOT_LEAK', rendered.text)

    def test_broken_pack_is_reported_not_loaded(self):
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            broken = Path(folder) / 'zz-ZZ.json'
            broken.write_text(json.dumps(base_pack(locale='zz-ZZ', language_code='zz',
                                                   messages={'alert.red.title': '<b>x</b>'})), encoding='utf-8')
            rows = validate_packs(folder)
            self.assertEqual(len(rows), 1)
            self.assertFalse(rows[0]['ok'])
            self.assertIn('alert.red.title', rows[0]['reason'])
            self.assertEqual(LocalizationRegistry(folder).refresh().locales, [])

    def test_duplicate_locale_is_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            for name in ('a-AA.json', 'b-AA.json'):
                (Path(folder) / name).write_text(json.dumps(base_pack(locale='aa-AA', language_code='aa')),
                                                 encoding='utf-8')
            local = LocalizationRegistry(folder).refresh()
            self.assertEqual(local.locales, ['aa-AA'])
            self.assertTrue(any('duplicate' in reason for reason in local.load_errors.values()))


if __name__ == '__main__':
    unittest.main()