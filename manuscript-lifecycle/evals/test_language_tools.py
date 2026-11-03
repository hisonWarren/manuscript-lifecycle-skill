# -*- coding: utf-8 -*-
"""语言与片段类工具的测试：中文切节、批准号、回复信拼写与分点、交付残留与占位符、断言与设计规则、片段模式、句式对照、语言修订计划、图注表注抽取。"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, S)
import mslib as M  # noqa: E402


def run(script, *args):
    p = subprocess.run([sys.executable, os.path.join(S, script)] + list(args), capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def write(d, name, text):
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


EN_DOC = """# Mood and complaints

## Abstract

We studied mood. Scores fell by 12.5 points (95% CI 8.1 to 16.9).

## Introduction

Mood matters for recovery (Smith et al., 2020). We asked whether complaints track mood.

## Methods

We analysed 112 patients. Models were fitted in R.

## Results

Scores fell by 12.5 points in the treated group rather than in controls (Table 1).

## Discussion

The decline reflects mood rather than cognition. Complaints were stable rather than variable, and this was not explained by age (Lee, 2019).

Taken together, these findings highlight the importance of mood in follow-up.

## Conclusions

Mood may potentially suggest recovery.
"""


def exemplar(i, disc):
    return """# Paper %d

## Abstract

We examined symptoms in a clinical cohort over two years and report associations with functioning.

## Introduction

Symptoms vary over time in clinical samples (Brown, 2015). Few studies separate stable and changing parts of these reports.

## Methods

Participants completed questionnaires at four visits. Mixed models were used to estimate change across visits in all participants.

## Results

Symptom scores declined across visits. Functioning improved in parallel with the decline in symptoms over the study period.

## Discussion

%s

## Conclusion

Symptoms and functioning changed together over the study period.
""" % (i, disc)


DISC_VARIANTS = [
    "The present study examined change in symptoms over time. For example, scores fell between the first two visits in most participants. However, the decline was smaller in older participants. These patterns agree with earlier cohort work on the course of symptoms.",
    "The present study followed patients for two years. For example, functioning improved in parallel with symptom change at each visit. However, the size of change varied across clinics. Earlier work reported a similar course in outpatients with comparable baseline severity.",
    "The present study adds repeated measures to this literature. For example, change at the second visit predicted later functioning in the cohort. However, attrition was higher in the last year. Similar findings were reported in an inpatient sample followed over one year.",
    "The current study describes symptom course in routine care. For example, most of the improvement occurred early in treatment. However, some participants worsened after discharge. Comparable trajectories were reported in community samples followed for several years.",
]


class ChineseSectioning(unittest.TestCase):
    def test_pua_page_marks_running_heads_and_multi_experiment(self):
        text = "\n".join([
            "1  引言\uf020", "", "抑郁与主观认知相关，但二者关系尚不清楚。" * 3, "", "## 第 2 页", "", "426 心 理 科 学 进 展 第 33 卷", "",
            "2  实验 1：情绪启动", "", "2.1  被试", "", "共招募 40 名大学生参加实验，均为右利手。" * 2, "",
            "2.4  实验结果", "", "两组反应时差异显著，效应量中等。" * 2, "",
            "3  实验 2：认知负荷", "", "3.1  被试", "", "共招募 42 名大学生参加实验，均为右利手。" * 2, "",
            "3.3  结果", "", "两组正确率差异显著，效应量较小。" * 2, "",
            "4  总讨论", "", "两项实验的结果一致，提示情绪启动影响主观评价。" * 2])
        with tempfile.TemporaryDirectory() as d:
            blocks = M.parse(M.load_text(write(d, "zh.md", text)))
        paras = [b for b in blocks if b["kind"] == "para"]
        seq = []
        for b in paras:
            if not seq or seq[-1] != b["sec"]:
                seq.append(b["sec"])
        self.assertEqual(seq[0], "introduction")
        self.assertIn("results", seq)
        self.assertEqual(seq[-1], "discussion")
        first_m, first_r = seq.index("methods"), seq.index("results")
        self.assertLess(first_m, first_r)
        self.assertIn("methods", seq[first_r:], "第二个实验的方法应重新识别为方法")
        joined = " ".join(b["text"] for b in blocks)
        self.assertNotIn("第 2 页", joined)
        self.assertNotIn("心 理 科 学", joined)
        self.assertNotIn("\uf020", joined)


class StatisticsDenseProse(unittest.TestCase):
    def test_statistics_lines_in_results_prose_are_not_tables(self):
        text = "\n".join(["# T", "", "## Results", "",
                         "被试在匹配试次中有更高的信心评分 (2.32 ± 0.48),",
                         "t(37) = 3.20, p = 0.003, Cohen’s d = 0.52, 95% CI =",
                         "[0.05, 0.21], BF 10 = 12.31 ( 图 2c)。", "",
                         "Age 34.2 8.1 35.1 7.9 0.42 0.68", "", "## Discussion", "", "结果与预期一致。"])
        with tempfile.TemporaryDirectory() as d:
            blocks = M.parse(M.load_text(write(d, "s.md", text)))
        res = [b for b in blocks if b["sec"] == "results"]
        prose = " ".join(b["text"] for b in res if b["kind"] == "para")
        self.assertIn("t(37) = 3.20", prose)
        self.assertIn("信心评分", prose)
        self.assertTrue(any(b["kind"] == "table" and b["text"].startswith("Age") for b in res), res)


class RefCheckIdentifiers(unittest.TestCase):
    def test_approval_number_is_not_a_citation(self):
        doc = ("# T\n\n## Methods\n\nThe study was approved by the ethics committee of the center (no. 2021-49) and followed "
               "earlier procedures (Smith, 2020).\n\n## References\n\nSmith, J. (2020). A study of mood. Journal of Mood, 1, 1-10.\n")
        with tempfile.TemporaryDirectory() as d:
            code, out = run("ref_check.py", write(d, "ms.md", doc))
        self.assertNotIn("2021", out.replace("2021-49", ""), out)
        self.assertNotIn("center 2021", out.lower())


class ResponseLetters(unittest.TestCase):
    def test_misspelled_answer_label_is_recognised(self):
        doc = ("Response to reviewers\n\nWe thank the editor and reviewers.\n\nReviewer 1\n\n1. The sample size is not justified.\n\n"
               "Anwser: We added a power analysis to the Methods (page 6, lines 10-14).\n\n2. Please report effect sizes.\n\n"
               "Anwser: Effect sizes are now reported in Table 2 (page 9).\n")
        with tempfile.TemporaryDirectory() as d:
            code, out = run("response_lint.py", write(d, "resp.md", doc))
        self.assertIn("意见 2 条", out, out)
        self.assertIn("ERROR 0", out, out)

    def test_numbered_points_inside_a_response_are_not_new_comments(self):
        doc = ("Response letter\n\nWe thank the editor.\n\nEditor Comments\n\nThe paper needs a clearer description of the CAP method "
               "and a fuller account of the clinical implications of the findings.\n\nAnwser: We made two changes in our revision:\n\n"
               "1. Regarding the CAP method, we expanded the Methods (page 7, lines 3-20).\n\n"
               "2. Concerning implications, we added a paragraph to the Discussion (page 15, lines 2-18).\n\n"
               "Reviewer 1\n\n1. The figure legend is unclear and should define all abbreviations used in the panels.\n\n"
               "Anwser: We rewrote the legend of Figure 2 (page 22).\n")
        with tempfile.TemporaryDirectory() as d:
            code, out = run("response_lint.py", write(d, "resp.md", doc))
        self.assertIn("ERROR 0", out, out)
        self.assertIn("Editor 1", out, out)


class SimulationFindings(unittest.TestCase):
    """模拟测试中发现的误报：中文目的句、单独的“分析”小节、回复信引用被删除的旧文字。"""
    ZH = ("# 题目\n\n## 引言\n\n学生做练习时常常只得到对错判断，这不足以说明错在哪里。\n\n"
          "本研究在两个班级中开展随机试验，比较解释反馈与仅对错反馈对两周后测验分数的影响。\n\n"
          "## 方法\n\n### 被试\n\n两个班级的学生参与，共 120 人。\n\n### 分析\n\n用协方差分析估计组间差值，调整基线分数。主分析纳入 112 人。\n\n"
          "## 结果\n\n解释反馈组高 2.1 分（95% CI −0.4 至 4.6）。\n\n## 讨论\n\n区间包含 0。\n")

    def test_chinese_aim_and_plain_analysis_heading(self):
        with tempfile.TemporaryDirectory() as d:
            j = os.path.join(d, "l.json")
            run("section_lint.py", write(d, "ms.md", self.ZH), "--json", j)
            codes = {i["code"] for i in json.load(open(j, encoding="utf-8"))}
        self.assertNotIn("I1", codes)
        self.assertNotIn("M1", codes)

    def test_lexicon_rules_are_all_compiled(self):
        for lang in ("zh", "en"):
            R = M.lex_rx(M.load_lexicon(lang, []), lang)
            for key in ("aim", "interpretive", "purpose", "synthesis", "negation", "gap"):
                self.assertIn(key, R, "%s 词表缺少可用的 %s 规则" % (lang, key))

    def test_quoting_deleted_text_is_not_an_error(self):
        resp = ("回复信\n\n我们修订了讨论。\n\nReviewer 1\n\n1. 亚组结论过强，请改写。\n\n"
                "回复：“讨论”第 1 段已改为探索性表述，删去了“证明应优先分配资源”的结论。\n")
        ms = "# 修订稿\n\n## 讨论\n\n低基线学生的差值较大，但这是事后分析。\n"
        with tempfile.TemporaryDirectory() as d:
            code, out = run("response_lint.py", write(d, "r.md", resp), "--manuscript", write(d, "m.md", ms))
        self.assertIn("ERROR 0", out, out)


class DeliveryResidue(unittest.TestCase):
    def test_chat_residue_and_zero_width_are_must(self):
        doc = EN_DOC.replace("Models were fitted in R.", "Models were fitted in R. I hope this helps.").replace("follow-up", "follow\u200b-up")
        with tempfile.TemporaryDirectory() as d:
            code, out = run("section_lint.py", write(d, "ms.md", doc), "--report", os.path.join(d, "r.md"))
            rep = open(os.path.join(d, "r.md"), encoding="utf-8").read()
        self.assertEqual(code, 1, out)
        self.assertIn("A1", rep)
        self.assertIn("U+200B", rep)

    def test_placeholder_is_info_not_must(self):
        doc = EN_DOC.replace("Models were fitted in R.", "Models were fitted in R [VERIFY: version].")
        with tempfile.TemporaryDirectory() as d:
            code, out = run("section_lint.py", write(d, "ms.md", doc), "--report", os.path.join(d, "r.md"))
            rep = open(os.path.join(d, "r.md"), encoding="utf-8").read()
        self.assertIn("A2", rep)
        self.assertNotIn("A1", rep)


class PhraseContrast(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.exdir = os.path.join(d, "ex")
        os.mkdir(self.exdir)
        for i, disc in enumerate(DISC_VARIANTS, 1):
            write(self.exdir, "ex%d.md" % i, exemplar(i, disc))
        disc = " ".join("Notably, the %s changed between visits in this cohort." % w for w in
                        ("score", "rating", "estimate", "profile", "pattern", "course"))
        self.draft = write(d, "draft.md", exemplar(9, disc))

    def tearDown(self):
        self.tmp.cleanup()

    def test_flags_repeated_opener_and_lists_common_openers(self):
        js = os.path.join(self.tmp.name, "p.json")
        code, out = run("phrase_contrast.py", "--exemplars", self.exdir, "--draft", "draft=" + self.draft,
                        "--report", os.path.join(self.tmp.name, "p.md"), "--json", js)
        self.assertEqual(code, 0, out)
        res = json.load(open(js, encoding="utf-8"))["drafts"]["draft"]["discussion_all"]
        self.assertTrue(any(o["opener"].startswith("notably the") for o in res["overused_openers"]), res)
        self.assertTrue(any(o["opener"] == "the present study" and o["papers"] >= 3 for o in res["common_openers"]), res)

    def test_draft_inside_exemplars_is_rejected(self):
        code, out = run("phrase_contrast.py", "--exemplars", self.exdir, os.path.join(self.exdir, "ex1.md"),
                        "--draft", "d=" + os.path.join(self.exdir, "ex1.md"), "--report", os.path.join(self.tmp.name, "p.md"))
        self.assertEqual(code, 2, out)

    def test_language_mismatch_is_rejected(self):
        zh = write(self.tmp.name, "zh.md", "# 题目\n\n## 讨论\n\n" + "本研究发现症状随时间下降，功能同步改善。" * 20)
        code, out = run("phrase_contrast.py", "--exemplars", self.exdir, "--draft", "zh=" + zh, "--report", os.path.join(self.tmp.name, "p.md"))
        self.assertEqual(code, 2, out)


ZH_EX = """# 论文 %d

## 摘要

本研究考察症状的稳定成分与变化成分，并报告其与功能的关系。

## 引言

症状在临床样本中随时间波动。以往研究较少区分稳定成分与变化成分。

## 方法

被试在四次随访中完成问卷。采用多层模型估计各次随访之间的变化。

## 结果

症状得分在随访中下降，功能同步改善，变化幅度在不同被试之间存在差异。

## 讨论

%s

## 结论

症状与功能在研究期间同步变化。
"""
ZH_DISC = ["本研究发现症状随时间下降。例如，多数被试在前两次随访之间改善。然而，年龄较大的被试改善较少。这些结果与以往的队列研究一致。",
           "本研究追踪患者两年。例如，功能在每次随访中都与症状同步变化。然而，不同诊所之间的变化幅度不同。以往研究在门诊样本中报告了相似的病程。",
           "本研究为这一领域补充了重复测量证据。例如，第二次随访时的变化可以预测后来的功能。然而，最后一年的流失率较高。住院样本中也有类似发现。"]


class PhraseTerms(unittest.TestCase):
    def test_terms_are_masked_automatically_and_by_option(self):
        with tempfile.TemporaryDirectory() as d:
            ex = os.path.join(d, "ex")
            os.mkdir(ex)
            for i, disc in enumerate(ZH_DISC, 1):
                write(ex, "ex%d.md" % i, ZH_EX % (i, disc))
            # 词表外的术语（场合特异性）自动并成一个〈X〉；由词表内的词组成的术语（影响因素）要靠 --terms
            disc = "".join("第%s次随访的场合特异性高于预期，影响因素高于预期。" % w for w in "一二三四五六")
            dr = write(d, "draft.md", ZH_EX % (9, disc))
            js1, js2 = os.path.join(d, "a.json"), os.path.join(d, "b.json")
            c1, o1 = run("phrase_contrast.py", "--exemplars", ex, "--draft", "d=" + dr, "--report", os.path.join(d, "a.md"), "--json", js1)
            c2, o2 = run("phrase_contrast.py", "--exemplars", ex, "--draft", "d=" + dr, "--terms", "影响因素", "--report", os.path.join(d, "b.md"), "--json", js2)
            self.assertEqual((c1, c2), (0, 0), o1 + o2)
            def frames(js):
                dj = json.load(open(js, encoding="utf-8"))["drafts"]["d"]
                return [f["frame"] for v in dj.values() for f in v["overused_frames"]]
            self.assertFalse(any("特异" in f or "场合" in f for f in frames(js1) + frames(js2)), frames(js1))
            self.assertTrue(any("因素" in f for f in frames(js1)), frames(js1))
            self.assertFalse(any("因素" in f for f in frames(js2)), frames(js2))


def fill(plan_in, plan_out, decide):
    rows = list(csv.DictReader(open(plan_in, encoding="utf-8-sig")))
    for r in rows:
        r["decision"], r["reason"], r["new_text"] = decide(r)
    with open(plan_out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows


class LanguagePlan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.ms = write(self.d, "ms.md", EN_DOC.replace("Models were fitted in R.", "Models were fitted in R. I hope this helps."))
        self.plan = os.path.join(self.d, "plan.csv")
        code, out = run("language_plan.py", "scan", "--doc", "正文=" + self.ms, "--plan", self.plan, "--patterns", "L4,L5")
        self.assertEqual(code, 0, out)

    def tearDown(self):
        self.tmp.cleanup()

    def good_after(self):
        t = open(self.ms, encoding="utf-8").read().replace(" I hope this helps.", "")
        t = t.replace("The decline reflects mood rather than cognition.", "The decline tracks changes in mood.")
        return t.replace("Mood may potentially suggest recovery.", "Mood may indicate recovery.")

    @staticmethod
    def good_decide(r):
        if r["pattern"] == "A1":
            return "改", "对话残留，删除", ""
        if r["pattern"] == "L4" and "decline reflects" in r["sentence"]:
            return "改", "正面陈述所是", ""
        if r["pattern"] == "L4":
            return "留", "真正二选一的比较", ""
        return "改", "只保留一层限定", ""

    def check(self, after_text, plan=None):
        after = write(self.d, "after_%d.md" % len(os.listdir(self.d)), after_text)
        return run("language_plan.py", "check", "--plan", plan or self.plan, "--after", "正文=" + after)

    def test_scan_lists_every_instance_of_named_patterns_only(self):
        rows = list(csv.DictReader(open(self.plan, encoding="utf-8-sig")))
        pats = [r["pattern"] for r in rows]
        self.assertEqual(pats.count("L4"), 3)
        self.assertIn("A1", pats)
        self.assertNotIn("C1", pats, "点名模式且无对标时，不应列入未点名的 compare 级模式")
        self.assertTrue(os.path.isfile(self.plan + ".meta.json"))

    def test_unfilled_plan_fails(self):
        code, out = self.check(open(self.ms, encoding="utf-8").read())
        self.assertEqual(code, 1)
        self.assertIn("未裁决", out)

    def test_complete_applied_plan_passes(self):
        fill(self.plan, self.plan, self.good_decide)
        code, out = self.check(self.good_after())
        self.assertEqual(code, 0, out)

    def test_claimed_revision_not_in_file_fails(self):
        fill(self.plan, self.plan, self.good_decide)
        code, out = self.check(self.good_after().replace("Mood may indicate recovery.", "Mood may potentially suggest recovery."))
        self.assertEqual(code, 1)
        self.assertIn("原句仍原样", out)

    def test_number_lost_without_reason_fails(self):
        def decide(r):
            if r["pattern"] == "L4" and "Scores fell" in r["sentence"]:
                return "改", "正面陈述", ""
            return self.good_decide(r)
        fill(self.plan, self.plan, decide)
        after = self.good_after().replace("Scores fell by 12.5 points in the treated group rather than in controls (Table 1).",
                                          "Scores fell in the treated group but not in controls (Table 1).")
        code, out = self.check(after)
        self.assertEqual(code, 1, out)
        self.assertIn("数字丢失", out)

    def test_deleted_row_fails(self):
        rows = fill(self.plan, self.plan, self.good_decide)
        with open(self.plan, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows[1:])
        code, out = self.check(self.good_after())
        self.assertEqual(code, 1)
        self.assertIn("计划行被删除", out)

    def test_reintroduced_residue_fails(self):
        fill(self.plan, self.plan, self.good_decide)
        code, out = self.check(self.good_after() + "\nCertainly! Here is the revised version.\n")
        self.assertEqual(code, 1)
        self.assertIn("交付残留", out)

    def test_calibration_selects_only_categories_above_exemplars(self):
        exdir = os.path.join(self.d, "ex")
        os.mkdir(exdir)
        for i, disc in enumerate(DISC_VARIANTS, 1):
            write(exdir, "ex%d.md" % i, exemplar(i, disc))
        heavy = " ".join("The %s reflected change rather than stability in this cohort over the visits." % w
                         for w in ("score", "rating", "estimate", "profile"))
        ms = write(self.d, "heavy.md", exemplar(9, heavy))
        plan = os.path.join(self.d, "plan2.csv")
        code, out = run("language_plan.py", "scan", "--doc", "正文=" + ms, "--plan", plan, "--exemplars", exdir)
        self.assertEqual(code, 0, out)
        rows = list(csv.DictReader(open(plan, encoding="utf-8-sig")))
        l4 = [r for r in rows if r["pattern"] == "L4"]
        self.assertEqual(len(l4), 4)
        self.assertTrue(all("对标" in r["calibration"] for r in rows if r["level"] == "compare"))


class DisplayExtract(unittest.TestCase):
    DRAFT = ("# T\n\n## Results\n\nScores fell (Table 1).\n\nTable 1. Sample characteristics at baseline\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
             "Note. SD = standard deviation; values are means with 95% CI. These results suggest that mood drives complaints.\n\n"
             "Figure 1. Mean scores by occasion (A) and by group (B). Error bars show 95% CI.\n")
    EXEMPLAR = ("# E\n\n## Results\n\nTable 1 shows the sample.\n\nTable 1.\n\nDemographic characteristics of the sample\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
                "Note. SD = standard deviation.\n\nFigure 1. Scores at each visit (A) and by clinic (B).\n")

    def test_manifest_is_accepted_by_display_profile(self):
        with tempfile.TemporaryDirectory() as d:
            dr, ex = write(d, "draft.md", self.DRAFT), write(d, "ex.md", self.EXEMPLAR)
            out = os.path.join(d, "disp", "corpus.json")
            code, msg = run("display_extract.py", "--draft", dr, "--exemplar", ex, "--out", out, "--signals", os.path.join(d, "disp", "sig.md"))
            self.assertEqual(code, 0, msg)
            data = json.load(open(out, encoding="utf-8"))
            kinds = {(r["role"], r["kind"]) for r in data["records"]}
            self.assertTrue({("draft", "table_title"), ("draft", "table_note"), ("draft", "figure_caption")} <= kinds, kinds)
            fig = [r for r in data["records"] if r["role"] == "draft" and r["kind"] == "figure_caption"][0]
            self.assertEqual(fig["panels"], 2)
            note = [r for r in data["records"] if r["role"] == "draft" and r["kind"] == "table_note"][0]
            self.assertTrue(note["signals"]["interpretive"])
            titles = [r["text"] for r in data["records"] if r["role"] == "exemplar" and r["kind"] == "table_title"]
            self.assertEqual(titles, ["Table 1. Demographic characteristics of the sample"])
            self.assertIn("解释句通常属于正文", open(os.path.join(d, "disp", "sig.md"), encoding="utf-8").read())
            code2, msg2 = run("display_profile.py", out)
            self.assertIn(code2, (0, 1), msg2)


class FragmentMode(unittest.TestCase):
    """单独的 Highlights、投稿信、图注表注：不加 --fragment 时拒绝，加了只做全文级检查。"""

    PKG = ("# Display items\n\n"
           "Table 2. Association between tutoring hours and mathematics score\n\n"
           "Note. CI = confidence interval.\n\n"
           "Highlights\n\n"
           "- Each extra weekly hour of tutoring was linked to 0.04 SD higher scores.\n"
           "- This single highlight is deliberately far too long for the journal limit because it keeps going well past the character cap.\n")

    def test_without_flag_the_fragment_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = run("section_lint.py", write(d, "pkg.md", self.PKG))
            self.assertEqual(code, 2, out)
            self.assertIn("--fragment", out)

    def test_fragment_checks_highlight_limits(self):
        with tempfile.TemporaryDirectory() as d:
            lim = write(d, "limits.json", json.dumps({"highlights_max_n": 5, "highlights_max_chars": 85}))
            j = os.path.join(d, "out.json")
            code, out = run("section_lint.py", write(d, "pkg.md", self.PKG), "--fragment", "--limits", lim,
                            "--report", os.path.join(d, "r.md"), "--json", j)
            self.assertEqual(code, 1, out)
            items = json.load(open(j, encoding="utf-8"))
            self.assertIn("H1", {i["code"] for i in items})
            self.assertIn("片段", open(os.path.join(d, "r.md"), encoding="utf-8").read())

    def test_main_word_limit_is_not_applied_to_a_fragment(self):
        with tempfile.TemporaryDirectory() as d:
            lim = write(d, "limits.json", json.dumps({"main_words": 5}))
            j = os.path.join(d, "out.json")
            run("section_lint.py", write(d, "pkg.md", self.PKG), "--fragment", "--limits", lim, "--json", j)
            self.assertNotIn("W1", {i["code"] for i in json.load(open(j, encoding="utf-8"))})


class PlaceholderRules(unittest.TestCase):
    """方括号里的作者待办也是占位符；section_lint 与 delivery_check 用同一套规则。"""

    CASES = ["[Authors to add: why the manuscript fits this journal.]",
             "(2024; [full reference to be added])",
             "[待作者确认：伦理批准号]",
             "[VERIFY sample size]"]

    def test_bracketed_author_todos_are_placeholders(self):
        for s in self.CASES:
            with self.subTest(text=s):
                self.assertTrue(M.PLACEHOLDER.search(s), s)

    def test_plain_brackets_are_not_placeholders(self):
        for s in ["[12]", "[Smith et al., 2020]", "scores [z-scores] were used"]:
            with self.subTest(text=s):
                self.assertIsNone(M.PLACEHOLDER.search(s), s)

    def test_delivery_check_uses_the_same_rule(self):
        sys.path.insert(0, S)
        import delivery_check as DC
        self.assertIs(DC.PLACEHOLDER, M.PLACEHOLDER)

    def test_fragment_reports_bracketed_placeholder(self):
        with tempfile.TemporaryDirectory() as d:
            doc = "Dear Editor,\n\nWe submit the manuscript. [Authors to add: fit with the journal.]\n"
            j = os.path.join(d, "o.json")
            run("section_lint.py", write(d, "cover.md", doc), "--fragment", "--json", j)
            self.assertIn("A2", {i["code"] for i in json.load(open(j, encoding="utf-8"))})


class AssertionAndDesign(unittest.TestCase):
    """趋势话术、因果措辞与声明的设计、建议句、新颖性宣称、投稿信里的声明。"""

    def codes(self, text, *extra, **kw):
        with tempfile.TemporaryDirectory() as d:
            j = os.path.join(d, "o.json")
            run("section_lint.py", write(d, "ms.md", text), "--json", j, *extra)
            items = json.load(open(j, encoding="utf-8"))
            return {i["code"] for i in items}

    ZH_SPIN = "## 讨论\n\n性别的调节作用不显著，但女生的效应呈现出更强的趋势。性别差异虽然不显著，但值得关注。\n"
    EN_SPIN = "## Discussion\n\nThe difference was marginally significant. The association approached significance in older adults.\n"
    ZH_CAUSE = "## 讨论\n\n手机使用通过破坏睡眠导致抑郁。本研究支持这一解释。\n"
    ZH_SAFE = "## 讨论\n\n横断面自评数据不能确定手机使用是否导致抑郁。\n"

    def test_spin_is_flagged_in_both_languages(self):
        self.assertIn("S1", self.codes(self.ZH_SPIN))
        self.assertIn("S1", self.codes(self.EN_SPIN))

    def test_causal_wording_needs_a_declared_design(self):
        self.assertNotIn("G1", self.codes(self.ZH_CAUSE))
        self.assertIn("G1", self.codes(self.ZH_CAUSE, "--design", "cross_sectional"))

    def test_negated_or_contrasted_causal_sentences_are_not_flagged(self):
        self.assertNotIn("G1", self.codes(self.ZH_SAFE, "--design", "cross_sectional"))
        en = "## Discussion\n\nThe study estimates an association rather than an effect of tutoring.\n"
        self.assertNotIn("G1", self.codes(en, "--design", "cohort"))

    def test_declared_design_contradiction_is_a_must(self):
        doc = "## Discussion\n\nIn this randomized trial, students were randomly assigned to tutoring.\n"
        with tempfile.TemporaryDirectory() as d:
            j = os.path.join(d, "o.json")
            code, out = run("section_lint.py", write(d, "ms.md", doc), "--json", j, "--design", "cohort")
            items = json.load(open(j, encoding="utf-8"))
            self.assertEqual(code, 1, out)
            self.assertIn("G2", {i["code"] for i in items if i["level"] == "MUST"})

    def test_random_intercept_is_not_a_design_contradiction(self):
        doc = "## Methods\n\nModels included a random intercept for school and random slopes.\n"
        self.assertNotIn("G2", self.codes(doc, "--design", "cohort"))

    def test_recommendations_beyond_the_design_are_flagged(self):
        doc = "## 结论\n\n因此，高校应当限制学生的手机使用时间。\n"
        self.assertIn("P1", self.codes(doc, "--design", "cross_sectional"))

    def test_overclaims_outside_the_introduction_are_listed(self):
        doc = "## 结论\n\n本研究填补了国内该领域研究的空白。\n"
        self.assertIn("N1", self.codes(doc))
        intro_only = "## 引言\n\n本研究首次在中国样本中考察这一关联，目的是检验该假设。\n## 方法\n\n参与者为 860 名学生。\n"
        self.assertNotIn("N1", self.codes(intro_only))

    def test_declarations_are_only_checked_in_fragment_mode(self):
        letter = "Dear Editor,\n\nWe declare no conflicts of interest and all authors have approved the submission.\n"
        with tempfile.TemporaryDirectory() as d:
            j = os.path.join(d, "o.json")
            run("section_lint.py", write(d, "cover.md", letter), "--fragment", "--json", j)
            self.assertIn("N2", {i["code"] for i in json.load(open(j, encoding="utf-8"))})
        body = "## 方法\n\n本研究经伦理委员会批准，参与者签署知情同意书。\n## 结果\n\n得分下降 2.1 分。\n"
        self.assertNotIn("N2", self.codes(body))

    def test_short_chinese_fragments_are_detected_as_chinese(self):
        for s in ["Highlights\n\n- 每周多补习 1 小时与数学分数高 0.04 个标准差相关。\n",
                  "## 讨论\n\n性别的调节作用不显著。\n"]:
            with self.subTest(text=s[:12]):
                self.assertEqual(M.detect_lang(s), "zh")
        self.assertEqual(M.detect_lang("Dear Editor,\n\nWe submit the manuscript.\n"), "en")

    def test_chinese_numbered_section_and_table_crossrefs_reach_the_discussion_rule(self):
        doc = "## 讨论\n\n本研究发现两者相关。具体结果见 3.2 节和表 3。\n"
        self.assertIn("D2", self.codes(doc))


if __name__ == "__main__":
    unittest.main()
