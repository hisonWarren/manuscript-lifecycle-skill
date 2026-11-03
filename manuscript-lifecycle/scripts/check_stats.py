#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_stats.py — 汇总多次 check_all 的结果：哪些规则最常阻断、最常被作者判为误报、哪些检查常常没能运行。

  python check_stats.py 检查目录或项目目录… [--notes 作者说明.md …] [--report 汇总.md] [--json 汇总.json]

在给出的目录下递归查找 check_all 写的 summary.json。--notes 读作者说明里写有“误报”的行或小节，取出其中的规则代码
（如 section_lint R1、P2）。输出运行次数、可交次数、没能运行的检查，以及每条规则的命中次数（必须处理、看一眼）、
出现在几次运行里、被判为误报的次数。
用途是监控：误报多的规则先复查，再决定改规则还是改说明；命中为零的规则，检查它是否还能触发。它不判断规则本身对不对。
退出码：0 正常；2 没找到 summary.json 或输入错误。
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402

CODE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,4}\d{1,2})(?![A-Za-z0-9])")


def summaries(paths):
    found = []
    for p in paths:
        if os.path.isfile(p) and os.path.basename(p) == "summary.json":
            found.append(p)
        if os.path.isdir(p):
            for dp, dn, fn in os.walk(p):
                if "summary.json" in fn:
                    found.append(os.path.join(dp, "summary.json"))
    return sorted(set(os.path.abspath(f) for f in found))


def fp_codes(path):
    """作者说明里写有“误报”的行，以及标题含“误报”的小节，取出其中的规则代码。"""
    codes, inside = [], False
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            if re.match(r"^\s*#{1,6}\s", line):
                inside = "误报" in line or "false positive" in line.lower()
                continue
            if inside or "误报" in line or "false positive" in line.lower():
                codes += CODE.findall(line)
    return codes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--notes", nargs="*", default=[])
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    for p in a.paths + a.notes:
        if not os.path.exists(p):
            print("找不到：%s" % p, file=sys.stderr)
            return 2
    files = summaries(a.paths)
    if not files:
        print("没找到 summary.json：先用 check_all.py 跑检查，再把它的输出目录（或上层目录）交给本脚本。", file=sys.stderr)
        return 2
    runs, ok, notrun, rules = 0, 0, collections.Counter(), {}
    for fpath in files:
        try:
            with open(fpath, encoding="utf-8") as f:
                s = json.load(f)
        except ValueError:
            print("跳过无法解析的文件：%s" % fpath, file=sys.stderr)
            continue
        runs += 1
        ok += s.get("exit") == 0
        seen = set()
        for kind in ("must", "look"):
            for it in s.get(kind, []):
                key = ("%s %s" % (it.get("tool", ""), it.get("code", ""))).strip() or "（未标代码）"
                r = rules.setdefault(key, {"must": 0, "look": 0, "runs": 0, "fp": 0, "example": it.get("text", "")[:120]})
                r[kind] += 1
                if key not in seen:
                    r["runs"] += 1
                    seen.add(key)
        for it in s.get("notrun", []):
            notrun[(it.get("text", "").split("：")[0] or "？")[:40]] += 1
    fp = collections.Counter(c for n in a.notes for c in fp_codes(n))
    for key, r in rules.items():
        r["fp"] = fp.get(key.split()[-1], 0)
    order = sorted(rules.items(), key=lambda kv: (-kv[1]["must"], -kv[1]["fp"], -kv[1]["look"], kv[0]))
    data = {"runs": runs, "deliverable": ok, "notrun": dict(notrun), "rules": dict(order),
            "notes": len(a.notes), "false_positive_codes": dict(fp)}
    L = ["# 检查汇总", "",
         "%d 次运行，可交 %d 次；读了 %d 份作者说明。误报次数来自作者说明里写有“误报”的行或小节。" % (runs, ok, len(a.notes)), "",
         "| 规则 | 必须处理 | 看一眼 | 出现在几次运行 | 判为误报 | 例 |", "|---|---|---|---|---|---|"]
    for key, r in order:
        L.append("| %s | %d | %d | %d | %d | %s |" % (key, r["must"], r["look"], r["runs"], r["fp"], r["example"].replace("|", "/")))
    if notrun:
        L += ["", "## 没能运行的检查", ""] + ["- %s：%d 次" % kv for kv in notrun.most_common()]
    L += ["", "读法：判为误报的次数接近命中次数的规则，先看是词表还是阈值的问题；命中为零的规则，检查它是否还能触发。汇总只计次数，不判断规则对错。", ""]
    text = "\n".join(L)
    if a.report:
        with M.wfile(a.report) as f:
            f.write(text)
    if a.json:
        with M.wfile(a.json) as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    print("已写 %s：%d 次运行，%d 条规则。" % (a.report, runs, len(rules)) if a.report else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
