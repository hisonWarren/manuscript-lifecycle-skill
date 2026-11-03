"""Adversarial regression tests for mechanical checks and their honest boundaries.
Run: python -m unittest discover -s evals -p test_evidence.py -v
Fixtures are synthetic, not research data or a scientific validation sample.
"""
import copy
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import ref_check
import verify_evidence


class EvidenceRegression(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.empty=self.write('empty.md','')
        self.source=self.write('source.csv','outcome,group,value\nfatigue,treatment,0.234\nanxiety,control,0.123\n')
        self.ms=self.write('draft.md','# Results\n\nFor fatigue in treatment, the effect was 0.234.\n')

    def tearDown(self):
        self.temp.cleanup()

    def write(self,name,text):
        path=self.root/name;path.write_text(text,encoding='utf-8');return path

    def run_tool(self,script,*args):
        return subprocess.run([sys.executable,'-X','utf8',str(SCRIPTS/script),*map(str,args)],capture_output=True,text=True,encoding='utf-8',env={**os.environ,'PYTHONIOENCODING':'utf-8'})

    def assert_rejected(self,script,*args):
        result=self.run_tool(script,*args)
        self.assertIn(result.returncode,(1,2),result.stdout+result.stderr)
        self.assertNotIn('Traceback',result.stderr)
        return result

    def file_record(self,path):
        return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

    def numeric_manifest(self):
        return {'schema_version':1,'manuscript':self.file_record(self.ms),'checks':[{
            'id':'N1','kind':'numeric','manuscript_anchor':'For fatigue in treatment, the effect was 0.234.',
            'source':self.file_record(self.source),'row_key':{'outcome':'fatigue','group':'treatment'},
            'value_column':'value','manuscript_value':'0.234','source_unit':'correlation','target_unit':'correlation',
            'scale':'1','rounding':'half_up','context':{'outcome':'fatigue','group':'treatment'}}]}

    def verify(self,data):
        path=self.write('manifest.json',json.dumps(data))
        p=self.run_tool('verify_evidence.py',path)
        return p,json.loads(p.stdout) if p.stdout.strip() else None

    def test_unknown_mode_cannot_complete(self):
        log=self.write('gates.md','MODE: Z\nDONE: yes\n| G7 | pass | source.csv | note |\n')
        self.assert_rejected('gate_check.py',log)

    def test_na_cannot_bypass_required_gates(self):
        log=self.write('gates.md','MODE: A\nDONE: yes\n| G0 | na | | not needed |\n| G11 | na | | not needed |\n')
        self.assert_rejected('gate_check.py',log)

    def test_file_existence_does_not_certify_done(self):
        log=self.write('gates.md','MODE: A\nDONE: yes\n| G0 | pass | source.csv | |\n| G11 | pass | source.csv | |\n')
        self.assert_rejected('gate_check.py',log)

    def test_zero_number_coverage_rejected(self):
        self.assert_rejected('number_trace.py',self.empty,'--sources',self.source)

    def test_sign_is_not_automatically_ignored(self):
        ms=self.write('negative.md','# Results\n\nThe effect was -0.234.\n')
        self.assert_rejected('number_trace.py',ms,'--sources',self.source)

    def test_scaling_is_not_guessed(self):
        ms=self.write('scale.md','# Results\n\nThe score was 23.4.\n')
        self.assert_rejected('number_trace.py',ms,'--sources',self.source)

    def test_tables_are_scanned(self):
        ms=self.write('table.md','# Results\n\n| Outcome | Value |\n|---|---|\n| fatigue | 0.999 |\n')
        r=self.assert_rejected('number_trace.py',ms,'--sources',self.source)
        self.assertIn('0.999',r.stdout)

    def test_membership_success_does_not_claim_context_verified(self):
        r=self.run_tool('number_trace.py',self.ms,'--sources',self.source)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('启发式筛查',r.stdout)

    def test_scientific_notation_keeps_exponent(self):
        source=self.write('scientific.csv','value\n0.0012\n')
        ms=self.write('scientific.md','# Results\n\nThe estimate was 1.2e-3.\n')
        r=self.run_tool('number_trace.py',ms,'--sources',source)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        bad=self.write('scientific_bad.md','# Results\n\nThe estimate was 1.2e-2.\n')
        self.assert_rejected('number_trace.py',bad,'--sources',source)

    def test_membership_detects_number_next_to_chinese(self):
        ms=self.write('chinese.md','# 结果\n\n治疗组的效应为0.234。\n')
        r=self.run_tool('number_trace.py',ms,'--sources',self.source)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_empty_keywords_do_not_skip_disclosure_check(self):
        ledger=self.write('ledger.csv','id,analysis,result,supports_claim,tier,must_disclose,keywords,source,reviewer_question,decision\nA,exclusions,,,omit,y,,,,\n')
        r=self.assert_rejected('ledger_check.py',ledger,'--manuscript',self.empty)
        self.assertIn('必须披露',r.stdout)

    def test_missing_supplement_is_not_pass(self):
        ledger=self.write('ledger.csv','id,analysis,result,supports_claim,tier,must_disclose,keywords,source,reviewer_question,decision\nA,exclusions,,,supp,n,fatigue,source.csv,,\n')
        self.assert_rejected('ledger_check.py',ledger,'--manuscript',self.ms)

    def test_missing_requested_manuscript_rejected(self):
        letter=self.write('response.md','Reviewer 1\nComment 1: Clarify the result.\nResponse: Revised in Results.\n')
        self.assert_rejected('response_lint.py',letter,'--manuscript',self.root/'missing.md')

    def test_full_quote_tail_must_match(self):
        prefix='The long identical beginning of this sentence deliberately occupies more than eighty characters and '
        ms=self.write('tail.md','# Discussion\n\n'+prefix+'cannot establish causation.\n')
        letter=self.write('response.md','Reviewer 1\nComment 1: Clarify interpretation.\nResponse: Revised in Discussion: "'+prefix+'demonstrates causation."\n')
        self.assert_rejected('response_lint.py',letter,'--manuscript',ms,'--comments',1)

    def test_empty_comment_extraction_not_success(self):
        self.assert_rejected('response_lint.py',self.empty,'--to-matrix',self.root/'comments.csv')

    def test_zero_coding_units_rejected(self):
        p=self.write('coding.json','{"units":[]}')
        self.assert_rejected('move_check.py',p)

    def test_inline_text_does_not_prove_external_source(self):
        p=self.write('coding.json',json.dumps({'units':[{'role':'exemplar','paper':'fake','section':'disc_first','source':'missing.md','text':'The effect needs interpretation.','codes':[['FND','effect needs']]}]}))
        self.assert_rejected('move_check.py',p)

    def test_empty_cue_rejected(self):
        p=self.write('coding.json',json.dumps({'units':[{'role':'draft','paper':'draft','section':'results','source':'draft.md','text':'For fatigue in treatment, the effect was 0.234.','codes':[['FND','']]}]}))
        self.assert_rejected('move_check.py',p)

    def test_real_anchor_still_not_semantic_validation(self):
        p=self.write('coding.json',json.dumps({'units':[{'role':'draft','paper':'draft','section':'results','source':'draft.md','text':'For fatigue in treatment, the effect was 0.234.','codes':[['FND','effect was']]}]}))
        r=self.run_tool('move_check.py',p)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('不验证语步标签',r.stdout)

    def test_empty_benchmark_rejected(self):
        self.assert_rejected('bench_profile.py','--exemplars',self.empty,'--draft','d='+str(self.empty),'--report',self.root/'bench.md')

    def test_draft_cannot_benchmark_itself(self):
        self.assert_rejected('bench_profile.py','--exemplars',self.ms,'--draft','d='+str(self.ms),'--report',self.root/'bench.md')

    def test_mixed_language_pool_rejected(self):
        zh=self.write('zh.md','# 结果\n\n研究发现治疗组的疲劳症状与对照组不同。这一结果在不同测量时间都能够观察到。样本包括多种不同年龄的人群，研究团队按照事先规定的方法报告所有数据。\n')
        draft=self.write('other.md','# Results\n\nThe treatment group showed lower fatigue scores at follow up in the present sample.\n')
        self.assert_rejected('bench_profile.py','--exemplars',self.ms,zh,'--draft','d='+str(draft),'--report',self.root/'bench.md')

    def test_explicit_reference_numbers_are_used(self):
        refs=self.write('refs.md','# Introduction\n\nEvidence [1,2].\n\n# References\n\n[5] Smith A. 2020. Study one.\n\n[7] Jones B. 2021. Study two.\n')
        self.assert_rejected('ref_check.py',refs,'--style','num')

    def test_online_http_failure_does_not_pass(self):
        refs=self.write('refs.md','# Introduction\n\nEvidence [1].\n\n# References\n\n[1] Smith A. 2020. Study one. doi:10.1234/test\n')
        error=urllib.error.HTTPError('https://api.crossref.org',403,'forbidden',None,None)
        with patch.object(sys,'argv',['ref_check.py',str(refs),'--online']),patch.object(ref_check.urllib.request,'urlopen',side_effect=error):
            self.assertEqual(ref_check.main(),1)

    def test_numeric_structured_positive(self):
        p,r=self.verify(self.numeric_manifest())
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertEqual(r['checks'][0]['status'],'verified_mechanical')

    def test_numeric_context_count_adjacent_to_chinese(self):
        self.assertTrue(verify_evidence.bounded_phrase('112','主分析112人，差值2.1分。'))
        self.assertFalse(verify_evidence.bounded_phrase('112','主分析2112人。'))
        self.assertFalse(verify_evidence.bounded_phrase('112','112.5单位'))

    def test_latin_context_adjacent_to_chinese(self):
        self.assertTrue(verify_evidence.bounded_phrase('primary','本次primary分析'))
        self.assertFalse(verify_evidence.bounded_phrase('primary','nonprimary analysis'))

    def test_numeric_chinese_context_and_adjacent_number(self):
        self.ms.write_text('# 结果\n\n治疗组疲劳的效应为0.234。\n',encoding='utf-8')
        self.source.write_text('结局,组别,值\n疲劳,治疗组,0.234\n',encoding='utf-8')
        data=self.numeric_manifest();c=data['checks'][0]
        c.update(manuscript_anchor='治疗组疲劳的效应为0.234。',row_key={'结局':'疲劳','组别':'治疗组'},context={'结局':'疲劳','组别':'治疗组'},value_column='值')
        p,r=self.verify(data)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_same_value_wrong_context_rejected(self):
        data=self.numeric_manifest()
        self.source.write_text('outcome,group,value\nfatigue,treatment,0.234\nanxiety,control,0.234\n',encoding='utf-8')
        c=data['checks'][0];c['source']=self.file_record(self.source);c['row_key']={'outcome':'anxiety','group':'control'}
        c['context']={'outcome':'anxiety','group':'control'}
        p,r=self.verify(data)
        self.assertEqual(p.returncode,1)
        self.assertEqual(r['checks'][0]['status'],'failed')

    def test_stale_source_hash_rejected(self):
        data=self.numeric_manifest();self.source.write_text('changed',encoding='utf-8')
        p,r=self.verify(data)
        self.assertEqual(p.returncode,1)
        self.assertIn('Hash mismatch',r['checks'][0]['reason'])

    def test_stale_manuscript_hash_rejected(self):
        data=self.numeric_manifest();self.ms.write_text('changed',encoding='utf-8')
        p,r=self.verify(data)
        self.assertEqual(p.returncode,1)
        self.assertIn('Hash mismatch',r['reason'])

    def test_arbitrary_unit_conversion_rejected(self):
        data=self.numeric_manifest();data['checks'][0]['scale']='100'
        p,r=self.verify(data)
        self.assertEqual(p.returncode,1)
        self.assertEqual(r['checks'][0]['status'],'failed')

    def test_percent_conversion_requires_declared_units(self):
        self.ms.write_text('# Results\n\nFor fatigue in treatment, the proportion was 23.4%.\n',encoding='utf-8')
        data=self.numeric_manifest();c=data['checks'][0]
        c.update(manuscript_anchor='For fatigue in treatment, the proportion was 23.4%.',manuscript_value='23.4%',source_unit='proportion',target_unit='percent',scale='100')
        p,r=self.verify(data)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_empty_structured_checks_rejected(self):
        data=self.numeric_manifest();data['checks']=[]
        p,_=self.verify(data);self.assertEqual(p.returncode,2)

    def test_numeric_anchor_cannot_drop_negative_sign(self):
        self.ms.write_text('# Results\n\nFor fatigue in treatment, the effect was -0.234.\n',encoding='utf-8')
        data=self.numeric_manifest();data['checks'][0]['manuscript_anchor']='For fatigue in treatment, the effect was -0.234.'
        p,r=self.verify(data)
        self.assertEqual(p.returncode,1)
        self.assertIn('bounded token',r['checks'][0]['reason'])

    def test_citation_record_cannot_machine_certify_support(self):
        source=self.write('paper.md','# Results\n\nThe association was observational and could not establish causation.\n')
        data=self.numeric_manifest();data['checks']=[{'id':'C1','kind':'citation','manuscript_anchor':'For fatigue in treatment, the effect was 0.234.','source':self.file_record(source),'source_passage':'The association was observational and could not establish causation.','source_location':'Results paragraph 1','access_level':'fulltext','review':{'decision':'supports','reviewer':'A supplied name','reviewed_at':'2026-10-25','rationale':'A supplied rationale'}}]
        p,r=self.verify(data)
        self.assertEqual(p.returncode,1)
        self.assertEqual(r['checks'][0]['status'],'review_required')
        self.assertIn('not machine verified',r['checks'][0]['reason'])


if __name__=='__main__':
    unittest.main()
