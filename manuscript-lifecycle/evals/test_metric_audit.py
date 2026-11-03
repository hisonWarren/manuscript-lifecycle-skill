"""Regression tests for source-based arithmetic, reported-value comparison and boundaries."""
from pathlib import Path
import csv
import json
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import metric_audit as A


class MetricAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.csv=self.root/'toy.csv'
        self.spec=self.root/'spec.json'
        self.rows=[
            ['A','10','4','2','1','3'],['A','10','4','3','0','5'],
            ['B','10','8','4','1','2'],['B','10','8','3','0','5']]
        self.write_csv()
        self.conf={'schema_version':1,'group_by':'arm','metrics':[
            {'id':'unconditional','kind':'rate','numerator':'success','denominator':'all','aggregation':'mean_row_ratios',
              'reported_by_group':{'A':.25,'B':.35}},
            {'id':'conditional','kind':'rate','numerator':'success','denominator':'prompt','aggregation':'pooled'},
            {'id':'completion','kind':'event_fraction','column':'mastered','positive_values':['1']},
            {'id':'days','kind':'capped_mean','column':'days','event_column':'mastered','event_values':['1'],'cap':5},
            {'id':'avg_days','kind':'mean','column':'days'}]}
        self.save()
    def tearDown(self): self.temp.cleanup()
    def write_csv(self):
        with self.csv.open('w',encoding='utf-8',newline='') as f:
            w=csv.writer(f);w.writerow(['arm','all','prompt','success','mastered','days']);w.writerows(self.rows)
    def save(self): self.spec.write_text(json.dumps(self.conf),encoding='utf-8')
    def result(self): return A.audit(self.csv,self.spec)
    def test_detect_denominator_change_and_cap(self):
        x=self.result();a=x['groups']['A']['metrics'];b=x['groups']['B']['metrics']
        self.assertAlmostEqual(a['unconditional']['value'],.25)
        self.assertAlmostEqual(a['conditional']['value'],.625)
        self.assertAlmostEqual(b['conditional']['value'],.4375)
        self.assertEqual(a['days']['unfinished_or_capped_n'],1)
        self.assertAlmostEqual(b['days']['value'],3.5)
        self.assertEqual(x['reported_mismatches'],[])
        self.assertNotEqual(x['status'],'scientifically_validated')
    def test_rate_mismatch_is_flagged(self):
        self.conf['metrics'][0]['reported_by_group']['B']=.5;self.save()
        self.assertEqual(len(self.result()['reported_mismatches']),1)
        cmd=[sys.executable,str(Path(A.__file__)),'--csv',str(self.csv),'--spec',str(self.spec)]
        p=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(p.returncode,1)
    def test_duplicate_header_refused(self):
        self.csv.write_text('arm,arm,prompt,success,mastered,days\nA,10,4,2,1,3\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'duplicate'): self.result()
    def test_out_of_range_rejected(self):
        self.rows[0][3]='12';self.write_csv()
        with self.assertRaisesRegex(ValueError,'numerator'): self.result()
    def test_no_zero_denominator(self):
        self.rows[0][2]='0';self.write_csv()
        with self.assertRaisesRegex(ValueError,'denominator'): self.result()
    def test_missing_group_rejected(self):
        self.rows[0][0]='';self.write_csv()
        with self.assertRaisesRegex(ValueError,'Incomplete'): self.result()
    def test_nonfinite_refused(self):
        self.rows[0][2]='NaN';self.write_csv()
        with self.assertRaisesRegex(ValueError,'finite'): self.result()
    def test_reported_group_missing_is_rejected(self):
        self.conf['metrics'][0]['reported_by_group']['Z']=.42;self.save()
        with self.assertRaisesRegex(ValueError,'absent from CSV'):self.result()
    def test_report_is_not_overwritten(self):
        old=self.root/'out.json';old.write_text('KEEP',encoding='utf-8')
        cmd=[sys.executable,str(Path(A.__file__)),'--csv',str(self.csv),'--spec',str(self.spec),'--out',str(old)]
        p=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(p.returncode,2);self.assertEqual(old.read_text(encoding='utf-8'),'KEEP')
    def test_mean_row_vs_pooled_not_interchangeable(self):
        self.rows[1][2]='2';self.rows[1][3]='0';self.write_csv()
        x=self.result()['groups']['A']['metrics']['conditional']
        self.assertTrue(x['aggregation_differs']);self.assertNotAlmostEqual(x['pooled_rate'],x['mean_row_rate'])
    def test_cap_overflow_raises(self):
        self.rows[0][-1]='7';self.write_csv()
        with self.assertRaisesRegex(ValueError,'exceeds cap'):self.result()


if __name__=='__main__': unittest.main()
