"""Output collisions must reject without overwriting inputs or running commands.
All files, outputs, receipts, and subprocess working directories are temporary.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import mslib


class OutputSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.draft=self.write('draft.md','# Results\n\nFor fatigue in treatment, the effect was 0.234.\n')
        self.source=self.write('source.csv','outcome,group,value\nfatigue,treatment,0.234\n')
        self.review=self.write('review.md','Review confirms the bounded numeric wording.')
        self.log=self.write('check.log.txt','STDOUT\nChecked\nSTDERR\n')
        self.run_output=self.write('check-output.txt','Synthetic check output.')
        self.receipt=self.write_json('check.json',{'schema_version':1,'receipt_kind':'execution_only',
            'command':['synthetic-test'],'started_at':'2026-10-26T00:00:00Z','finished_at':'2026-10-26T00:00:01Z',
            'exit_code':0,'inputs_unchanged':True,'declared_outputs_complete':True,
            'inputs':{str(self.draft):self.digest(self.draft)},'outputs':{str(self.run_output):self.digest(self.run_output)},
            'log':self.record(self.log)})

    def write(self,name,text):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8');return p

    def write_json(self,name,data):return self.write(name,json.dumps(data,ensure_ascii=False))

    def digest(self,path):return hashlib.sha256(path.read_bytes()).hexdigest()

    def record(self,path):return {'path':path.name,'sha256':self.digest(path)}

    def run_tool(self,tool,*args):
        return subprocess.run([sys.executable,'-X','utf8',str(SCRIPTS/tool),*map(str,args)],cwd=self.root,
            capture_output=True,text=True,encoding='utf-8',env={**os.environ,'PYTHONIOENCODING':'utf-8'})

    def rejected(self,result):
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertTrue(result.stdout.strip(),'Input/path error must be explained on stdout')
        self.assertNotIn('Traceback',result.stderr)

    def manifest(self,tool):
        if tool=='verify_evidence.py':
            data={'schema_version':1,'manuscript':self.record(self.draft),'checks':[{
                'id':'N1','kind':'numeric','manuscript_anchor':'For fatigue in treatment, the effect was 0.234.',
                'source':self.record(self.source),'row_key':{'outcome':'fatigue','group':'treatment'},
                'context':{'outcome':'fatigue','group':'treatment'},'value_column':'value','manuscript_value':'0.234',
                'source_unit':'correlation','target_unit':'correlation','scale':'1','rounding':'half_up'}]}
        elif tool=='display_profile.py':
            caption=self.write('caption.md','Bars show means and 95% confidence intervals.')
            exemplar=self.write('exemplar.md','Bars represent 95% confidence intervals.')
            data={'schema_version':1,'records':[]}
            for role,path in [('draft',caption),('exemplar',exemplar)]:
                data['records'].append({'id':role,'role':role,'paper_id':role,**self.record(path),
                    'text':path.read_text(encoding='utf-8'),'kind':'figure_caption','task':'group mean','language':'en','panels':1})
        elif tool=='delivery_check.py':
            data={'schema_version':1,'files':[{'id':'draft','role':'manuscript_clean',**self.record(self.draft)}],
                  'required_roles':['manuscript_clean'],'displays':[]}
        elif tool=='release_check.py':
            review={**self.record(self.review),'reviewer':'synthetic model','kind':'model','locator':'Review',
                    'quote':'bounded numeric wording'}
            data={'schema_version':1,'stage':'review','artifacts':[{'id':'draft',**self.record(self.draft)}],
                  'targets':['draft'],'findings':[],
                  'checks':[{'id':cid,'status':'pass','bindings':['draft'],'reviews':[copy.deepcopy(review)]}
                  for cid in ['source_coverage','numbers','citations','section_logic','reporting']]}
            data['checks'][0]['runs']=[self.record(self.receipt)]
        else:raise AssertionError(tool)
        return self.write_json(tool+'.json',data),data

    def protected_inputs(self,tool,manifest):
        if tool=='verify_evidence.py':return [manifest,self.draft,self.source]
        if tool=='display_profile.py':return [manifest,self.root/'caption.md',self.root/'exemplar.md']
        if tool=='delivery_check.py':return [manifest,self.draft]
        return [manifest,self.draft,self.review,self.receipt,self.log,self.run_output]

    def check_collisions(self,tool):
        manifest,_=self.manifest(tool)
        for target in self.protected_inputs(tool,manifest):
            with self.subTest(tool=tool,target=target.name):
                before={p:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
                self.rejected(self.run_tool(tool,manifest,'--report',target))
                for path,content in before.items():self.assertEqual(path.read_bytes(),content,str(path))
                self.assertEqual(set(before),{p for p in self.root.iterdir() if p.is_file()})

    def check_positive(self,tool):
        manifest,_=self.manifest(tool);target=self.root/'reports'/('fresh-'+tool+'.json')
        before={p:p.read_bytes() for p in self.protected_inputs(tool,manifest)}
        result=self.run_tool(tool,manifest,'--report',target)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(target.is_file());json.loads(target.read_text(encoding='utf-8'))
        for path,content in before.items():self.assertEqual(path.read_bytes(),content,str(path))

    def test_display_manifest_and_sources_preserved(self):self.check_collisions('display_profile.py')
    def test_display_fresh_report_succeeds(self):self.check_positive('display_profile.py')
    def test_verify_manifest_manuscript_and_source_preserved(self):self.check_collisions('verify_evidence.py')
    def test_verify_fresh_report_succeeds(self):self.check_positive('verify_evidence.py')
    def test_delivery_manifest_and_files_preserved(self):self.check_collisions('delivery_check.py')
    def test_delivery_fresh_report_succeeds(self):self.check_positive('delivery_check.py')
    def test_release_manifest_artifacts_reviews_receipt_log_outputs_preserved(self):self.check_collisions('release_check.py')
    def test_release_fresh_report_succeeds(self):self.check_positive('release_check.py')

    def test_all_report_tools_preserve_existing_unrelated_report(self):
        for tool in ('display_profile.py','verify_evidence.py','delivery_check.py','release_check.py'):
            with self.subTest(tool=tool):
                manifest,_=self.manifest(tool);target=self.write('prior-report.json','{"old":"keep"}')
                self.rejected(self.run_tool(tool,manifest,'--report',target))
                self.assertEqual(target.read_text(encoding='utf-8'),'{"old":"keep"}')

    def test_all_report_tools_bad_json_does_not_create_report(self):
        for tool in ('display_profile.py','verify_evidence.py','delivery_check.py','release_check.py'):
            with self.subTest(tool=tool):
                manifest=self.write('malformed.json','not JSON');target=self.root/('never-'+tool+'.json')
                self.rejected(self.run_tool(tool,manifest,'--report',target))
                self.assertFalse(target.exists());self.assertEqual(manifest.read_text(encoding='utf-8'),'not JSON')

    def test_all_report_tools_reject_missing_declared_input_as_output(self):
        for tool in ('display_profile.py','verify_evidence.py','delivery_check.py','release_check.py'):
            with self.subTest(tool=tool):
                manifest,data=self.manifest(tool);missing=self.root/('missing-'+tool+'.md')
                if tool=='display_profile.py':data['records'][0]['path']=missing.name
                elif tool=='verify_evidence.py':data['checks'][0]['source']['path']=missing.name
                elif tool=='delivery_check.py':data['files'][0]['path']=missing.name
                else:data['artifacts'][0]['path']=missing.name
                manifest.write_text(json.dumps(data),encoding='utf-8')
                self.rejected(self.run_tool(tool,manifest,'--report',missing));self.assertFalse(missing.exists())

    def test_release_missing_receipt_log_cannot_be_created_as_report(self):
        manifest,_=self.manifest('release_check.py')
        receipt=json.loads(self.receipt.read_text(encoding='utf-8'));missing=self.root/'missing-log.txt'
        receipt['log']['path']=missing.name;self.receipt.write_text(json.dumps(receipt),encoding='utf-8')
        self.rejected(self.run_tool('release_check.py',manifest,'--report',missing))
        self.assertFalse(missing.exists())

    def test_hardlink_alias_cannot_overwrite_source(self):
        for tool in ('display_profile.py','verify_evidence.py','delivery_check.py','release_check.py'):
            with self.subTest(tool=tool):
                manifest,_=self.manifest(tool);alias=self.root/('alias-'+tool+'.json')
                try:os.link(manifest,alias)
                except OSError as error:self.skipTest('Hard links unavailable: '+str(error))
                original=manifest.read_bytes()
                self.rejected(self.run_tool(tool,manifest,'--report',alias))
                self.assertEqual(manifest.read_bytes(),original);self.assertEqual(alias.read_bytes(),original)

    def runner(self,receipt='new-run.json',inputs=None,outputs=(),body=None):
        args=['--receipt',receipt]
        for item in inputs or [self.draft]:args+=['--input',str(item)]
        for item in outputs:args+=['--output',str(item)]
        return self.run_tool('audit_run.py',*args,'--',sys.executable,'-c',body or "from pathlib import Path; Path('command-ran.txt').write_text('ran', encoding='utf-8')")

    def test_audit_input_cannot_be_receipt(self):
        before=self.draft.read_bytes();self.rejected(self.runner(receipt=str(self.draft)))
        self.assertEqual(self.draft.read_bytes(),before);self.assertFalse((self.root/'command-ran.txt').exists())

    def test_audit_input_cannot_be_declared_output(self):
        before=self.draft.read_bytes();self.rejected(self.runner(outputs=[self.draft]))
        self.assertEqual(self.draft.read_bytes(),before);self.assertFalse((self.root/'command-ran.txt').exists())

    def test_audit_existing_log_rejected_before_command(self):
        log=self.write('new-run.log.txt','keep log')
        self.rejected(self.runner());self.assertEqual(log.read_text(encoding='utf-8'),'keep log')
        self.assertFalse((self.root/'command-ran.txt').exists());self.assertFalse((self.root/'new-run.json').exists())

    def test_audit_receipt_log_and_output_collisions_rejected(self):
        for outputs in (['new-run.json'],['new-run.log.txt'],['duplicate.txt','duplicate.txt']):
            with self.subTest(outputs=outputs):
                self.rejected(self.runner(outputs=outputs))
                self.assertFalse((self.root/'command-ran.txt').exists())
                self.assertFalse((self.root/'new-run.json').exists());self.assertFalse((self.root/'new-run.log.txt').exists())

    def test_audit_output_inside_input_directory_rejected(self):
        seed=self.write('inputs/seed.txt','keep');target=self.root/'inputs/new.txt'
        self.rejected(self.runner(inputs=[seed.parent],outputs=[target]))
        self.assertFalse(target.exists());self.assertFalse((self.root/'command-ran.txt').exists())

    def test_audit_fresh_receipt_log_and_command_output_succeed(self):
        result=self.runner(outputs=['created-report.txt'],body="from pathlib import Path; Path('created-report.txt').write_text('check report', encoding='utf-8'); print('checked')")
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        receipt=json.loads((self.root/'new-run.json').read_text(encoding='utf-8'))
        self.assertTrue(receipt['inputs_unchanged']);self.assertTrue(receipt['declared_outputs_complete'])
        self.assertIn('checked',(self.root/'new-run.log.txt').read_text(encoding='utf-8'))
        self.assertEqual((self.root/'created-report.txt').read_text(encoding='utf-8'),'check report')

    def test_mslib_source_path_refused_without_truncation(self):
        before=self.draft.read_bytes()
        with self.assertRaises(FileExistsError):mslib.wfile(str(self.draft))
        self.assertEqual(self.draft.read_bytes(),before)

    def test_mslib_existing_report_refused_without_truncation(self):
        report=self.write('prior.md','Earlier audit evidence.')
        with self.assertRaises(FileExistsError):mslib.wfile(str(report))
        self.assertEqual(report.read_text(encoding='utf-8'),'Earlier audit evidence.')

    def test_mslib_fresh_report_succeeds(self):
        report=self.root/'reports/new.md'
        with mslib.wfile(str(report)) as handle:handle.write('New audit evidence.')
        self.assertEqual(report.read_text(encoding='utf-8'),'New audit evidence.')


if __name__=='__main__':unittest.main()
