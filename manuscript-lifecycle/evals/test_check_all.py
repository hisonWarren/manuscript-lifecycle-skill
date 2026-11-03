"""check_all：一条命令的检查与一页白话状态。用例来自实地试写（模拟精分 PRL 初稿）暴露的问题。"""
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(os.path.dirname(HERE), "scripts")

CLEAN = """# Win-switching is more frequent in simulated patient-like agents

**SIMULATION ONLY.** All data are synthetic and do not describe real participants.

## Abstract

We compared two groups of simulated agents on a reversal learning task. Win-switching was more frequent in the patient-like group, and perseverative errors were fewer.

## Introduction

Reversal learning difficulties are often read as perseveration. This study asked whether the observed profile is closer to perseveration or to win-switching.

## Methods

Two groups of 48 agents completed a two-choice task with 80/20 feedback. Groups were compared with Welch t tests.

## Results

Win-switching was more frequent in the patient-like group (0.153 versus 0.064, d = 1.63). Perseverative errors were fewer (4.92 versus 10.71, d = -0.88).

## Discussion

The simulated difference lies in switching after reward rather than in sticking to the old option.

## Conclusion

Under these generating rules, the profile is one of win-switching, not perseveration.
"""


def run(*args):
    p = subprocess.run([sys.executable] + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class CheckAll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ms = os.path.join(self.tmp, "ms.md")
        self.res = os.path.join(self.tmp, "stats.csv")
        with open(self.res, "w", encoding="utf-8") as f:
            f.write("outcome,HC_mean,SZ_mean,d\nwin_switch_rate,0.064,0.153,1.63\nperseverative_errors,10.71,4.92,-0.88\nn,48,48,\nfeedback,80,20,\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _status(self, out):
        with open(os.path.join(out, "STATUS.md"), encoding="utf-8") as f:
            return f.read()

    def test_clean_simulated_draft_can_go_to_the_author(self):
        with open(self.ms, "w", encoding="utf-8") as f:
            f.write(CLEAN)
        out = os.path.join(self.tmp, "c1")
        code, log = run(os.path.join(S, "check_all.py"), self.ms, "--out", out, "--results", self.res, "--simulation", "--design", "simulation")
        st = self._status(out)
        self.assertEqual(code, 0, st)
        self.assertIn("可以交给作者通读", st)

    def test_field_trial_failures_block_with_plain_reasons(self):
        bad = CLEAN.replace("**SIMULATION ONLY.** All data are synthetic and do not describe real participants.\n", "")
        bad = bad.replace("## Conclusion", "Limitations: sentence-pattern benchmarking against a domain pack was not completed.\n\n## Conclusion")
        bad += "\nThe study was approved by the ethics committee of the university.\n\n**作者待办**：确认主线。\n"
        bad = bad.replace("(0.153 versus 0.064, d = 1.63)", "(0.163 versus 0.064, d = 1.63)")
        with open(self.ms, "w", encoding="utf-8") as f:
            f.write(bad)
        ledger = os.path.join(self.tmp, "ledger.csv")
        with open(ledger, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "plan_status", "claim", "location"])
            w.writerow(["R1", "pre-specified", "win-switch higher", "results"])
        out = os.path.join(self.tmp, "c2")
        code, log = run(os.path.join(S, "check_all.py"), self.ms, "--out", out, "--results", self.res, "--ledger", ledger, "--simulation")
        st = self._status(out)
        self.assertEqual(code, 1, st)
        for want in ("X11", "模拟标识", "真人研究", "列名", "找不到", "0.163"):
            self.assertIn(want, st)
        self.assertNotIn("tier「", st, "列名不对时只报一次“没能运行”，不逐行刷屏")

    def test_allow_file_needs_a_reason_and_thresholds_match(self):
        txt = CLEAN.replace("(0.153 versus 0.064, d = 1.63)", "(0.153 versus 0.064, d = 1.63, P < .001; generating learning rate 0.30)")
        with open(self.ms, "w", encoding="utf-8") as f:
            f.write(txt)
        with open(self.res, "a", encoding="utf-8") as f:
            f.write("p_win_switch,0.00006,,\n")
        out = os.path.join(self.tmp, "c4")
        code, log = run(os.path.join(S, "check_all.py"), self.ms, "--out", out, "--results", self.res)
        st = self._status(out)
        self.assertIn("0.30", st)
        self.assertNotIn(".001 在", st, "P < .001 是阈值写法，来源里有更小的 p 时不算找不到")
        allow = os.path.join(self.tmp, "allow.txt")
        with open(allow, "w", encoding="utf-8") as f:
            f.write("0.30 # 模拟的生成参数，来自模拟设定，不来自结果表\n")
        out2 = os.path.join(self.tmp, "c5")
        code, log = run(os.path.join(S, "check_all.py"), self.ms, "--out", out2, "--results", self.res, "--allow", allow)
        st = self._status(out2)
        self.assertEqual(code, 0, st)
        self.assertIn("生成参数", st)

    def test_refuses_to_reuse_a_report_folder_and_missing_input(self):
        with open(self.ms, "w", encoding="utf-8") as f:
            f.write(CLEAN)
        out = os.path.join(self.tmp, "c3")
        os.makedirs(out)
        with open(os.path.join(out, "STATUS.md"), "w", encoding="utf-8") as f:
            f.write("old")
        code, log = run(os.path.join(S, "check_all.py"), self.ms, "--out", out)
        self.assertIn(code, (0, 1), log)   # 已有报告的目录不覆盖，自动另开 目录_2
        self.assertTrue(os.path.isfile(os.path.join(out + "_2", "STATUS.md")), log)
        code, log = run(os.path.join(S, "check_all.py"), os.path.join(self.tmp, "nope.md"))
        self.assertEqual(code, 2, log)


if __name__ == "__main__":
    unittest.main()
