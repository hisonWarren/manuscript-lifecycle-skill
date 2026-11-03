"""Fail-closed scope/schema tests, using synthetic fixtures only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'


class GuardRegression(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.ms=self.write('draft.md','# Results\n\nThe estimated association was 0.234.\n\n# Discussion\n\nThis is an observational estimate.\n')

    def tearDown(self):
        self.temp.cleanup()

    def write(self,name,text):
        p=self.root/name;p.write_text(text,encoding='utf-8');return p

    def run_tool(self,script,*args):
        return subprocess.run([sys.executable,'-X','utf8',str(SCRIPTS/script),*map(str,args)],text=True,capture_output=True,encoding='utf-8',env={**os.environ,'PYTHONIOENCODING':'utf-8'})

    def rule(self,**updates):
        r={'id':'R1','type':'forbidden','pattern':'demonstrates causation','why':'Design is observational.','decision':'D1'}
        r.update(updates);return r

    def claims(self,rules,*extra,doc=None):
        register=self.write('rules.json',json.dumps({'rules':rules}))
        return self.run_tool('claims_guard.py','--register',register,'--doc','en='+str(doc or self.ms),*extra)

    def rejected(self,result):
        self.assertIn(result.returncode,(1,2),result.stdout+result.stderr)
        self.assertNotIn('Traceback',result.stderr)

    def test_empty_rules_rejected(self):
        self.rejected(self.claims([]))

    def test_non_list_rules_rejected(self):
        self.rejected(self.claims({'R1':'unused'}))

    def test_unknown_type_rejected(self):
        self.rejected(self.claims([self.rule(type='forbiden')]))

    def test_unknown_field_does_not_broaden_scope(self):
        self.rejected(self.claims([self.rule(section=['results'])]))

    def test_duplicate_ids_rejected(self):
        self.rejected(self.claims([self.rule(),self.rule()]))

    def test_missing_declared_doc_rejected(self):
        self.rejected(self.claims([self.rule(docs=['zh'])]))

    def test_supplied_doc_with_no_rule_rejected(self):
        self.rejected(self.claims([self.rule(docs=['en'])],'--doc','zh='+str(self.ms)))

    def test_duplicate_doc_label_rejected(self):
        self.rejected(self.claims([self.rule()],'--doc','en='+str(self.ms)))

    def test_no_text_in_declared_section_rejected(self):
        self.rejected(self.claims([self.rule(sections=['methods'])]))

    def test_invalid_section_rejected(self):
        self.rejected(self.claims([self.rule(sections=['resultz'])]))

    def test_invalid_regex_and_empty_pattern_rejected(self):
        for value in ('','[','^$'):
            with self.subTest(value=value):
                self.rejected(self.claims([self.rule(regex=True,pattern=value)]))

    def test_zero_or_bool_min_cannot_disable_required(self):
        for value in (0,True,-1):
            with self.subTest(value=value):
                self.rejected(self.claims([self.rule(type='required',pattern='observational',min=value)]))

    def test_reverse_regex_forbidden_needs_sample(self):
        r=self.claims([self.rule(regex=True,pattern=r'\bprove\b')],'--reverse-test')
        self.rejected(r);self.assertIn('缺少 sample',r.stdout)

    def test_reverse_regex_conditional_needs_sample(self):
        r=self.rule(type='if_then',regex=True)
        r.pop('pattern');r.update({'if':r'pre-specified','then':r'not preregistered'})
        result=self.claims([r],'--reverse-test')
        self.rejected(result);self.assertIn('缺少 sample',result.stdout)

    def test_reverse_sample_must_trigger_checker(self):
        self.rejected(self.claims([self.rule(regex=True,pattern=r'\bprove\b',sample='We estimated an association.')],'--reverse-test'))

    def test_conditional_scope_honored(self):
        ms=self.write('scoped.md','# Methods\n\nThis was pre-specified.\n\n# Discussion\n\nThis was not preregistered.\n')
        r=self.rule(type='if_then',sections=['methods']);r.pop('pattern')
        r.update({'if':'pre-specified','then':'not preregistered'})
        self.rejected(self.claims([r],doc=ms))

    def test_positive_scoped_required_forbidden_reverse(self):
        rules=[self.rule(type='required',pattern='observational',sections=['discussion']),self.rule(id='F1',regex=True,pattern=r'\bprove\b',sample='These data prove causation.',sections=['results'])]
        r=self.claims(rules,'--reverse-test')
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('实际评估 2',r.stdout)
        self.assertIn('不证明主张真实',r.stdout)

    def test_claims_empty_document_rejected(self):
        self.rejected(self.claims([self.rule()],doc=self.write('empty.md','   \n')))

    def test_section_and_density_empty_input_rejected(self):
        empty=self.write('empty.md','\n  \n')
        for tool in ('section_lint.py','density_check.py'):
            with self.subTest(tool=tool):
                self.rejected(self.run_tool(tool,empty))

    def test_section_and_density_no_assessable_prose_rejected(self):
        heading=self.write('headings.md','# Results\n\n# Discussion\n')
        for tool in ('section_lint.py','density_check.py'):
            with self.subTest(tool=tool):
                self.rejected(self.run_tool(tool,heading))

    def test_section_and_density_invalid_language_rejected(self):
        for tool in ('section_lint.py','density_check.py'):
            with self.subTest(tool=tool):
                r=self.run_tool(tool,self.ms,'--lang','invalid')
                self.assertEqual(r.returncode,2);self.assertNotIn('Traceback',r.stderr)

    def test_section_and_density_valid_input_runs(self):
        for tool in ('section_lint.py','density_check.py'):
            with self.subTest(tool=tool):
                r=self.run_tool(tool,self.ms,'--lang','en')
                self.assertEqual(r.returncode,0,r.stdout+r.stderr)


if __name__=='__main__':
    unittest.main()
