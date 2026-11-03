"""回归测试：弱模型试跑暴露的问题（摘要与结论里的状态话、口径限定、全稿清扫、检查器自身的误报与摩擦），以及文献证据阶梯。

每个测试对应 references/16 里的一行。试跑稿件的句子在这里只用短改写，不复制整篇。
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
S = os.path.join(ROOT, "scripts")
KIT = os.path.join(HERE, "trial_kit")
T1 = os.path.join(KIT, "executor", "T1_draft")
REF = os.path.join(KIT, "grader", "reference", "T1_reference_manuscript.md")
ALLOW = os.path.join(KIT, "grader", "reference", "T1_allow.txt")
LIT = os.path.join(ROOT, "assets", "examples", "literature")
SOURCES = [os.path.join(T1, f) for f in ("results_summary.md", "practice_logs_by_school.csv", "analysis_notes.md")]


def run(*args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([sys.executable] + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace", env=e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def doc(abstract, conclusion, methods="Students were randomized by school. Parents gave written consent.",
        intro="Hints are common. This study asked whether hints help, and the primary question was whether test scores rose.", front=""):
    return ("# Hints and learning\n\n" + front + "## Abstract\n\n" + abstract + "\n\n## Introduction\n\n" + intro + "\n\n## Methods\n\n" + methods +
            "\n\n## Results\n\nScores did not differ detectably (difference 1.8, 95% CI −0.6 to 4.2).\n\n## Discussion\n\nHints changed practice but not scores.\n\n"
            "## Conclusion\n\n" + conclusion + "\n")


def lint(text, *extra):
    tmp = tempfile.mkdtemp()
    try:
        p = write(os.path.join(tmp, "m.md"), text)
        code, out = run(os.path.join(S, "section_lint.py"), p, "--json", os.path.join(tmp, "o.json"), *extra)
        with open(os.path.join(tmp, "o.json"), encoding="utf-8") as f:
            return code, {(i["code"], i["level"]) for i in json.load(f)}, out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_all(ms_text, *extra):
    tmp = tempfile.mkdtemp()
    p = write(os.path.join(tmp, "m.md"), ms_text)
    code, out = run(os.path.join(S, "check_all.py"), p, "--out", os.path.join(tmp, "chk"), *extra)
    status = ""
    if os.path.exists(os.path.join(tmp, "chk", "STATUS.md")):
        with open(os.path.join(tmp, "chk", "STATUS.md"), encoding="utf-8") as f:
            status = f.read()
    shutil.rmtree(tmp, ignore_errors=True)
    return code, status, out


def must_part(status):
    i, j = status.find("## 必须先处理"), status.find("## 没能运行")
    return status[i:j]


class StatusTalk(unittest.TestCase):
    def test_status_talk_in_abstract_or_conclusion_is_must(self):
        for ab, con in (("Hints helped practice. Claims about adoption should await author verification of ethics documentation.", "Hints helped practice."),
                        ("Hints helped practice.", "Hints helped practice. [VERIFY: funding; conflicts; data availability]")):
            code, codes, out = lint(doc(ab, con))
            self.assertIn(("X13", "MUST"), codes, out)

    def test_inline_fact_placeholder_is_only_advisory(self):
        code, codes, out = lint(doc("In 12 schools in one city [VERIFY: city], hints changed practice but not scores.", "Hints changed practice."))
        self.assertIn(("X14", "SHOULD"), codes, out)
        self.assertNotIn(("X13", "MUST"), codes, out)

    def test_plain_synthetic_banner_is_not_a_leak_but_workflow_banner_is(self):
        ok = doc("Hints changed practice but not scores.", "Hints changed practice.", front="All data are synthetic and do not describe real participants.\n\n")
        self.assertNotIn(("X11", "MUST"), lint(ok)[1])
        bad = doc("Hints changed practice but not scores.", "Hints changed practice.", front="All data are synthetic; this is a demonstration draft for a writing-workflow test.\n\n")
        self.assertIn(("X11", "MUST"), lint(bad)[1])

    def test_methods_status_sentence_is_a_leak(self):
        t = doc("Hints changed practice but not scores.", "Hints changed practice.",
                methods="Students were randomized by school. Funding and conflicts of interest were not supplied for this draft [VERIFY].")
        self.assertIn(("X11", "MUST"), lint(t)[1])


class CleanReference(unittest.TestCase):
    def test_clean_reference_is_deliverable(self):
        with open(REF, encoding="utf-8") as f:
            ref = f.read()
        code, status, out = check_all(ref, "--results", *SOURCES, "--allow", ALLOW, "--design", "cluster_randomized", "--lang", "en")
        self.assertEqual(code, 0, must_part(status) or out)
        self.assertIn("可以交给作者通读", status)

    def test_design_aliases_and_unknown_design(self):
        code, codes, out = lint(doc("Hints changed practice.", "Hints changed practice."), "--design", "Randomised controlled trial")
        self.assertNotEqual(code, 2, out)
        code, status, out = check_all(doc("Hints changed practice.", "Hints changed practice."), "--design", "foo-design")
        self.assertEqual(code, 2)
        self.assertIn("cross_sectional", out)

    def test_aim_question_phrase_satisfies_i1(self):
        codes = lint(doc("Hints changed practice.", "Hints changed practice."))[1]
        self.assertNotIn(("I1", "MUST"), codes)

    def test_trend_towards_improvement_is_spin(self):
        t = doc("Scores showed a trend towards improvement with hints (P = 0.14).", "Hints changed practice.")
        self.assertIn("S1", {c for c, l in lint(t, "--design", "rct")[1]})


class NumberTracePercents(unittest.TestCase):
    def test_verbatim_percent_matched_ci_level_skipped_derived_flagged(self):
        tmp = tempfile.mkdtemp()
        try:
            src = write(os.path.join(tmp, "res.md"), "Mastery 62.0% vs 55.1%; difference 1.8, 95% CI [-0.6, 4.2]\n")
            ms = write(os.path.join(tmp, "m.md"), "# T\n\n## Results\n\nMastery was 62.0% vs 55.1% (difference 1.8, 95% CI −0.6 to 4.2). Completion was 90.2%.\n")
            code, out = run(os.path.join(S, "number_trace.py"), ms, "--sources", src, "--report", os.path.join(tmp, "r.md"), "--json", os.path.join(tmp, "r.json"))
            with open(os.path.join(tmp, "r.json"), encoding="utf-8") as f:
                un = [u["number"] for u in json.load(f)["unmatched"]]
            self.assertEqual(un, ["90.2%"], un)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Qualifiers(unittest.TestCase):
    def _q(self, tmp):
        return write(os.path.join(tmp, "q.csv"), "label,values,requires\n截断均值,24.1|26.3,按 40|赋值|封顶|capped|assigned 40\n")

    def test_qualifiers_catch_unqualified_capped_mean(self):
        tmp = tempfile.mkdtemp()
        try:
            t = doc("Hints changed practice.", "Hints changed practice.").replace("Scores did not differ", "Mean days to mastery were 24.1 and 26.3. Scores did not differ")
            code, status, out = check_all(t, "--qualifiers", self._q(tmp))
            self.assertIn("限定口径", must_part(status), status)
            t2 = t.replace("Mean days to mastery were 24.1 and 26.3.", "Students who did not master were assigned 40 days. The resulting means were 24.1 and 26.3.")
            code, status, out = check_all(t2, "--qualifiers", self._q(tmp))
            self.assertNotIn("限定口径", must_part(status), status)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class FabricatedIds(unittest.TestCase):
    def test_fabricated_ids_and_citations_are_blocked(self):
        t = doc("Hints changed practice.", "Hints changed practice.",
                methods="The study was approved by the Ethics Committee (approval No. 2024-117) and registered as NCT01234567. Hints help repair errors (Smith et al., 2019).")
        code, status, out = check_all(t, "--results", *SOURCES)
        m = must_part(status)
        self.assertIn("2024-117", m)
        self.assertIn("NCT01234567", m)
        self.assertIn("作者–年份或编号引文", m)

    def test_registration_claim_contradicting_materials_is_must(self):
        t = doc("Hints changed practice.", "Hints changed practice.", methods="The trial was preregistered before data collection.")
        code, status, out = check_all(t, "--results", *SOURCES)
        self.assertIn("注册", must_part(status))

    def test_simulation_flag_does_not_block_consent_from_materials(self):
        t = doc("Hints changed practice.", "Hints changed practice.", front="All data are synthetic and do not describe real participants.\n\n")
        code, status, out = check_all(t, "--simulation")
        self.assertNotIn("知情同意", must_part(status))
        self.assertNotIn("模拟标识", must_part(status))


class MetricAuditTolerance(unittest.TestCase):
    def test_rounded_report_matches_by_default(self):
        tmp = tempfile.mkdtemp()
        try:
            spec = write(os.path.join(tmp, "s.json"), json.dumps({"schema_version": 1, "group_by": "arm", "metrics": [
                {"id": "per_item", "kind": "rate", "numerator": "success_after_hint", "denominator": "practice_items", "aggregation": "pooled",
                 "reported_by_group": {"AH": 0.070, "SF": 0.040}}]}))
            code, out = run(os.path.join(S, "metric_audit.py"), "--csv", os.path.join(T1, "practice_logs_by_school.csv"), "--spec", spec, "--out", os.path.join(tmp, "o.json"))
            self.assertEqual(code, 0, out)
            spec2 = write(os.path.join(tmp, "s2.json"), json.dumps({"schema_version": 1, "group_by": "arm", "metrics": [
                {"id": "per_hint", "kind": "rate", "numerator": "success_after_hint", "denominator": "hints_shown", "aggregation": "pooled",
                 "reported_by_group": {"AH": 0.070, "SF": 0.040}}]}))
            code, out = run(os.path.join(S, "metric_audit.py"), "--csv", os.path.join(T1, "practice_logs_by_school.csv"), "--spec", spec2, "--out", os.path.join(tmp, "o2.json"))
            self.assertEqual(code, 1, "按每次提示算是 0.42/0.47，与报告的 0.070/0.040 不符，应当报出")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


LEDGER_HEAD = "id,claim_location,claim_text,claim_type,citation_id,doi_or_url,ref_title,ref_first_author,ref_year,doi_status,identity,version_status,version_source,version_checked_at,citation_access,relation,source_locator,source_passage,tool,checked_on,source_sha256,reviewer,notes\n"


class LitEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.led = write(os.path.join(self.tmp, "led.csv"), LEDGER_HEAD +
                         "C1,Intro,Organise papers around one message,background,Mensh2017,https://doi.org/10.1371/journal.pcbi.1005619,Ten simple rules for structuring papers,Mensh,2017,,,,,,abstract,supports,,,,,,,\n"
                         "C2,Disc,Effect was 0.4,number,X2019,10.1371/journal.pcbi.1005619,A different paper,Smith,2019,,,,,,metadata,supports,,,,,,,\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _resolve(self, *extra, env=None):
        out = os.path.join(self.tmp, "res_%d.csv" % len(os.listdir(self.tmp)))
        code, o = run(os.path.join(S, "lit_evidence.py"), "resolve", "--ledger", self.led, "--out", out, *extra, env=env)
        self.assertEqual(code, 0, o)
        with open(out, encoding="utf-8") as f:
            return out, list(csv.DictReader(f))

    def _check(self, *args):
        return run(os.path.join(S, "lit_evidence.py"), "check", *args)

    def test_saved_record_resolves_and_reads_the_correction(self):
        out, rows = self._resolve("--fixtures", LIT)
        self.assertEqual(rows[0]["doi_status"], "resolved_crossref")
        self.assertEqual(rows[0]["identity"], "matched")
        self.assertEqual(rows[0]["version_status"], "correction")
        self.assertIn("10.1371/journal.pcbi.1005830", rows[0]["version_source"])
        self.assertEqual(rows[1]["identity"], "mismatch")
        code, o = self._check("--ledger", out)
        self.assertEqual(code, 1)
        for fid in ("F13", "F14", "F15"):
            self.assertIn(fid, o)

    def test_unreachable_registry_is_not_verified(self):
        out, rows = self._resolve("--online", env={"LIT_EVIDENCE_CROSSREF_BASE": "http://127.0.0.1:9", "LIT_EVIDENCE_OPENALEX_BASE": "http://127.0.0.1:9"})
        self.assertEqual({r["doi_status"] for r in rows}, {"not_verified"})

    def test_claims_need_records_and_negations_do_not_count(self):
        note = write(os.path.join(self.tmp, "n.md"), "- DOI 已核实。\n- 已完成同类文献对标。\n- 这条据记忆补。\n- 未发现撤稿，因此可靠。\n- MCP 没有安装，所以技能无法使用。\n")
        code, o = self._check("--text", note, "--benchmark-mode", "case")
        for fid in ("F16", "F04", "F08", "F07", "F11"):
            self.assertIn(fid, o, o)
        neg = write(os.path.join(self.tmp, "neg.md"), "- DOI 未核实（本轮没有联网）。\n- 尚未完成同类文献对标，只做了结构个案参照。\n")
        code, o = self._check("--text", neg, "--benchmark-mode", "case")
        self.assertEqual(code, 0, o)

    def test_reasoning_only_cannot_claim_live_queries(self):
        out, rows = self._resolve("--fixtures", LIT)
        rows[0]["tool"] = "crossref(api 2026-10-27)"
        live = os.path.join(self.tmp, "live.csv")
        with open(live, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows[:1])
        note = write(os.path.join(self.tmp, "n2.md"), "我们查询了 Crossref。\n")
        code, o = self._check("--ledger", live, "--text", note, "--execution", "REASONING-ONLY")
        self.assertIn("F10", o)
        code, o = self._check("--ledger", out, "--execution", "REASONING-ONLY")
        self.assertNotIn("F10", o, "保存好的记录（saved:）在无网时可以沿用")

    def test_distribution_needs_local_full_texts_and_a_report(self):
        corpus = os.path.join(self.tmp, "corpus")
        os.makedirs(corpus)
        for i in range(2):
            write(os.path.join(corpus, "p%d.md" % i), "text")
        note = write(os.path.join(self.tmp, "n3.md"), "稿件的冒号用量高于同类文献 p90。\n")
        code, o = self._check("--text", note, "--benchmark-mode", "distribution", "--benchmark-corpus", corpus)
        self.assertIn("F05", o)
        for i in range(2, 9):
            write(os.path.join(corpus, "p%d.md" % i), "text")
        rep = write(os.path.join(self.tmp, "bench.md"), "report")
        code, o = self._check("--text", note, "--benchmark-mode", "distribution", "--benchmark-corpus", corpus, "--benchmark-report", rep)
        self.assertEqual(code, 0, o)
        dp = write(os.path.join(self.tmp, "n4.md"), "按领域包对标了近邻全文。\n")
        self.assertIn("F06", self._check("--text", dp, "--benchmark-mode", "domain_pack")[1])

    def test_check_all_runs_the_ladder(self):
        note = write(os.path.join(self.tmp, "note.md"), "全部 DOI 已核实。\n")
        code, status, out = check_all(doc("Hints changed practice.", "Hints changed practice."), "--note", note, "--execution", "REASONING-ONLY")
        self.assertIn("lit_evidence", must_part(status), status)


class TrialKit(unittest.TestCase):
    def test_scorer_passes_reference_and_catches_status_talk(self):
        tmp = tempfile.mkdtemp()
        try:
            root = os.path.join(tmp, "ret", "runs")
            with open(REF, encoding="utf-8") as f:
                ref = f.read()
            for rid, text in (("R01", ref), ("R02", ref.replace("remains open.", "remains open. Claims should await author verification of ethics documentation."))):
                o = os.path.join(root, rid, "workspace", "T1_draft", "outputs")
                os.makedirs(o)
                write(os.path.join(o, "manuscript.md"), text)
                write(os.path.join(o, "author_note.md"), "伦理批准号待核；利益冲突与资助未提供；文献检索需求见下。\n")
                write(os.path.join(o, "RUN_REPORT.md"), "check_all 退出码 0；没能运行：无。\n")
                write(os.path.join(root, rid, "meta.json"), json.dumps({"task": "T1", "arm": "X"}))
            code, o = run(os.path.join(KIT, "grader", "score_return.py"), os.path.join(tmp, "ret"), "--out", os.path.join(tmp, "score"))
            self.assertEqual(code, 0, o)
            self.assertRegex(o, r"\| R01 \| T1 \| X \| 合格")
            self.assertRegex(o, r"\| R02 \| T1 \| X \| 不合格 \| [^|]*H-过程进稿")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TrapRules(unittest.TestCase):
    def test_null_written_as_equivalent_with_ci_is_flagged(self):
        t = doc("Hints changed practice.", "Hints changed practice.").replace(
            "Scores did not differ detectably (difference 1.8, 95% CI −0.6 to 4.2).",
            "Multiple imputation confirmed that the two conditions were equivalent (1.5, 95% CI −1.0 to 4.0).")
        self.assertIn("S2", {c for c, l in lint(t, "--design", "rct")[1]})

    def test_dose_gradient_causal_verbs_and_internal_processing(self):
        t = doc("Hints changed practice.", "Hints changed practice.",
                methods="After a school identifier error was corrected during data merging, all analyses were re-run because of it. Raw scores were cleaned in Excel before export.").replace(
            "Scores did not differ detectably", "Using more hints led to larger gains across tertiles of hint use. Scores did not differ detectably")
        codes = {c for c, l in lint(t, "--design", "rct")[1]}
        self.assertIn("P2", codes)
        self.assertIn("X15", codes)

    def test_negated_registration_and_chinese_aim_are_not_flagged(self):
        t = doc("Hints changed practice.", "Hints changed practice.", methods="The analysis plan was timestamped internally rather than publicly preregistered.")
        code, status, out = check_all(t, "--results", *SOURCES)
        self.assertNotIn("注册", must_part(status))
        zh = ("# 提示与学习\n\n## 摘要\n\n自适应提示改变了练习过程。\n\n## 1 引言\n\n在线练习很常见。本研究的问题是：自适应提示能否提高后测成绩？\n\n"
              "## 2 方法\n\n按学校随机分配。\n\n## 3 结果\n\n后测差值 1.8 分，95% CI 跨零。\n\n## 4 讨论\n\n提示改变了练习。\n\n## 5 结论\n\n提示改变了练习过程。\n")
        self.assertNotIn(("I1", "MUST"), lint(zh)[1])


# ---------------------------------------------------------------- 检查器自身的误报与摩擦
import json as _json
import shutil as _shutil
import subprocess as _sp
import tempfile as _tf
import zipfile as _zip

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
_KIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trial_kit")


def _py(*args):
    p = _sp.run([sys.executable] + [str(x) for x in args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


_ZH = """# 自适应提示与代数学习

## 摘要

本研究比较自适应提示与标准反馈。主要结局未见明确差异。

## 一、引言

在线练习很常见，但针对错误类型的提示能否提高成绩尚不清楚[ref]。本研究的问题是：自适应提示能否提高后测成绩？

## 二、方法

12 所学校按规模分层后随机分组。后测为平行卷，系统评分。

## 三、结果

{results}

## 四、讨论

自适应提示改变了练习过程，但后测差异不明确。

## 五、结论

自适应提示改善了练习过程，后测是否提高仍不明确。
"""

_EN = """# Adaptive hints and algebra practice

## Abstract

Adaptive hints changed practice but did not clearly change posttest scores.

## Introduction

Online practice is common in schools. {intro} This study asked whether adaptive hints improve posttest scores.

## Method

Twelve schools were randomized within size strata. {methods}

## Results

Posttest scores did not differ detectably (difference 1.8, 95% CI −0.6 to 4.2). {results}

## Discussion

Hints changed practice more than they changed scores.

### Limitations

{lim}

## Conclusion

Hints changed practice; score gains were unclear.

{legend}
"""


def _en(intro="It remains unclear whether hints raise scores [ref].", methods="", results="", lim="Only one city took part.", legend=""):
    return _EN.format(intro=intro, methods=methods, results=results, lim=lim, legend=legend)


class ToolFrictionRegressions(unittest.TestCase):
    """一句话提示试跑里检查器自身造成的问题：误报会逼模型改坏正确的内容。"""

    def setUp(self):
        self.tmp = _tf.mkdtemp()
        self.n = 0

    def tearDown(self):
        _shutil.rmtree(self.tmp, ignore_errors=True)

    def w(self, name, text):
        p = os.path.join(self.tmp, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def wj(self, path, obj):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(obj, f, ensure_ascii=False)

    def lint(self, text, *extra):
        self.n += 1
        ms = self.w("lint%d.md" % self.n, text)
        code, out = _py(os.path.join(_SCRIPTS, "section_lint.py"), ms, "--json", ms + ".json", "--report", ms + ".report.md", *extra)
        self.assertIn(code, (0, 1), out)
        with open(ms + ".json", encoding="utf-8") as f:
            return {(i["code"], i["level"]) for i in _json.load(f)}

    def check(self, ms, out, *extra):
        code, log = _py(os.path.join(_SCRIPTS, "check_all.py"), ms, "--out", out, *extra)
        self.assertIn(code, (0, 1), log)
        with open(os.path.join(out, "summary.json"), encoding="utf-8") as f:
            return code, _json.load(f)

    def src(self):
        return self.w("results.md", "# Results\n\nAdjusted difference 1.8, 95% CI −0.6 to 4.2; p = .14. Schools: 12. Mastery days 24.1 and 26.3.\n")

    def test_hint_as_intervention_name_is_not_interpretation(self):
        res = ("自适应组后测均值 63.4，标准组 61.9，调整后差值 1.8（95% CI [−0.6, 4.2]）。"
               "按全部练习题计的提示成功率自适应组为 0.070，标准组为 0.040。"
               "每题提示显示次数分别为 0.166 与 0.084。"
               "干预组内提示使用量最高三分位比最低三分位后测提高多 6.2 分。")
        self.assertNotIn("R1", {c for c, l in self.lint(_ZH.format(results=res), "--lang", "zh")})

    def test_interpretation_needs_three_sentences_to_block(self):
        two = "结果提示自适应提示有积极作用。这说明学生加工更深。自适应组后测 63.4，标准组 61.9。纠错率分别为 0.46 与 0.31。"
        three = "结果提示自适应提示有积极作用。这说明学生加工更深。纠错率更高表明提示更有效。自适应组后测 63.4，标准组 61.9。"
        self.assertIn(("R1", "SHOULD"), self.lint(_ZH.format(results=two), "--lang", "zh"))
        self.assertIn(("R1", "MUST"), self.lint(_ZH.format(results=three), "--lang", "zh"))

    def test_denied_causation_is_not_flagged_as_dose_causal(self):
        neg = "干预组内提示使用量与后测提高的关联属观察性，不能推出提示使用导致成绩提高。自适应组后测 63.4。"
        pos = "提示使用越多导致成绩提高越大，最高三分位多提高 6.2 分。自适应组后测 63.4。"
        self.assertNotIn("P2", {c for c, l in self.lint(_ZH.format(results=neg), "--lang", "zh")})
        self.assertIn("P2", {c for c, l in self.lint(_ZH.format(results=pos), "--lang", "zh")})

    def test_material_gap_in_limitations_is_process_talk(self):
        bad = _en(lim="The frustration scale's reliability was not fully documented in the analysis materials.")
        ok = _en(lim="Frustration was measured with a brief four-item scale, so small differences are hard to interpret.")
        self.assertIn(("X11", "MUST"), self.lint(bad))
        self.assertNotIn("X11", {c for c, l in self.lint(ok)})

    def test_tension_counts_as_a_gap_statement(self):
        t = _en(intro="That leaves an unresolved tension: hints may raise scores, or they may only change practice.")
        self.assertNotIn("I2", {c for c, l in self.lint(t)})
        self.assertIn("I2", {c for c, l in self.lint(_en(intro="Hints are popular in many schools."))})

    def test_invented_legend_encodings_are_flagged(self):
        leg = "**Figure 1.** Cumulative mastery by condition. Solid line = adaptive hints; dashed line = standard feedback."
        plain = "**Figure 1.** Cumulative proportion of students reaching mastery within 40 days, by condition (adaptive hints, n = 552; standard feedback, n = 566)."
        self.assertIn(("V1", "SHOULD"), self.lint(_en(legend=leg)))
        self.assertNotIn("V1", {c for c, l in self.lint(_en(legend=plain))})

    def test_display_notes_with_conclusions_or_software_are_flagged(self):
        bad = _en(legend="*Note.* Models were fitted by REML with lme4 1.1-35 in R 4.4.1. These results demonstrate that adaptive hints are superior to standard feedback.")
        ok = _en(legend="*Note.* Differences are adaptive hints minus standard feedback, adjusted for pretest score and school size; students without mastery by day 40 were censored.")
        self.assertIn(("V2", "SHOULD"), self.lint(bad))
        self.assertNotIn("V2", {c for c, l in self.lint(ok)})

    def test_strip_markers_keeps_package_names(self):
        sys.path.insert(0, _SCRIPTS)
        import mslib
        s = mslib.strip_markers("We used lme4 1.1-35 and ggplot2.")
        self.assertIn("lme4 1.1-35", s)
        self.assertIn("ggplot2", s)
        self.assertEqual(mslib.strip_markers("common disorders12,13 were"), "common disorders were")

    def test_rerun_into_same_out_opens_new_directory_and_writes_codes(self):
        ms = self.w("ms.md", _en(methods="The study was approved by the Ethics Committee of Northfield University (approval No. 2024-117)."))
        out = os.path.join(self.tmp, "chk")
        c1, s1 = self.check(ms, out, "--results", self.src())
        code, log = _py(os.path.join(_SCRIPTS, "check_all.py"), ms, "--out", out, "--results", self.src())
        self.assertIn(code, (0, 1), log)
        self.assertIn(out + "_2", log)
        with open(os.path.join(out + "_2", "summary.json"), encoding="utf-8") as f:
            s2 = _json.load(f)
        self.assertEqual(s2["exit"], code)
        self.assertTrue(s2["previous"])
        self.assertIn(("check_all", "ID1"), {(i["tool"], i["code"]) for i in s2["must"]})
        self.assertTrue(all(i["code"] for i in s2["must"]), s2["must"])

    def test_ethics_claim_asks_for_materials_before_deletion(self):
        body = _en(methods="The study was approved by a university ethics committee [VERIFY: approval number]. Parents provided written informed consent.")
        ms = self.w("sim.md", "# Hints\n\n*All data are synthetic and do not represent real participants.*\n" + body.split("\n", 1)[1])
        notes = self.w("notes.md", "Ethics: approved by a university ethics committee; approval number pending. Parents gave informed consent.\n")
        c1, s1 = self.check(ms, os.path.join(self.tmp, "s1"), "--results", self.src(), "--simulation")
        sim3 = [i for i in s1["must"] if i["code"] == "SIM3"]
        self.assertTrue(sim3, s1["must"])
        self.assertIn("加进 --results", sim3[0]["text"])
        c2, s2 = self.check(ms, os.path.join(self.tmp, "s2"), "--results", self.src(), notes, "--simulation")
        self.assertNotIn("SIM3", {i["code"] for i in s2["must"]})
        self.assertIn("SIM2", {i["code"] for i in s2["look"]})

    def test_qualifier_check_skips_version_numbers(self):
        q = self.w("q.csv", "label,values,requires\nversion_like,1.1,assigned\ncapped,24.1|26.3,assigned 40|non-masters\n")
        good = self.w("good.md", _en(methods="Analyses used R 4.4.1 (lme4 1.1-35).", results="Mean days to mastery, with non-masters assigned 40 days, were 24.1 and 26.3."))
        bad = self.w("bad.md", _en(methods="Analyses used R 4.4.1 (lme4 1.1-35).", results="Mean days to mastery were 24.1 and 26.3."))
        _, sg = self.check(good, os.path.join(self.tmp, "g"), "--results", self.src(), "--qualifiers", q)
        _, sb = self.check(bad, os.path.join(self.tmp, "b"), "--results", self.src(), "--qualifiers", q)
        self.assertNotIn("Q1", {i["code"] for i in sg["must"]})
        q1 = [i for i in sb["must"] if i["code"] == "Q1"]
        self.assertTrue(q1, sb["must"])
        self.assertNotIn("lme4", q1[0]["text"])

    def test_response_lint_counts_comments_from_file(self):
        sys.path.insert(0, _SCRIPTS)
        import response_lint
        f = self.w("comments.md", "# 审稿意见\n\n## 编辑\nE1. 摘要请精简。\n\n## 审稿人 1\nR1.1 请说明亚组性质。\nR1.2 请做外部验证。\n")
        self.assertEqual(response_lint.comment_count(f), 3)
        self.assertEqual(response_lint.comment_count("9"), 9)
        self.assertIsNone(response_lint.comment_count(os.path.join(self.tmp, "nope.md")))

    def test_check_stats_counts_hits_and_false_positives(self):
        self.wj(os.path.join(self.tmp, "runs", "c1", "summary.json"),
                {"exit": 1, "must": [{"tool": "section_lint", "code": "R1", "text": "解释句"}], "notrun": [], "look": [{"tool": "section_lint", "code": "P2", "text": "剂量"}]})
        self.wj(os.path.join(self.tmp, "runs", "c2", "summary.json"),
                {"exit": 0, "must": [], "notrun": [], "look": [{"tool": "section_lint", "code": "P2", "text": "剂量"}]})
        note = self.w("note.md", "# 作者说明\n\n## 检查与裁决\n- 判为误报而保留原文的项目、规则代码及理由：section_lint R1（“提示成功率”是指标名）\n")
        js = os.path.join(self.tmp, "stats.json")
        code, out = _py(os.path.join(_SCRIPTS, "check_stats.py"), os.path.join(self.tmp, "runs"), "--notes", note, "--json", js)
        self.assertEqual(code, 0, out)
        with open(js, encoding="utf-8") as f:
            s = _json.load(f)
        self.assertEqual((s["runs"], s["deliverable"]), (2, 1))
        self.assertEqual((s["rules"]["section_lint R1"]["must"], s["rules"]["section_lint R1"]["fp"]), (1, 1))
        self.assertEqual((s["rules"]["section_lint P2"]["look"], s["rules"]["section_lint P2"]["runs"]), (2, 2))
        os.makedirs(os.path.join(self.tmp, "empty"))
        self.assertEqual(_py(os.path.join(_SCRIPTS, "check_stats.py"), os.path.join(self.tmp, "empty"))[0], 2)

    def test_short_trial_withholds_the_task_brief(self):
        runs = os.path.join(self.tmp, "runs")
        code, out = _py(os.path.join(_KIT, "tools", "new_run.py"), "--run", "S01", "--task", "T1", "--arm", "F", "--model", "m", "--runs", runs, "--short")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.exists(os.path.join(runs, "S01", "workspace", "T1_draft", "request.md")))
        self.assertTrue(os.path.isfile(os.path.join(runs, "S01", "hidden", "request.md")))

    def test_trial_skill_package_leaves_out_evals(self):
        z = os.path.join(self.tmp, "t.zip")
        code, out = _py(os.path.join(_KIT, "tools", "make_trial_skill.py"), os.path.dirname(_SCRIPTS), "--out", z)
        self.assertEqual(code, 0, out)
        names = _zip.ZipFile(z).namelist()
        self.assertTrue(any(n.endswith("/SKILL.md") for n in names))
        self.assertFalse(any("/evals/" in n for n in names))


if __name__ == "__main__":
    unittest.main()
