import ast
import re
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PackageStructure(unittest.TestCase):
    def test_scripts_parse(self):
        for p in (ROOT/'scripts').glob('*.py'):
            with self.subTest(path=p.name): ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    def test_local_markdown_links_resolve(self):
        for p in [ROOT/'SKILL.md',*(ROOT/'references').glob('*.md')]:
            for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
                if re.match(r'https?://|#',target): continue
                target=target.split('#')[0]
                with self.subTest(source=p.name,target=target): self.assertTrue((p.parent/target).exists())
    def test_entrypoint_frontmatter(self):
        text=(ROOT/'SKILL.md').read_text(encoding='utf-8-sig')
        self.assertTrue(text.startswith('---\n'))
        header=text.split('---',2)[1]
        self.assertRegex(header,r'(?m)^name: manuscript-lifecycle$')
        self.assertRegex(header,r'(?m)^description:')

    def test_description_fits_the_frontmatter_limit(self):
        text=(ROOT/'SKILL.md').read_text(encoding='utf-8-sig')
        header=text.split('---',2)[1]
        m=re.search(r'(?m)^description:\s*"(.*)"\s*$',header)
        self.assertIsNotNone(m)
        self.assertLessEqual(len(m.group(1)),1024,'description 超过 1024 字符')
        self.assertNotRegex(m.group(1),r'[<>]')
        self.assertLess(len(text.splitlines()),500,'SKILL.md 应保持在 500 行以内，细节放 references')

    def test_default_path_comes_first(self):
        text=(ROOT/'SKILL.md').read_text(encoding='utf-8-sig')
        self.assertLess(text.find('## 0. 最短路径'),text.find('## 1. 判断任务与材料'),'作者要的是稿件：最短路径必须在最前面')
        self.assertIn('check_all.py',text[:text.find('## 1. 判断任务与材料')])

    def test_skill_is_self_contained(self):
        """不依赖、不提及其他 skill 或外部写作工具：不是每个用户都装了它们。"""
        bad=re.compile(r'humaniz|no-ai-slop|anti-defensive|patina|qu-ai-wei|nsfc|grant-copilot|advisor-orchestration|gated-pipeline|expert-peer-review|skill-creator|methodology-review',re.I)
        files=[ROOT/'SKILL.md',*(ROOT/'references').glob('*.md'),*(ROOT/'agents').glob('*'),*(ROOT/'assets').rglob('*.md'),*(ROOT/'assets'/'templates').glob('*')]
        for p in files:
            if p.is_file():
                with self.subTest(path=str(p.relative_to(ROOT))):
                    self.assertIsNone(bad.search(p.read_text(encoding='utf-8-sig',errors='replace')))

    def test_every_script_is_documented(self):
        doc=(ROOT/'SKILL.md').read_text(encoding='utf-8-sig')+(ROOT/'references'/'17_tool_contracts.md').read_text(encoding='utf-8-sig')
        for p in (ROOT/'scripts').glob('*.py'):
            if p.stem in ('mslib','output_safety'):
                continue
            with self.subTest(script=p.name):
                self.assertIn(p.stem,doc,'脚本没有写进 SKILL.md 或 17_tool_contracts.md')

if __name__=='__main__':unittest.main()
