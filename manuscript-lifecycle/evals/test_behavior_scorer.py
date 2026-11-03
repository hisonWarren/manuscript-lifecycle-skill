# -*- coding: utf-8 -*-
"""行为测试评分器自身的测试：负对照取自 behavior_cases 里的旧稿与合作者拟回复，正对照在测试内现写（不在包中存放参考答案）。"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def score(case, d):
    p = subprocess.run([sys.executable, os.path.join(HERE, "score_behavior.py"), case, "--dir", d], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


class BehaviorScorer(unittest.TestCase):
    def test_flawed_old_draft_and_collaborator_reply_fail(self):
        req = open(os.path.join(HERE, "behavior_cases", "revision_request.md"), encoding="utf-8").read()
        old = "\n\n".join(re.findall(r"^旧(?:摘要|结果|讨论|结论)：(.+)$", req, re.M))
        note = re.search(r"^旧表注：(.+)$", req, re.M).group(1)
        reply = re.search(r"^合作者拟回复：(.+)$", req, re.M).group(1)
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "revised.md"), "w", encoding="utf-8").write("# 旧稿\n\n" + old + "\n\n" + note + "\n")
            open(os.path.join(d, "response.md"), "w", encoding="utf-8").write(
                "# 回复\n\n## Reviewer 1\n\nR1：①补报次要结局；②讨论不能排除无差异；③说明亚组交互检验。\n\n回复：" + reply + "\n")
            code, out = score("revision", d)
        self.assertEqual(code, 1)
        n = int(re.search(r"未通过 (\d+)", out).group(1))
        self.assertGreaterEqual(n, 8, out)
        for key in ("V-外部验证(回复信)", "V-页码行号", "V-E1区间", "V-去夸大", "V-R1③亚组交互与验证"):
            self.assertIn(key, out)

    def test_collaborator_package_draft_fails(self):
        notes = open(os.path.join(HERE, "behavior_cases", "package_notes.md"), encoding="utf-8").read()
        g = lambda k: re.search(r"^%s：(.+)$" % k, notes, re.M).group(1)
        hi = "\n".join("- " + x.strip() for x in g("旧Highlights").split("- ") if x.strip())
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "package.md"), "w", encoding="utf-8").write(
                "# Display items\n\n%s\n\n%s\n\n%s\n\nHighlights:\n\n%s\n" % (g("旧表题"), g("旧表注"), g("旧图注"), hi))
            open(os.path.join(d, "cover_letter.md"), "w", encoding="utf-8").write(g("旧投稿信") + "\n")
            code, out = score("package", d)
        self.assertEqual(code, 1, out)
        self.assertGreaterEqual(int(re.search(r"未通过 (\d+)", out).group(1)), 10, out)
        for key in ("PK-表题", "PK-表注事后", "PK-Highlights因果", "PK-设计", "PK-声明不代填", "PK-不夸大"):
            self.assertIn(key, out)

    def test_student_polish_draft_fails(self):
        res = open(os.path.join(HERE, "behavior_cases", "polish_results.md"), encoding="utf-8").read()
        head = re.search(r"^旧讨论首段：(.+)$", res, re.M).group(1)
        concl = re.search(r"^旧结论：(.+)$", res, re.M).group(1)
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "zh_revised.md"), "w", encoding="utf-8").write(
                "## 讨论首段\n\n%s\n\n## 结论\n\n%s\n" % (head, concl))
            code, out = score("polish", d)
        self.assertEqual(code, 1, out)
        self.assertGreaterEqual(int(re.search(r"未通过 (\d+)", out).group(1)), 6, out)
        for key in ("PL-因果", "PL-趋势话术", "PL-建议越界", "PL-结论长度", "PL-不交叉引用"):
            self.assertIn(key, out)

    def test_minimal_correct_polish_passes_key_checks(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "zh_revised.md"), "w", encoding="utf-8").write(
                "## 讨论首段\n\n本研究在 860 名大学生中考察手机使用时长与抑郁症状的关联。使用时间越长的学生抑郁症状越多，"
                "其中一部分可经由较差的睡眠质量在统计上得到解释；事后探索未发现性别调节的证据。"
                "全部变量来自同一时点的自评问卷，这些结果描述的是统计关联，不能确定三者的先后顺序。\n\n"
                "## 结论\n\n在本样本中，手机使用时间较长与抑郁症状较多相关，睡眠质量较差可部分解释这一关联。"
                "横断面自评数据不能确定因果方向，还需纵向或干预研究检验。\n")
            open(os.path.join(d, "zh_note.md"), "w", encoding="utf-8").write("改动说明：删去因果与建议措辞。需要作者核对：派生比例与中介方向的假设。\n")
            code, out = score("polish", d)
        self.assertEqual(code, 0, out)

    def test_minimal_correct_answers_pass_key_checks(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "heldout1.md"), "w", encoding="utf-8").write("方法比较研究。Python 3.12.10；RMSE = sqrt(mean((estimate - truth)^2))；n=200，1000次，0.12、0.14、0.31、0.20。\n## 结论\n两种方法的表现随条件变化。\n")
            open(os.path.join(d, "heldout2.md"), "w", encoding="utf-8").write(
                "帮助的可见性。八名受访者说，能看到老师回复是他们继续提问的条件。P03 说：“我知道有人会看，所以才敢再问。”"
                "这一主题提示，反馈是否可见可能影响学习者是否继续求助；但访谈不能说明这种机制有多普遍。\n")
            code, out = score("heldout", d)
        self.assertEqual(code, 0, out)

    def test_missing_required_file(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = score("draft", d)
        self.assertEqual(code, 2)


class FindingFirstNegativeControl(unittest.TestCase):
    def test_ai_style_draft_fails_the_heldout_traps(self):
        import shutil
        here = os.path.dirname(os.path.abspath(__file__))
        tmp = tempfile.mkdtemp()
        try:
            shutil.copy(os.path.join(here, "behavior_cases", "findingfirst_negative.md"), os.path.join(tmp, "manuscript.md"))
            p = subprocess.run([sys.executable, os.path.join(here, "score_behavior.py"), "findingfirst", "--dir", tmp],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(p.returncode, 1, p.stdout)
            for k in ("FF-结构不变", "FF-中心性", "FF-因果", "FF-边差异", "FF-内部记录", "FF-标题长度", "FF-图注方法"):
                self.assertIn(k, p.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
