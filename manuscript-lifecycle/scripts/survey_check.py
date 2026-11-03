#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
survey_check.py — 同类调研：看过的同类论文够不够广、够不够深，有没有读出“作者为什么只呈现这些”（references/29 §4）。

  python survey_check.py survey_corpus.csv [--synthesis survey_synthesis.md] [--stage draft|submission]
         [--min-screen 20] [--min-full 6] [--min-matched 4] [--min-axes 3] [--scope survey_scope.json] [--norms-out norms.json]
         [--report out.md] [--json out.json]

survey_corpus.csv 每篇一行，列：id, doi_or_url, title, year, journal, axes, type_match, access, coded, n_main_analyses,
n_main_displays, n_supp_items, exploratory_handling, omitted_but_possible, why_only_these, locator。
axes 取 topic / field / method / analysis / framing / journal / flagship，可多个，用 | 分隔；也认中文写法
（主题、领域、方法、分析、背景、目标刊、旗舰）。type_match 以 yes/是 开头算类型匹配；coded=yes 表示做了选材编码。

为什么要有它：只读三篇近邻、只看开头和收尾的句子，学到的是措辞；选材（呈现哪些分析、多少、放在哪里、为什么不放别的）
要从足够多、多维相似的同类论文里看出来。一次实测中，执行者在读任何同类论文之前就把项目里做过的分析全部分进了主文和补充。

规则（submission 为 MUST；draft 时 SV1–SV3、SV7 为 SHOULD）：
  SV0 MUST  表为空或缺列。
  SV1       筛选篇数少于 --min-screen。
  SV2       相似维度少于 --min-axes。
  SV3       全文编码少于 --min-full，或其中类型匹配的少于 --min-matched。
  SV4 MUST  编码行缺选材字段：主文分析数与补充项数（数字）、why_only_these（推断作者为什么只呈现这些）、omitted_but_possible。
  SV5 MUST  why_only_these 在不同论文之间雷同：是模板，不是读出来的。
  SV6 MUST  没读到全文（access 不是 fulltext）却编码了选材。
  SV7       survey_synthesis.md 缺失或有节没填（1 同类论文通常呈现什么；2 为什么只呈现这些；3 审稿人常问什么；4 对本稿的含义）。
  SV8 MUST  --scope 改了默认规模却没写理由，或低于最低限度（筛选 5、全文编码 2、类型匹配 2、维度 2）。
调研规模按领域与模式可调：survey_scope.json 写 min_screen、min_full、min_matched、min_axes 与 reason（references/29 §10）。
norms：类型匹配的全文编码论文中，主文分析数、主文图表数、补充项数的最小值、中位数、最大值（genre_gate PB1 用）。

退出码：0 没有 MUST；1 有 MUST；2 输入错误。输出文件已存在时拒绝写入。
它只核对广度与填写，不判断选的论文对不对、推断准不准；后者靠站点质检员与选材审稿人（agents/reviewer_selection.md）。
"""
import argparse
import csv
import json
import os
import re
import statistics
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

COLS = ["id", "doi_or_url", "title", "year", "journal", "axes", "type_match", "access", "coded", "n_main_analyses",
        "n_main_displays", "n_supp_items", "exploratory_handling", "omitted_but_possible", "why_only_these", "locator"]
AXES = {"topic": "topic", "主题": "topic", "同主题": "topic", "field": "field", "领域": "field", "同领域": "field",
        "method": "method", "方法": "method", "同方法": "method", "analysis": "analysis", "分析": "analysis", "同分析": "analysis",
        "framing": "framing", "背景": "framing", "理论": "framing", "同背景": "framing", "journal": "journal", "目标刊": "journal",
        "同刊": "journal", "flagship": "flagship", "旗舰": "flagship", "旗舰刊": "flagship"}
YES = ("yes", "y", "是", "true", "1")
DEFAULTS = {"min_screen": 20, "min_full": 6, "min_matched": 4, "min_axes": 3}
FLOORS = {"min_screen": 5, "min_full": 2, "min_matched": 2, "min_axes": 2}
SYN_SECS = {"1": "同类论文通常呈现什么", "2": "他们为什么只呈现这些", "3": "审稿人在这类论文上常问什么", "4": "对本稿的含义（材料预算）"}


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def _int(v):
    try:
        x = int(float(v))
        return x if x >= 0 else None
    except (TypeError, ValueError):
        return None


def _width(s):
    return sum(2 if "\u4e00" <= ch <= "\u9fff" else 1 for ch in s if not ch.isspace())


def axes_of(r):
    out = set()
    for part in re.split(r"[|;,，；/、]", r.get("axes", "")):
        k = part.strip().lower()
        if k in AXES:
            out.add(AXES[k])
    return out


def matched(r):
    return r.get("type_match", "").strip().lower().startswith(("yes", "是", "y"))


def coded(r):
    return r.get("coded", "").strip().lower() in YES


def fulltext(r):
    return r.get("access", "").strip().lower() == "fulltext"


def synthesis_gaps(path):
    """返回没填的节号；文件不存在返回 None。"""
    if not path or not os.path.exists(path):
        return None
    secs, cur = {}, None
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            m = re.match(r"^#{2,3}\s*(\d+)", line)
            if m:
                cur = m.group(1)
                secs[cur] = []
                continue
            if cur is not None:
                secs[cur].append(line.rstrip("\n"))
    gaps = []
    for k in SYN_SECS:
        body = [l for l in secs.get(k, []) if l.strip() and "填写" not in l and not re.match(r"^\s*[（(].*[)）]\s*$", l.strip())]
        if _width("".join(body)) < 24:
            gaps.append(k)
    return gaps


def norms(rows):
    use = [r for r in rows if coded(r) and fulltext(r) and matched(r)]
    out = {"n_papers": len(use)}
    for k in ("n_main_analyses", "n_main_displays", "n_supp_items"):
        vals = [v for v in (_int(r.get(k)) for r in use) if v is not None]
        if vals:
            out[k] = {"min": min(vals), "median": statistics.median(vals), "max": max(vals), "n": len(vals)}
    return out


def evaluate(rows, synthesis="", stage="submission", min_screen=20, min_full=6, min_matched=4, min_axes=3, scope=None):
    """返回 (items, metrics, norms)。items 每项 {level, code, msg, examples}。scope：survey_scope.json 的内容（可选）。"""
    items = []
    hard = "MUST" if stage == "submission" else "SHOULD"

    def add(level, code, msg, ex=()):
        items.append({"level": level, "code": code, "msg": msg, "examples": [str(e)[:200] for e in ex][:6]})
    params = {"min_screen": min_screen, "min_full": min_full, "min_matched": min_matched, "min_axes": min_axes}
    if scope:
        changed = []
        for k in DEFAULTS:
            if k in scope:
                try:
                    v = int(scope[k])
                except (TypeError, ValueError):
                    add("MUST", "SV8", "survey_scope.json 的 %s 不是整数：%s。" % (k, scope[k]))
                    continue
                if v != DEFAULTS[k]:
                    changed.append("%s=%d（默认 %d）" % (k, v, DEFAULTS[k]))
                params[k] = v
        if changed and _width(str(scope.get("reason", ""))) < 20:
            add("MUST", "SV8", "调整了调研规模（%s）却没写理由。写清为什么这个领域或这个模式可以少看：同类论文本来就少、只做投稿前复核……" % "、".join(changed))
        below = ["%s=%d（最低 %d）" % (k, params[k], FLOORS[k]) for k in FLOORS if params[k] < FLOORS[k]]
        if below:
            add("MUST", "SV8", "调研规模低于最低限度：%s。再少就看不出同类论文怎样取舍。" % "、".join(below))
    min_screen, min_full, min_matched, min_axes = params["min_screen"], params["min_full"], params["min_matched"], params["min_axes"]
    if not rows or any(c not in rows[0] for c in COLS):
        miss = [c for c in COLS if not rows or c not in rows[0]]
        add("MUST", "SV0", "survey_corpus.csv 为空或缺列：%s。模板在 assets/templates/survey_corpus.csv。" % ("、".join(miss) or "没有行"))
        return items, {"screened": len(rows)}, {}
    axes = set()
    for r in rows:
        axes |= axes_of(r)
    cod = [r for r in rows if coded(r)]
    full = [r for r in cod if fulltext(r)]
    full_m = [r for r in full if matched(r)]
    metrics = {"screened": len(rows), "axes": sorted(axes), "coded": len(cod), "coded_fulltext": len(full), "coded_fulltext_matched": len(full_m)}
    if len(rows) < min_screen:
        add(hard, "SV1", "只筛选了 %d 篇同类论文（默认不少于 %d）。按主题、领域、方法、分析、背景、目标刊、旗舰刊分别检索，读题目与摘要并记录类型是否匹配（references/29 §4）。" % (len(rows), min_screen))
    if len(axes) < min_axes:
        add(hard, "SV2", "相似维度只覆盖了 %d 个（%s；默认不少于 %d）。只按一个维度找到的论文，学不到这一类论文通常怎样取舍。" % (len(axes), "、".join(sorted(axes)) or "无", min_axes))
    if len(full) < min_full or len(full_m) < min_matched:
        add(hard, "SV3", "全文编码 %d 篇、其中类型匹配 %d 篇（默认分别不少于 %d、%d）。选材惯例要从全文里读：主文放了哪些分析、补充放了什么、没放什么。" % (len(full), len(full_m), min_full, min_matched))
    thin = []
    for r in cod:
        lack = []
        if _int(r.get("n_main_analyses")) is None:
            lack.append("主文分析数")
        if _int(r.get("n_supp_items")) is None:
            lack.append("补充项数")
        if _width(r.get("why_only_these", "")) < 20:
            lack.append("why_only_these")
        if _width(r.get("omitted_but_possible", "")) < 6:
            lack.append("omitted_but_possible")
        if lack:
            thin.append("%s（缺 %s）" % (r.get("id") or r.get("title")[:30], "、".join(lack)))
    if thin:
        add("MUST", "SV4", "%d 篇编码缺选材字段。主文分析数、补充项数写数字；why_only_these 写作者为什么只呈现这些（他们的主张需要什么、不需要什么）；omitted_but_possible 写能推断出做过却没报告的。" % len(thin), thin)
    seen = {}
    for r in cod:
        key = re.sub(r"[\W_]+", "", r.get("why_only_these", "").lower())
        if len(key) >= 8:
            seen.setdefault(key, []).append(r.get("id") or r.get("title")[:30])
    dup = [v for v in seen.values() if len(v) >= 2]
    if dup:
        add("MUST", "SV5", "“为什么只呈现这些”在不同论文之间雷同：%s。每篇的取舍理由不同，雷同说明没读。" % "；".join("、".join(v) for v in dup[:4]))
    nofull = [r.get("id") or r.get("title")[:30] for r in cod if not fulltext(r)]
    if nofull:
        add("MUST", "SV6", "这些论文没读到全文却编码了选材：%s。只读到摘要的只能用于筛选，不能推断作者怎样取舍。" % "、".join(nofull[:8]))
    gaps = synthesis_gaps(synthesis)
    if gaps is None:
        add(hard, "SV7", "没有 survey_synthesis.md：同类论文通常呈现什么、为什么只呈现这些、审稿人常问什么、对本稿的含义，四件事没有写下来。")
    elif gaps:
        add(hard, "SV7", "survey_synthesis.md 第 %s 节没填（%s）。" % ("、".join(gaps), "；".join(SYN_SECS[g] for g in gaps)))
    return items, metrics, norms(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus")
    ap.add_argument("--synthesis", default="")
    ap.add_argument("--stage", default="draft", choices=["draft", "submission"])
    ap.add_argument("--min-screen", type=int, default=20)
    ap.add_argument("--min-full", type=int, default=6)
    ap.add_argument("--min-matched", type=int, default=4)
    ap.add_argument("--min-axes", type=int, default=3)
    ap.add_argument("--scope", default="")
    ap.add_argument("--norms-out", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    for p in [a.corpus] + [x for x in (a.synthesis, a.scope) if x]:
        if not os.path.isfile(p):
            print("找不到输入：%s" % p, file=sys.stderr)
            return 2
    for p in (a.norms_out, a.report, a.json):
        if p and os.path.exists(p):
            print("输出文件已存在，换一个新路径：%s" % p, file=sys.stderr)
            return 2
    try:
        rows = read_rows(a.corpus)
    except (csv.Error, UnicodeDecodeError) as e:
        print("读不了调研表：%s" % e, file=sys.stderr)
        return 2
    scope = None
    if a.scope:
        try:
            with open(a.scope, encoding="utf-8-sig") as f:
                scope = json.load(f)
        except ValueError as e:
            print("survey_scope.json 不是合法 JSON：%s" % e, file=sys.stderr)
            return 2
    items, metrics, nm = evaluate(rows, a.synthesis, a.stage, a.min_screen, a.min_full, a.min_matched, a.min_axes, scope=scope)
    n_must = sum(i["level"] == "MUST" for i in items)
    L = ["# 同类调研（survey_check）：%s" % os.path.basename(a.corpus), "",
         "阶段 %s；筛选 %d 篇；维度 %s；全文编码 %s 篇（类型匹配 %s）；MUST %d、SHOULD %d。" % (
             a.stage, metrics.get("screened", 0), "、".join(metrics.get("axes", [])) or "无", metrics.get("coded_fulltext", 0),
             metrics.get("coded_fulltext_matched", 0), n_must, sum(i["level"] == "SHOULD" for i in items)), ""]
    for lvl in ("MUST", "SHOULD"):
        sel = [i for i in items if i["level"] == lvl]
        if sel:
            L += ["## " + lvl, ""]
            for i in sel:
                L.append("- **%s %s** %s" % (lvl, i["code"], i["msg"]))
                L += ["  - " + e for e in i["examples"]]
            L.append("")
    L += ["## 同类论文的材料范围（类型匹配的全文编码论文）", ""]
    if nm.get("n_papers"):
        for k, label in (("n_main_analyses", "主文分析数"), ("n_main_displays", "主文图表数"), ("n_supp_items", "补充项数")):
            if k in nm:
                L.append("- %s：%s–%s，中位数 %s（%d 篇）" % (label, nm[k]["min"], nm[k]["max"], nm[k]["median"], nm[k]["n"]))
    else:
        L.append("- 没有可用的编码论文，算不出范围。")
    L += ["", "通过只说明调研够广、编码填了；选的论文对不对、推断准不准，要人看。", ""]
    res = {"schema_version": 1, "corpus": os.path.basename(a.corpus), "stage": a.stage, "must": n_must,
           "should": sum(i["level"] == "SHOULD" for i in items), "items": items, "metrics": metrics, "norms": nm}
    if a.report:
        with open(a.report, "x", encoding="utf-8") as f:
            f.write("\n".join(L))
    if a.json:
        with open(a.json, "x", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    if a.norms_out:
        with open(a.norms_out, "x", encoding="utf-8") as f:
            json.dump(nm, f, ensure_ascii=False, indent=1)
    print("\n".join(L) if not a.report else L[2])
    return 1 if n_must else 0


if __name__ == "__main__":
    sys.exit(main())
