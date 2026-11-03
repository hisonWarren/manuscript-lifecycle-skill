#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pack_return.py — 把全部试跑打成一个验收包（在本工具包根目录执行）。

  python tools/pack_return.py --tester 名字 [--runs runs] [--arm-key arm_key.csv] [--out RETURN_日期_名字.zip]

逐个检查 runs/Rxx：meta.json、prompt.txt、transcript（或 NOT_AVAILABLE.txt 说明原因）、workspace/…/outputs/ 里的必交文件；
生成 manifest.json（每个文件的 SHA-256、环境信息、缺件清单）与每个 run 的 workspace_tree.txt，再打包。
不改动任何试跑文件；不会打包 grader/ 目录；单个文件超过 30 MB 跳过并记录。缺件时仍然打包，但退出码为 1，并列出缺什么。
"""
import argparse, datetime, hashlib, json, os, platform, re, sys, zipfile
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQ = {"T1": ["manuscript.md", "author_note.md", "RUN_REPORT.md"],
       "T2": ["manuscript_zh_v2.md", "response_letter.md", "changes.md", "RUN_REPORT.md"],
       "T3": ["highlights.md", "table1_title_note.md", "figure1_legend.md", "cover_letter.md", "author_todo.md", "RUN_REPORT.md"]}
# 一句话试跑不规定文件名：按技能的默认交付找得到对应文件即可
REQ_SHORT = {"T1": [("稿件", r"(?i)\.(?:md|docx)$")], "T2": [("修改稿", r"(?i)v2|revis|修改|修订|manuscript"), ("回复信", r"(?i)response|reply|rebuttal|回复")],
             "T3": [("Highlights", r"(?i)highlight"), ("投稿信", r"(?i)cover|投稿信")]}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tester", required=True); ap.add_argument("--runs", default=os.path.join(ROOT, "runs"))
    ap.add_argument("--arm-key", default=os.path.join(ROOT, "arm_key.csv")); ap.add_argument("--out", default="")
    a = ap.parse_args()
    if not os.path.isdir(a.runs):
        print("找不到 runs 目录：%s" % a.runs, file=sys.stderr); return 2
    out = a.out or "RETURN_%s_%s.zip" % (datetime.date.today().strftime("%Y%m%d"), a.tester)
    if os.path.exists(out):
        print("%s 已存在：换个文件名" % out, file=sys.stderr); return 2
    man = {"schema": 1, "tester": a.tester, "packed_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "env": {"os": platform.platform(), "python": platform.python_version()}, "runs": [], "skipped_large_files": []}
    problems = []; files = []
    for rid in sorted(os.listdir(a.runs)):
        rd = os.path.join(a.runs, rid)
        if not os.path.isdir(rd): continue
        info = {"run": rid, "missing": []}
        try:
            with open(os.path.join(rd, "meta.json"), encoding="utf-8-sig") as f: meta = json.load(f)
        except (OSError, ValueError):
            meta = {}; info["missing"].append("meta.json（缺失或不是合法 JSON）")
        task = (meta.get("task") or "").upper(); info.update({"task": task, "arm": meta.get("arm", ""), "model": meta.get("model", "")})
        if not os.path.exists(os.path.join(rd, "prompt.txt")): info["missing"].append("prompt.txt")
        if not any(os.path.exists(os.path.join(rd, n)) for n in ("transcript.md", "transcript.jsonl", "transcript.txt", "transcript.json", "NOT_AVAILABLE.txt")):
            info["missing"].append("transcript.*（导不出就放 NOT_AVAILABLE.txt 写明原因）")
        outs = [dp for dp, dn, fn in os.walk(rd) if os.path.basename(dp) == "outputs"]
        if not outs and meta.get("prompt_style") != "short": info["missing"].append("outputs/ 目录")
        else:
            have = set(os.listdir(sorted(outs, key=len)[0]))
            if meta.get("prompt_style") == "short":
                names = [n for dp, dn, fn in os.walk(sorted(outs, key=len)[0]) for n in fn]
                info["missing"] += ["outputs/ 里没有%s" % lab for lab, rx in REQ_SHORT.get(task, []) if not any(re.search(rx, n) for n in names)]
            else:
                info["missing"] += ["outputs/" + r for r in REQ.get(task, []) if r not in have]
        if not meta.get("end_time"): info["missing"].append("meta.json 的 end_time")
        tree = []
        for dp, dn, fn in os.walk(rd):
            dn[:] = [d for d in dn if d not in ("grader", "__pycache__")]
            for n in sorted(fn):
                p = os.path.join(dp, n); rel = os.path.relpath(p, a.runs).replace("\\", "/")
                size = os.path.getsize(p)
                if size > 30 * 1024 * 1024:
                    man["skipped_large_files"].append(rel); continue
                files.append((p, "runs/" + rel)); tree.append("%10d  %s" % (size, os.path.relpath(p, rd).replace("\\", "/")))
        info["tree"] = "\n".join(tree)
        man["runs"].append(info)
        if info["missing"]: problems.append("%s：%s" % (rid, "；".join(info["missing"])))
    if os.path.exists(a.arm_key): files.append((a.arm_key, "arm_key.csv"))
    else: problems.append("没有 arm_key.csv（盲码对应哪个技能版本）")
    man["files"] = [{"path": arc, "sha256": sha(p), "bytes": os.path.getsize(p)} for p, arc in files]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p, arc in files: z.write(p, arc)
        for r in man["runs"]: z.writestr("runs/%s/workspace_tree.txt" % r["run"], r.pop("tree") + "\n")
        z.writestr("manifest.json", json.dumps(man, ensure_ascii=False, indent=1))
    print("已打包 %s：%d 个 run，%d 个文件。" % (out, len(man["runs"]), len(files)))
    if problems:
        print("缺件（仍已打包，评分时按缺件处理）：\n- " + "\n- ".join(problems)); return 1
    return 0
if __name__ == "__main__":
    sys.exit(main())
