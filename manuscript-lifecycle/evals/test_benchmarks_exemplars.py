"""范例、期刊规则档案与新工具的回归测试。

范例库是本 skill 的"写到什么程度"的标准。标准必须可验证，否则它会和检查规则、文档慢慢脱节：
每个范例里的坏例必须触发它标注的规则，改写必须不触发。改了范例、规则或档案，这个文件必须重跑。

`<!-- test: … -->` 行的字段：tool=lint|journal|table|none；section=各节名 / front / legend / fragment / zh；
design=声明的设计；profile=期刊档案；limits={…}；bad=期望触发的规则；good_no=改写必须不触发的规则。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
S = os.path.join(ROOT, "scripts")
EX = os.path.join(ROOT, "assets", "exemplars")
PROF = os.path.join(ROOT, "assets", "journal_profiles")
BASE = os.path.join(ROOT, "assets", "benchmarks", "display_baseline.json")

FILLER = {
    "abstract": "We compared two groups of pupils on eight depressive symptoms and report how strongly the symptoms were connected in each group.",
    "introduction": ("Depressive symptoms in adolescence rarely occur alone. Studies comparing groups have mostly asked whether symptoms are "
                     "more severe in one group. This study compared how the symptoms connect in boarding and day pupils, and two questions "
                     "were specified before analysis."),
    "methods": ("Students in six schools completed the survey. To describe how symptoms relate to one another, we estimated one network per "
                "school type and judged stability by the correlation-stability coefficient."),
    "results": ("The network structure did not differ detectably between groups (M = 0.14, P = 0.41). Global strength was higher in boarding "
                "pupils (3.92 versus 3.41, P = 0.02)."),
    "discussion": "Boarding and day pupils showed a similar pattern of connections, but the symptoms were more interconnected in boarding pupils.",
    "limitations": "The survey was cross-sectional and cannot show the direction of associations between symptoms.",
    "conclusion": "The same symptoms were linked in both groups, but the links were tighter in boarding pupils.",
}
ORDER = ["abstract", "introduction", "methods", "results", "discussion", "limitations", "conclusion"]
HEAD = {k: k.capitalize() for k in ORDER}


def run(*args):
    p = subprocess.run([sys.executable] + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def skeleton(section, block):
    """把范例块放进一份最小稿件。front 块里的 # 行当题目，其余当摘要，否则摘要会落进篇首而不被各节规则扫到。"""
    secs = dict(FILLER)
    head = "# Depressive symptoms connect more tightly in boarding-school pupils"
    if section == "front":
        lines = [l for l in block.strip().split("\n")]
        title = next((l for l in lines if l.startswith("# ")), "")
        rest = "\n".join(l for l in lines if not l.startswith("# ")).strip()
        head = title or head
        if rest:
            secs["abstract"] = rest
        section = ""
    elif section in secs:
        secs[section] = block.strip()
    body = "\n\n".join("## %s\n\n%s" % (HEAD[k], secs[k]) for k in ORDER)
    if section == "legend":
        return head + "\n\n" + body + "\n\n" + block.strip()
    return head + "\n\n" + body


def exemplar_files():
    return [f for f in sorted(os.listdir(EX)) if f.endswith(".md") and f != "README.md"]


def parse_tests(text):
    out = []
    for line in re.findall(r"<!-- test:(.*?)-->", text, re.S):
        d = dict(re.findall(r"(\w+)=(\{.*?\}|\S+)", line))
        if d.get("tool"):
            out.append(d)
    return out


def blocks(text, kind):
    return re.findall(r"```" + kind + r"\n(.*?)```", text, re.S)


class ExemplarLibrary(unittest.TestCase):
    def test_every_exemplar_declares_a_test_line_and_both_blocks(self):
        for fn in exemplar_files():
            with open(os.path.join(EX, fn), encoding="utf-8") as fh:
                t = fh.read()
            with self.subTest(file=fn):
                self.assertTrue(parse_tests(t), "缺 <!-- test: … --> 标注")
                self.assertTrue(blocks(t, "bad"), "缺 ```bad 块")
                self.assertTrue(blocks(t, "good"), "缺 ```good 块")
                self.assertIn("这份范例不校准什么", t, "范例必须写明它不校准什么")

    def _codes(self, meta, block, tmp, name):
        path = os.path.join(tmp, name + ".md")
        sec = meta.get("section", "fragment")
        with open(path, "w", encoding="utf-8") as f:
            f.write((block.strip() + "\n") if sec in ("fragment", "zh") else (skeleton(sec, block) + "\n"))
        if meta["tool"] == "lint":
            out_json = os.path.join(tmp, name + ".json")
            args = [os.path.join(S, "section_lint.py"), path, "--json", out_json]
            if sec == "fragment":
                args.append("--fragment")
            if meta.get("design"):
                args += ["--design", meta["design"]]
            if meta.get("limits"):
                lp = os.path.join(tmp, name + "_limits.json")
                with open(lp, "w", encoding="utf-8") as f:
                    f.write(meta["limits"])
                args += ["--limits", lp]
            code, out = run(*args)
            self.assertNotEqual(code, 2, out)
            with open(out_json, encoding="utf-8") as f:
                return {it["code"] for it in json.load(f)}, out
        if meta["tool"] == "journal":
            code, out = run(os.path.join(S, "journal_check.py"), path,
                            "--profile", os.path.join(PROF, meta["profile"] + ".json"), "--baseline", BASE)
            self.assertNotEqual(code, 2, out)
            return set(re.findall(r"\*\*(?:FAIL|CAND|INFO) (\w+)\*\*", out)), out
        code, out = run(os.path.join(S, "table_style.py"), "check", path)
        self.assertNotEqual(code, 2, out)
        return set(), out

    def test_every_exemplar_bad_block_triggers_its_rules(self):
        tmp = tempfile.mkdtemp()
        try:
            for fn in exemplar_files():
                with open(os.path.join(EX, fn), encoding="utf-8") as fh:
                    t = fh.read()
                for i, meta in enumerate(parse_tests(t)):
                    if meta["tool"] == "none":
                        continue
                    want = [w for w in meta.get("bad", "").split(",") if w]
                    if not want:
                        continue
                    codes, out = self._codes(meta, blocks(t, "bad")[0], tmp, "%s_bad%d" % (fn[:2], i))
                    for w in want:
                        with self.subTest(file=fn, tool=meta["tool"], rule=w):
                            self.assertTrue(w in codes or w in out, "坏例没有触发 %s；实际：%s" % (w, sorted(codes) or out[:200]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_exemplar_good_blocks_are_clean(self):
        tmp = tempfile.mkdtemp()
        try:
            for fn in exemplar_files():
                with open(os.path.join(EX, fn), encoding="utf-8") as fh:
                    t = fh.read()
                for i, meta in enumerate(parse_tests(t)):
                    if meta["tool"] == "none":
                        continue
                    forbid = [w for w in meta.get("good_no", "").split(",") if w]
                    if not forbid:
                        continue
                    codes, out = self._codes(meta, blocks(t, "good")[0], tmp, "%s_good%d" % (fn[:2], i))
                    for w in forbid:
                        with self.subTest(file=fn, tool=meta["tool"], rule=w):
                            self.assertFalse(w in codes or w in out, "改写仍触发 %s：%s" % (w, out[:200]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class JournalProfiles(unittest.TestCase):
    def test_profiles_declare_sources_and_status(self):
        files = [f for f in sorted(os.listdir(PROF)) if f.endswith(".json")]
        self.assertTrue(files)
        for fn in files:
            with open(os.path.join(PROF, fn), encoding="utf-8") as f:
                p = json.load(f)
            with self.subTest(profile=fn):
                sids = {s["id"] for s in p["sources"]}
                for s in p["sources"]:
                    self.assertTrue(s.get("url") and s.get("accessed") and s.get("access"), "来源要写 url、access 与访问日")
                for r in p["rules"]:
                    self.assertIn(r["status"], ("verified", "unverified"))
                    self.assertIn(r["source"], sids)
                    self.assertTrue(r.get("note"), "每条规则要写它管什么")
        code, out = run(os.path.join(S, "journal_check.py"), "--list")
        self.assertEqual(code, 0, out)
        self.assertNotIn("档案有问题", out)

    def test_profile_missing_source_is_refused(self):
        tmp = tempfile.mkdtemp()
        try:
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w", encoding="utf-8") as f:
                json.dump({"schema_version": 1, "id": "x", "journal": "X", "sources": [],
                           "rules": [{"id": "t", "check": "title_chars", "max": 10, "level": "FAIL",
                                      "status": "verified", "source": "none", "note": "n"}]}, f)
            ms = os.path.join(tmp, "m.md")
            with open(ms, "w", encoding="utf-8") as f:
                f.write(skeleton("results", "A result.") + "\n")
            code, out = run(os.path.join(S, "journal_check.py"), ms, "--profile", bad)
            self.assertEqual(code, 2, out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unverified_rule_cannot_fail(self):
        """来源没核实过的数字，不能用来判失败：期刊规则会改版。"""
        tmp = tempfile.mkdtemp()
        try:
            prof = os.path.join(tmp, "p.json")
            with open(prof, "w", encoding="utf-8") as f:
                json.dump({"schema_version": 1, "id": "p", "journal": "P",
                           "sources": [{"id": "A", "url": "https://example.org", "access": "未访问", "accessed": "2026-10-26"}],
                           "rules": [{"id": "title", "check": "title_chars", "max": 10, "level": "FAIL",
                                      "status": "unverified", "source": "A", "note": "n"}]}, f)
            ms = os.path.join(tmp, "m.md")
            with open(ms, "w", encoding="utf-8") as f:
                f.write(skeleton("results", "A result.") + "\n")
            code, out = run(os.path.join(S, "journal_check.py"), ms, "--profile", prof)
            self.assertIn("CAND title", out)
            self.assertIn("来源未核实", out)
            self.assertEqual(code, 0, out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_baseline_reports_position(self):
        tmp = tempfile.mkdtemp()
        try:
            long_leg = "Fig. 1 | Networks. " + " ".join(["word"] * 400) + "."
            ms = os.path.join(tmp, "m.md")
            with open(ms, "w", encoding="utf-8") as f:
                f.write(skeleton("legend", long_leg) + "\n")
            code, out = run(os.path.join(S, "journal_check.py"), ms,
                            "--profile", os.path.join(PROF, "nature_article.json"), "--baseline", BASE)
            self.assertEqual(code, 1, out)
            self.assertIn("同类实测", out)
            fam = json.load(open(BASE, encoding="utf-8"))["families"]["nature_family"]["figure_legend"]
            words = int(re.search(r"图注 (\d+) 词", out).group(1))
            want = "在范围内" if fam["p10"] <= words <= fam["p90"] else ("高于 p90" if words > fam["p90"] else "低于 p10")
            self.assertIn(want, out)  # 位置按随包基线计算；超期刊上限照样 FAIL，与基线位置无关
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_visual_encoding_in_legend_is_not_a_conclusion(self):
        tmp = tempfile.mkdtemp()
        try:
            ms = os.path.join(tmp, "m.md")
            legend = ("Fig. 1 | Networks. a, Group A. Nodes are symptoms; thicker lines indicate stronger connections "
                      "and dashed lines indicate negative ones.\n\nFig. 2 | Scores. These results indicate that X impairs Y.")
            with open(ms, "w", encoding="utf-8") as f:
                f.write(skeleton("legend", legend) + "\n")
            code, out = run(os.path.join(S, "journal_check.py"), ms, "--profile", os.path.join(PROF, "nature_article.json"))
            self.assertEqual(out.count("图注下结论"), 1, out)
            self.assertIn("Fig. 2", out.split("图注下结论")[1])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class SectionLintRegressions(unittest.TestCase):
    def _pack(self):
        return os.path.join(ROOT, "assets", "domains", "clinical_psych_en")

    def test_domain_calibration_does_not_excuse_going_beyond_the_field(self):
        """同领域大多数论文也触发的规则降为参照；但本稿的数值已超出它们的上界时不降级。"""
        tmp = tempfile.mkdtemp()
        try:
            heavy = " ".join(["The effect was larger in group A, which suggests that the mechanism differs." for _ in range(6)])
            ms = os.path.join(tmp, "m.md")
            with open(ms, "w", encoding="utf-8") as f:
                f.write(skeleton("results", heavy) + "\n")
            out_json = os.path.join(tmp, "o.json")
            code, out = run(os.path.join(S, "section_lint.py"), ms, "--domain", self._pack(), "--json", out_json)
            with open(out_json, encoding="utf-8") as f:
                items = {it["code"]: it for it in json.load(f)}
            self.assertIn("R1", items, out)
            self.assertEqual(items["R1"]["level"], "MUST", "解释句比例远超同领域上界，不能降成参照")
            self.assertIn("不降级", items["R1"]["msg"])
            self.assertEqual(code, 1, out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_verify_placeholder_is_not_a_ghostwritten_declaration(self):
        tmp = tempfile.mkdtemp()
        try:
            good = os.path.join(tmp, "g.md")
            with open(good, "w", encoding="utf-8") as f:
                f.write("Dear Editor,\n\nWe submit our manuscript.\n\n"
                        "[VERIFY: 作者确认后填写——利益冲突、资金、全体作者同意投稿。]\n")
            code, out = run(os.path.join(S, "section_lint.py"), good, "--fragment")
            self.assertNotIn("N2", out, out)
            bad = os.path.join(tmp, "b.md")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("Dear Editor,\n\nThe authors declare no conflict of interest. "
                        "All authors have approved the manuscript and agree with its submission.\n")
            code, out = run(os.path.join(S, "section_lint.py"), bad, "--fragment")
            self.assertIn("N2", out, out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_display_led_results_paragraphs_are_caught(self):
        """已发表论文很少以"如表 2 所示"起句（实测见 assets/benchmarks/display_baseline.json）。"""
        tmp = tempfile.mkdtemp()
        try:
            paras = ["As shown in Table 1, the groups differed (P = 0.02).",
                     "Table 2 presents the descriptive statistics for both groups.",
                     "Figure 1 shows the estimated networks for each school type.",
                     "Global strength was higher in boarding pupils (3.92 versus 3.41)."]
            ms = os.path.join(tmp, "m.md")
            with open(ms, "w", encoding="utf-8") as f:
                f.write(skeleton("results", "\n\n".join(paras)) + "\n")
            code, out = run(os.path.join(S, "section_lint.py"), ms)
            self.assertIn("R3", out, out)
            self.assertIn("3/4", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_assertion_rules_also_scan_the_abstract(self):
        """摘要常常是唯一被读到的部分：因果措辞、趋势话术和越界建议在这里代价最大。"""
        tmp = tempfile.mkdtemp()
        try:
            ab = ("Boarding causes tighter symptom coupling. There was a trend towards a difference in the subgroup, "
                  "which did not reach significance but is noteworthy. Schools should therefore prioritise sleep interventions.")
            ms = os.path.join(tmp, "m.md")
            with open(ms, "w", encoding="utf-8") as f:
                f.write(skeleton("abstract", ab) + "\n")
            code, out = run(os.path.join(S, "section_lint.py"), ms, "--design", "cross_sectional")
            for rule in ("S1", "G1", "P1"):
                self.assertIn(rule, out, "摘要里的 %s 没有被发现：%s" % (rule, out[:300]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class NullAsEquivalence(unittest.TestCase):
    """留出模拟中发现：只有任务专用评分器抓得住“把不显著写成相同”，通用检查抓不到。"""

    def _lint(self, text):
        tmp = tempfile.mkdtemp()
        try:
            ms = os.path.join(tmp, "m.md")
            with open(ms, "w", encoding="utf-8") as f:
                f.write(skeleton("results", text) + "\n")
            out_json = os.path.join(tmp, "o.json")
            code, out = run(os.path.join(S, "section_lint.py"), ms, "--json", out_json)
            with open(out_json, encoding="utf-8") as f:
                return {it["code"]: it["level"] for it in json.load(f)}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_null_written_as_identical_is_flagged(self):
        self.assertEqual(self._lint("The networks were identical in structure (M = 0.14, P = 0.41).").get("S2"), "SHOULD")
        self.assertEqual(self._lint("The two groups were essentially equivalent (P = 0.30).").get("S2"), "SHOULD")

    def test_descriptive_same_pattern_is_only_a_candidate(self):
        self.assertEqual(self._lint("The pattern of effects was the same for both groups.").get("S2"), "INFO")

    def test_null_reported_as_no_detectable_difference_is_clean(self):
        self.assertNotIn("S2", self._lint("The network structure did not differ detectably between groups (M = 0.14, P = 0.41)."))

    def test_equivalence_test_and_procedures_are_exceptions(self):
        self.assertNotIn("S2", self._lint("The groups were equivalent within a margin of 0.1 (two one-sided tests, P = 0.01)."))
        self.assertNotIn("S2", self._lint("All materials were identical between groups, as in Experiment 1."))


class WorkflowLeak(unittest.TestCase):
    """实地试写：两份稿件都把“对标未完成”“见审计列表”“作者待办”写进了论文。"""

    def _codes(self, text):
        tmp = tempfile.mkdtemp()
        try:
            ms = os.path.join(tmp, "m.md")
            with open(ms, "w", encoding="utf-8") as f:
                f.write(text)
            j = os.path.join(tmp, "o.json")
            run(os.path.join(S, "section_lint.py"), ms, "--json", j)
            with open(j, encoding="utf-8") as f:
                return {it["code"]: it["level"] for it in json.load(f)}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_process_notes_in_the_paper_are_a_must(self):
        lim = "The survey was cross-sectional. Sentence-pattern benchmarking against a domain pack was not completed."
        self.assertEqual(self._codes(skeleton("limitations", lim) + "\n").get("X11"), "MUST")
        self.assertEqual(self._codes(skeleton("results", "A result.") + "\n\n**作者待办**：确认主线。\n").get("X11"), "MUST")

    def test_local_paths_in_the_conclusion_are_flagged_and_clean_text_is_not(self):
        c = self._codes(skeleton("conclusion", "Trial data are in `00_inputs/sim_data/trials.csv`.") + "\n")
        self.assertEqual(c.get("X12"), "SHOULD")
        clean = self._codes(skeleton("results", "A result.") + "\n")
        self.assertNotIn("X11", clean)
        self.assertNotIn("X12", clean)


class TableStyle(unittest.TestCase):
    def _csv(self, tmp, text):
        p = os.path.join(tmp, "t.csv")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_three_line_table_round_trip(self):
        tmp = tempfile.mkdtemp()
        try:
            c = self._csv(tmp, 'Measure,"Boarding (n = 1,032)","Day (n = 1,108)"\nEdge weight,0.31,0.290\nStrength,3.92,3.41\n')
            out_docx = os.path.join(tmp, "t.docx")
            code, out = run(os.path.join(S, "table_style.py"), "build", "--csv", c, "--title", "Closest pair",
                            "--label", "Table 1", "--note", "Note. Edge weights are partial correlations. Boarding n = 1,032.",
                            "--decimals", "2", "--out", out_docx)
            self.assertEqual(code, 0, out)
            code, out = run(os.path.join(S, "table_style.py"), "check", out_docx)
            self.assertEqual(code, 0, out)
            self.assertIn("ERROR 0", out)
            code, out = run(os.path.join(S, "mslib.py"), "totext", out_docx)
            self.assertIn("0.29", out, "小数位应统一为两位")
            self.assertNotIn("0.290", out)
            code, out = run(os.path.join(S, "table_style.py"), "build", "--csv", c, "--title", "x", "--out", out_docx)
            self.assertEqual(code, 2, "不能覆盖已存在的输出文件")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_csv_with_unquoted_comma_is_refused(self):
        tmp = tempfile.mkdtemp()
        try:
            c = self._csv(tmp, "Measure,Boarding (n = 1,032),Day (n = 1,108)\nEdge,0.31,0.29\n")
            code, out = run(os.path.join(S, "table_style.py"), "build", "--csv", c, "--title", "x",
                            "--out", os.path.join(tmp, "t.docx"))
            self.assertEqual(code, 2, out)
            self.assertIn("双引号", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_bad_p_value_and_note_order_are_reported(self):
        tmp = tempfile.mkdtemp()
        try:
            md = os.path.join(tmp, "t.md")
            with open(md, "w", encoding="utf-8") as f:
                f.write("| A | B |\n| --- | --- |\n| 1.0 | p = 0.000 |\n\n"
                        "Note. ***p < .001. EI = expected influence.\n")
            code, out = run(os.path.join(S, "table_style.py"), "check", md)
            self.assertEqual(code, 1, out)
            self.assertIn("p 值写成", out)
            self.assertIn("表注顺序", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_note_only_fragment_is_accepted_but_empty_input_is_not(self):
        tmp = tempfile.mkdtemp()
        try:
            n = os.path.join(tmp, "n.md")
            with open(n, "w", encoding="utf-8") as f:
                f.write("Note. Edge weights are partial correlations. Boarding n = 1,032.\n")
            code, out = run(os.path.join(S, "table_style.py"), "check", n)
            self.assertEqual(code, 0, out)
            e = os.path.join(tmp, "e.md")
            with open(e, "w", encoding="utf-8") as f:
                f.write("Just a sentence with no table and no note.\n")
            code, out = run(os.path.join(S, "table_style.py"), "check", e)
            self.assertEqual(code, 2, out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class PunctuationOnlyRevision(unittest.TestCase):
    def test_colon_to_period_counts_as_landed_and_phrase_lists_colons(self):
        """bench 标出冒号偏多，但模式目录里没有冒号：要能用 --phrase 列进计划，并认出只改标点的修订。"""
        import csv as _csv
        tmp = tempfile.mkdtemp()
        try:
            before, after, plan = (os.path.join(tmp, n) for n in ("a.md", "b.md", "plan.csv"))
            with open(before, "w", encoding="utf-8") as f:
                f.write("# T\n\n## Introduction\n\nLiving arrangements matter: pupils sleep in dormitories and follow a shared timetable.\n\n"
                        "This study asked whether X relates to Y.\n")
            with open(after, "w", encoding="utf-8") as f:
                f.write("# T\n\n## Introduction\n\nLiving arrangements matter. Pupils sleep in dormitories and follow a shared timetable.\n\n"
                        "This study asked whether X relates to Y.\n")
            code, out = run(os.path.join(S, "language_plan.py"), "scan", "--doc", "正文=" + before, "--plan", plan, "--phrase", ":")
            self.assertEqual(code, 0, out)
            with open(plan, encoding="utf-8-sig") as fh:
                rows = list(_csv.DictReader(fh))
            fields = list(rows[0].keys())
            self.assertTrue(any(":" in r["sentence"] for r in rows), rows)
            for r in rows:
                if ":" in r["sentence"]:
                    r["decision"], r["new_text"], r["reason"] = "改", "Living arrangements matter.", "冒号高于同类文献，改为两句"
                else:
                    r["decision"], r["reason"] = "留", "与本次模式无关，原句保留"
            with open(plan, "w", encoding="utf-8", newline="") as f:
                w = _csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
            code, out = run(os.path.join(S, "language_plan.py"), "check", "--plan", plan, "--after", "正文=" + after)
            self.assertNotIn("原句仍原样留在", out)
            self.assertEqual(code, 0, out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
