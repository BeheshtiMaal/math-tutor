"""A failed-only evaluation must never expand into both languages or the full set."""
import json
from pathlib import Path
import unittest
from scripts.run_evaluation import failed_jobs, unrun_jobs

ROOT = Path(__file__).resolve().parents[1]


class EvaluationSelectionChecks(unittest.TestCase):
    def test_resume_subset_does_not_include_cases_outside_previous_selection(self):
        dataset = {'records': [{'id': 'one'}, {'id': 'two'}]}
        prior = {'runs': 1, 'planned_runs': 2,
                 'selected_pairs': [{'id': 'one', 'language': 'fa'}, {'id': 'two', 'language': 'en'}],
                 'results': [{'id': 'one', 'language': 'fa', 'status': 'complete'}]}
        self.assertEqual(unrun_jobs(dataset, prior), [({'id': 'two'}, 'en')])

    def test_unfinished_reconstruction_is_exact_and_aggregate_consistent(self):
        dataset = json.loads((ROOT / 'sources/manifests/evaluation_set.json').read_text(encoding='utf-8'))
        prior = json.loads((ROOT / 'sources/manifests/evaluation_run_aborted_42.json').read_text(encoding='utf-8'))
        jobs = unrun_jobs(dataset, prior)
        self.assertEqual(len(jobs), 38)
        integral = {(record['id'], language) for record, language in jobs if record['topic'] == 'integral'}
        self.assertEqual(integral, {(f'integral.{item}', language)
            for item in ('beginner.question', 'advanced.question', 'advanced.probe') for language in ('fa', 'en')})
        self.assertEqual({record['topic'] for record, _ in jobs},
                         {'integral', 'limits', 'matrix', 'probability', 'optimization'})
        prior['by_level']['beginner']['n'] += 1
        with self.assertRaises(ValueError):
            unrun_jobs(dataset, prior)

    def test_unfinished_uses_rows_when_available(self):
        dataset = {'records': [{'id': 'one'}, {'id': 'two'}]}
        previous = {'runs': 1, 'results': [{'id': 'one', 'language': 'en', 'status': 'complete'}]}
        self.assertEqual(unrun_jobs(dataset, previous),
                         [({'id': 'one'}, 'fa'), ({'id': 'two'}, 'fa'), ({'id': 'two'}, 'en')])

    def test_reconstructed_failures_select_exact_thirteen_pairs(self):
        dataset = json.loads((ROOT / 'sources/manifests/evaluation_set.json').read_text(encoding='utf-8'))
        prior = json.loads((ROOT / 'sources/manifests/evaluation_run_aborted_42.json').read_text(encoding='utf-8'))
        jobs = failed_jobs(dataset, prior)
        self.assertEqual(len(jobs), 13)
        self.assertEqual({(record['id'], language) for record, language in jobs},
                         {(row['id'], row['language']) for row in prior['non_complete_runs']})

    def test_complete_rows_excluded_and_language_pairs_deduplicated(self):
        dataset = {'records': [{'id': 'one'}, {'id': 'two'}]}
        row = dict(id='one', language='fa', status='partial')
        jobs = failed_jobs(dataset, {'results': [row, row, dict(id='two', language='en', status='complete')]})
        self.assertEqual(jobs, [({'id': 'one'}, 'fa')])
        with self.assertRaises(ValueError):
            failed_jobs(dataset, {'results': [dict(id='missing', language='en', status='error')]})

if __name__ == '__main__':
    unittest.main()
