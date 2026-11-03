#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bench_profile.py — 分节分布对标：稿件各节的用法，落在同类文献分布的什么位置。

  python bench_profile.py --exemplars 对标目录/ 或 文件... --draft 现稿=ms.md [--draft 旧稿=old.md]
         [--lexicon 领域词表.json] [--report bench.md] [--csv per_paper.csv] [--json bench.json] [--lang auto|en|zh]

读法（报告页首也写）：
  · 数字是诊断，不是写作目标。偏离只说明"该看一眼"，改不改看句子承担的功能。要改的是原因：把内容移到该去的节、
    删掉自造标签、拆开塞了三个判断的句子。不要改指标本身——用同义词把术语"换"低，就是换词造假。
  · 只与同体裁、同类研究比。对标 <10 篇只看是否超出范围，10–19 篇看 p10–p90，≥20 篇看 p05–p95。
  · 先看语料质量提示（缺节、剔除句子、疑似重复），再看结论。PDF 转写的表格残留会抬高词数、数字与句长。
  · --json 的输出可交给 section_lint.py --bench，用对标分布校准它的阈值。
退出码：0 报告已写出（偏离不是失败）；2 输入错误。
"""
import argparse, csv, glob, hashlib, json, os, re, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

SECS = ["abstract", "introduction", "methods", "results", "discussion_all", "limitations", "conclusion"]
SEC_ZH = {"abstract": "摘要", "introduction": "引言", "methods": "方法", "results": "结果",
          "discussion_all": "讨论(含局限)", "limitations": "局限小节", "conclusion": "结论"}
BODY = ("introduction", "methods", "results", "discussion_all", "conclusion")
# (键, 名称, 只在这些节报告(None=全部), 用于定位句子的特征)
METRICS = [
    ("words", "词数", None, None), ("share_body", "占正文比例", None, None),
    ("sent_mean", "平均句长", None, "len"), ("sent_p90", "句长90分位", None, None), ("long_share", "长句占比", None, "len"),
    ("para_cv", "段长变异系数", None, None),
    ("numbers_per100", "数字/百词", None, "numbers"), ("cites_per100", "引文/百词", None, "cites"),
    ("stat_terms_per100", "通用统计词/百词", None, "stat_terms"), ("domain_terms_per100", "领域术语/百词", None, "domain_terms"),
    ("parens_per100", "括号/百词", None, "parens"),
    ("we_per1000", "第一人称/千词", None, "first_person"), ("we_initial_share", "We开头句占比", None, "we_initial"),
    ("connectives_per1000", "连接词/千词", None, "connectives"), ("hedges_per1000", "限定语/千词", None, "hedges"),
    ("boosters_per1000", "强化语/千词", None, "boosters"),
    ("dashes_per1000", "破折号/千词", None, "dashes"), ("colons_per1000", "冒号/千词", None, "colons"),
    ("semicolons_per1000", "分号/千词", None, "semicolons"),
    ("rather_than_per1000", "rather than/而非 每千词", None, "rather_than"), ("contrast_neg_per1000", "否定对照句式/千词", None, "contrast_neg"),
    ("backref_per1000", "回指路标/千词", None, "backref"), ("section_xref_per1000", "编号节回指/千词", None, "section_xref"),
    ("ai_marker_per1000", "词表风格标记/千词", None, "ai_marker"), ("ai_common_per1000", "高频风格词/千词", None, "ai_common"),
    ("template_per1000", "模板短语/千词", None, "template"), ("defensive_per1000", "防御句式/千词", None, "defensive"),
    ("coinage_per1000", "自造标签/千词", None, "coinage"),
    ("negation_share", "含否定句占比", None, "negation"),
    ("para_final_neg_share", "段末否定句占比", ("discussion_all", "limitations"), None),
    ("interpretive_share", "解释性句占比", ("results", "discussion_all"), "interpretive"),
    ("table_led_share", "以表图开段占比", ("results",), None),
    ("jinxing_per1000", "\"进行\"/千字", None, "jinxing"), ("de_per100", "\"的\"/百字", None, "de"),
]
TEXTURE = {"ai_marker_per1000", "template_per1000", "defensive_per1000", "coinage_per1000", "rather_than_per1000",
           "dashes_per1000", "colons_per1000", "backref_per1000", "section_xref_per1000", "contrast_neg_per1000"}
FEAT_KEYS = ["stat_terms", "domain_terms", "first_person", "connectives", "hedges", "boosters", "rather_than", "contrast_neg",
             "backref", "section_xref", "ai_marker", "ai_common", "template", "defensive", "coinage", "jinxing"]
PER = {"numbers_per100": ("numbers", 100), "cites_per100": ("cites", 100), "stat_terms_per100": ("stat_terms", 100),
       "domain_terms_per100": ("domain_terms", 100), "parens_per100": ("parens", 100), "we_per1000": ("first_person", 1000),
       "connectives_per1000": ("connectives", 1000), "hedges_per1000": ("hedges", 1000), "boosters_per1000": ("boosters", 1000),
       "dashes_per1000": ("dashes", 1000), "colons_per1000": ("colons", 1000), "semicolons_per1000": ("semicolons", 1000),
       "rather_than_per1000": ("rather_than", 1000), "contrast_neg_per1000": ("contrast_neg", 1000), "backref_per1000": ("backref", 1000),
       "section_xref_per1000": ("section_xref", 1000), "ai_marker_per1000": ("ai_marker", 1000), "ai_common_per1000": ("ai_common", 1000),
       "template_per1000": ("template", 1000), "defensive_per1000": ("defensive", 1000), "coinage_per1000": ("coinage", 1000),
       "jinxing_per1000": ("jinxing", 1000), "de_per100": ("de", 100)}
ABS_LABEL = re.compile(r"^\W*(?:background|objectives?|aims?|purpose|introduction|design|setting|participants|methods?|measures|results?|findings|limitations?|conclusions?|discussion|目的|方法|结果|结论|局限)\W{0,3}[:：]\W*", re.I)
SHARE_KEYS = {"long_share", "we_initial_share", "negation_share", "para_final_neg_share", "interpretive_share", "table_led_share", "share_body"}


def feats(s, lang, R):
    f = {"len": M.count_words(s), "numbers": M.count_numbers(s), "cites": M.count_citations(s)}
    for k in FEAT_KEYS:
        rx = R.get(k)
        f[k] = len(rx.findall(s)) if rx else 0
    for k in ("interpretive", "negation", "we_initial"):
        rx = R.get(k)
        f[k] = 1 if (rx and rx.search(s)) else 0
    if lang == "zh":
        pairs = s.count("——")
        f["dashes"] = pairs + s.count("—") - 2 * pairs
        f["colons"] = s.count("：") + len(re.findall(r"(?<!\d):(?!\d)", s))
        f["semicolons"] = s.count("；") + s.count(";")
        f["parens"] = s.count("（") + s.count("(")
        f["de"] = s.count("的")
    else:
        f["dashes"] = s.count("—") + len(re.findall(r"\s–\s", s)) + s.count("--")
        f["colons"] = len(re.findall(r"(?<!\d):(?!\d)", s))
        f["semicolons"] = s.count(";")
        f["parens"] = s.count("(")
        f["de"] = 0
    return f


def clean_para(ss, lang):
    """剔除疑似表格残留或断句失败的句子；剩下不足一半时整段剔除（对标与稿件同一口径）。返回 (句子, 剔除句数)。"""
    if not ss:
        return None, 0
    lim = 100 if lang == "en" else 200
    keep = [s for s in ss if M.count_words(s) <= lim and M._numeric_ratio(s) <= 0.3]
    if len(keep) < 0.5 * len(ss):
        return None, len(ss)
    return keep, len(ss) - len(keep)


def measure(paras, lang, R):
    sents = [s for p in paras for s in p]
    if not sents:
        return None
    F = [feats(s, lang, R) for s in sents]
    words = sum(x["len"] for x in F)
    if words < 40:
        return None
    m = {"words": words}
    lens = [x["len"] for x in F]
    m["sent_mean"] = round(statistics.mean(lens), 2)
    m["sent_p90"] = round(M.quantile(lens, .9), 1)
    m["long_share"] = round(sum(1 for x in lens if x > (40 if lang == "en" else 80)) / len(lens), 3)
    plen, i = [], 0
    for p in paras:
        plen.append(sum(F[i + j]["len"] for j in range(len(p)))); i += len(p)
    m["para_cv"] = round(statistics.pstdev(plen) / statistics.mean(plen), 3) if len(plen) >= 3 and max(plen) <= 600 else None
    for key, (fk, unit) in PER.items():
        m[key] = round(unit * sum(x[fk] for x in F) / words, 3)
    m["we_initial_share"] = round(sum(x["we_initial"] for x in F) / len(F), 3)
    m["negation_share"] = round(sum(x["negation"] for x in F) / len(F), 3)
    m["interpretive_share"] = round(sum(x["interpretive"] for x in F) / len(F), 3)
    rxneg = R.get("negation")
    m["para_final_neg_share"] = round(sum(1 for p in paras if rxneg and rxneg.search(p[-1])) / len(paras), 3)
    rxt = R.get("table_led")
    m["table_led_share"] = round(sum(1 for p in paras if rxt and rxt.search(p[0])) / len(paras), 3)
    return m, list(zip(sents, F))


PLACEHOLDER_STRIP = re.compile(r"\s*\[(?:VERIFY|ref|REF|TODO|待核|待补)[^\]]*\]")


def analyze(path, lang_opt, lex_extra):
    # 占位符（[VERIFY: …]、[ref]）不是作者的文字：它们的冒号、括号与词数会让方法节的标点率虚高（第五轮实测：方法冒号率因占位符被报“偏高”）
    text = PLACEHOLDER_STRIP.sub("", M.load_text(path))
    lang = M.detect_lang(text) if lang_opt == "auto" else lang_opt
    R = M.lex_rx(M.load_lexicon(lang, lex_extra), lang)
    blocks = M.parse(text)
    groups, dropped, heads = {k: [] for k in SECS}, 0, []
    for b in blocks:
        if b["kind"] == "heading":
            heads.append((b["sec"], b["level"], b["text"])); continue
        if b["kind"] != "para":
            continue
        tg = {"discussion": ["discussion_all"], "limitations": ["discussion_all", "limitations"]}.get(
            b["sec"], [b["sec"]] if b["sec"] in groups else [])
        if not tg:
            continue
        txt = ABS_LABEL.sub("", b["text"]) if b["sec"] == "abstract" else b["text"]
        ss, nd = clean_para(M.sentences(txt), lang)
        dropped += nd
        if ss is None:
            continue
        for t in tg:
            groups[t].append(ss)
    res = {"file": os.path.basename(path), "path": path, "lang": lang, "dropped": dropped, "sections": {}, "sents": {}}
    res["content_sha256"] = hashlib.sha256(M.norm_for_match(text).encode("utf-8")).hexdigest()
    res["body_sha256"] = M.corpus_body_sha256(text)
    for k, ps in groups.items():
        out = measure(ps, lang, R)
        if out:
            res["sections"][k], res["sents"][k] = out
    if not res["sections"]:
        raise ValueError("not_verified：文件没有可测量的论文节或全部文本被剔除：%s" % path)
    body = sum(res["sections"][k]["words"] for k in BODY if k in res["sections"])
    for k, m in res["sections"].items():
        m["share_body"] = round(m["words"] / body, 3) if body and k in BODY else None
    pre = [b["text"] for b in blocks if b["sec"] != "references" and b["kind"] in ("para", "caption", "table")]
    res["supp_mentions"] = sum(len(R["supp"].findall(t)) for t in pre) if R.get("supp") else None
    res["distinct_domain_terms"] = None
    if R.get("domain_terms"):
        terms = set()
        for k in BODY:
            for ss in groups[k]:
                for s in ss:
                    terms.update(x.lower() for x in R["domain_terms"].findall(s))
        res["distinct_domain_terms"] = len(terms)
    res["methods_heads"] = [h for (sec, lvl, h) in heads if sec == "methods" and not re.match(r"page \d+$", h, re.I)]
    try:
        import results_function as _RF
        res["results_heads"] = [h for (sec, lvl, h) in heads if sec == "results" and not _RF.is_top_results(h) and not re.match(r"page \d+$", h, re.I)]
        res["results_head_styles"] = [_RF.heading_style(h) for h in res["results_heads"]]
    except Exception:
        res["results_heads"], res["results_head_styles"] = [], []
    res["missing"] = [SEC_ZH[k] for k in ("introduction", "methods", "results", "discussion_all") if k not in res["sections"]]
    # Do not mistake the first cited reference DOI for the paper's own identity.
    d = re.search(r"^\s*(?:doi\s*:?\s*|https?://(?:dx\.)?doi\.org/)(10\.\d{4,9}/[^\s\"<>)\]]+)", text[:2000], re.I | re.M)
    res["doi"] = d.group(1).rstrip(".,;").lower() if d else None
    return res


def verdict(x, s):
    if x is None or not s:
        return ""
    if x > s["max"]:
        return "高于全部"
    if x < s["min"]:
        return "低于全部"
    if s["n"] >= 20:
        return "高(>p95)" if x > s["p95"] else ("低(<p05)" if x < s["p05"] else "")
    if s["n"] >= 10:
        return "偏高(>p90)" if x > s["p90"] else ("偏低(<p10)" if x < s["p10"] else "")
    return ""


def fmt(v, key=""):
    if v is None:
        return "—"
    if key in SHARE_KEYS:
        return "%.0f%%" % (100 * v)
    if isinstance(v, int) or (isinstance(v, float) and v.is_integer() and abs(v) >= 100):
        return "%d" % v
    return ("%.2f" % v) if abs(v) < 10 else ("%.1f" % v)


def collect_paths(items):
    out = []
    for it in items:
        if os.path.isdir(it):
            for ext in ("*.md", "*.txt", "*.docx"):
                out += sorted(glob.glob(os.path.join(it, "**", ext), recursive=True))
        elif os.path.exists(it):
            out.append(it)
        else:
            raise ValueError("找不到指定的对标文件：%s" % it)
    return [p for p in out if not os.path.basename(p).lower().startswith("readme")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exemplars", nargs="+", default=[])
    ap.add_argument("--baseline", default="", help="领域包目录（assets/domains/…）：用其中已发表论文的指标作参照")
    ap.add_argument("--genre", default="", help="只用领域包中这一体裁的论文（如 experiment）")
    ap.add_argument("--draft", action="append", required=True, help="标签=路径，可多次")
    ap.add_argument("--lexicon", action="append", default=[])
    ap.add_argument("--lang", default="auto", choices=["auto", "en", "zh"])
    ap.add_argument("--keep-dupes", action="store_true")
    ap.add_argument("--report", default="bench_report.md")
    ap.add_argument("--csv", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    try:
        paths = collect_paths(a.exemplars) if a.exemplars else []
    except ValueError as e:
        print(str(e), file=sys.stderr); return 2
    ex, seen, dupes, content_seen, body_seen = [], {}, [], {}, {}
    pack_note = ""
    if a.baseline:
        try:
            pdir = a.baseline if os.path.isdir(a.baseline) else os.path.dirname(a.baseline)
            prof = json.load(open(os.path.join(pdir, "profile.json"), encoding="utf-8"))
            base = json.load(open(os.path.join(pdir, "bench_baseline.json"), encoding="utf-8"))
        except (OSError, ValueError, KeyError) as e:
            print("领域包无法读取：%s" % e, file=sys.stderr); return 2
        for r in base["exemplars"]:
            if a.genre and r.get("genre") != a.genre:
                continue
            r = dict(r); r["file"] = r.get("id") or r["file"]
            content_seen[r["content_sha256"]] = r["file"]
            if r.get("body_sha256"):
                body_seen[r["body_sha256"]] = r["file"]
            if r.get("doi"):
                seen[r["doi"]] = r["file"]
            ex.append(r)
        pack_note = "领域基线 %s（%s；%s；构建 %s）%s。领域基线是同领域已发表论文的分布，不是与稿件匹配的对标。" % (
            prof["id"], prof.get("label", ""), "%d 篇" % len(ex), prof.get("built", ""), "，体裁限定 %s" % a.genre if a.genre else "")
    if not paths and not ex:
        print("没有可用的对标文件（需要 --exemplars 或 --baseline）", file=sys.stderr); return 2
    for p in paths:
        try:
            r = analyze(p, a.lang, a.lexicon)
        except (OSError, ValueError) as e:
            print(str(e), file=sys.stderr); return 2
        if r["content_sha256"] in content_seen:
            dupes.append((r["file"], content_seen[r["content_sha256"]])); continue
        if r["body_sha256"] in body_seen:
            dupes.append((r["file"], body_seen[r["body_sha256"]])); continue
        content_seen[r["content_sha256"]] = r["file"]
        body_seen[r["body_sha256"]] = r["file"]
        if r["doi"] and r["doi"] in seen and not a.keep_dupes:
            dupes.append((r["file"], seen[r["doi"]])); continue
        if r["doi"]:
            seen[r["doi"]] = r["file"]
        ex.append(r)
    drafts = []
    for d in a.draft:
        lab, _, p = d.partition("=") if "=" in d else (os.path.basename(d), "", d)
        if not os.path.exists(p):
            print("找不到稿件：%s" % p, file=sys.stderr); return 2
        try:
            r = analyze(p, a.lang, a.lexicon)
        except (OSError, ValueError) as e:
            print(str(e), file=sys.stderr); return 2
        if r["content_sha256"] in content_seen or r["body_sha256"] in body_seen or (r.get("doi") and r["doi"] in seen):
            print("not_verified：稿件本身或其文本副本不能作为对标文献：%s" % p, file=sys.stderr); return 2
        r["label"] = lab; drafts.append(r)
    langs = {r["lang"] for r in ex}
    if len(langs) != 1 or any(d["lang"] not in langs for d in drafts):
        print("not_verified：不能混合中英文计算同一分布；请按语言分别运行，跨语言结构比较另作人工记录。", file=sys.stderr); return 2
    if any(not any(set(d["sections"]) & set(e["sections"]) for e in ex) for d in drafts):
        print("not_verified：稿件与对标没有共同可测量的节", file=sys.stderr); return 2
    summ = {}
    for sec in SECS:
        for key, name, only, _ in METRICS:
            if only and sec not in only:
                continue
            s = M.summarize([r["sections"][sec].get(key) for r in ex if sec in r["sections"]])
            if s:
                summ[(sec, key)] = s
    gl = {}
    for key in ("supp_mentions", "distinct_domain_terms"):
        s = M.summarize([r.get(key) for r in ex])
        if s:
            gl[key] = s
    L = []
    w = L.append
    w("# 分节分布对标报告\n")
    w("对标 %d 篇（去重后；语言：%s）。稿件：%s。\n" % (len(ex), "/".join(sorted(langs)), "、".join(d["label"] for d in drafts)))
    if pack_note:
        w(pack_note + "\n")
    w("**读法**：数字是诊断，不是目标。偏离只提示\"该看一眼\"：先看定位到的句子承担什么功能，再决定改不改；改原因，不改指标"
      "（不要用同义词把术语换低）。对标 <10 篇只看是否超出范围，10–19 篇看 p10–p90，≥20 篇看 p05–p95。"
      "百分位用中位秩（低于计 1、相等计 0.5）；对标只有 8 篇时，每篇约占 12.5 个百分点，只宜看相对位置。"
      "标 ◆ 的是词表定义的风格指标，超出对标上限时优先看其功能；它们不是 AI 身份检测标准。\n")
    if any(d["lang"] not in langs for d in drafts):
        w("> ⚠ 稿件与对标文献语言不同，表层指标（句长、标点、词表类）不可比，只看结构与信息分配类指标。\n")
    w("## 一、语料与质量\n")
    w("| 文件 | 语言 | 正文词数 | 缺失节 | 剔除句子 | 补充材料提及 |")
    w("|---|---|---|---|---|---|")
    for r in ex + drafts:
        bw = sum(r["sections"][k]["words"] for k in BODY if k in r["sections"])
        w("| %s%s | %s | %d | %s | %d | %s |" % ("**[稿]** " if r in drafts else "", r.get("label", r["file"]), r["lang"], bw,
                                               "、".join(r["missing"]) or "—", r["dropped"], fmt(r["supp_mentions"])))
    if dupes:
        w("\n疑似重复（同 DOI，已跳过；确认不是同一篇时用 --keep-dupes）：" + "；".join("%s = %s" % x for x in dupes))
    w("\n剔除句子 = 超过 100 词（中文 200 字）或数字占比 >30% 的\"句子\"（疑似表格残留或断句失败）；一段剔除过半则整段剔除。"
      "稿件与对标同口径。段长变异系数只在段落切分可信时（最长段 ≤600 词）计算。缺节的文献不进入该节分布；缺失多或剔除多的文献，"
      "先用 `python mslib.py sections 文件` 核对标题，必要时手工补 Markdown 标题后重跑。\n")
    w("## 二、偏离汇总\n")
    for d in drafts:
        w("### %s\n" % d["label"])
        rows = []
        for sec in SECS:
            if sec not in d["sections"]:
                continue
            for key, name, only, fk in METRICS:
                if (only and sec not in only) or (sec, key) not in summ:
                    continue
                x = d["sections"][sec].get(key); s = summ[(sec, key)]; v = verdict(x, s)
                if v and x is not None:
                    rows.append((sec, key, name, fk, x, s, v))
        if not rows:
            w("没有超出判定区间的指标。\n"); continue
        w("| 节 | 指标 | 稿件 | 对标中位数 [四分位] | 范围 | 百分位 | 判断 |")
        w("|---|---|---|---|---|---|---|")
        for sec, key, name, fk, x, s, v in rows:
            vals = [r["sections"][sec].get(key) for r in ex if sec in r["sections"]]
            w("| %s | %s%s | %s | %s [%s–%s] | %s–%s | %s | %s |" % (SEC_ZH[sec], "◆" if key in TEXTURE else "", name, fmt(x, key),
                                                               fmt(s["median"], key), fmt(s["q1"], key), fmt(s["q3"], key),
                                                               fmt(s["min"], key), fmt(s["max"], key),
                                                               fmt(M.median_rank_pct(x, vals)), v))
        w("\n**定位到的句子**（每项最多 3 句，供判断功能，不是必改清单）：\n")
        for sec, key, name, fk, x, s, v in rows:
            if not fk or not v.startswith(("高", "偏高")):
                continue
            top = [p for p in sorted(d["sents"].get(sec, []), key=lambda p: p[1][fk], reverse=True)[:3] if p[1][fk] > 0]
            if top:
                w("- %s · %s：" % (SEC_ZH[sec], name))
                for sent, f in top:
                    w("  - (%s) %s" % (f[fk], sent[:220] + ("…" if len(sent) > 220 else "")))
        w("")
    w("## 三、逐节全表\n")
    for sec in SECS:
        keys = [(k, n) for k, n, only, _ in METRICS if (sec, k) in summ and not (only and sec not in only)]
        if not keys:
            continue
        w("### %s\n" % SEC_ZH[sec])
        w("| 指标 | n | 中位数 [四分位] | 范围 | " + " | ".join("%s（百分位）" % d["label"] for d in drafts) + " |")
        w("|---|---|---|---|" + "---|" * len(drafts))
        for key, name in keys:
            s = summ[(sec, key)]
            vals = [r["sections"][sec].get(key) for r in ex if sec in r["sections"]]
            cells = []
            for d in drafts:
                x = d["sections"].get(sec, {}).get(key)
                cells.append("%s（%s）%s" % (fmt(x, key), fmt(M.median_rank_pct(x, vals)), " ⚑" if verdict(x, s) else ""))
            w("| %s%s | %d | %s [%s–%s] | %s–%s | %s |" % ("◆" if key in TEXTURE else "", name, s["n"], fmt(s["median"], key), fmt(s["q1"], key),
                                                       fmt(s["q3"], key), fmt(s["min"], key), fmt(s["max"], key), " | ".join(cells)))
        w("")
    w("## 四、全文层面\n")
    w("| 指标 | 对标中位数 [四分位]，范围 | " + " | ".join(d["label"] for d in drafts) + " |")
    w("|---|---|" + "---|" * len(drafts))
    for key, name in (("supp_mentions", "补充材料提及（含表注图注）"), ("distinct_domain_terms", "正文不同领域术语数")):
        if key in gl:
            s = gl[key]; vals = [r.get(key) for r in ex]
            w("| %s | %s [%s–%s]，%s–%s | %s |" % (name, fmt(s["median"]), fmt(s["q1"]), fmt(s["q3"]), fmt(s["min"]), fmt(s["max"]),
                                               " | ".join("%s（%s）" % (fmt(d.get(key)), fmt(M.median_rank_pct(d.get(key), vals))) for d in drafts)))
    w("\n## 五、方法部分小标题（结构对照）\n")
    umb = re.compile(r"statistic|data analys|analytic|analysis strategy|^analys[ie]s$|统计|数据分析", re.I)
    k = sum(1 for r in ex if any(umb.search(h) for h in r["methods_heads"]))
    w("设有总的统计/数据分析小节：%d/%d 篇对标文献；%s。\n" % (k, len(ex), "；".join(
        "%s %s" % (d["label"], "有" if any(umb.search(h) for h in d["methods_heads"]) else "无") for d in drafts)))
    for r in ex + drafts:
        w("- %s：%s" % (r.get("label", r["file"]), " / ".join(r["methods_heads"][:12]) or "（未识别到方法小标题）"))
    import collections as _co
    _kinds = {"finding": "发现句式", "nominal": "名词化发现", "object": "分析对象/指标式"}
    w("\n## 六、结果部分小标题（风格对照）\n")
    _dom = lambda r: _co.Counter(r.get("results_head_styles") or []).most_common(1)[0][0] if r.get("results_head_styles") else ""
    _cnt = _co.Counter(_dom(r) for r in ex if r.get("results_head_styles"))
    w("对标文献中有结果小标题的 %d 篇：以分析对象/指标式为主 %d、以发现句式为主 %d、以名词化发现为主 %d。这是风格证据，不是规则："
      "结合用户偏好与目标刊选定后，写进 benchmark_decisions.csv 与 expectations.json（results_function --heading-style 据此检查）。\n" % (
          sum(_cnt.values()), _cnt["object"], _cnt["finding"], _cnt["nominal"]))
    for r in ex + drafts:
        _h, _s = r.get("results_heads") or [], r.get("results_head_styles") or []
        w("- %s：%s" % (r.get("label", r["file"]), " / ".join("%s〔%s〕" % (h, _kinds.get(t, t)) for h, t in zip(_h[:10], _s[:10])) or "（未识别到结果小标题）"))
    with M.wfile(a.report) as f:
        f.write("\n".join(L) + "\n")
    if a.csv:
        with M.wfile(a.csv) as f:
            cw = csv.writer(f); cw.writerow(["label", "file", "section", "metric", "value"])
            for r in ex + drafts:
                for sec, m in r["sections"].items():
                    for key, v in m.items():
                        cw.writerow([r.get("label", "exemplar"), r["file"], sec, key, v])
    if a.json:
        with M.wfile(a.json) as f:
            json.dump({"exemplars": [{k: v for k, v in r.items() if k != "sents"} for r in ex],
                       "drafts": [{k: v for k, v in r.items() if k != "sents"} for r in drafts],
                       "summary": {"%s|%s" % k: v for k, v in summ.items()},
                       "global": gl}, f, ensure_ascii=False, indent=1)
    flags = [(d["label"], sec, key) for d in drafts for sec in d["sections"] for key, _, only, _ in METRICS
             if (sec, key) in summ and not (only and sec not in only) and verdict(d["sections"][sec].get(key), summ[(sec, key)])]
    for d in drafts:
        n = sum(1 for x in flags if x[0] == d["label"]); nt = sum(1 for x in flags if x[0] == d["label"] and x[2] in TEXTURE)
        print("%s：超出判定区间 %d 项（其中风格信号 %d 项）" % (d["label"], n, nt))
    print("对标 %d 篇。报告：%s。这是描述性筛查；退出 0 表示已生成报告，不是语言质量或身份检测通过。" % (len(ex), a.report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
