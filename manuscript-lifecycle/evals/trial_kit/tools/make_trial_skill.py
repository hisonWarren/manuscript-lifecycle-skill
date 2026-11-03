#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_trial_skill.py — 打一份给执行模型安装的技能包：去掉 evals/（评分材料、陷阱清单与参考稿都在里面），其余原样。

  python tools/make_trial_skill.py 技能目录 --out 试跑用.zip

试跑时执行模型只装这一份；evals/ 永远不给执行模型。
"""
import argparse, os, sys, zipfile
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_dir"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root = os.path.abspath(a.skill_dir)
    if not os.path.isfile(os.path.join(root, "SKILL.md")):
        print("不是技能目录（缺 SKILL.md）：%s" % a.skill_dir, file=sys.stderr); return 2
    if os.path.exists(a.out):
        print("%s 已存在：换个文件名" % a.out, file=sys.stderr); return 2
    name, n = os.path.basename(root.rstrip("/\\")), 0
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dn, fn in os.walk(root):
            dn[:] = sorted(d for d in dn if d != "__pycache__" and not (dp == root and d == "evals"))
            for f in sorted(fn):
                p = os.path.join(dp, f)
                z.write(p, os.path.join(name, os.path.relpath(p, root)).replace(os.sep, "/")); n += 1
    print("已写 %s：%d 个文件，不含 evals/。" % (a.out, n)); return 0


if __name__ == "__main__":
    sys.exit(main())
