#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coverage_check.py — 文献覆盖：该引的有没有引。它和“引文核实”（lit_evidence、citation_checker）是两件事：
引文条条核实，照样可能缺刺激来源、竞争理论和方法出处。

  python coverage_check.py 稿件.md|docx --map coverage_map.csv [--neighbors neighbors.csv] [--note 作者说明.md]
         [--stage draft|submission] [--roles 键=说明,…] [--report out.md] [--json out.json]
  python coverage_check.py 稿件.md|docx --scan-only [--neighbors neighbors.csv] [--report out.md] [--json out.json]

覆盖表（assets/templates/coverage_map.csv）按论证职能列行：role、need、required、sources、status、search_log、notes。
默认七类 role：background 背景；direct_neighbor 问题与设计最接近的实证研究；competing_account 竞争解释；
materials_source 刺激、材料、任务或范式出处；measure_source 测量与指标定义；analysis_source 统计与分析方法出处；
contrary_evidence 相反、限定或未重复的证据。不适用的写 status=na 并在 notes 写理由。
status：covered（sources 里的文献都在参考文献表中）、gap（检索过仍缺）、searched_none（检索过确实没有）、deferred（作者决定暂缓）、na。

  CV1 MUST   必需的角色没有行、status 不认识，或 na 没写理由。
  CV2 MUST   gap、searched_none 没有检索记录（检索式、数据库、日期、命中与筛选）：“没找”不能写成“没有”。
  CV3        仍有缺口：起草阶段 SHOULD；--stage submission 为 MUST。deferred 列为作者待办。
  CV4 MUST   status=covered 却没写 sources，或 sources 在稿件参考文献表里找不到。
  CV5 SHOULD 方法、结果里出现命名方法、刺激或软件（Greenhouse–Geisser、Holm、Firth、Spearman–Brown、bootstrap、point-light 等），
             所在句没有引文。供覆盖审查逐条判断，不是自动缺陷。
  CV6 SHOULD 参考文献数与实际读到的近邻论文（--neighbors：label、doi、n_refs、source_locator）相差悬殊。只作信号：
             从不设最低篇数，也不能用边缘引用凑数。
  CV7 MUST   作者说明写了“投稿包备齐 / 可直接投稿 / submission-ready”，而覆盖还有未关闭的缺口或必须处理项。
  CV0 SHOULD 没有覆盖表（--scan-only）。
退出码：0 无 MUST；1 有 MUST；2 输入错误。
"""
import argparse
import collections
import csv
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402
from output_safety import output_path, write_fresh  # noqa: E402

ROLES = collections.OrderedDict([
    ("background", "研究问题的背景与重要性"), ("direct_neighbor", "问题与设计最接近的实证研究"),
    ("competing_account", "竞争解释或理论（不止一家）"), ("materials_source", "刺激、材料、任务或范式的出处"),
    ("measure_source", "测量与指标的定义出处"), ("analysis_source", "统计与分析方法的出处"),
    ("contrary_evidence", "相反、限定或未重复的证据")])
STATUSES = {"covered", "gap", "searched_none", "deferred", "na"}
DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>\]]+", re.I)
REF_MD = re.compile(r"^\s*#{1,6}\s*(?:\*\*)?\s*(?:\d+(?:\.\d+)*\.?\s*)?(?:supplementary\s+)?(?:references?|bibliography|literature\s+cited|works\s+cited|参\s*考\s*文\s*献)\b", re.I)
REF_LINE = re.compile(r"^\s*(?:\*\*)?\s*(?:references?|bibliography|参\s*考\s*文\s*献)\s*(?:\*\*)?\s*[:：]?\s*$", re.I)
METHOD_TERMS = re.compile(
    r"Greenhouse[–-]Geisser|Huynh[–-]Feldt|\bHolm\b|Bonferroni|Benjamini[–-]Hochberg|false discovery rate|\bFirth\b|Spearman[–-]Brown|Cronbach"
    r"|bootstrap\w*|permutation tests?|sign-flip|mixed[- ]effects? models?|\bIRLS\b|ridge (?:penalty|regression)|psychometric functions?|point-light"
    r"|biological motion (?:stimuli|displays?|walkers?)|motion capture|independent component analysis|\bICA\b|EEGLAB|ERPLAB|FieldTrip|\bMNE\b"
    r"|cluster-based permutation|Bayes factors?|\bTOST\b|equivalence tests?|repeated-measures correlation|rmcorr|multiple imputation|\bFIML\b"
    r"|lavaan|lme4|brms|PsychoPy|Psychtoolbox|E-Prime|Kaplan[–-]Meier|格林豪斯|自助法|置换检验|点光源|生物运动刺激|独立成分分析|多重插补", re.I)
CLAIM = re.compile(r"投稿包备齐|投稿就绪|可直接投稿|已可投稿|ready\s+(?:for|to)\s+(?:submission|submit)|submission[- ]ready", re.I)
NEG = re.compile(r"(?:未|不|尚未|还不|not|isn't|is not|n't)\s*$", re.I)


def references(text):
    refs, on = [], False
    for line in text.split("\n"):
        s = line.strip()
        if re.match(r"^#{1,6}\s", s) or REF_LINE.match(s):
            on = bool(REF_MD.match(s) or REF_LINE.match(s))
            continue
        if on and s and not s.startswith("|"):
            refs.append(s)
    keys, dois = set(), set()
    for r in refs:
        dois.update(d.rstrip(".,;)").lower() for d in DOI.findall(r))
        m = re.match(r"\s*(?:\[\d+\]\s*|\d+\.\s*)?([A-Z][A-Za-z'’\-]+|[\u4e00-\u9fff]{1,4})", r)
        y = re.search(r"\b(?:19|20)\d{2}", r)
        if m and y:
            keys.add((m.group(1).lower(), y.group(0)))
    return refs, keys, dois


def source_keys(s):
    out = []
    for item in re.split(r"[;；\n]+", s or ""):
        item = item.strip()
        if not item:
            continue
        d = DOI.search(item)
        if d:
            out.append(("doi", d.group(0).rstrip(".,;)").lower(), item))
            continue
        m = re.match(r"([A-Z][A-Za-z'’\-]+|[\u4e00-\u9fff]{1,4})", item)
        y = re.search(r"\b(?:19|20)\d{2}", item)
        out.append(("ay", (m.group(1).lower(), y.group(0)), item) if (m and y) else ("bad", None, item))
    return out


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manuscript")
    ap.add_argument("--map", default="")
    ap.add_argument("--scan-only", action="store_true")
    ap.add_argument("--neighbors", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--stage", default="draft", choices=["draft", "submission"])
    ap.add_argument("--roles", default="", help="自定义必需角色：键=说明,键=说明（替换默认七类）")
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    inputs = [x for x in (a.manuscript, a.map, a.neighbors, a.note) if x]
    miss = [x for x in inputs if not os.path.isfile(x)]
    if miss:
        print("找不到输入：%s" % "、".join(miss), file=sys.stderr)
        return 2
    if not a.map and not a.scan_only:
        print("要给 --map 覆盖表；只想列候选就用 --scan-only", file=sys.stderr)
        return 2
    try:
        outs = {k: output_path(v, inputs) for k, v in (("report", a.report), ("json", a.json)) if v}
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    text = M.load_text(a.manuscript)
    if not text.strip():
        print("not_verified：稿件为空，不能把零检查记为通过", file=sys.stderr)
        return 2
    roles = ROLES
    if a.roles:
        roles = collections.OrderedDict((x.split("=", 1)[0].strip(), x.split("=", 1)[-1].strip()) for x in a.roles.split(",") if x.strip())
    refs, keys, dois = references(text)
    items, open_gaps, summary = [], 0, collections.OrderedDict()

    def add(level, code, msg, ex=()):
        items.append({"level": level, "code": code, "msg": msg, "examples": [e[:240] for e in ex][:8]})
    if a.map:
        rows = read_csv(a.map)
        if rows and "role" not in rows[0]:
            print("覆盖表缺 role 列（模板见 assets/templates/coverage_map.csv）", file=sys.stderr)
            return 2
        for role, desc in roles.items():
            if not any(r.get("role") == role for r in rows):
                add("MUST", "CV1", "覆盖表没有“%s”（%s）这一类：写出需要哪些文献，或写 status=na 并说明为什么不适用。" % (role, desc))
                open_gaps += 1
        for i, r in enumerate(rows, 2):
            role, st = r.get("role", ""), (r.get("status") or "").lower()
            tag = "第 %d 行 %s：%s" % (i, role or "?", (r.get("need") or "")[:60])
            req = (r.get("required") or "yes").lower() not in ("no", "否", "false", "0")
            summary.setdefault(role, collections.Counter())[st or "空"] += 1
            if st not in STATUSES:
                add("MUST", "CV1", "%s 的 status 写成“%s”，不认识（covered / gap / searched_none / deferred / na）。" % (tag, st or "空"))
                open_gaps += 1
                continue
            if st == "na" and not r.get("notes"):
                add("MUST", "CV1", "%s 标为不适用却没写理由。" % tag)
            if st in ("gap", "searched_none") and not r.get("search_log"):
                add("MUST", "CV2", "%s 标为%s，却没有检索记录（检索式、数据库、日期、命中与筛选）。没找不能写成没有。" % (tag, "缺口" if st == "gap" else "检索后没有"))
                open_gaps += 1
            elif st == "gap":
                add("MUST" if (a.stage == "submission" and req) else "SHOULD", "CV3", "%s 仍是缺口（已有检索记录）。补读原文后引用，或改写依赖这条证据的句子。" % tag)
                open_gaps += 1
            if st == "deferred":
                add("SHOULD", "CV3", "%s 由作者决定暂缓：列进作者待办；暂缓期间不能写“投稿包备齐”。" % tag)
                open_gaps += 1
            if st == "covered":
                srcs = source_keys(r.get("sources"))
                if not srcs:
                    add("MUST", "CV4", "%s 标为已覆盖，却没写 sources。" % tag)
                    open_gaps += 1
                bad = [x[2] for x in srcs if (x[0] == "doi" and x[1] not in dois) or (x[0] == "ay" and x[1] not in keys) or x[0] == "bad"]
                if bad:
                    add("MUST", "CV4", "%s 写的来源在参考文献表里找不到：%s。覆盖表只能记稿件里真引用了的文献。" % (tag, "；".join(bad[:4])))
                    open_gaps += 1
    else:
        add("SHOULD", "CV0", "没有文献覆盖表：引文逐条核实不等于该引的都引了。按 references/24 建 coverage_map.csv。")
    cands, seen = [], set()
    for b in M.parse(text):
        if b["kind"] != "para" or b["sec"] not in ("methods", "results"):
            continue
        for s in M.sentences(b["text"]):
            if M.count_citations(s):
                continue
            for m in METHOD_TERMS.finditer(s):
                k = m.group(0).lower()
                if k not in seen:
                    seen.add(k)
                    cands.append("%s：%s" % (m.group(0), s[:150]))
    if cands:
        add("SHOULD", "CV5", "%d 个命名方法、刺激或软件所在句没有引文。逐条判断是否需要方法学、刺激或软件出处（通行到不需要引用的写明理由）。" % len(cands), cands)
    nb = []
    if a.neighbors:
        for r in read_csv(a.neighbors):
            try:
                nb.append((r.get("label") or r.get("doi") or "?", int(float(r.get("n_refs") or ""))))
            except ValueError:
                continue
    if len(nb) >= 2 and refs:
        lo, med = min(n for _, n in nb), statistics.median(n for _, n in nb)
        if len(refs) < 0.5 * lo:
            add("SHOULD", "CV6", "参考文献 %d 条；实际读到的 %d 篇近邻论文为 %d–%d 条（中位 %g）。这不是阈值：按覆盖表逐项找缺口，不用边缘引用凑数。" % (
                len(refs), len(nb), lo, max(n for _, n in nb), med), ["%s：%d" % x for x in nb])
    if a.note:
        note = M.load_text(a.note)
        claims = [m for m in CLAIM.finditer(note) if not NEG.search(note[max(0, m.start() - 8):m.start()])]
        if claims and (open_gaps or any(i["level"] == "MUST" for i in items)):
            add("MUST", "CV7", "作者说明写了“%s”，但文献覆盖还有 %d 处未关闭。覆盖、图表语义、论证与版式分别验收，任何一项没过都不能这样写。" % (claims[0].group(0), open_gaps))
    must = sum(i["level"] == "MUST" for i in items)
    L = ["# 文献覆盖（coverage_check）", "", "参考文献 %d 条；覆盖表%s；阶段 %s；未关闭缺口 %d。" % (len(refs), "已给" if a.map else "没给", a.stage, open_gaps), "",
         "引文核实回答“引得对不对”，本表回答“该引的有没有引”。两者都过，才谈得上文献充分。", ""]
    for lvl in ("MUST", "SHOULD"):
        sel = [i for i in items if i["level"] == lvl]
        if sel:
            L += ["## %s" % lvl, ""]
            for i in sel:
                L.append("- **%s** %s" % (i["code"], i["msg"]))
                L += ["  - %s" % e for e in i["examples"]]
            L.append("")
    if summary:
        L += ["## 各角色状态", "", "| 角色 | 状态计数 |", "|---|---|"] + ["| %s | %s |" % (k, "、".join("%s %d" % kv for kv in v.items())) for k, v in summary.items()] + [""]
    rep = "\n".join(L) + "\n"
    if "report" in outs:
        write_fresh(outs["report"], rep)
    if "json" in outs:
        write_fresh(outs["json"], json.dumps({"items": items, "open_gaps": open_gaps, "references": len(refs), "candidates": cands,
                                              "roles": {k: dict(v) for k, v in summary.items()}}, ensure_ascii=False, indent=1))
    print("coverage_check：MUST %d、SHOULD %d；参考文献 %d 条；未关闭缺口 %d。" % (must, sum(i["level"] == "SHOULD" for i in items), len(refs), open_gaps))
    if not outs:
        print(rep[:4000])
    return 1 if must else 0


if __name__ == "__main__":
    sys.exit(main())
