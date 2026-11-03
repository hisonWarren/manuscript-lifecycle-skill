#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convention_profile.py — 表面惯例画像：把近邻全文里能测的写法惯例都测出来，与稿件对照，列出需要裁决的偏离（references/29 §4b）。

  python convention_profile.py --neighbors 近邻全文.md… --draft 稿件.md [--supplement 补充.md] [--titles survey_corpus.csv]
         [--term-groups "stimulus=biological motion|point-light;method=EEG|ERP"] [--min-share 0.25] [--report out.md] [--json out.json]

为什么要有它：对标决策表只列六个节职能维度时，题目怎么起、补充材料叫什么、局限写几段这类惯例没有外部尺子，执行者会退回范例或
检查器的默认写法（一次实测：两分句结论式长题目且不点名刺激与方法、领域里没人用的 “Supplementary Note”、带小标题的四段局限）。
这里不再逐项加维度：凡是能从近邻全文里测出来的惯例都测，稿件取值落在多数做法之外的，一律在 benchmark_decisions.csv 写
dimension=convention:<维度> 的行裁决（采用多数做法，或保留并写理由）。genre_gate CN1 核对裁决。

维度（近邻分布 / 稿件取值）：
  title_words  title_form（statement / question / noun_phrase）  title_subtitle  title_method（点名测量方法或成分）
  title_terms:<组>（--term-groups 给的术语组，如刺激类型）  supp_labels（补充材料在正文里的称呼族）
  limitations_heading  limitations_paras  discussion_subheads  abstract_structured
偏离规则：数值维度落在近邻范围之外；类别维度的稿件取值在近邻里占比 < --min-share；称呼族在用过补充称呼的近邻里占比 < --min-share。
近邻少于 3 个有效值的维度记 NA（不算偏离）。抽取是启发式的：网页或 PDF 转写的标题层级可能不全，报告写明哪些维度是 NA。

退出码：0 没有偏离；1 有偏离（要裁决，不等于错误）；2 输入错误。报告与 JSON 必须是新路径。
"""
import argparse, csv, json, os, re, sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
SKIP_TITLE = re.compile(r"^(permalink|abstract|contents|references|actions|resources|cite|author summary|supplementary)\b", re.I)
VERBS = (r"(?:is|are|was|were|lengthens?|shortens?|increases?|decreases?|influences?|affects?|modulates?|predicts?|shapes?|biases|warps?|"
         r"slows?|alters?|enhances?|reduces?|impairs?|drives?|reveals?|reflects?|depends?|differs?|leads?|changes?|distorts?|dilates?|"
         r"compresses?|carries|tracks?|encodes?|determines?|underlies|underlie|matters?|improves?|facilitates?|disrupts?|requires?|relies|emerges?)")
STATEMENT = re.compile(r"\b%s\b" % VERBS, re.I)
# 题目里“点名方法或测量”的默认词表跨学科（神经影像、实验、调查、临床、计量、计算、质性）。它只是默认值：
# 给了 --term-groups "method=…" 时，以用户为本领域写的词表为准，默认的 title_method 维度不再计算（第六轮：原表只有神经科学词）。
METHOD = re.compile(r"\b(?:EEG|ERPs?|MEG|fMRI|MRI|PET|electrophysiolog\w*|event[- ]related|potentials?|CNV|contingent negative variation|N1P2|N170|P300|LPP|LPCt?|"
                    r"oscillat\w*|neural|cortical|brain|neuroimaging|eye[- ]tracking|pupil\w*|TMS|tDCS|"
                    r"randomi[sz]ed|RCT|trial|cohort|cross[- ]sectional|longitudinal|survey|questionnaire|interviews?|qualitative|ethnograph\w*|"
                    r"meta[- ]analy\w*|systematic review|panel data|regression|difference[- ]in[- ]differences|instrumental variables?|"
                    r"simulation|computational model\w*|machine learning|deep learning|neural networks?|mendelian randomi[sz]ation|"
                    r"single[- ]cell|RNA[- ]seq|sequencing|spectroscop\w*|microscop\w*)\b"
                    r"|脑电|事件相关电位|功能磁共振|眼动|随机对照|队列|横断面|纵向|问卷|访谈|质性|元分析|面板数据|双重差分|工具变量|仿真|模拟|机器学习|深度学习|单细胞|测序", re.I)
CJK = re.compile(r"[\u4e00-\u9fff]")
SUPP_FAMILIES = [
    ("Supplementary Note", r"\bSupplementary\s+Notes?\b"),
    ("Supplementary Section/Text", r"\bSupplementary\s+(?:Sections?|Text|Methods)\b"),
    ("Supplementary Material(s)", r"\b[Ss]upplementary\s+[Mm]aterials?\b"),
    ("Supplementary/Supporting Information", r"\b[Ss]upplementary\s+[Ii]nformation\b|\bSupporting\s+Information\b"),
    ("Supplementary Table/Figure n", r"\bSupplementary\s+(?:Tables?|Fig(?:ure)?s?\.?)\s*S?\d"),
    ("Table S#/Fig. S#", r"\b(?:Tables?|Fig(?:ure)?s?\.?)\s*S\d+"),
    ("S# Table/Fig (PLOS)", r"\bS\d+\s+(?:Table|Fig|File|Text|Appendix|Data)\b"),
    ("Appendix", r"\bAppendix\s+(?:[A-Z]\b|S?\d)"),
    ("Extended Data", r"\bExtended\s+Data\s+(?:Fig|Table)"),
    ("figure supplement (eLife)", r"\bfigure\s+supplement\s+\d"),
    ("Supplementary data/file", r"\b[Ss]upplementary\s+(?:data|file\s*\d*)\b"),
]
STRUCT_ABS = re.compile(r"(?:^|\n|\.\s)\s*(?:\*\*)?(Background|Objectives?|Aims?|Purpose|Methods?|Results?|Conclusions?|Significance)(?:\*\*)?\s*[:：]", re.I)
LIMIT_WORD = re.compile(r"\blimitations?\b|\blimited by\b|\bcaveats?\b|局限|不足", re.I)
DISC = r"^(?:\d+(?:\.\d+)*\.?\s*)?(?:general\s+)?discussion\b|^results and discussion\b|^讨论"
REFS = re.compile(r"^(?:references|bibliography|literature cited|参考文献)\b", re.I)


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().replace("\r\n", "\n")


def headings(text):
    out = []
    for i, line in enumerate(text.split("\n")):
        m = HEAD.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2).strip().strip("*").strip()))
    return out


def title_of(text):
    for _, lvl, h in headings(text):
        if lvl == 1 and len(h) > 15 and not SKIP_TITLE.match(h):
            return h
    return ""


def paragraphs(lines):
    paras, cur = [], []
    for l in lines:
        if not l.strip() or HEAD.match(l) or l.lstrip().startswith(("|", "[", "!", "- ", "* ")):
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        cur.append(l.strip())
    if cur:
        paras.append(" ".join(cur))
    return [p for p in paras if len(p) >= 60 and not re.match(r"^\**(?:fig(?:ure)?\.?|table)\s*\d", p, re.I)]


def section(text, pat):
    lines, hs = text.split("\n"), headings(text)
    for idx, (i, lvl, h) in enumerate(hs):
        if re.search(pat, h, re.I):
            end = len(lines)
            for (j, l2, _h2) in hs[idx + 1:]:
                if l2 <= lvl:
                    end = j
                    break
            return lvl, lines[i + 1:end], [(j, l2, h2) for (j, l2, h2) in hs[idx + 1:] if j < end]
    return None


def body_before_refs(text):
    lines = text.split("\n")
    for (i, _l, h) in headings(text):
        if REFS.match(h):
            return "\n".join(lines[:i])
    return text


NOUN_NEXT = {"of", "on", "in", "for", "from", "between", "and", "to", "across", "within", "during", "among", "after", "before"}


def is_statement(t):
    """含限定动词的陈述式题目。复数名词后接介词（influences on、changes in、signals of）不算动词。"""
    if re.match(r"^(how|what|why|when|does|do|is|are|can)\b", t.strip(), re.I):
        return False
    for m in STATEMENT.finditer(t):
        nxt = re.match(r"\s+([A-Za-z]+)", t[m.end():])
        if m.group(0).lower().endswith("s") and nxt and nxt.group(1).lower() in NOUN_NEXT:
            continue
        return True
    return False


def title_features(t, groups):
    # 中文题目按汉字计长度（同一语言的近邻之间可比）；英文按词
    f = {"title_words": len(CJK.findall(t)) if len(CJK.findall(t)) > 4 else len(re.findall(r"[A-Za-z][\w'’\-]*", t)),
         "title_form": "question" if t.strip().endswith("?") else ("statement" if is_statement(t) else "noun_phrase"),
         "title_subtitle": bool(re.search(r":|—|–| - ", t)),
         "title_method": bool(METHOD.search(t))}
    for name, rx in groups.items():
        f["title_terms:" + name] = bool(rx.search(t))
    return f


def doc_features(text):
    f = {}
    body = body_before_refs(text)
    f["supp_labels"] = sorted(n for n, rx in SUPP_FAMILIES if re.search(rx, body))
    lim = None
    for idx, (i, lvl, h) in enumerate(headings(text)):
        if re.search(r"\blimitations?\b|局限", h, re.I):
            lines, end = text.split("\n"), len(text.split("\n"))
            for (j, l2, _h2) in headings(text)[idx + 1:]:
                if l2 <= lvl:
                    end = j
                    break
            lim = (True, len(paragraphs(lines[i + 1:end])))
            break
    d = section(text, DISC)
    if lim is None:
        lim = (False, sum(1 for p in paragraphs(d[1]) if LIMIT_WORD.search(p))) if d else (None, None)
    f["limitations_heading"], f["limitations_paras"] = lim
    f["discussion_subheads"] = (sum(1 for (_j, _l, h) in d[2] if not re.match(r"(?:fig(?:ure)?\.?|table)\s*\d", h, re.I)) if d else None)
    a = section(text, r"^abstract\b|^摘要")
    f["abstract_structured"] = (len({m.group(1).lower()[:6] for m in STRUCT_ABS.finditer("\n".join(a[1]))}) >= 2) if a else None
    return f


def parse_groups(s):
    out = {}
    for part in (s or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = re.compile(r"\b(?:%s)\b" % "|".join(x.strip() for x in v.split("|") if x.strip()), re.I)
    return out


def profile(neighbor_paths, draft_path, supplement=None, titles_csv=None, term_groups="", min_share=0.25):
    groups = parse_groups(term_groups)
    nb_docs = [read(p) for p in neighbor_paths]
    titles, seen, matched = [], set(), set()
    rows = list(csv.DictReader(open(titles_csv, encoding="utf-8-sig"))) if titles_csv else []
    for r in rows:
        if (r.get("type_match") or "").strip().lower().startswith(("yes", "y", "是")):
            matched.add(re.sub(r"\W", "", (r.get("title") or "").lower()))
    for t in [r.get("title", "") for r in rows] + [title_of(x) for x in nb_docs]:
        k = re.sub(r"\W", "", (t or "").lower())
        if t and k not in seen:
            seen.add(k)
            titles.append(t)
    # 惯例按论文类型而异：调研表标了类型匹配且不少于 5 篇时，题目维度以类型匹配的论文为参照（同时报告全部）
    tm_titles = [t for t in titles if re.sub(r"\W", "", t.lower()) in matched]
    ref_titles = tm_titles if len(tm_titles) >= 5 else titles
    draft = read(draft_path) + ("\n" + read(supplement) if supplement and os.path.exists(supplement) else "")
    dtitle = title_of(read(draft_path))
    nb_t = [title_features(t, groups) for t in ref_titles]
    all_t = [title_features(t, groups) for t in titles]
    nb_d = [doc_features(x) for x in nb_docs]
    d_t, d_d = title_features(dtitle, groups), doc_features(draft)
    dims, devs, na = {}, [], []

    def numeric(name, vals, dv):
        vals = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(vals) < 3 or dv is None:
            na.append(name)
            return
        lo, hi = min(vals), max(vals)
        med = sorted(vals)[len(vals) // 2]
        dims[name] = {"draft": dv, "min": lo, "median": med, "max": hi, "n": len(vals)}
        if dv < lo or dv > hi:
            devs.append({"dim": name, "draft": dv, "reference": "%s–%s（中位 %s，n=%d）" % (lo, hi, med, len(vals)),
                         "msg": "稿件取值 %s 落在近邻范围 %s–%s 之外" % (dv, lo, hi)})

    def categorical(name, vals, dv):
        vals = [v for v in vals if v is not None]
        if len(vals) < 3 or dv is None:
            na.append(name)
            return
        from collections import Counter
        c = Counter(vals)
        share = c.get(dv, 0) / len(vals)
        dims[name] = {"draft": dv, "distribution": {str(k): v for k, v in c.items()}, "n": len(vals), "draft_share": round(share, 2)}
        if share < min_share:
            maj = c.most_common(1)[0][0]
            devs.append({"dim": name, "draft": dv, "reference": "%s（%d/%d）" % (maj, c[maj], len(vals)),
                         "msg": "稿件取值 %s 只占近邻 %d/%d；多数做法是 %s" % (dv, c.get(dv, 0), len(vals), maj)})

    numeric("title_words", [x["title_words"] for x in nb_t], d_t["title_words"] if dtitle else None)
    base_dims = ["title_form", "title_subtitle"] + ([] if "method" in groups else ["title_method"])
    for k in base_dims + ["title_terms:" + g for g in groups]:
        categorical(k, [x[k] for x in nb_t], d_t[k] if dtitle else None)
    users = [x["supp_labels"] for x in nb_d if x["supp_labels"]]
    if len(users) >= 2 and d_d["supp_labels"]:
        from collections import Counter
        c = Counter(f for u in users for f in u)
        dims["supp_labels"] = {"draft": d_d["supp_labels"], "neighbors_using_any": len(users), "families": dict(c)}
        for fam in d_d["supp_labels"]:
            if c.get(fam, 0) / len(users) < min_share:
                maj = ", ".join(f for f, _ in c.most_common(2))
                devs.append({"dim": "supp_labels", "draft": fam, "reference": maj,
                             "msg": "补充材料称呼“%s”只在 %d/%d 篇用过补充称呼的近邻里出现；常见的是 %s" % (fam, c.get(fam, 0), len(users), maj)})
    else:
        na.append("supp_labels")
    categorical("limitations_heading", [x["limitations_heading"] for x in nb_d], d_d["limitations_heading"])
    numeric("limitations_paras", [x["limitations_paras"] for x in nb_d], d_d["limitations_paras"])
    numeric("discussion_subheads", [x["discussion_subheads"] for x in nb_d], d_d["discussion_subheads"])
    categorical("abstract_structured", [x["abstract_structured"] for x in nb_d], d_d["abstract_structured"])
    if ref_titles is not titles:
        from collections import Counter
        dims["title_reference_all"] = {"draft": "—", "distribution": {k: dict(Counter(str(x[k]) for x in all_t)) for k in ("title_form", "title_method")}, "n": len(all_t)}
    return {"schema_version": 1, "draft_title": dtitle, "n_titles": len(ref_titles), "title_reference": "type_matched" if ref_titles is not titles else "all", "n_neighbor_texts": len(nb_docs),
            "dims": dims, "deviations": devs, "na": na, "min_share": min_share}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--neighbors", nargs="+", required=True)
    ap.add_argument("--draft", required=True)
    ap.add_argument("--supplement", default="")
    ap.add_argument("--titles", default="", help="survey_corpus.csv：用其中 title 列扩大题目参照集")
    ap.add_argument("--term-groups", default="")
    ap.add_argument("--min-share", type=float, default=0.25)
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    for p in a.neighbors + [a.draft] + ([a.titles] if a.titles else []):
        if not os.path.exists(p):
            print("找不到 %s" % p, file=sys.stderr)
            return 2
    for p in (a.report, a.json):
        if p and os.path.exists(p):
            print("输出文件已存在：%s" % p, file=sys.stderr)
            return 2
    res = profile(a.neighbors, a.draft, a.supplement or None, a.titles or None, a.term_groups, a.min_share)
    L = ["# 表面惯例画像（convention_profile）", "", "稿件题目：%s" % (res["draft_title"] or "（没找到一级标题）"),
         "题目参照 %d 个（%s）；近邻全文 %d 篇；占比阈值 %.2f。" % (res["n_titles"], "类型匹配" if res.get("title_reference") == "type_matched" else "全部", res["n_neighbor_texts"], res["min_share"]), "",
         "| 维度 | 稿件 | 近邻 |", "|---|---|---|"]
    for k, v in res["dims"].items():
        ref = v.get("distribution") or v.get("families") or "%s–%s（中位 %s）" % (v.get("min"), v.get("max"), v.get("median"))
        L.append("| %s | %s | %s |" % (k, v["draft"], ref))
    L += ["", "## 需要裁决的偏离（benchmark_decisions.csv 写 dimension=convention:<维度>）", ""]
    L += ["- **%s**：%s" % (d["dim"], d["msg"]) for d in res["deviations"]] or ["没有。"]
    if res["na"]:
        L += ["", "没能测（近邻有效值不足 3 个或稿件缺该部分）：%s。不算偏离，也不算通过。" % "、".join(res["na"])]
    L += ["", "偏离不等于错误：目标刊另有规定或有充分理由时可以保留，但要写下来。画像只测表面惯例，不判断内容。"]
    out = "\n".join(L) + "\n"
    if a.report:
        open(a.report, "w", encoding="utf-8").write(out)
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(out if not a.report else "偏离 %d 项；报告 %s" % (len(res["deviations"]), a.report))
    return 1 if res["deviations"] else 0


if __name__ == "__main__":
    sys.exit(main())
