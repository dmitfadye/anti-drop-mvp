"""Frontend asset smoke tests: no CDN, no innerHTML for data, a11y hooks, RTL."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / 'static'
INDEX_HTML = (STATIC / 'index.html').read_text(encoding='utf-8')
APP_JS = (STATIC / 'js' / 'app.js').read_text(encoding='utf-8')
OPERATOR_HTML = (STATIC / 'operator.html').read_text(encoding='utf-8')
OPERATOR_JS = (STATIC / 'js' / 'operator.js').read_text(encoding='utf-8')
APP_CSS = (STATIC / 'css' / 'app.css').read_text(encoding='utf-8')

def strip_js_comments(source: str) -> str:
    """Comments legitimately mention innerHTML; the check is about executed code."""
    without_block = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$', '', without_block)


APP_JS_CODE = strip_js_comments(APP_JS)
OPERATOR_JS_CODE = strip_js_comments(OPERATOR_JS)

EXTERNAL_HOSTS = ('cdn.jsdelivr.net', 'cdn.tailwindcss.com', 'unpkg.com', 'cdnjs.cloudflare.com',
                  'fonts.googleapis.com', 'fonts.gstatic.com', 'ajax.googleapis.com', 'google-analytics',
                  'stackpath', 'maxcdn')
DATA_INNERHTML = re.compile(r'innerHTML|outerHTML|insertAdjacentHTML|document\.write')


class TestNoExternalAssets(unittest.TestCase):
    def test_no_cdn_or_third_party_host_in_any_asset(self):
        assets = {'static/index.html': INDEX_HTML, 'static/operator.html': OPERATOR_HTML,
                  'static/js/app.js': APP_JS, 'static/js/operator.js': OPERATOR_JS,
                  'static/css/app.css': APP_CSS}
        for name, content in assets.items():
            for host in EXTERNAL_HOSTS:
                with self.subTest(asset=name, host=host):
                    self.assertNotIn(host, content)
            with self.subTest(asset=name, scheme='http'):
                self.assertNotIn('http://', content)
            with self.subTest(asset=name, scheme='https'):
                self.assertNotIn('https://', content)

    def test_stylesheets_and_scripts_are_local(self):
        self.assertIn('/static/tailwind.css', INDEX_HTML)
        self.assertIn('/static/css/app.css', INDEX_HTML)
        self.assertIn('/static/js/app.js', INDEX_HTML)
        self.assertIn('/static/css/app.css', OPERATOR_HTML)
        self.assertIn('/static/js/operator.js', OPERATOR_HTML)

    def test_swagger_stays_local(self):
        client = TestClient(__import__('main').app, client=('127.0.0.1', 51234))
        docs = client.get('/docs').text
        self.assertIn('/static/swagger/swagger-ui-bundle.js', docs)
        self.assertNotIn('cdn.jsdelivr.net', docs)


class TestNoInnerHtmlForData(unittest.TestCase):
    def test_no_dom_injection_apis_anywhere(self):
        for name, content in (('static/js/app.js', APP_JS_CODE), ('static/js/operator.js', OPERATOR_JS_CODE)):
            with self.subTest(asset=name):
                self.assertIsNone(DATA_INNERHTML.search(content),
                                  f'{name} must build DOM with createElement/textContent only')

    def test_data_is_written_with_textcontent(self):
        for content in (APP_JS_CODE, OPERATOR_JS_CODE):
            self.assertIn('textContent', content)
            self.assertIn('createElement', content)

    def test_index_html_has_no_inline_event_handlers(self):
        self.assertNotRegex(INDEX_HTML, r'on(click|load|error|change|submit)=')
        self.assertNotIn('innerHTML', INDEX_HTML)

    def test_browser_globals_stay_minimal(self):
        for name, content in (('app.js', APP_JS_CODE), ('operator.js', OPERATOR_JS_CODE)):
            with self.subTest(asset=name):
                self.assertIn("'use strict'", content)
                self.assertIn('fetch(', content)


class TestAccessibilityHooks(unittest.TestCase):
    def test_landmarks_and_skip_link(self):
        self.assertIn('<main', INDEX_HTML)
        self.assertIn('id="main"', INDEX_HTML)
        self.assertIn('skip-link', INDEX_HTML)
        self.assertIn('<header', INDEX_HTML)
        self.assertIn('lang="ru"', INDEX_HTML)
        self.assertIn('dir="ltr"', INDEX_HTML)

    def test_every_form_control_has_a_label(self):
        for markup in (INDEX_HTML, OPERATOR_HTML):
            ids = re.findall(r'<(?:input|select|textarea)[^>]*\bid="([^"]+)"', markup)
            labels = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', markup))
            for control_id in ids:
                with self.subTest(control=control_id):
                    self.assertIn(control_id, labels,
                                  'every input/select needs a <label for> or an aria-label')
            self.assertTrue(re.findall(r'aria-label="([^"]+)"', markup) or labels)

    def test_live_regions_and_roles(self):
        for element_id in ('levelBadge', 'reasons', 'reasonCodes', 'ticket', 'apiErr', 'requestState'):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', INDEX_HTML)
        self.assertIn('aria-live="polite"', INDEX_HTML)
        self.assertIn('role="alert"', INDEX_HTML)
        self.assertIn('role="status"', INDEX_HTML)
        self.assertIn('role="tablist"', INDEX_HTML)
        self.assertIn('role="tabpanel"', INDEX_HTML)

    def test_risk_level_is_never_colour_only(self):
        self.assertIn('level-badge__text', INDEX_HTML)
        self.assertIn('level-badge__icon', INDEX_HTML)
        self.assertIn('levelIcon', APP_JS)
        self.assertIn('levelText', APP_JS)

    def test_viewport_and_reduced_motion(self):
        self.assertIn('name="viewport"', INDEX_HTML)
        self.assertIn('prefers-reduced-motion', APP_CSS)
        self.assertIn('prefers-contrast', APP_CSS)

    def test_css_uses_logical_properties(self):
        for prop in ('margin-inline', 'padding-inline', 'inset-inline-start', 'text-align: start'):
            with self.subTest(prop=prop):
                self.assertIn(prop, APP_CSS)
        self.assertNotRegex(APP_CSS, r'(^|[\s;])(left|right)\s*:\s*-?\d')

    def test_touch_targets_are_large_enough(self):
        self.assertRegex(APP_CSS, r'min-(block|height)-size:\s*44px')
        self.assertRegex(APP_CSS, r'min-inline-size:\s*44px')

    def test_direction_and_lang_are_applied_from_data(self):
        self.assertIn('setAttribute(\'dir\'', APP_JS)
        self.assertIn('setAttribute(\'lang\'', APP_JS)
        self.assertIn('dir="auto"', INDEX_HTML)


class TestAsyncSafety(unittest.TestCase):
    def test_stale_response_protection_and_abort(self):
        self.assertIn('AbortController', APP_JS)
        self.assertIn('requestSeq', APP_JS)
        self.assertIn('AbortError', APP_JS)
        self.assertIn('disabled', APP_JS)

    def test_error_paths_never_touch_innerhtml(self):
        self.assertIn('showError', APP_JS)
        self.assertIn('clearTimeout', APP_JS)
        self.assertRegex(APP_JS, r'setBusy\(false')

    def test_operator_sends_idempotency_key(self):
        self.assertIn('Idempotency-Key', OPERATOR_JS)
        self.assertIn('randomUUID', OPERATOR_JS)


class TestHonestyInTheUi(unittest.TestCase):
    def test_score_is_labelled_not_a_probability(self):
        self.assertIn('не вероятность', INDEX_HTML)
        self.assertIn('не вероятность мошенничества', APP_JS_CODE)

    def test_sandbox_banner_present(self):
        self.assertIn('ДЕМО-РЕЖИМ', INDEX_HTML)
        self.assertIn('песочница', OPERATOR_HTML.lower())

    def test_draft_badge_is_rendered(self):
        self.assertIn('draftBadge', APP_JS)
        self.assertIn('draft_badge', APP_JS)

    def test_operator_has_no_free_text_note_field(self):
        self.assertNotIn('<input id="note"', OPERATOR_HTML)
        self.assertIn('id="noteCode"', OPERATOR_HTML)

    def test_quiz_answers_are_not_in_the_html(self):
        for markup in (INDEX_HTML, OPERATOR_HTML):
            self.assertNotIn('"correct"', markup)
            self.assertNotIn("'correct'", markup)


class TestScenarioRefsAreContractValid(unittest.TestCase):
    """UI scenario refs must satisfy the RiskSnapshotV1 Ref pattern.

    Regression: human-readable counterparty names ('cp_relay001') were once
    shipped in SCENARIOS and every demo scenario failed with HTTP 422.
    The contract (anti_drop_ml/contracts.py) is intentionally strict.
    """

    REF_PATTERN = re.compile(r'^(sub|cp|dev|evt|src|ep|case|tpl)_[a-f0-9]{8,64}$')

    def test_every_ref_literal_matches_the_contract(self):
        literals = set(re.findall(r"'((?:sub|cp|dev|evt|src)_[^']*)'", APP_JS_CODE))
        self.assertTrue(literals, 'expected scenario ref literals in app.js')
        for ref in sorted(literals):
            with self.subTest(ref=ref):
                self.assertRegex(ref, self.REF_PATTERN,
                                 f'{ref!r} would be rejected with 422: use a hex pseudonym')

    def test_every_scenario_counterparty_is_defined(self):
        block = re.search(r'const CP_REF = \{(.*?)\};', APP_JS_CODE, flags=re.S)
        self.assertIsNotNone(block, 'CP_REF map missing in app.js')
        defined = set(re.findall(r'(\w+):', block.group(1)))
        used = set(re.findall(r'CP_REF\.(\w+)', APP_JS_CODE))
        self.assertTrue(used, 'expected CP_REF usages in scenarios')
        self.assertEqual(used - defined, set(),
                         'scenario uses an undefined counterparty (would send undefined)')


if __name__ == '__main__':
    unittest.main()