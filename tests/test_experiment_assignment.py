"""ExperimentAssignmentV1: deterministic, subject-level, refused while draft."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError  # noqa: E402

from anti_drop_ml.adapter import RULE_VERSION, THRESHOLD_VERSION  # noqa: E402
from src.experiments import (  # noqa: E402
    ASSIGNMENT_SALT_VERSION,
    ExperimentAssignmentV1,
    ExperimentConfigError,
    assign,
    assign_arm,
    deterministic_bucket,
    template_id_for_assignment,
)

EXPERIMENT_ID = 'exp-warning-language-2026.10'
SUBJECTS = [f'sub_{index:016x}' for index in range(1, 201)]


def make(arm_subject: str, **kwargs):
    options = {'experiment_id': EXPERIMENT_ID, 'subject_pseudonym': arm_subject,
               'rule_version': RULE_VERSION, 'threshold_version': THRESHOLD_VERSION}
    options.update(kwargs)
    return assign(**options)


class TestDeterminism(unittest.TestCase):
    def test_bucket_is_stable_and_salt_sensitive(self):
        first = deterministic_bucket(EXPERIMENT_ID, SUBJECTS[0])
        self.assertEqual(first, deterministic_bucket(EXPERIMENT_ID, SUBJECTS[0]))
        self.assertNotEqual(first, deterministic_bucket(EXPERIMENT_ID, SUBJECTS[0], 'salt-v2'))
        self.assertNotEqual(first, deterministic_bucket('exp-other', SUBJECTS[0]))
        self.assertTrue(0 <= first <= 99)

    def test_same_subject_same_arm_every_time(self):
        for subject in SUBJECTS[:20]:
            with self.subTest(subject=subject):
                arms = {make(subject, allow_draft_treatment=True).arm for _ in range(3)}
                self.assertEqual(len(arms), 1)

    def test_split_ratio_is_close_to_the_request(self):
        for percent in (25, 50, 75):
            with self.subTest(percent=percent):
                arms = [assign_arm(EXPERIMENT_ID, subject, percent, allow_draft_treatment=True)
                        for subject in SUBJECTS]
                share = arms.count('treatment') / len(arms)
                self.assertAlmostEqual(share, percent / 100, delta=0.07)

    def test_percent_bounds_are_validated(self):
        for percent in (0, 100, -1, 150):
            with self.subTest(percent=percent):
                with self.assertRaises(ExperimentConfigError):
                    assign_arm(EXPERIMENT_ID, SUBJECTS[0], percent, allow_draft_treatment=True)


class TestDraftTreatmentIsRefused(unittest.TestCase):
    def test_default_assignment_is_control_with_a_reason(self):
        assignment = make(SUBJECTS[0])
        self.assertEqual(assignment.arm, 'control')
        self.assertIsNotNone(assignment.treatment_blocked_reason)
        self.assertIn('draft', assignment.treatment_blocked_reason)

    def test_draft_can_be_demonstrated_explicitly(self):
        assignment = make(SUBJECTS[0], allow_draft_treatment=True)
        self.assertEqual(assignment.assignment_method, 'deterministic_hash')
        self.assertIsNone(assignment.treatment_blocked_reason)

    def test_whole_experiment_falls_back_to_control_without_the_override(self):
        arms = [make(subject).arm for subject in SUBJECTS]
        self.assertEqual(set(arms), {'control'})


class TestAssignmentContract(unittest.TestCase):
    def test_assignment_carries_versions_and_status(self):
        assignment = make(SUBJECTS[0], allow_draft_treatment=True)
        self.assertEqual(assignment.rule_version, RULE_VERSION)
        self.assertEqual(assignment.threshold_version, THRESHOLD_VERSION)
        self.assertEqual(assignment.assignment_salt_version, ASSIGNMENT_SALT_VERSION)
        self.assertEqual(assignment.status, 'active')
        self.assertEqual(assignment.control_template_id, 'warning_ru_control_v1')
        self.assertEqual(assignment.treatment_template_id, 'warning_uz_treatment_v1')

    def test_raw_identifiers_are_refused(self):
        for subject in ('+79990000000', 'ivan@example.com', 'sub_XYZ', 'cp_00000000aaaa0001'):
            with self.subTest(subject=subject):
                with self.assertRaises(ValidationError):
                    make(subject)

    def test_unknown_experiment_id_is_refused(self):
        with self.assertRaises(ValidationError):
            make(SUBJECTS[0], experiment_id='language-2026')

    def test_template_mapping_depends_only_on_arm_and_level(self):
        assignment = make(SUBJECTS[0], allow_draft_treatment=True)
        mapping = {
            'control': template_id_for_assignment(assignment.model_copy(update={'arm': 'control'}), 'RED'),
            'treatment': template_id_for_assignment(assignment.model_copy(update={'arm': 'treatment'}), 'RED'),
        }
        self.assertEqual(mapping['control'], 'warning_ru_control_v1')
        self.assertEqual(mapping['treatment'], 'warning_uz_treatment_v1')
        self.assertEqual(template_id_for_assignment(assignment.model_copy(update={'arm': 'control'}), 'YELLOW'),
                         'warning_ru_control_yellow_v1')
        with self.assertRaises(ValidationError):
            ExperimentAssignmentV1.model_validate({**assignment.model_dump(), 'arm': 'holdout'})

    def test_status_vocabulary(self):
        for status in ('active', 'paused', 'completed'):
            self.assertEqual(make(SUBJECTS[0], status=status).status, status)
        with self.assertRaises(ValidationError):
            make(SUBJECTS[0], status='stopped')


if __name__ == '__main__':
    unittest.main()