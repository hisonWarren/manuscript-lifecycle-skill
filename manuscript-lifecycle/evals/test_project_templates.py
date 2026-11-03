import csv
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NewProject(unittest.TestCase):
    def test_new_project_has_no_fabricated_analysis_or_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([sys.executable, str(ROOT/'scripts/init_project.py'), '--dir', tmp, '--mode', 'D'], capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(list(csv.DictReader((Path(tmp)/'01_frame/results_ledger.csv').read_text(encoding='utf-8').splitlines())), [])
            # 初稿项目不建投稿与返修的空模板（实地试写中它们从建好到交付一字未动）
            self.assertFalse((Path(tmp)/'07_response/comments_matrix.csv').exists())
            self.assertFalse((Path(tmp)/'06_submission/cover_letter.md').exists())
            self.assertTrue((Path(tmp)/'作者说明.md').exists())
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([sys.executable, str(ROOT/'scripts/init_project.py'), '--dir', tmp, '--mode', 'V'], capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(list(csv.DictReader((Path(tmp)/'07_response/comments_matrix.csv').read_text(encoding='utf-8').splitlines())), [])

    def test_empty_template_cannot_be_complete_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            ms = Path(tmp)/'ms.md'
            ms.write_text('# Results\nNo supplied analyses.\n', encoding='utf-8')
            p = subprocess.run([sys.executable, str(ROOT/'scripts/ledger_check.py'), str(ROOT/'assets/templates/results_ledger.csv'), '--manuscript', str(ms)], capture_output=True)
            self.assertEqual(p.returncode, 2)

    def test_ledger_has_places_for_analysis_identity(self):
        fields = (ROOT/'assets/templates/results_ledger.csv').read_text(encoding='utf-8').strip().split(',')
        self.assertTrue({'analysis_status','population','n','model','estimand','unit','denominator','source_locator','data_version','disclosure_reason','placement_reason'}.issubset(fields))

    def run_ledger(self, decision, disclose='n'):
        with tempfile.TemporaryDirectory() as tmp:
            ms, ledger, report = (Path(tmp)/x for x in ('ms.md', 'ledger.csv', 'report.md'))
            ms.write_text('# Results\nThe age range was expanded.\n', encoding='utf-8')
            fields = (ROOT/'assets/templates/results_ledger.csv').read_text(encoding='utf-8').strip().split(',')
            with ledger.open('w', encoding='utf-8', newline='') as out:
                w = csv.DictWriter(out, fieldnames=fields); w.writeheader()
                w.writerow(dict(id='A', analysis='Eligibility deviation', result='recorded', supports_claim='scope', tier='omit', must_disclose=disclose, keywords='age range', source='protocol.md', reviewer_question='scope', decision=decision))
            p = subprocess.run([sys.executable, str(ROOT/'scripts/ledger_check.py'), str(ledger), '--manuscript', str(ms), '--report', str(report)], capture_output=True)
            return p.returncode, report.read_text(encoding='utf-8')

    def test_omission_requires_rationale(self):
        code, report = self.run_ledger('')
        self.assertEqual(code, 1)
        self.assertIn('须登记具体决定依据', report)

    def test_conflict_requires_disclosure_review_not_deletion(self):
        code, report = self.run_ledger('D-1 requires source review')
        self.assertEqual(code, 1)
        self.assertIn('关键词命中不能作为删稿依据', report)
        self.assertNotIn('要么从稿件删去', report)

    def test_required_disclosure_cannot_be_omitted(self):
        code, report = self.run_ledger('D-1', 'y')
        self.assertEqual(code, 1)
        self.assertIn('必须披露的项目不能', report)


if __name__ == '__main__':
    unittest.main()
