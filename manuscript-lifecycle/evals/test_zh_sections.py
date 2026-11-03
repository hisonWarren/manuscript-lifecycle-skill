"""中文期刊的标题与切节（不用标题样式的“一、”“（一）”、方括号摘要与关键词、PDF 折行与表头里的单字词），
目的写在综述之前时的 I1，报告的可重复性，以及随包领域包的完整性。"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import mslib as M  # noqa: E402

AIM = '鉴于此，本研究旨在回答两个研究问题：认知负荷是否调节学习投入与学习满意度的关系？这种调节作用是否因学段而异？'
ZH = '''# 混合学习中的认知负荷与学习投入

[摘要]　本研究考察混合学习情境下认知负荷对学习投入的调节作用，样本为初中学生，采用问卷与平台日志数据。
[关键词]　混合学习；认知负荷；学习投入

一、问题提出

混合学习带来新的认知负荷问题，已有研究对其作用方向的结论并不一致，需要在真实课堂中检验。

%s

二、相关研究

（一）认知负荷

已有研究区分了内在负荷与外在负荷，并讨论了二者对学习投入的不同影响。

（二）学习投入

学习投入包括行为、认知与情感三个方面，在线情境下以平台行为数据测量较多。

三、研究设计

（一）研究样本

共收回问卷 293 份，有效率为 96%%，样本来自两所初中的七、八年级。

2023 年 12 月

四、结果呈现

0.895

表1　各变量的描述统计
方法
条目及描述

调节效应在七年级样本中更明显，八年级样本中的估计不精确。

五、讨论与思考

讨论

结果提示负荷管理比单纯增加学习资源更重要。
伦理关怀意识涵养。高校要遵循价值对齐原则，主
动引导学生合理使用技术。

六、落地方向和关键抓手

学校层面需要统筹课程与平台建设。

参考文献

[1] 张三. 混合学习研究[J]. 开放教育研究, 2023.
'''


def find(blocks, text):
    return next(b for b in blocks if b['kind'] != 'heading' and text in b['text'])


class ChineseSections(unittest.TestCase):
    def test_bracketed_reference_heading_excludes_bibliography_from_body(self):
        for heading in ('[ 参考文献]', '【参 考 文 献】', '［参考文献］：'):
            with self.subTest(heading=heading):
                text = '## 讨论\n\n结果需要结合样本背景理解。\n\n%s\n[1] 王某. 学习研究[J]. 测试期刊, 2024.\n\nAbstract: This study examines learning outcomes.\n' % heading
                blocks = M.parse(M.normalize(text))
                self.assertEqual(find(blocks, '学习研究')['sec'], 'references')
                self.assertEqual(find(blocks, 'This study')['sec'], 'back')
                self.assertEqual(M.section_paras(blocks, ['discussion']), ['结果需要结合样本背景理解。'])

    def test_wrapped_abstract_prose_does_not_become_methods(self):
        text = '摘 要 本研究考察合作学习。\n研究设计了两个任务, 要求参与者共同完成练习, 并记录学习行为。\n关键词  合作；学习\n\n1 引言\n\n学习行为需要结合课堂情境研究。\n\n2 方法\n\n2.1 研究设计\n\n采用随机分配的课堂实验。\n'
        blocks = M.parse(M.normalize(text))
        self.assertEqual(find(blocks, '两个任务')['sec'], 'abstract')
        self.assertEqual(find(blocks, '随机分配')['sec'], 'methods')
        self.assertTrue(any(b['kind'] == 'heading' and b['text'] == '研究设计' and b['sec'] == 'methods' for b in blocks))

    def test_empirical_heading_variants_and_figure_labels(self):
        text = '三、研究设计与方法\n\n学习者随机分配到两个组。\n\n四、结果\n\n两组任务成绩存在差异。\n\nlimitation\n\n学习行为与成绩的关系仍然存在。\n\n五、简要讨论\n\n这些发现需要结合任务情境理解。\n\n六、结论与局限\n\n本研究来自单一学校，推广需要谨慎。\n'
        blocks = M.parse(text)
        for phrase, section in [('随机分配', 'methods'), ('关系仍然存在', 'results'), ('结合任务', 'discussion'), ('单一学校', 'discussion')]:
            self.assertEqual(find(blocks, phrase)['sec'], section)

    def test_numbered_results_subsection_inside_combined_methods_results(self):
        text = '三、研究方法与结果\n\n（二）实验与结果\n\n1. 数据处理\n\n本研究对学生的提问文本进行分词和分类。\n\n4. 主题词抽取结果\n\n实验组提出了更多主题，并且对话次数增加。\n\n四、讨论\n\n主题丰富程度可能反映了不同交互机会。\n'
        blocks = M.parse(text)
        self.assertEqual(find(blocks, '分词')['sec'], 'methods')
        self.assertEqual(find(blocks, '更多主题')['sec'], 'results')
        self.assertEqual(find(blocks, '不同交互')['sec'], 'discussion')

    def test_numbered_plain_headings_split_an_education_style_paper(self):
        blocks = M.parse(M.normalize(ZH % AIM))
        self.assertEqual(find(blocks, '本研究考察')['sec'], 'abstract')
        self.assertEqual(find(blocks, '关键词')['sec'], 'front')
        self.assertEqual(find(blocks, '鉴于此')['sec'], 'introduction')
        lit = find(blocks, '内在负荷')
        self.assertEqual((lit['sec'], lit['part']), ('introduction', '相关研究'))
        self.assertEqual(find(blocks, '293 份')['sec'], 'methods')
        self.assertEqual(find(blocks, '七年级样本')['sec'], 'results')          # 表头里的“方法”不切节
        self.assertEqual(find(blocks, '0.895')['kind'], 'table')                 # 孤立数字行是表格残留
        self.assertEqual(find(blocks, '伦理关怀')['sec'], 'discussion')          # 带句读的折行不是“伦理”声明标题
        self.assertEqual(find(blocks, '统筹课程')['sec'], 'discussion')          # 主题式标题留在所在节
        self.assertFalse(any('2023 年 12 月' in b['text'] for b in blocks))      # 期刊年月页眉
        self.assertEqual(blocks[-1]['sec'], 'references')

    def test_english_text_keeps_its_previous_parsing(self):
        en = 'Introduction\n\nWe studied help seeking. The aim of this study was to test visibility.\n\nMethods\n\nParticipants were 120 adults.\n\n0.895\n\nResults\n\nThe effect was small.\n'
        blocks = M.parse(en)
        self.assertEqual([b['sec'] for b in blocks if b['kind'] == 'heading'], ['introduction', 'methods', 'results'])
        self.assertEqual(find(blocks, '0.895')['kind'], 'para')

    def lint(self, text):
        with tempfile.TemporaryDirectory() as td:
            p, r = Path(td)/'paper.md', Path(td)/'report.md'
            p.write_text(text, encoding='utf-8')
            subprocess.run([sys.executable, str(ROOT/'scripts'/'section_lint.py'), str(p), '--report', str(r)], capture_output=True)
            return r.read_text(encoding='utf-8')

    def test_aims_stated_before_a_literature_review_satisfy_i1(self):
        self.assertNotIn('**MUST I1**', self.lint(ZH % AIM))
        self.assertIn('**MUST I1**', self.lint(ZH % '课堂中的负荷问题值得关注。'))

    def test_report_is_identical_across_hash_seeds(self):
        a = 'the scale measures perceived deficits in attention memory and planning in daily life.'
        b = 'we used the scale that measures perceived deficits in attention memory and planning.'
        text = ('Introduction\n\n%s The aim of this study was to test it.\n\nMethods\n\n%s\n\nDiscussion\n\n'
                'Overall %s and %s\n' % (a.capitalize(), b.capitalize(), a, b))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'paper.md'; p.write_text(text, encoding='utf-8')
            out = []
            for seed in ('1', '2', '3'):
                r = Path(td)/('r%s.md' % seed)
                subprocess.run([sys.executable, str(ROOT/'scripts'/'section_lint.py'), str(p), '--report', str(r)],
                               capture_output=True, env=dict(os.environ, PYTHONHASHSEED=seed))
                out.append(r.read_text(encoding='utf-8').replace(r.name, ''))
        self.assertIn('X1', out[0])
        self.assertEqual(out[0], out[1]); self.assertEqual(out[1], out[2])

    def test_every_shipped_domain_pack_checks_clean(self):
        packs = sorted(p.parent for p in (ROOT/'assets'/'domains').glob('*/profile.json'))
        self.assertTrue({'clinical_psych_en', 'education_zh', 'psychology_zh'}.issubset({p.name for p in packs}))
        for pack in packs:
            r = subprocess.run([sys.executable, str(ROOT/'scripts'/'domain_pack.py'), 'check', str(pack)], capture_output=True)
            self.assertEqual(r.returncode, 0, r.stdout.decode('utf-8')[-300:])
            self.assertIn('问题 0', r.stdout.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
