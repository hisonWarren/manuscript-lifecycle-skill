"""Regression checks from independent execution and Word revision inspection."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import mslib as M
import delivery_check as D
spec = importlib.util.spec_from_file_location('behavior_score', ROOT/'evals'/'score_behavior.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

class IndependentRegression(unittest.TestCase):
    def test_utf8_stderr_with_legacy_windows_encoding(self):
        env = dict(os.environ, PYTHONIOENCODING='gbk')
        p = subprocess.run([sys.executable, '-c', 'import mslib,sys; print("输入错误：文件不存在",file=sys.stderr)'], cwd=ROOT/'scripts', env=env, capture_output=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn('输入错误', p.stderr.decode('utf-8'))

    def test_moved_text_has_one_location_in_each_reading(self):
        p = ET.fromstring('<w:p xmlns:w="'+D.NS['w']+'"><w:moveFrom><w:r><w:t>Moved</w:t></w:r></w:moveFrom><w:r><w:t>Middle</w:t></w:r><w:moveTo><w:r><w:t>Moved</w:t></w:r></w:moveTo></w:p>')
        self.assertEqual(M._ptext(p, 'accept'), 'MiddleMoved')
        self.assertEqual(M._ptext(p, 'reject'), 'MovedMiddle')

    def test_deleted_tab_and_break_do_not_survive_acceptance(self):
        p = ET.fromstring('<w:p xmlns:w="'+D.NS['w']+'"><w:r><w:t>A</w:t></w:r><w:del><w:r><w:tab/><w:br/><w:delText>B</w:delText></w:r></w:del><w:r><w:t>C</w:t></w:r></w:p>')
        self.assertEqual(M._ptext(p, 'accept'), 'AC')
        self.assertEqual(M._ptext(p, 'reject'), 'A\t\nBC')

    def test_clean_word_rejects_move_and_format_revisions(self):
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            for name,xml in [('move','<w:p><w:moveFrom><w:r><w:t>old</w:t></w:r></w:moveFrom><w:moveTo><w:r><w:t>new</w:t></w:r></w:moveTo></w:p>'),('format','<w:p><w:pPr><w:pPrChange><w:pPr/></w:pPrChange></w:pPr><w:r><w:t>Text</w:t></w:r></w:p>')]:
                path=base/(name+'.docx')
                with zipfile.ZipFile(path,'w') as z:
                    z.writestr('word/document.xml','<w:document xmlns:w="'+D.NS['w']+'"><w:body>'+xml+'</w:body></w:document>')
                entry=dict(id=name,path=path.name,role='manuscript_clean',sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                report=D.evaluate(dict(schema_version=1,files=[entry],required_roles=['manuscript_clean'],displays=[]),base)
                self.assertTrue(any(f['code']=='docx_residue' for f in report['findings']))
                entry['role']='manuscript_marked'
                report=D.evaluate(dict(schema_version=1,files=[entry],required_roles=['manuscript_marked'],displays=[]),base)
                self.assertFalse(any(f['code']=='no_tracked_changes' for f in report['findings']))

    def test_package_markdown_and_equivalent_english(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            (base/'package.md').write_text('**Table 2. Associations with scores**\nNote. CI = confidence interval; SES = socioeconomic status. Post hoc analysis; no sex interaction was tested. n=1,032; imputation n=1,204.\n**Figure 1. Scores.** Shading is 95% confidence intervals, covariates held at sample means.\n## Highlights\n- A cohort examined associations.\n- Estimates were uncertain.\n- Follow-up was 12 months.',encoding='utf-8')
            (base/'cover_letter.md').write_text('This study uses the same cohort as the attendance paper.',encoding='utf-8')
            (base/'author_todo.md').write_text('Confirm approval identifier, competing-interest declarations, funding, data sharing, and the 2024 citation.',encoding='utf-8')
            self.assertEqual(S.score_package(td).fails(),[])
            p=base/'package.md';p.write_text(p.read_text(encoding='utf-8').replace('Associations with scores','Effect of tutoring'),encoding='utf-8')
            self.assertIn('PK-表题',{r['id'] for r in S.score_package(td).fails()})

    def test_heldout_conclusion_excludes_separate_author_note(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td)/'heldout1.md').write_text('方法比较。Python 3.12.10; RMSE = sqrt(mean((estimate - truth)^2)); 0.12 0.14 0.31 0.20\n## 结论\n所考察条件下方法表现不同。\n## 待核说明\n'+'未提供其他条件。'*40,encoding='utf-8')
            (Path(td)/'heldout2.md').write_text('八名参与者：我知道有人会看，所以才敢再问。不能判断多普遍。',encoding='utf-8')
            rows=S.score_heldout(td).rows
            self.assertEqual(next(r['result'] for r in rows if r['id']=='H1-结论长度'),'通过')

    def test_heldout_missing_one_task_cannot_pass(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td)/'heldout2.md').write_text('Only one task',encoding='utf-8')
            with self.assertRaises(FileNotFoundError):
                S.score_heldout(td)

    def test_polish_boundary_accepts_explicit_causal_denial(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td)/'zh_revised.md').write_text('# 讨论首段\n横断面自评数据无法确定手机使用、睡眠与抑郁症状的时间顺序。\n# 结论\n横断面结果不能确立因果关系。',encoding='utf-8')
            self.assertEqual(next(r['result'] for r in S.score_polish(td).rows if r['id']=='PL-保留边界'),'通过')

    def test_revision_discussion_may_deny_mechanism(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td)/'response.md').write_text('回复：核对结果。',encoding='utf-8')
            p=Path(td)/'revised.md';p.write_text('## 摘要\n主要结果尚不确定。\n## 讨论\n未提供支持深度编码的证据。',encoding='utf-8')
            self.assertEqual(next(r['result'] for r in S.score_revision(td).rows if r['id']=='V-去夸大'),'通过')
            p.write_text('## 结果\n结果证明深度编码。',encoding='utf-8')
            self.assertEqual(next(r['result'] for r in S.score_revision(td).rows if r['id']=='V-去夸大'),'未通过')

    def test_revision_exaggeration_is_checked_in_discussion_too(self):
        cases = [('## 讨论\n本研究证实了反馈的作用。', '未通过'),
                 ('## 讨论\n这些结果不能证实反馈改善了成绩。', '通过'),
                 ('## 讨论\n研究并未提供足以支持上述深度编码机制的证据。', '通过'),
                 ('## 讨论\n结果不仅证实了假设，也凸显了框架价值。', '未通过'),
                 ('## 讨论\n虽然差异不显著，但证实了趋势。', '未通过')]
        for text, expected in cases:
            with tempfile.TemporaryDirectory() as td:
                (Path(td)/'response.md').write_text('回复：核对结果。',encoding='utf-8')
                (Path(td)/'revised.md').write_text('## 摘要\n主要结果尚不确定。\n'+text,encoding='utf-8')
                got = next(r['result'] for r in S.score_revision(td).rows if r['id']=='V-去夸大')
                self.assertEqual(got, expected, text)

    def test_same_anchor_merges_across_section_labels(self):
        import review_merge as R
        q1 = '低基线亚组40人的差值为5.2分（95% CI 0.3至10.1），证明其获益显著大于其他学生。'
        q2 = '解释反馈能否改善延迟概念测验成绩是本研究的问题。'
        f = lambda role, sev, sec, q: dict(role=role, id=role+sec, severity=sev, section=sec, quote=q)
        groups = R.cluster([f('cold_reader', 'major', 'results', q1), f('reviewer_argument', 'major', 'results/discussion', q1),
                            f('reviewer_argument', 'minor', 'introduction', q2), f('reviewer_language', 'note', 'global', q2),
                            f('reviewer_methods', 'minor', 'methods', '本研究'), f('reviewer_language', 'minor', 'discussion', '本研究')])
        self.assertEqual(sorted(len(g) for g in groups), [1, 1, 2, 2])

    def test_draft_denial_is_local_and_does_not_hide_a_later_assertion(self):
        cases = [
            ('学生能辨认错误，不等于已经证明其延后概念掌握得到改善。', '通过'),
            ('虽然证据不足，但本研究证明概念掌握显著提高。', '未通过'),
            ('本研究不仅证明概念掌握提高，还支持知识迁移。', '未通过'),
            ('未成年学生概念成绩显著提高。', '未通过'),
            ('未采用盲法但概念成绩显著提高。', '未通过'),
            ('虽然未预注册但概念成绩显著提高。', '未通过'),
            ('概念成绩未显著提高。', '通过'),
            ('尚未证实概念成绩改善。', '通过'),
            ('没有证明概念成绩得到改善。', '通过'),
        ]
        for sentence, expected in cases:
            with tempfile.TemporaryDirectory() as td:
                (Path(td)/'manuscript.md').write_text('## 讨论\n\n'+sentence, encoding='utf-8')
                got = next(r['result'] for r in S.score_draft(td).rows if r['id']=='D-主要结论')
                self.assertEqual(got, expected)

    def test_package_short_notes_and_hyphenated_todo_do_not_need_redundant_numbers(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d/'package.md').write_text('Figure 1. Predictions for 1,032 complete cases.\nNote. The sensitivity analysis used 20 multiply imputed datasets.', encoding='utf-8')
            (d/'cover_letter.md').write_text('Dear Editor, This is a prospective cohort.', encoding='utf-8')
            (d/'author_todo.md').write_text('Confirm approval number, conflicts, funding, data-availability and the 2024 paper citation.', encoding='utf-8')
            rows = {r['id']: r['result'] for r in S.score_package(td).rows}
            self.assertEqual(rows['PK-样本'], '通过')
            self.assertEqual(rows['PK-待办'], '通过')
            (d/'package.md').write_text('The main analysis used 1,032 complete cases; multiple imputation used 1,204 students.', encoding='utf-8')
            rows = {r['id']: r['result'] for r in S.score_package(td).rows}
            self.assertEqual(rows['PK-样本'], '通过')
            for wrong in ('Main analysis: n = 1,204.', 'Multiple imputation analysis: n = 1,032.', 'The main analysis used 9,999 complete cases.',
                          'The multiply imputed sample comprised 1,032 students.', '1,032 imputed participants were analyzed.'):
                (d/'package.md').write_text(wrong, encoding='utf-8')
                rows = {r['id']: r['result'] for r in S.score_package(td).rows}
                self.assertEqual(rows['PK-样本'], '未通过')

if __name__ == '__main__':
    unittest.main()
