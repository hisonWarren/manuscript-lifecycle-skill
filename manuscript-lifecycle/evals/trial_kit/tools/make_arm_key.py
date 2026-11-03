#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_arm_key.py — 随机给技能版本分配盲码，写进 arm_key.csv（可选；想让评分方不知道哪个是哪个时用）。

  python tools/make_arm_key.py skill_A.zip skill_B.zip [skill_C.zip] [--baseline]

输出 arm_key.csv：code,version。--baseline 额外加一行 Z,无技能。已存在 arm_key.csv 时拒绝覆盖。
"""
import csv, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not args:
        print(__doc__); return 2
    p = os.path.join(ROOT, "arm_key.csv")
    if os.path.exists(p):
        print("arm_key.csv 已存在，不覆盖"); return 2
    codes = ["P", "Q", "R", "S"][:len(args)]; random.shuffle(args)
    rows = list(zip(codes, args)) + ([("Z", "无技能")] if "--baseline" in sys.argv else [])
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["code", "version"]); w.writerows(rows)
    print("已写 arm_key.csv。试跑时只用盲码；自己需要知道每个盲码装哪个技能，可以打开这个文件看，但不要把它放进模型的工作目录。")
    return 0
if __name__ == "__main__":
    sys.exit(main())
