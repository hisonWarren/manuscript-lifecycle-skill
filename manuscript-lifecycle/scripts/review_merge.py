#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_merge.py — 多位审稿人（子代理或人工）发现的校验、合并与改后核对。

  校验：python review_merge.py validate --manuscript ms.md review/round1/*.json
  合并：python review_merge.py merge --manuscript ms.md --out review/round1/adjudication.csv [--previous review/round0/adjudication.csv]
              [--report review/round1/summary.md] review/round1/*.json
  核对：python review_merge.py check --adjudication review/round1/adjudication.csv --after ms_v2.md [--report check.md]

发现文件格式见 agents/README.md。为什么需要它：
  · 子代理会"引用"稿件里并不存在的句子。validate 逐条核对 quote 是否逐字出现在稿件中（空白与标点归一后），
    并核对 manuscript_sha256 是否就是这份稿件；major 级别的发现锚点不存在即退回。
  · 多位审稿人常指出同一处问题。merge 按位置聚类（同一节、引文互相包含或词语重合 ≥50%），统计几位审稿人指出，
    多人共同指出的排在前面，不同审稿人的不同判断并列保留，不替他们投票。
  · 给了 --previous（上一轮裁决表）时，标出本轮发现是"仍在"（上一轮已指出、原文还在）还是"新出现"，用于判断是否收敛。
  · 裁决表每行填 decision（采纳 / 不采纳 / 暂缓）与 reason。check 核对：每行都有裁决；不采纳与暂缓写了理由；
    采纳且有 quote 的，原文不能原样留在修改后稿件中（理由写明"保留原文/移至/合并"的除外）。
退出码：validate/merge 0 成功、1 有退回项（锚点不存在的 major、稿件指纹不符）、2 输入错误；check 0 无问题、1 有未裁决或未落实。
脚本只核对形式与落实；发现本身对不对，由主对话按证据裁决。同一模型的多个审稿人意见一致，不等于独立专家共识。
"""
import argparse
import collections
import csv
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402
from output_safety import output_path, write_fresh  # noqa: E402

SEV = {"major": 0, "minor": 1, "note": 2}
DEC = {"采纳": "accept", "接受": "accept", "accept": "accept", "accepted": "accept",
       "不采纳": "reject", "拒绝": "reject", "reject": "reject", "rejected": "reject",
       "暂缓": "defer", "defer": "defer", "deferred": "defer"}
KEEP = re.compile(r"保留原文|原文保留|移至|移到|合并|并入|拆分|已在别处|moved|merged|kept|split", re.I)
FIELDS = ["cluster", "severity", "section", "category", "reviewers", "n_reviewers", "status", "quote", "problems", "suggestions",
          "anchor", "decision", "reason"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_findings(paths, ms_path):
    ms_text = M.load_text(ms_path)
    ms_norm = M.norm_for_match(ms_text)
    ms_sha = sha(ms_path)
    out, problems, notes = [], [], []
    for p in paths:
        try:
            data = json.load(open(p, encoding="utf-8-sig"))
        except (OSError, ValueError) as e:
            raise ValueError("无法读取 %s：%s" % (p, e))
        role = data.get("role") or os.path.splitext(os.path.basename(p))[0]
        if data.get("schema_version") != 1 or not isinstance(data.get("findings"), list):
            raise ValueError("%s 不是 schema_version 1 的审查发现文件（需要 findings 列表）" % p)
        if data.get("manuscript_sha256") and data["manuscript_sha256"] != ms_sha:
            problems.append("%s 审查的不是这份稿件（manuscript_sha256 不符）：全部发现退回，请对当前版本重新审查" % role)
            continue
        if not data.get("manuscript_sha256"):
            notes.append("%s 没有填写 manuscript_sha256，无法确认审查的是哪个版本" % role)
        cov = data.get("coverage") if isinstance(data.get("coverage"), dict) else None
        if not data["findings"]:
            okq = [x for x in (cov or {}).get("ok_examples", []) if isinstance(x, dict) and (x.get("quote") or "").strip()]
            found = [x for x in okq if M.norm_for_match(x["quote"].strip()) in ms_norm]
            if not cov or not cov.get("sections") or not cov.get("checked") or len(found) < 2:
                problems.append("%s 报告 0 条发现，却没有覆盖证明（coverage：sections、checked，以及至少 2 条能在稿件中找到的 ok_examples）：空审退回重审" % role)
                continue
            notes.append("%s 报告 0 条发现，附覆盖证明：%d 节、%d 项检查、%d 条通过样例" % (role, len(cov["sections"]), len(cov["checked"]), len(found)))
        elif cov:
            lost = [(x.get("quote") or "")[:40] for x in cov.get("ok_examples", []) if isinstance(x, dict) and (x.get("quote") or "").strip()
                    and M.norm_for_match(x["quote"].strip()) not in ms_norm]
            if lost:
                notes.append("%s 的覆盖证明里有 %d 条样例在稿件中找不到：%s" % (role, len(lost), "；".join(lost[:3])))
        for i, f in enumerate(data["findings"], 1):
            sev = (f.get("severity") or "").lower()
            if sev not in SEV or not (f.get("problem") or "").strip():
                problems.append("%s 第 %d 条缺少 severity（major/minor/note）或 problem" % (role, i))
                continue
            q = (f.get("quote") or "").strip()
            anchor = "global"
            if q:
                n_words = M.count_words(q)
                if n_words > 80:
                    notes.append("%s 第 %d 条 quote 过长（%d），只核对是否存在" % (role, i, n_words))
                anchor = "ok" if M.norm_for_match(q) in ms_norm else "missing"
                if anchor == "missing":
                    msg = "%s %s 条锚点不存在于稿件中：「%s」" % (role, f.get("id") or i, q[:60])
                    (problems if sev == "major" else notes).append(msg + ("（major 退回）" if sev == "major" else "（降为待核）"))
            out.append({"role": role, "id": f.get("id") or "%s-%d" % (role, i), "severity": sev, "section": (f.get("section") or "").strip(),
                        "category": (f.get("category") or "other").strip(), "quote": q, "problem": f["problem"].strip(),
                        "suggestion": (f.get("suggestion") or "").strip(), "anchor": anchor, "confidence": f.get("confidence", "")})
    return out, problems, notes


def tokens(s):
    return set(M.norm_for_match(s).split()) if not M.CJK.search(s) else set(M.CJK.findall(s))


def sections(label):
    """节标签可写成 results/discussion 这样的组合；global、全文或留空表示不限节。"""
    parts = {x.strip().lower() for x in re.split(r"[/,，、;；+&|]", label or "") if x.strip()}
    return set() if not parts or parts & {"global", "whole", "all", "全文", "整体"} else parts


def same_place(a, b):
    if not a["quote"] or not b["quote"]:
        return False
    qa, qb = M.norm_for_match(a["quote"]), M.norm_for_match(b["quote"])
    contained = qa in qb or qb in qa
    sa, sb = sections(a["section"]), sections(b["section"])
    if sa and sb and not sa & sb:
        # 节标签不同，但锚点原文相同或互相包含且够长（不是“本研究”这类到处都有的短语）时，仍是同一处。
        return contained and min(len(qa), len(qb)) >= 15
    if contained:
        return True
    ta, tb = tokens(a["quote"]), tokens(b["quote"])
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.5


def cluster(findings):
    groups = []
    for f in sorted(findings, key=lambda x: (SEV[x["severity"]], x["section"])):
        for g in groups:
            if any(same_place(f, h) for h in g):
                g.append(f)
                break
        else:
            groups.append([f])
    return groups


def read_csv(path):
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise ValueError("裁决表编码无法识别，请保存为 UTF-8")


def cmd_validate(a):
    _, problems, notes = load_findings(a.files, a.manuscript)
    for x in problems:
        print("- 退回：" + x)
    for x in notes:
        print("- 提示：" + x)
    print("校验：退回 %d、提示 %d" % (len(problems), len(notes)))
    return 1 if problems else 0


def cmd_merge(a):
    findings, problems, notes = load_findings(a.files, a.manuscript)
    usable = [f for f in findings if not (f["anchor"] == "missing" and f["severity"] == "major")]
    groups = cluster(usable)
    prev = read_csv(a.previous) if a.previous else []
    after_norm = M.norm_for_match(M.load_text(a.manuscript))
    rows = []
    for g in groups:
        roles = sorted({f["role"] for f in g})
        sev = min(g, key=lambda f: SEV[f["severity"]])["severity"]
        quote = max((f["quote"] for f in g), key=len, default="")
        status = ""
        if prev:
            hit = [r for r in prev if r.get("quote") and quote and same_place({"quote": quote, "section": g[0]["section"]},
                                                                               {"quote": r["quote"], "section": r.get("section", "")})]
            status = ("仍在（上轮 %s）" % "、".join(r["cluster"] for r in hit)) if hit else "新出现"
        rows.append({"severity": sev, "section": g[0]["section"], "category": "/".join(sorted({f["category"] for f in g})),
                     "reviewers": "、".join(roles), "n_reviewers": str(len(roles)), "status": status, "quote": quote,
                     "problems": " ‖ ".join("[%s] %s" % (f["role"], f["problem"]) for f in g),
                     "suggestions": " ‖ ".join("[%s] %s" % (f["role"], f["suggestion"]) for f in g if f["suggestion"]),
                     "anchor": "待核" if any(f["anchor"] == "missing" for f in g) else ("全局" if not quote else "已核"),
                     "decision": "", "reason": ""})
    rows.sort(key=lambda r: (SEV[r["severity"]], -int(r["n_reviewers"]), r["section"]))
    for i, r in enumerate(rows, 1):
        r["cluster"] = "C%02d" % i
    protected = list(a.files) + [a.manuscript] + ([a.previous] if a.previous else [])
    out = output_path(a.out, protected)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    write_fresh(out, "\ufeff" + buf.getvalue())
    by_sev = {k: sum(1 for r in rows if r["severity"] == k) for k in SEV}
    multi = sum(1 for r in rows if int(r["n_reviewers"]) >= 2)
    L = ["# 审查发现汇总\n",
         "审稿人 %d 位；发现 %d 条，合并为 %d 组（major %d、minor %d、note %d）；多人共同指出 %d 组。%s\n" % (
             len({f["role"] for f in findings}), len(findings), len(rows), by_sev["major"], by_sev["minor"], by_sev["note"], multi,
             ("新出现 %d 组、仍在 %d 组。" % (sum(r["status"] == "新出现" for r in rows), sum(r["status"].startswith("仍在") for r in rows))) if prev else ""),
         "读法：多人指出说明问题容易被看到，不等于一定正确；单人指出的 major 同样要按证据裁决。不同审稿人的判断并列保留在 problems 列。"
         "裁决填 decision（采纳/不采纳/暂缓）与 reason，改稿后运行 check。\n"]
    if problems:
        L.append("## 退回\n")
        L += ["- " + x for x in problems]
    if notes:
        L.append("\n## 提示\n")
        L += ["- " + x for x in notes]
    L.append("\n## 各组\n")
    L += ["- %s [%s·%s·%s人] %s：%s" % (r["cluster"], r["severity"], r["section"] or "全文", r["n_reviewers"], r["category"],
                                       (r["quote"][:50] + "…") if len(r["quote"]) > 50 else (r["quote"] or "（全局）")) for r in rows]
    if a.report:
        write_fresh(output_path(a.report, protected + [str(out)]), "\n".join(L) + "\n")
    print("合并：%d 条发现 → %d 组；退回 %d；裁决表 %s" % (len(findings), len(rows), len(problems), out))
    return 1 if problems else 0


def cmd_check(a):
    rows = read_csv(a.adjudication)
    after = M.norm_for_match(M.load_text(a.after))
    errs, warns, cnt = [], [], {"accept": 0, "reject": 0, "defer": 0}
    for r in rows:
        tag = "%s［%s %s］" % (r.get("cluster", "?"), r.get("severity", ""), r.get("section", "") or "全文")
        raw = (r.get("decision") or "").strip()
        d = DEC.get(raw.lower()) or DEC.get(raw)
        reason = (r.get("reason") or "").strip()
        if not d:
            errs.append(tag + "：未裁决（decision 填 采纳 / 不采纳 / 暂缓）")
            continue
        cnt[d] += 1
        if d in ("reject", "defer") and len(reason) < 4:
            errs.append(tag + "：%s但没有写理由" % ("不采纳" if d == "reject" else "暂缓"))
        q = (r.get("quote") or "").strip()
        if d == "accept" and q and M.norm_for_match(q) in after and not KEEP.search(reason):
            errs.append(tag + "：标为采纳，但锚点原文仍原样在修改后稿件中「%s」" % q[:50])
        if d == "accept" and not q:
            warns.append(tag + "：全局问题已采纳，脚本无法定位核对，需通读确认")
        if d == "accept" and r.get("severity") == "major" and not reason:
            warns.append(tag + "：采纳 major 问题，建议在 reason 中写明改了哪里")
    def _dec(r):
        raw = (r.get("decision") or "").strip()
        return DEC.get(raw.lower()) or DEC.get(raw)
    acc = [re.sub(r"\s+", "", (r.get("reason") or "")) for r in rows if _dec(r) == "accept"]
    for k, n in collections.Counter(x for x in acc if x).items():
        if n >= 3:
            errs.append("有 %d 组采纳理由一字不差（「%s」）：模板化理由说不清每组改了什么、问题是否真的解决。逐组写明改动位置与解决方式（可加 change_evidence 列：改前/改后摘录）。" % (n, k[:40]))
    acc_major = [r for r in rows if r.get("severity") == "major" and _dec(r) == "accept"]
    if rows and "change_evidence" in rows[0]:
        for r in acc_major:
            if not (r.get("change_evidence") or "").strip():
                errs.append("%s［major］：采纳却没有 change_evidence（改前/改后摘录或位置）" % r.get("cluster", "?"))
    elif acc_major:
        warns.append("裁决表没有 change_evidence 列：采纳的 major 问题只能靠 reason 说明改动，下一轮复查难以核对")
    L = ["# 审查裁决核对\n", "共 %d 组：采纳 %d、不采纳 %d、暂缓 %d、未裁决 %d。错误 %d、复核 %d。\n" % (
        len(rows), cnt["accept"], cnt["reject"], cnt["defer"], len(rows) - sum(cnt.values()), len(errs), len(warns)),
         "退出 0 只说明每组都有裁决、采纳的锚点原文已改动、理由不是同一句模板；改得对不对，交给下一轮未见本轮结论的审稿人复查。\n"]
    for title, items in (("错误", errs), ("复核", warns)):
        if items:
            L.append("## %s\n" % title)
            L += ["- " + x for x in items]
            L.append("")
    out = "\n".join(L) + "\n"
    if a.report:
        write_fresh(output_path(a.report, [a.adjudication, a.after]), out)
    print(out[:3000])
    return 1 if errs else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("--manuscript", required=True)
    v.add_argument("files", nargs="+")
    m = sub.add_parser("merge")
    m.add_argument("--manuscript", required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--previous", default="")
    m.add_argument("--report", default="")
    m.add_argument("files", nargs="+")
    c = sub.add_parser("check")
    c.add_argument("--adjudication", required=True)
    c.add_argument("--after", required=True)
    c.add_argument("--report", default="")
    a = ap.parse_args()
    try:
        for p in ([a.manuscript] if hasattr(a, "manuscript") else []) + list(getattr(a, "files", [])):
            if not os.path.isfile(p):
                raise ValueError("找不到文件：%s" % p)
        return {"validate": cmd_validate, "merge": cmd_merge, "check": cmd_check}[a.cmd](a)
    except (ValueError, OSError) as e:
        print("输入错误：%s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
