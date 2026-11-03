#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ledger_check.py — 结果台账与稿件的关键词定位候选；报告取舍和必要披露另做语义裁决。

  python ledger_check.py results_ledger.csv --manuscript ms.md [--supplement sm.md] [--report out.md]

台账列（assets/templates/results_ledger.csv）：id, analysis, result, supports_claim, tier, must_disclose, keywords,
source, reviewer_question, decision。tier 取 main / supp / reserve / omit（正文 / 补充 / 回复备用 / 不报告）。
keywords 用 ; 分隔，是这项分析在稿件中会出现的特征短语。
检查：
  · 列齐全，tier 合法；main 行写了 supports_claim 和 source。
  · main 行的关键词在正文出现；supp 行在补充材料出现（提供了补充材料时）。
  · reserve/omit 必须填写决定依据；命中稿件时先复核披露义务和分档，不指令删稿。
  · must_disclose=y 的行必须是 main 或 supp，且关键词出现。
关键词选得太泛（如 "model"）会误报。要用这项分析独有的短语，例如 "careless respond"、"questionnaire version"。
退出码：0 无 ERROR；1 有 ERROR；2 输入错误。
"""
import argparse, csv, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

COLS = ["id", "analysis", "result", "supports_claim", "tier", "must_disclose", "keywords", "source", "reviewer_question", "decision"]
TIERS = {"main": "正文", "supp": "补充", "reserve": "回复备用", "omit": "不报告"}


def body_text(path):
    return "\n".join(b["text"] for b in M.parse(M.load_text(path)) if b["sec"] not in ("references",))


def find(text, kws):
    nt = M.norm_for_match(text)
    return [k for k in kws if M.norm_for_match(k) and M.norm_for_match(k) in nt]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ledger"); ap.add_argument("--manuscript", required=True); ap.add_argument("--supplement", default="")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    for p in [a.ledger, a.manuscript] + ([a.supplement] if a.supplement else []):
        if not os.path.exists(p):
            print("找不到 %s" % p, file=sys.stderr); return 2
    rows = list(csv.DictReader(open(a.ledger, encoding="utf-8-sig", newline="")))
    if not rows:
        print("台账为空", file=sys.stderr); return 2
    miss_cols = [c for c in COLS if c not in rows[0]]
    ms = body_text(a.manuscript); sm = body_text(a.supplement) if a.supplement else ""
    err, warn, cnt, seen_ids = [], [], {}, set()
    if miss_cols:
        err.append("台账缺列：%s" % "、".join(miss_cols))
    for r in rows:
        rid = r.get("id", "?"); tier = (r.get("tier") or "").strip().lower()
        if not rid or rid in seen_ids:
            err.append("台账 ID 为空或重复：%s" % rid)
        seen_ids.add(rid)
        kws = [k.strip() for k in (r.get("keywords") or "").split(";") if k.strip()]
        disc = (r.get("must_disclose") or "").strip().lower() in ("y", "yes", "1", "是")
        if (r.get("must_disclose") or "").strip().lower() not in ("y", "yes", "1", "是", "n", "no", "0", "否"):
            err.append("%s：must_disclose 必须明确为 y/n，不能留空或用未知值" % rid)
        cnt[tier] = cnt.get(tier, 0) + 1
        if tier not in TIERS:
            err.append("%s：tier「%s」不合法（main/supp/reserve/omit）" % (rid, tier)); continue
        if disc and tier not in ("main", "supp"):
            err.append("%s：必须披露的项目不能定为%s" % (rid, TIERS[tier]))
        if tier in ("reserve", "omit") and not (r.get("decision") or "").strip():
            err.append("%s：备用/不报告须登记具体决定依据，先核必要披露，不能默认排除" % rid)
        if not kws:
            err.append("%s：没有关键词，无法核对位置；不能记为通过" % rid)
        in_ms, in_sm = find(ms, kws), (find(sm, kws) if sm else [])
        if tier == "main":
            if not (r.get("supports_claim") or "").strip() or not (r.get("source") or "").strip():
                err.append("%s：放正文的结果必须写明支撑哪条主张（supports_claim）和来源文件（source）" % rid)
            if not in_ms:
                err.append("%s：台账说放正文，正文里找不到关键词 %s（可能是措辞变化，须核查）" % (rid, kws))
        elif tier == "supp":
            if not sm or not in_sm:
                err.append("%s：补充材料未提供、为空或找不到关键词 %s" % (rid, kws))
        else:
            if (in_ms or in_sm) and not disc:
                err.append("%s：台账定为%s，稿件中出现 %s。先复核必要披露、实际分析身份及分档理由；关键词命中不能作为删稿依据。依据事实同步台账和稿件，保留裁决记录" % (rid, TIERS[tier], in_ms + in_sm))
        if disc:
            if tier in ("main", "supp") and not (in_ms or in_sm):
                err.append("%s：必须披露，但正文和补充材料里都找不到 %s" % (rid, kws))
    L = ["# 结果台账核对\n", "台账 %d 行：%s。ERROR %d、WARN %d。\n" % (len(rows), "，".join("%s %d" % (TIERS.get(k, k), v) for k, v in cnt.items()), len(err), len(warn))]
    L += ["- **ERROR** " + e for e in err] + ["- WARN " + w for w in warn]
    L.append("\n关键词命中只验证文本定位候选，不能证明分析、数字、来源或披露完整。来源须另做结构化证据核对。分档依据见 references/03_reporting_tiers.md。台账改动要同步写进决策登记。")
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    print(out if not a.report else L[1].strip())
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
