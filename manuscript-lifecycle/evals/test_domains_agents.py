# -*- coding: utf-8 -*-
"""领域包（domain_pack.py 与各工具的 --baseline/--domain）和多审稿人流程（agents/、review_merge.py）的测试。"""
import csv
import glob
import hashlib
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


def run(script, *args):
    p = subprocess.run([sys.executable, os.path.join(S, script)] + list(args), capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def write(d, name, text):
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


DISC = [
    "The present study examined change in symptoms over time. For example, scores fell between the first two visits in most participants. However, the decline was smaller in older participants. These patterns agree with earlier cohort work on the course of symptoms.",
    "The present study followed patients for two years. For example, functioning improved in parallel with symptom change at each visit. However, the size of change varied across clinics. Earlier work reported a similar course in outpatients with comparable baseline severity.",
    "The present study adds repeated measures to this literature. For example, change at the second visit predicted later functioning in the cohort. However, attrition was higher in the last year. Similar findings were reported in an inpatient sample followed over one year.",
    "The current study describes symptom course in routine care. For example, most of the improvement occurred early in treatment. However, some participants worsened after discharge. Comparable trajectories were reported in community samples followed for several years.",
]
UNIQUE = "Zebra-striped questionnaires were folded into origami cranes by the night nurse"


FILL = ["Participants were recruited from %s outpatient clinics and completed the same battery at each visit.",
        "The cohort included adults with a primary diagnosis confirmed by a structured interview at visit %s.",
        "Trained raters administered the interview and were blind to the previous ratings at wave %s.",
        "Missing data were handled with full information maximum likelihood across the %s planned visits.",
        "Sensitivity analyses repeated the main model after excluding participants who missed visit %s."]


def section(i, k, base):
    extra = " ".join(FILL[(i + j) % len(FILL)] % (j + k + i) for j in range(4))
    return base + " " + extra


def paper(i, disc, conclusion="Symptoms and functioning changed together over the study period."):
    return """# Paper %d

doi: 10.9999/test.%d

## Abstract

%s

## Introduction

%s

## Methods

%s

## Results

%s

## Discussion

%s

## Conclusion

%s
""" % (i, i,
       section(i, 1, "We examined symptoms in a clinical cohort over two years and report associations with functioning."),
       section(i, 2, "Symptoms vary over time in clinical samples (Brown, 2015). Few studies separate stable and changing parts of these reports. %s."
               % (UNIQUE if i == 1 else "We asked how these parts relate")),
       section(i, 3, "Participants completed questionnaires at four visits. Mixed models were used to estimate change across visits in all participants."),
       section(i, 4, "Symptom scores declined across visits. Functioning improved in parallel with the decline in symptoms over the study period."),
       section(i, 5, disc), section(i, 6, conclusion))


class DomainPack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.corpus = os.path.join(cls.tmp, "corpus")
        os.mkdir(cls.corpus)
        for i in range(1, 9):
            write(cls.corpus, "p%d.md" % i, paper(i, DISC[(i - 1) % len(DISC)]))
        cls.pack = os.path.join(cls.tmp, "pack")
        code, out = run("domain_pack.py", "build", "--corpus", cls.corpus, "--id", "test_en", "--label", "测试领域", "--lang", "en",
                        "--out", cls.pack, "--boot", "5")
        assert code == 0, out
        cls.draft = write(cls.tmp, "draft.md", paper(9, DISC[0].replace("The present study", "Notably, the present study"),
                                                     "Scores fell by 12.5 points (95% CI 8.1 to 16.9) in 112 patients."))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_pack_has_only_numbers_and_short_frames(self):
        for fn in ("profile.json", "bench_baseline.json", "phrase_baseline.json", "texture_baseline.json", "rule_rates.json", "corpus_manifest.csv", "build_report.md"):
            self.assertTrue(os.path.isfile(os.path.join(self.pack, fn)), fn)
        blob = "".join(open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(self.pack, "*")))
        self.assertNotIn("origami", blob, "语料原句不能进入领域包")
        self.assertNotIn(DISC[0][:60], blob)
        code, out = run("domain_pack.py", "check", self.pack)
        self.assertEqual(code, 0, out)

    def test_tools_run_from_the_pack(self):
        d = tempfile.mkdtemp(dir=self.tmp)
        code, out = run("bench_profile.py", "--baseline", self.pack, "--draft", "稿=" + self.draft, "--report", os.path.join(d, "b.md"))
        self.assertEqual(code, 0, out)
        self.assertIn("领域基线", open(os.path.join(d, "b.md"), encoding="utf-8").read())
        code, out = run("phrase_contrast.py", "--baseline", self.pack, "--draft", "稿=" + self.draft, "--report", os.path.join(d, "p.md"))
        self.assertEqual(code, 0, out)
        code, out = run("language_plan.py", "scan", "--doc", "稿=" + self.draft, "--plan", os.path.join(d, "plan.csv"), "--baseline", self.pack)
        self.assertEqual(code, 0, out)
        meta = json.load(open(os.path.join(d, "plan.csv.meta.json"), encoding="utf-8"))
        self.assertEqual(meta["baseline"], "test_en")
        self.assertFalse(meta["uncalibrated"])

    def test_rules_common_in_field_are_downgraded(self):
        pack = os.path.join(self.tmp, "pack_rules")
        shutil.copytree(self.pack, pack)
        rr = json.load(open(os.path.join(pack, "rule_rates.json"), encoding="utf-8"))
        rr["rules"]["C2"] = {"papers": 8, "n": 8, "share": 1.0, "levels": {"SHOULD": 8}}
        json.dump(rr, open(os.path.join(pack, "rule_rates.json"), "w", encoding="utf-8"), ensure_ascii=False)
        j0, j1 = os.path.join(self.tmp, "l0.json"), os.path.join(self.tmp, "l1.json")
        run("section_lint.py", self.draft, "--json", j0)
        run("section_lint.py", self.draft, "--json", j1, "--domain", pack)
        c0 = [i for i in json.load(open(j0, encoding="utf-8")) if i["code"] == "C2"]
        c1 = [i for i in json.load(open(j1, encoding="utf-8")) if i["code"] == "C2"]
        self.assertTrue(c0 and c0[0]["level"] == "SHOULD", c0)
        self.assertTrue(c1 and c1[0]["level"] == "INFO" and "领域校准" in c1[0]["msg"], c1)

    def test_tampered_or_stale_pack_is_refused(self):
        pack = os.path.join(self.tmp, "pack_bad")
        shutil.copytree(self.pack, pack)
        b = json.load(open(os.path.join(pack, "bench_baseline.json"), encoding="utf-8"))
        b["exemplars"][0]["note"] = DISC[1]
        json.dump(b, open(os.path.join(pack, "bench_baseline.json"), "w", encoding="utf-8"), ensure_ascii=False)
        code, out = run("domain_pack.py", "check", pack)
        self.assertEqual(code, 1, out)
        prof = json.load(open(os.path.join(pack, "profile.json"), encoding="utf-8"))
        prof["phrase_vocab_extra"] = ["unexpectedword"]
        json.dump(prof, open(os.path.join(pack, "profile.json"), "w", encoding="utf-8"), ensure_ascii=False)
        code, out = run("phrase_contrast.py", "--baseline", pack, "--draft", "稿=" + self.draft, "--report", os.path.join(self.tmp, "x.md"))
        self.assertEqual(code, 2, out)

    def test_corpus_paper_cannot_benchmark_against_its_own_pack(self):
        code, out = run("bench_profile.py", "--baseline", self.pack, "--draft", "稿=" + os.path.join(self.corpus, "p2.md"),
                        "--report", os.path.join(self.tmp, "self.md"))
        self.assertEqual(code, 2, out)


MS = """# Title

## Results

Scores fell by 12.5 points in the treated group (Table 1).

## Discussion

The decline reflects mood rather than cognition. Complaints were stable over the follow-up period in most patients.
"""


def findings(role, items, ms_sha):
    return {"schema_version": 1, "role": role, "manuscript_sha256": ms_sha, "findings": items}


class ReviewMerge(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.ms = write(self.d, "ms.md", MS)
        self.sha = hashlib.sha256(open(self.ms, "rb").read()).hexdigest()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def save(self, name, obj):
        return write(self.d, name, json.dumps(obj, ensure_ascii=False))

    def test_fabricated_major_quote_is_rejected(self):
        f = self.save("a.json", findings("reviewer_methods", [{"id": "M1", "severity": "major", "section": "discussion",
                                                                "quote": "The treatment caused recovery in all patients",
                                                                "problem": "Causal claim"}], self.sha))
        code, out = run("review_merge.py", "validate", "--manuscript", self.ms, f)
        self.assertEqual(code, 1, out)
        self.assertIn("锚点不存在", out)

    def test_version_mismatch_is_rejected(self):
        f = self.save("a.json", findings("reviewer_argument", [{"severity": "minor", "quote": "", "problem": "x"}], "0" * 64))
        code, out = run("review_merge.py", "merge", "--manuscript", self.ms, "--out", os.path.join(self.d, "adj.csv"), f)
        self.assertEqual(code, 1, out)

    def test_cluster_decide_and_check(self):
        a = self.save("a.json", findings("reviewer_methods", [{"id": "M1", "severity": "major", "section": "discussion",
                                                                "quote": "The decline reflects mood rather than cognition.",
                                                                "problem": "Cross-sectional design cannot show what the decline reflects"}], self.sha))
        b = self.save("b.json", findings("reviewer_argument", [{"id": "A1", "severity": "minor", "section": "discussion",
                                                                 "quote": "reflects mood rather than cognition",
                                                                 "problem": "No alternative explanation considered"},
                                                                {"id": "A2", "severity": "note", "section": "results", "quote": "",
                                                                 "problem": "Results could name the outcome first"}], self.sha))
        adj = os.path.join(self.d, "adj.csv")
        code, out = run("review_merge.py", "merge", "--manuscript", self.ms, "--out", adj, a, b)
        self.assertEqual(code, 0, out)
        rows = list(csv.DictReader(open(adj, encoding="utf-8-sig")))
        top = rows[0]
        self.assertEqual((top["severity"], top["n_reviewers"]), ("major", "2"), rows)
        self.assertEqual(len(rows), 2)
        code, out = run("review_merge.py", "check", "--adjudication", adj, "--after", self.ms)
        self.assertEqual(code, 1)
        self.assertIn("未裁决", out)
        rows[0]["decision"], rows[0]["reason"] = "采纳", "改为关联表述"
        rows[1]["decision"], rows[1]["reason"] = "不采纳", ""
        with open(adj, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        code, out = run("review_merge.py", "check", "--adjudication", adj, "--after", self.ms)
        self.assertEqual(code, 1)
        self.assertIn("原样在修改后稿件中", out)
        self.assertIn("没有写理由", out)
        rows[1]["reason"] = "结果节已先写结局，表述符合期刊体例"
        with open(adj, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        after = write(self.d, "ms_v2.md", MS.replace("The decline reflects mood rather than cognition.", "The decline was associated with lower mood."))
        code, out = run("review_merge.py", "check", "--adjudication", adj, "--after", after)
        self.assertEqual(code, 0, out)

    def test_previous_round_marks_persisting_issue(self):
        a = self.save("a.json", findings("cold_reader", [{"severity": "minor", "section": "discussion",
                                                          "quote": "Complaints were stable over the follow-up period in most patients.",
                                                          "problem": "Which complaints?"}], self.sha))
        adj1 = os.path.join(self.d, "adj1.csv")
        run("review_merge.py", "merge", "--manuscript", self.ms, "--out", adj1, a)
        adj2 = os.path.join(self.d, "adj2.csv")
        code, out = run("review_merge.py", "merge", "--manuscript", self.ms, "--out", adj2, "--previous", adj1, a)
        self.assertEqual(code, 0, out)
        self.assertTrue(list(csv.DictReader(open(adj2, encoding="utf-8-sig")))[0]["status"].startswith("仍在"))


class AgentBriefs(unittest.TestCase):
    def test_every_role_follows_the_contract(self):
        roles = [p for p in glob.glob(os.path.join(ROOT, "agents", "*.md")) if not p.endswith("README.md")]
        self.assertGreaterEqual(len(roles), 6)
        for p in roles:
            t = open(p, encoding="utf-8").read()
            for sec in ("使命", "输入", "不给", "流程", "输出契约", "禁止", "停止条件"):
                self.assertIn("**%s**" % sec, t, "%s 缺少 %s" % (os.path.basename(p), sec))


if __name__ == "__main__":
    unittest.main()
