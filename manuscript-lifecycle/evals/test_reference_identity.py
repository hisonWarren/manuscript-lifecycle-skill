"""A valid DOI must not bless an unrelated citation."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from reference_identity import compare

class ReferenceIdentity(unittest.TestCase):
    def setUp(self):
        self.record={'DOI':'10.1234/example','title':['Learning: an experiment'],
                     'author':[{'family':'Chen'}],'published-print':{'date-parts':[[2020]]},'published-online':{'date-parts':[[2019,12,1]]}}
    def test_existing_doi_with_other_title_or_author_fails(self):
        r=compare('10.1234/example','Unrelated clinical findings','Li',2020,self.record)
        self.assertEqual(r['status'],'identity_mismatch');self.assertTrue(r['checks']['doi'])
        self.assertFalse(r['checks']['title']);self.assertFalse(r['checks']['first_author'])
    def test_identity_match_does_not_verify_claim(self):
        r=compare('10.1234/example','Learning — an experiment','Chen',2019,self.record)
        self.assertEqual(r['status'],'identity_matched');self.assertFalse(r['claim_support_verified'])
    def test_missing_metadata_is_not_verified(self):
        r=compare('10.1234/example','Learning: an experiment','Chen',2020,{'DOI':'10.1234/example'})
        self.assertEqual(r['status'],'identity_mismatch')
