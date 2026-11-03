import copy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from display_profile import profile
from audit_run import digest

class DisplayProfiles(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
        self.data={'schema_version':1,'records':[]}
        for i,(role,text) in enumerate([('draft','Bars show means and 95% confidence intervals.'),('exemplar','Bars represent 95% confidence intervals.')]):
            p=self.p/(str(i)+'.md');p.write_text(text,encoding='utf-8')
            self.data['records'].append({'id':str(i),'role':role,'paper_id':str(i),'path':p.name,'sha256':digest(p),
                'text':text,'kind':'figure_caption','task':'group mean','language':'en','panels':1})
    def test_descriptive_not_quality_pass(self):
        out=profile(self.data,self.p);self.assertFalse(out['quality_pass']);self.assertEqual(out['comparisons'][0]['papers'],1)
    def test_forged_excerpt_rejected(self):
        self.data['records'][1]['text']='Not actually read'
        with self.assertRaises(ValueError):profile(self.data,self.p)
    def test_stale_source_rejected(self):
        (self.p/'1.md').write_text('changed',encoding='utf-8')
        with self.assertRaises(ValueError):profile(self.data,self.p)
    def test_complexity_not_mixed(self):
        self.data['records'][1]['panels']=4
        self.assertEqual(profile(self.data,self.p)['comparisons'][0]['papers'],0)
    def test_language_not_mixed(self):
        self.data['records'][1]['language']='zh'
        self.assertEqual(profile(self.data,self.p)['comparisons'][0]['papers'],0)
    def test_duplicates_not_independent_papers(self):
        r=copy.deepcopy(self.data['records'][1]);r['id']='another';self.data['records'].append(r)
        out=profile(self.data,self.p)['comparisons'][0];self.assertEqual(out['papers'],1);self.assertEqual(out['items'],1)
    def test_self_benchmark_excluded(self):
        self.data['records'][1].update(path='0.md',text=self.data['records'][0]['text'],sha256=digest(self.p/'0.md'))
        self.assertEqual(profile(self.data,self.p)['comparisons'][0]['papers'],0)
    def test_empty_corpus_rejected(self):
        with self.assertRaises(ValueError):profile({'schema_version':1,'records':[]},self.p)

if __name__=='__main__':unittest.main()
