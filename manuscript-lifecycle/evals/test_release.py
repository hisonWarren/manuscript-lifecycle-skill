import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from audit_run import digest
from release_check import evaluate


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'draft.md').write_text('The estimates remain uncertain.', encoding='utf-8')
        (self.root/'review.md').write_text('Review: uncertainty preserved; source identities checked.', encoding='utf-8')
        review = {'path':'review.md','sha256':digest(self.root/'review.md'), 'locator':'Review',
                  'quote':'uncertainty preserved','reviewer':'isolated model','kind':'model'}
        self.data = {'schema_version':1,'stage':'review','artifacts':[{'id':'draft','path':'draft.md',
             'sha256':digest(self.root/'draft.md')}], 'targets':['draft'],'findings':[],
             'checks':[{'id':c,'status':'pass','bindings':['draft'],'reviews':[copy.deepcopy(review)]}
                       for c in ['source_coverage','numbers','citations','section_logic','reporting']]}

    def result(self): return evaluate(self.data,self.root)
    def blocked(self): self.assertEqual(self.result()['status'],'blocked')
    def test_positive_review_contract(self): self.assertEqual(self.result()['status'],'contract_pass')
    def test_stale_draft(self):
        (self.root/'draft.md').write_text('The estimates prove success.',encoding='utf-8'); self.blocked()
    def test_stale_review(self):
        (self.root/'review.md').write_text('Changed',encoding='utf-8'); self.blocked()
    def test_missing_target(self): self.data['targets']=[]; self.blocked()
    def test_duplicate_check(self): self.data['checks'].append(copy.deepcopy(self.data['checks'][0])); self.blocked()
    def test_all_na_forbidden(self):
        for c in self.data['checks']: c.update(status='na',reason='irrelevant',fallback='none')
        self.blocked()
    def test_specific_na_allowed_with_review(self):
        self.data['checks'][1].update(status='na',reason='No numeric claims in requested text',fallback='semantic review')
        self.assertEqual(self.result()['status'],'contract_pass')
    def test_na_without_fallback(self): self.data['checks'][1].update(status='na',reason='no numbers'); self.blocked()
    def test_unsupported_mode(self):
        self.data['stage']='unknown'
        with self.assertRaises(ValueError): self.result()
    def test_missing_required_check(self): self.data['checks'].pop(); self.blocked()
    def test_unbound_check(self): self.data['checks'][0]['bindings']=[]; self.blocked()
    def test_absent_review_excerpt(self): self.data['checks'][0]['reviews'][0]['quote']='Not present'; self.blocked()
    def test_critical_not_offset(self):
        self.data['findings']=[{'id':'N1','severity':'critical','status':'accepted','rationale':'Style improved',
                                'evidence':'Wrong estimate at paragraph 2'}]; self.blocked()
    def test_missing_findings_list(self): self.data.pop('findings'); self.blocked()
    def test_regression_requires_run(self):
        self.data['checks'].append({'id':'regression','status':'pass','bindings':['draft'],
                                   'reviews':copy.deepcopy(self.data['checks'][0]['reviews'])}); self.blocked()


class ExecutionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'input.txt').write_text('original',encoding='utf-8')

    def run_command(self,body,extra=()):
        (self.root/'check.py').write_text(body,encoding='utf-8')
        cmd=[sys.executable,str(SCRIPTS/'audit_run.py'),'--receipt','run.json','--input','input.txt',
             '--input','check.py',*extra,'--',sys.executable,'check.py']
        return subprocess.run(cmd,cwd=self.root,capture_output=True,text=True,encoding='utf-8')

    def test_success_real_receipt(self):
        r=self.run_command("print('checked')")
        self.assertEqual(r.returncode,0,r.stderr)
        data=json.loads((self.root/'run.json').read_text(encoding='utf-8'))
        self.assertIn('checked',(self.root/'run.log.txt').read_text(encoding='utf-8'))
        self.assertEqual(data['command_exit'],0)
    def test_command_failure_preserved(self): self.assertEqual(self.run_command('raise SystemExit(2)').returncode,2)
    def test_input_mutation_detected(self):
        self.assertEqual(self.run_command("from pathlib import Path\nPath('input.txt').write_text('changed', encoding='utf-8')").returncode,125)
    def test_missing_output_detected(self): self.assertEqual(self.run_command('pass',['--output','report.md']).returncode,125)
    def test_old_output_rejected(self):
        (self.root/'report.md').write_text('old',encoding='utf-8')
        self.assertEqual(self.run_command('pass',['--output','report.md']).returncode,2)
    def test_real_output_recorded(self):
        self.assertEqual(self.run_command("from pathlib import Path\nPath('report.md').write_text('new', encoding='utf-8')",['--output','report.md']).returncode,0)
    def test_receipt_not_overwritten(self):
        self.assertEqual(self.run_command('pass').returncode,0)
        self.assertEqual(self.run_command('pass').returncode,2)


if __name__=='__main__': unittest.main()
