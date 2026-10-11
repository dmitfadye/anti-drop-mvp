"""TemplateVariantV1 tests: a template is copy, never a new score."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anti_drop_ml.adapter import RULE_VERSION, evaluate_snapshot  # noqa: E402
from anti_drop_ml.contracts import RiskSnapshotV1  # noqa: E402
from src.localization import LocalizationRegistry  # noqa: E402
from src.templates import (  # noqa: E402
    CONTROL_LOCALE,
    CONTROL_TEMPLATE_ID,
    CONTROL_TEMPLATE_ID_YELLOW,
    TREATMENT_LOCALE,
    TREATMENT_TEMPLATE_ID,
    TREATMENT_TEMPLATE_ID_YELLOW,
    RenderedWarning,
    TemplateError,
    TemplateRegistry,
    TemplateVariantV1,
    load_template,
    render_warning,
    resolve_pair,
    template_id_for,
    validate_templates,
)
from scripts.generate_synthetic_fixtures import _small_inbound, snapshot  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / 'templates'
LOCALES_DIR = ROOT / 'locales'


class TestTemplateContract(unittest.TestCase):
    def test_shipped_templates_are_valid_and_draft(self):
        rows = validate_templates(TEMPLATES_DIR)
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(row['file']):
                self.assertTrue(row['ok'], row['reason'])
                self.assertEqual(row['status'], 'draft')
        self.assertEqual(len(rows), 4)

    def test_approved_requires_reviewers_and_approved_at(self):
        payload = json.loads((TEMPLATES_DIR / 'warning_ru_control_v1.json').read_text(encoding='utf-8'))
        with self.assertRaises(ValidationError):
            TemplateVariantV1.model_validate({**payload, 'status': 'approved'})
        approved = {
            **payload, 'status': 'approved', 'approved_at': '2026-10-25T10:00:00Z',
            'reviewers': [
                {'role': 'native_reviewer', 'reviewed_at': '2026-10-24T10:00:00Z', 'review_hash_or_pseudonym': 'n1'},
                {'role': 'legal_reviewer', 'reviewed_at': '2026-10-25T10:00:00Z', 'review_hash_or_pseudonym': 'l1'},
            ],
        }
        template = TemplateVariantV1.model_validate(approved)
        self.assertTrue(template.is_approved)
        with self.assertRaises(ValidationError):
            TemplateVariantV1.model_validate({**payload, 'approved_at': '2026-10-25T10:00:00Z'})

    def test_variable_names_and_key_patterns_are_restricted(self):
        payload = json.loads((TEMPLATES_DIR / 'warning_ru_control_v1.json').read_text(encoding='utf-8'))
        for value in ['amount; DROP', '<script>', 'AMOUNT', '']:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    TemplateVariantV1.model_validate({**payload, 'variables_allowed': [value]})
        for value in ['cta.telegram', 'alert.red.title.html', 'https://example.com']:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    TemplateVariantV1.model_validate({**payload, 'title_key': value})


class TestRendering(unittest.TestCase):
    def setUp(self):
        self.templates = TemplateRegistry(TEMPLATES_DIR).refresh()
        self.locales = LocalizationRegistry(LOCALES_DIR).refresh()

    def render(self, template_id, level):
        return render_warning(template_id, level, values={'amount': '15000', 'currency': 'RUB',
                                                          'reason_short': 'транзит'},
                              localization_registry=self.locales, templates_registry=self.templates)

    def test_control_and_treatment_render_the_same_decision(self):
        control = self.render(CONTROL_TEMPLATE_ID, 'RED')
        treatment = self.render(TREATMENT_TEMPLATE_ID, 'RED')
        self.assertIsInstance(control, RenderedWarning)
        self.assertEqual(control.risk_level, treatment.risk_level)
        self.assertEqual(control.score_is_not_probability, treatment.score_is_not_probability)
        self.assertNotEqual(control.locale, treatment.locale)
        self.assertEqual(control.locale, CONTROL_LOCALE)
        self.assertEqual(treatment.locale, TREATMENT_LOCALE)

    def test_locale_never_changes_the_score(self):
        transactions = _small_inbound(5)
        decision = evaluate_snapshot(snapshot(transactions, 'tpl-test'))
        for locale in ('ru-RU', 'uz-UZ'):
            template_id = template_id_for(locale, decision.level)
            warning = self.render(template_id, decision.level)
            self.assertEqual(warning.score_is_not_probability, True)
            self.assertEqual(warning.risk_level, decision.level)
        # The decision object itself is unchanged by looking at either locale.
        self.assertEqual(evaluate_snapshot(snapshot(transactions, 'tpl-test')), decision)

    def test_level_mismatch_is_refused(self):
        with self.assertRaises(TemplateError):
            render_warning(CONTROL_TEMPLATE_ID, 'YELLOW', templates_registry=self.templates,
                           localization_registry=self.locales)
        with self.assertRaises(TemplateError):
            render_warning(CONTROL_TEMPLATE_ID, 'GREEN', templates_registry=self.templates,
                           localization_registry=self.locales)

    def test_unknown_template_and_locale(self):
        with self.assertRaises(TemplateError):
            self.templates.get('warning_nope_v1')
        with self.assertRaises(TemplateError):
            template_id_for('tg-TJ', 'RED')

    def test_draft_badge_and_fallback_are_reported(self):
        treatment = self.render(TREATMENT_TEMPLATE_ID, 'RED')
        self.assertEqual(treatment.template_status, 'draft')
        self.assertIsNotNone(treatment.draft_badge)
        self.assertIn('privacy.notice', treatment.used_fallback_keys)
        control = self.render(CONTROL_TEMPLATE_ID, 'RED')
        self.assertEqual(control.used_fallback_keys, [])

    def test_sandbox_and_legal_disclaimers_are_always_present(self):
        for template_id, level in ((CONTROL_TEMPLATE_ID, 'RED'), (TREATMENT_TEMPLATE_ID, 'RED'),
                                   (CONTROL_TEMPLATE_ID_YELLOW, 'YELLOW'),
                                   (TREATMENT_TEMPLATE_ID_YELLOW, 'YELLOW')):
            warning = self.render(template_id, level)
            with self.subTest(template_id=template_id):
                self.assertTrue(warning.sandbox_notice)
                self.assertTrue(warning.legal_disclaimer)
                self.assertTrue(warning.privacy_notice)
                self.assertIn('sandbox_notice', warning.as_dict())
                self.assertIn('legal_disclaimer', warning.as_dict())
                for field in ('title', 'body', 'cta'):
                    self.assertNotIn('<', getattr(warning, field))

    def test_rendered_text_never_promises_a_block(self):
        for phrase in ('заблокирован', 'заморожено', '6 лет', 'кешбэк', 'otp'):
            with self.subTest(phrase=phrase):
                for template_id, level in ((CONTROL_TEMPLATE_ID, 'RED'), (TREATMENT_TEMPLATE_ID, 'RED')):
                    warning = self.render(template_id, level)
                    self.assertNotIn(phrase, warning.body.lower())

    def test_yaml_style_template_file_is_rejected_with_reason(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'broken.json'
            path.write_text(json.dumps({'schema_version': 'TemplateVariantV1'}), encoding='utf-8')
            with self.assertRaises(TemplateError) as ctx:
                load_template(path)
            self.assertIn('template_id', str(ctx.exception))
            rows = validate_templates(folder)
            self.assertFalse(rows[0]['ok'])


class TestExperimentPair(unittest.TestCase):
    def test_draft_treatment_blocks_the_pair(self):
        pair = resolve_pair('exp-warning-language-2026.10', CONTROL_TEMPLATE_ID, TREATMENT_TEMPLATE_ID)
        self.assertFalse(pair.treatment_available)
        self.assertIn('draft', pair.blocked_reason)

    def test_approved_pair_is_available(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, source in (('c.json', 'warning_ru_control_v1.json'), ('t.json', 'warning_uz_treatment_v1.json')):
                payload = json.loads((TEMPLATES_DIR / source).read_text(encoding='utf-8'))
                payload.update(status='approved', approved_at='2026-10-25T10:00:00Z', reviewers=[
                    {'role': 'native_reviewer', 'reviewed_at': '2026-10-24T10:00:00Z', 'review_hash_or_pseudonym': 'n1'},
                    {'role': 'legal_reviewer', 'reviewed_at': '2026-10-25T10:00:00Z', 'review_hash_or_pseudonym': 'l1'},
                ])
                (Path(folder) / name).write_text(json.dumps(payload), encoding='utf-8')
            import src.templates as module

            original = module.TEMPLATES_DIR
            module.TEMPLATES_DIR = Path(folder)
            try:
                pair = resolve_pair('exp-warning-language-2026.10', CONTROL_TEMPLATE_ID, TREATMENT_TEMPLATE_ID)
                self.assertTrue(pair.treatment_available)
                self.assertIsNone(pair.blocked_reason)
            finally:
                module.TEMPLATES_DIR = original


class TestSnapshotIntegrity(unittest.TestCase):
    def test_risk_snapshot_contract_still_rejects_language(self):
        payload = snapshot(_small_inbound(5), 'tpl-test')
        for field in ('language', 'locale', 'citizenship', 'ethnicity', 'full_name', 'phone'):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    RiskSnapshotV1.model_validate({**payload, field: 'x'})
        self.assertEqual(evaluate_snapshot(payload).rule_version, RULE_VERSION)


if __name__ == '__main__':
    unittest.main()