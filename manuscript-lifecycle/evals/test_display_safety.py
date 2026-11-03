"""Adversarial input and scientific-value preservation regressions."""
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from xml.etree import ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import journal_check as J
import table_style as T
import section_lint as S


class DisplaySafety(unittest.TestCase):
    def test_profile_typos_and_invalid_limits_are_refused(self):
        original = json.loads((ROOT / 'assets/journal_profiles/nature_article.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'p.json'
            for val in (-1, '200', True, None):
                prof = json.loads(json.dumps(original))
                prof['rules'][0]['max'] = val
                p.write_text(json.dumps(prof), encoding='utf-8')
                with self.assertRaises(ValueError): J.load_profile(p)
            prof = original
            prof['rules'][0]['check'] = 'title_charz'
            p.write_text(json.dumps(prof), encoding='utf-8')
            with self.assertRaises(ValueError): J.load_profile(p)

    def test_markdown_highlights_are_checked(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'm.md'
            p.write_text('## Highlights\n\n- ' + 'x' * 100 + '\n', encoding='utf-8')
            prof = J.load_profile(ROOT / 'assets/journal_profiles/cell_article.json')
            result = J.run(str(p), prof, True, None)
            self.assertEqual(result['counts']['highlights'], 1)
            self.assertIn('highlights', [i['rule'] for i in result['items']])

    def test_visual_words_do_not_hide_scientific_claim(self):
        self.assertTrue(J.interp_hit('The bars demonstrate clinical efficacy.'))
        self.assertFalse(J.interp_hit('Thicker lines indicate stronger connections.'))

    def test_failed_equivalence_test_and_scale_scores_remain_candidates(self):
        self.assertTrue(S.null_equiv('The groups were equivalent (P = .30), although the equivalence test failed.'))
        self.assertTrue(S.null_equiv('Scale scores were identical across groups (P = .30).'))

    def test_placeholder_masks_only_its_own_content(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'letter.md'
            for i, text in enumerate(('The authors declare no conflict of interest. [VERIFY: funding]', '[VERIFY: The authors declare no conflict of interest.]')):
                p.write_text(text, encoding='utf-8')
                report = Path(d) / ('r%d.json' % i)
                subprocess.run([sys.executable, str(ROOT / 'scripts/section_lint.py'), str(p), '--fragment', '--json', str(report)], capture_output=True, encoding='utf-8', check=False)
                codes = [x['code'] for x in json.loads(report.read_text(encoding='utf-8'))]
                self.assertEqual('N2' in codes, i == 0)

    def test_build_preserves_p_values_counts_and_large_integers(self):
        with tempfile.TemporaryDirectory() as d:
            csv = Path(d) / 't.csv'; out = Path(d) / 't.docx'
            csv.write_text('Measure,p,N,Estimate\nA,0.0004,9007199254740993,0.1234\nB,0.02,8,0.4567\n', encoding='utf-8')
            args = SimpleNamespace(csv=str(csv),out=str(out),title='Values',label='Table 1',note='',decimals=2)
            self.assertEqual(T.do_build(args), 0)
            tables, _ = T.read_docx_tables(out)
            self.assertEqual(tables[0]['rows'][1]['cells'], ['A','0.0004','9007199254740993','0.12'])
            self.assertEqual(T.fmt_num('9007199254740993', 2), '9007199254740993.00')

    def test_false_word_flags_and_cell_vertical_borders_are_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 't.docx'
            T.write_docx(p, 'Values', 'Table 1', ['Item','Value'], [['A','1']], ['left','right'], '')
            with zipfile.ZipFile(p) as z: files = {n:z.read(n) for n in z.namelist()}
            x = files['word/document.xml'].decode('utf-8').replace('<w:tblHeader/>','<w:tblHeader w:val="false"/>').replace('<w:cantSplit/>','<w:cantSplit w:val="0"/>')
            x = x.replace('<w:tcBorders>', '<w:tcBorders><w:left w:val="single"/>', 1)
            files['word/document.xml'] = x.encode('utf-8')
            with zipfile.ZipFile(p,'w') as z:
                for n,b in files.items(): z.writestr(n,b)
            tables, _ = T.read_docx_tables(p)
            self.assertFalse(tables[0]['header_repeat'])
            self.assertFalse(tables[0]['cant_split'])
            self.assertEqual(tables[0]['borders']['insideV'], 'single')

    def test_zero_p_value_in_separate_column_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 't.md'; report = Path(d) / 'r.json'
            p.write_text('| Test | p |\n| --- | --- |\n| A | 0.000 |\n', encoding='utf-8')
            args = SimpleNamespace(path=str(p),house='nature',report='',json=str(report))
            self.assertEqual(T.do_check(args), 1)
            self.assertTrue(json.loads(report.read_text(encoding='utf-8'))['errors'])

    def test_small_p_values_do_not_trigger_fixed_precision_advice(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 't.md'; report = Path(d) / 'r.json'
            p.write_text('| Test | p |\n| --- | --- |\n| A | 0.0004 |\n| B | 0.66 |\n| C | 0.2 |\n', encoding='utf-8')
            args = SimpleNamespace(path=str(p),house='nature',report='',json=str(report))
            self.assertEqual(T.do_check(args), 0)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertFalse(data['errors'])
            self.assertFalse(data['warnings'])
