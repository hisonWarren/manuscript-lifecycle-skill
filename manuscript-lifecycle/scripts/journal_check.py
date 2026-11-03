#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
journal_check.py — 按目标刊规则档案检查稿件：标题、摘要、小标题、图注、表注、Highlights 等。

  python journal_check.py 稿件.md|docx --profile assets/journal_profiles/nature_article.json
         [--fragment] [--baseline assets/benchmarks/display_baseline.json] [--report out.md] [--json out.json]
  python journal_check.py --list                      # 列出随包的规则档案
  python journal_check.py --show 档案.json            # 打印该刊每条规则及其来源与核实状态

规则档案里每条规则都写明来源、访问日期和核实状态（verified 官方页面正文 / unverified 仅见于第三方）。
unverified 的规则一律只作候选（CAND），不判 FAIL：期刊规则会改版，数字不能靠记忆。
没有写进档案的项目不检查，也不虚构"期刊要求"。投稿前必须重新核对当期作者须知，并更新档案里的访问日期。

级别：FAIL 明确的硬要求未满足；CAND 需要人看一眼的候选；INFO 数值与参照。
退出码：0 无 FAIL；1 有 FAIL；2 输入或档案错误。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(os.path.dirname(HERE), "assets", "journal_profiles")

# 图注里"下结论"的词
INTERP_RX = re.compile(
    r"\b(?:suggest(?:s|ing)?|indicat(?:e|es|ing)|demonstrat(?:e|es|ing)|reveal(?:s|ing)?|highlight(?:s|ing)?"
    r"|underscor\w+|implies|implying|confirm(?:s|ing)?|prove[sd]?)\b|(?:表明|说明|提示|证实|揭示|意味着)", re.I)
# 描述读图编码的说法（"thicker lines indicate…"、"粗体表示…"）不是下结论
VISUAL_RX = re.compile(
    r"(?:lines?|bars?|dots?|points?|colou?rs?|shading|arrows?|symbols?|asterisks?|circles?|squares?|triangles?"
    r"|boxes|whiskers?|dashed|solid|bold|italic|widths?|sizes?|nodes?|edges?|shaded|error bars?|markers?)"
    r"[^.;]{0,30}$|(?:线|虚线|实线|颜色|柱|点|箭头|阴影|粗体|星号|误差条|图例)[^。；]{0,12}$", re.I)
METHOD_RX = re.compile(
    r"\b(?:bootstrap\w*|permutation\w*|EBICglasso|tuning|Spearman|Pearson|qgraph|bootnet|lavaan|Mplus|SPSS|Stata"
    r"|mixed[- ]effects|estimated (?:with|using)|fitted (?:with|using)|implemented in|software|version \d)\b"
    r"|(?:自助法|置换检验|估计采用|拟合采用|软件|版本\s*\d)", re.I)
ERRBAR_RX = re.compile(r"\b(?:error bars?|s\.?e\.?m|SEM|s\.?d\.?|SD|95%\s*(?:CI|confidence)|\bCI\b|IQR|whiskers?)\b"
                       r"|误差(?:条|棒)|标准误|标准差|置信区间", re.I)
N_RX = re.compile(r"\bn\s*=\s*\d|\bN\s*=\s*\d|样本量|人数|例数|[（(]\s*n\s*=", re.I)
NOTE_RX = re.compile(r"^\s*(?:\*\*)?\s*(?:Note[s]?\s*[.:：]|注\s*[:：]|Abbreviations?\s*[:：])", re.I)
SUMMARY_RX = re.compile(r"^\s*(?:\*\*)?\s*(?:One[- ]sentence summary|一句话(?:摘要|总结))\s*(?:\*\*)?\s*[:：]\s*(.+)$", re.I)
INBRIEF_RX = re.compile(r"^\s*(?:\*\*)?\s*(?:In Brief|eTOC(?: blurb)?)\s*(?:\*\*)?\s*[:：]\s*(.+)$", re.I)
HL_RX = re.compile(r"^\s*(?:\*\*)?\s*(?:Highlights?|研究亮点|亮点)\s*(?:\*\*)?\s*[:：]?\s*$", re.I)
BULLET_RX = re.compile(r"^\s*(?:[-*•·]|\d+[.)、])\s+(.*\S)\s*$")
DISPLAY_LED_RX = re.compile(
    r"^\s*(?:\*\*)?\s*(?:(?:As|as)\s+(?:is\s+)?(?:shown|presented|displayed|reported|summari[sz]ed|can be seen|illustrated)"
    r"|(?:Table|Tab\.|Fig\.?|Figure)\s*S?\d+[A-Za-z]?\s*(?:and|,|&)?\s*(?:Table|Fig\.?|Figure)?\s*S?\d*[A-Za-z]?\s*"
    r"(?:shows?|presents?|displays?|reports?|summari[sz]es?|lists?|gives?|provides?|illustrates?|indicates?)"
    r"|(?:如|见|详见|参见)?\s*(?:表|图)\s*\d+\s*(?:所示|显示|呈现|列出|给出|报告|表明|中)"
    r"|(?:如|见|详见|参见)\s*(?:表|图)\s*\d)", re.I)


def interp_hit(text):
    """返回第一个"下结论"的词；描述读图编码的"thicker lines indicate…"不算。"""
    for m in INTERP_RX.finditer(text):
        if VISUAL_RX.search(text[max(0, m.start() - 42):m.start()]):
            if re.match(r"(?:indicat(?:e|es|ing)|表示|代表)$", m.group(0), re.I) and not re.search(r"caus|efficacy|impair|treat|干预|导致", text[m.end():m.end()+80], re.I):
                continue
        return m.group(0)
    return ""


def load_profile(path):
    with open(path, encoding="utf-8-sig") as f:
        prof = json.load(f)
    if not isinstance(prof, dict) or prof.get("schema_version") != 1:
        raise ValueError("档案 schema_version 必须是 1")
    for key in ("id", "journal", "rules", "sources"):
        if key not in prof:
            raise ValueError("档案缺字段 %s" % key)
    if not isinstance(prof["rules"], list) or not isinstance(prof["sources"], list):
        raise ValueError("rules 和 sources 必须是数组")
    if any(not isinstance(x, dict) for x in prof["rules"] + prof["sources"]):
        raise ValueError("规则与来源必须是对象")
    sids = {s.get("id") for s in prof["sources"]}
    if None in sids or len(sids) != len(prof["sources"]):
        raise ValueError("来源 id 缺失或重复")
    known = {"title_chars", "abstract_words", "abstract_numbers", "abstract_citations", "main_words", "heading_chars", "legend_words", "note_words", "legend_no_methods", "legend_defines_stats", "legend_conclusion", "highlights", "one_sentence_summary", "in_brief_words", "results_display_led"}
    rule_ids = set()
    for r in prof["rules"]:
        if not r.get("check") or not r.get("id"):
            raise ValueError("规则缺 id 或 check")
        if r["id"] in rule_ids or r["check"] not in known:
            raise ValueError("重复规则 id 或不支持的检查项")
        rule_ids.add(r["id"])
        if r.get("level", "CAND") not in ("FAIL", "CAND", "INFO"):
            raise ValueError("规则 level 无效")
        numeric = {"title_chars", "abstract_words", "abstract_numbers", "main_words", "heading_chars", "legend_words", "note_words", "one_sentence_summary", "in_brief_words"}
        for key in (["max"] if r["check"] in numeric else ["max_n", "max_chars"] if r["check"] == "highlights" else []):
            val = r.get(key)
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not 0 < val < float("inf"):
                raise ValueError("规则数值限额必须是有限正数")
        if r.get("status") not in ("verified", "unverified"):
            raise ValueError("规则 %s 的 status 必须是 verified 或 unverified" % r["id"])
        if r.get("source") not in sids:
            raise ValueError("规则 %s 的 source 不在 sources 里" % r["id"])
    for s in prof["sources"]:
        if not s.get("accessed") or not s.get("url"):
            raise ValueError("来源 %s 必须写 url 与 accessed" % s.get("id"))
    return prof


def captions(blocks, raw):
    """返回 (图注, 表题, 注释)。图注与表题来自 caption 块；注释按行首的 Note/注 取。"""
    figs, tabs = [], []
    for b in blocks:
        if b["kind"] != "caption":
            continue
        t = re.sub(r"\s+", " ", b["text"]).strip()
        (figs if re.match(r"^\**\s*(?:Supplementary\s+)?(?:Fig|图)", t, re.I) else tabs).append(t)
    notes, lines = [], raw.split("\n")
    for i, l in enumerate(lines):
        if not NOTE_RX.match(l.strip()):
            continue
        buf = [l.strip()]
        j = i + 1
        while j < len(lines) and len(buf) < 8:
            n = lines[j].strip()
            if not n or M.CAPTION.match(n) or n.startswith("#") or n.startswith("|"):
                break
            buf.append(n)
            j += 1
        notes.append(re.sub(r"\s+", " ", " ".join(buf)))
    return figs, tabs, notes


def unit_count(text, lang):
    return len(M.CJK.findall(text)) + len(M.LAT.findall(text)) if lang == "zh" else M.count_words_ws(text)


def band(baseline, family, metric, value):
    d = ((baseline or {}).get(family) or {}).get(metric)
    if not d or not value:
        return ""
    where = "在范围内"
    if value > d.get("p90", 1e9):
        where = "高于 p90"
    elif value < d.get("p10", -1):
        where = "低于 p10"
    return "；同类实测 中位 %s、p10–p90 %s–%s、n=%s（%s）" % (d.get("median"), d.get("p10"), d.get("p90"), d.get("n"), where)


def run(path, prof, fragment, baseline):
    raw = M.load_text(path)
    if not raw.strip():
        raise ValueError("稿件为空，不能把零检查项记为通过")
    lang = prof.get("language") or M.detect_lang(raw)
    blocks = M.parse(raw)
    P = {}
    for b in blocks:
        if b["kind"] == "para":
            P.setdefault(b["sec"], []).append(b["text"])
    figs, tabs, notes = captions(blocks, raw)
    title = next((b["text"] for b in blocks if b["kind"] == "heading" and b.get("level") == 1),
                 next((l[2:].strip() for l in raw.split("\n") if l.startswith("# ")), ""))
    abstract = " ".join(P.get("abstract", []))
    body_secs = [s for s in ("introduction", "methods", "results", "discussion", "limitations", "conclusion") if s in P]
    main_words = sum(M.count_words_ws(t) for s in body_secs for t in P[s])
    heads = [b["text"] for b in blocks if b["kind"] == "heading" and (b.get("level") or 1) >= 2]
    bullets = []
    lines = raw.split("\n")
    for i, l in enumerate(lines):
        if HL_RX.match(re.sub(r"^\s*#{1,6}\s+", "", l)):
            for n in lines[i + 1:i + 20]:
                m = BULLET_RX.match(n)
                if m:
                    bullets.append(m.group(1))
                elif n.strip():
                    break
    one_sentence = next((m.group(1).strip() for l in lines for m in [SUMMARY_RX.match(l)] if m), "")
    in_brief = next((m.group(1).strip() for l in lines for m in [INBRIEF_RX.match(l)] if m), "")
    family = prof.get("display_family", "")

    out = []

    def rep(rule, level, msg, ex=""):
        if rule.get("status") == "unverified" and level == "FAIL":
            level = "CAND"
            msg += "（来源未核实，只作候选）"
        out.append({"rule": rule["id"], "check": rule["check"], "level": level, "msg": msg,
                    "example": ex[:200], "source": rule.get("source", ""), "status": rule.get("status")})

    for r in prof["rules"]:
        ck, mx = r["check"], r.get("max")
        if fragment and ck in ("abstract_words", "abstract_numbers", "abstract_citations", "main_words",
                               "heading_chars", "results_display_led"):
            continue
        if ck == "title_chars":
            if title and len(title) > mx:
                rep(r, r.get("level", "FAIL"), "标题 %d 字符，上限 %d。" % (len(title), mx), title)
        elif ck == "abstract_words":
            n = unit_count(abstract, lang)
            if not abstract:
                rep(r, "INFO", "没有识别到摘要，未检查上限 %d。" % mx)
            elif n > mx:
                rep(r, r.get("level", "FAIL"), "摘要 %d %s，上限 %d。" % (n, "字" if lang == "zh" else "词", mx))
            else:
                rep(r, "INFO", "摘要 %d / 上限 %d。" % (n, mx))
        elif ck == "abstract_numbers":
            n = M.count_numbers(abstract)
            if abstract and n > mx:
                rep(r, r.get("level", "CAND"), "摘要里有 %d 个数字（参照上限 %d）。只留承重数字，其余交给正文。" % (n, mx))
        elif ck == "abstract_citations":
            n = M.count_citations(abstract)
            if n:
                rep(r, r.get("level", "CAND"), "摘要里有 %d 处引用。" % n)
        elif ck == "main_words":
            if main_words > mx:
                rep(r, r.get("level", "FAIL"), "正文约 %d 词，上限 %d。" % (main_words, mx))
        elif ck == "heading_chars":
            bad = [h for h in heads if len(h) > mx]
            if bad:
                rep(r, r.get("level", "CAND"), "%d 个小标题超过 %d 字符。" % (len(bad), mx), bad[0])
        elif ck == "legend_words":
            for f in figs:
                n = unit_count(f, lang)
                if n > mx:
                    rep(r, r.get("level", "FAIL"), "图注 %d %s，上限 %d%s。" % (
                        n, "字" if lang == "zh" else "词", mx, band(baseline, family, "figure_legend", n)), f)
        elif ck == "note_words":
            for t in notes:
                n = unit_count(t, lang)
                if n > mx:
                    rep(r, r.get("level", "CAND"), "注释 %d %s（参照 %d）%s。先问读者只看这一图表能否读对，再决定删什么。" % (
                        n, "字" if lang == "zh" else "词", mx, band(baseline, family, "table_note", n)), t)
        elif ck == "legend_no_methods":
            if "methods" in P:
                for f in figs:
                    m = METHOD_RX.search(f)
                    if m:
                        rep(r, r.get("level", "CAND"), "图注里有方法细节（%s）。有方法节时方法写在方法节。" % m.group(0), f)
        elif ck == "legend_defines_stats":
            for f in figs:
                if ERRBAR_RX.search(f) and not re.search(r"(?:represent|show|are|denote|indicat|是|为|表示)", f, re.I):
                    rep(r, "CAND", "图注提到误差条或区间，但没有写明它代表什么。", f)
                if not N_RX.search(f) and re.search(r"\bmean|average|均值|平均", f, re.I):
                    rep(r, "CAND", "图注给了均值但没有写样本量。", f)
        elif ck == "legend_conclusion":
            for f in figs:
                w = interp_hit(f)
                if w:
                    rep(r, r.get("level", "CAND"), "图注下结论（%s）：图注说明怎样读图，含义放正文。" % w, f)
            for t in notes:
                w = interp_hit(t)
                if w:
                    rep(r, r.get("level", "CAND"), "表注下结论（%s）。" % w, t)
        elif ck == "highlights":
            if bullets:
                if r.get("max_n") and len(bullets) > r["max_n"]:
                    rep(r, r.get("level", "FAIL"), "Highlights %d 条，上限 %d。" % (len(bullets), r["max_n"]))
                long_ = [b for b in bullets if len(b) > (r.get("max_chars") or 10 ** 6)]
                if long_:
                    rep(r, r.get("level", "FAIL"), "%d 条 Highlights 超过 %d 字符（含空格）。不要靠删限定词来省字符。" % (
                        len(long_), r["max_chars"]), long_[0])
        elif ck == "one_sentence_summary":
            if one_sentence and len(one_sentence) > mx:
                rep(r, r.get("level", "FAIL"), "一句话摘要 %d 字符，上限 %d。" % (len(one_sentence), mx), one_sentence)
        elif ck == "in_brief_words":
            if in_brief and M.count_words_ws(in_brief) > mx:
                rep(r, r.get("level", "CAND"), "In Brief %d 词（参照 %d）。写想法，不复述信息。" % (M.count_words_ws(in_brief), mx))
        elif ck == "results_display_led":
            rp = P.get("results", [])
            led = [t for t in rp if DISPLAY_LED_RX.match(t)]
            if led:
                rep(r, r.get("level", "CAND"), "%d/%d 个结果段以“见表/如图/As shown in”起句。"
                    "考虑先写发现，再把表图放进括号；这是写作候选，不是期刊禁止项。" % (len(led), len(rp)), led[0])
        else:
            rep(r, "INFO", "未实现的检查项 %s，已跳过。" % ck)
    return {"profile": prof["id"], "journal": prof["journal"], "article_type": prof.get("article_type", ""),
            "lang": lang, "items": out, "counts": {"title_chars": len(title), "abstract": unit_count(abstract, lang),
                                                   "main_words": main_words, "figures": len(figs),
                                                   "tables": len(tabs), "notes": len(notes), "highlights": len(bullets)}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", default="")
    ap.add_argument("--profile", default="")
    ap.add_argument("--baseline", default="")
    ap.add_argument("--fragment", action="store_true", help="输入是片段（Highlights、投稿信、图注表注）")
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--list", action="store_true", help="列出随包的规则档案")
    ap.add_argument("--show", default="", help="打印某个档案的全部规则与来源")
    a = ap.parse_args()
    if a.list:
        if not os.path.isdir(PROFILE_DIR):
            print("没有 assets/journal_profiles 目录", file=sys.stderr)
            return 2
        for f in sorted(os.listdir(PROFILE_DIR)):
            if f.endswith(".json"):
                try:
                    p = load_profile(os.path.join(PROFILE_DIR, f))
                except (OSError, ValueError, json.JSONDecodeError) as e:
                    print("%-28s 档案有问题：%s" % (f, e))
                    continue
                print("%-28s %s %s｜规则 %d 条（已核实 %d）" % (
                    f, p["journal"], p.get("article_type", ""), len(p["rules"]),
                    sum(1 for r in p["rules"] if r["status"] == "verified")))
        return 0
    if a.show:
        try:
            p = load_profile(a.show)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            print("档案无法读取：%s" % e, file=sys.stderr)
            return 2
        print("# %s %s（%s）" % (p["journal"], p.get("article_type", ""), p["id"]))
        for s in p["sources"]:
            print("- 来源 %s：%s（%s，访问 %s）" % (s["id"], s["url"], s.get("access", ""), s["accessed"]))
        for r in p["rules"]:
            print("- %-22s %-20s %s %s｜%s" % (r["id"], r["check"], r.get("level", ""), r["status"], r.get("note", "")))
        return 0
    if not a.path or not a.profile:
        print("用法：journal_check.py 稿件 --profile 档案.json（或 --list / --show）", file=sys.stderr)
        return 2
    for p in (a.path, a.profile):
        if not os.path.exists(p):
            print("找不到 %s" % p, file=sys.stderr)
            return 2
    try:
        prof = load_profile(a.profile)
    except (ValueError, json.JSONDecodeError) as e:
        print("档案无法使用：%s" % e, file=sys.stderr)
        return 2
    baseline = None
    if a.baseline:
        if not os.path.exists(a.baseline):
            print("找不到 %s" % a.baseline, file=sys.stderr)
            return 2
        try:
            with open(a.baseline, encoding="utf-8-sig") as f:
                baseline = json.load(f).get("families", {})
            if not isinstance(baseline, dict):
                raise ValueError("families 必须是对象")
        except (OSError, ValueError, AttributeError) as e:
            print("基线无法使用：%s" % e, file=sys.stderr)
            return 2
    try:
        res = run(a.path, prof, a.fragment, baseline)
    except ValueError as e:
        print("not_verified：%s" % e, file=sys.stderr)
        return 2
    items = res["items"]
    nf = sum(i["level"] == "FAIL" for i in items)
    nc = sum(i["level"] == "CAND" for i in items)
    src = {s["id"]: s for s in prof["sources"]}
    L = ["# 期刊规则检查：%s（%s %s）\n" % (os.path.basename(a.path), res["journal"], res["article_type"]),
         "档案 %s；规则 %d 条（已核实 %d、未核实 %d）。FAIL %d、复读候选 %d。\n" % (
             prof["id"], len(prof["rules"]), sum(1 for r in prof["rules"] if r["status"] == "verified"),
             sum(1 for r in prof["rules"] if r["status"] == "unverified"), nf, nc),
         "计数：标题 %d 字符、摘要 %d、正文约 %d 词、图 %d、表 %d、注释 %d、Highlights %d。\n" % (
             res["counts"]["title_chars"], res["counts"]["abstract"], res["counts"]["main_words"],
             res["counts"]["figures"], res["counts"]["tables"], res["counts"]["notes"], res["counts"]["highlights"])]
    for i in items:
        L.append("- **%s %s**　%s" % (i["level"], i["rule"], i["msg"]))
        if i["example"]:
            L.append("  - %s" % i["example"])
    L.append("\n## 规则来源\n")
    for s in prof["sources"]:
        L.append("- %s：%s（%s，访问 %s）" % (s["id"], s["url"], s.get("access", ""), s["accessed"]))
    L.append("\n期刊规则会更新：投稿前以当期作者须知为准，并更新档案的访问日期。未写进档案的项目没有检查，"
             "不能据此说“全部符合期刊要求”。有理由的偏离写进决策登记即可保留。")
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    if a.json:
        with M.wfile(a.json) as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    print(out if not (a.report or a.json) else
          "FAIL %d、复读候选 %d。期刊规则会更新，投稿前以当期作者须知为准；候选可在写明理由后保留。" % (nf, nc))
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())
