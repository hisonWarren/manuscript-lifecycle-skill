#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
language_plan.py — 语言修订"一次到位"：先把全稿（及配套文件）里每一处同类问题列成计划，逐条裁决后改稿，再核对。

  扫描：python language_plan.py scan --doc 正文=ms.md [--doc 补充=sm.md] --plan plan.csv
              [--exemplars 对标目录/ ...] [--patterns L4,S2] [--phrase "in keeping with"] [--regex "..."] [--report scan.md]
  核对：python language_plan.py check --plan plan.csv --after 正文=ms_v2.md [--after 补充=sm_v2.md]
              [--stage draft|submission] --report check.md

为什么需要它：改语言时只改被点到的几句，同类问题在别处原样存在，下一轮又冒出来；或者改过头，把数字、限定、否定改丢。
扫描把选中的每一类问题在所有文件中的每一处都列出来（plan.csv，另写 plan.csv.meta.json 记录指纹）。
每行填 decision（改 / 留 / 误报）、new_text（可选）、reason。核对检查：
  · 完整：每行都有裁决；"改"和"留"都写了理由；计划行没有被删、原句列没有被改（meta 记录了每行指纹）。
  · 落实：标为"改"的原句不能原样留在修改后文件里；写了 new_text 的，新文字必须真的出现在文件里。
  · 保真：改后句子对照原句。数字或引文丢失，须在理由中写明移到哪里或为何删除，否则算错误；
    否定词、限定词减少或强化/因果措辞增加列为复核项。
  · 回潮：用同一批模式重扫修改后文件，新出现的命中列出来；交付残留（对话残留、零宽字符、域错误、表情）出现即为错误。
选哪些模式：交付残留、占位符、always 与 scope 级模式总是列入。compare 级模式：给了 --exemplars 时，只在稿件高于同类文献
p90（不足 10 篇用最大值）且命中 ≥2 的节列入；--patterns 点名的模式全文列入；两者都没有时全部列入并标"未校准"，
这时很多命中是合理用法，逐条按 keep 条件判断。--phrase / --regex 用来把 phrase_contrast.py 找出的偏多句式纳入逐处裁决。
脚本只找形式，改不改看句子的功能。不以改动数量或检测率为目标，不为"去 AI 味"制造口语、笔误或随机变化。
退出码：scan 0 计划已写出、2 输入错误；check 0 无错误、1 有未裁决/未落实/保真或回潮错误、2 输入错误。
"""
import argparse
import collections
import csv
import datetime
import difflib
import glob
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402
from output_safety import output_path, write_fresh  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(os.path.dirname(HERE), "assets", "lexicons", "texture_catalog.json")
SECS = ["abstract", "introduction", "methods", "results", "discussion_all", "conclusion"]
SEC_ZH = {"front": "题名页", "abstract": "摘要", "introduction": "引言", "methods": "方法", "results": "结果", "discussion": "讨论",
          "discussion_all": "讨论(含局限)", "limitations": "局限", "conclusion": "结论", "back": "文末/表图", "caption": "图表说明", "全文": "全文"}
FIELDS = ["no", "doc", "pattern", "family", "label", "level", "section", "para", "sent", "sentence", "match", "calibration",
          "keep_if", "fix", "decision", "new_text", "reason"]
DEC = {"改": "revise", "修改": "revise", "revise": "revise", "revised": "revise", "edit": "revise",
       "留": "keep", "保留": "keep", "keep": "keep", "kept": "keep",
       "误报": "fp", "非问题": "fp", "false_positive": "fp", "fp": "fp", "not_issue": "fp"}
MOVE = re.compile(r"移至|移到|移入|删除|删去|删掉|合并|并入|拆分|已在|moved?|remov|delet|merg|split|relocat", re.I)
NEG = {"en": re.compile(r"\b(?:not|no|never|cannot|nor|neither|without|none)\b|n[’']t\b", re.I), "zh": re.compile(r"不|未|没有|非|尚未")}
HEDGE = {"en": re.compile(r"\b(?:may|might|could|possibly|perhaps|likely|suggests?|suggested|appears?|partly|only|primarily|mainly|largely)\b", re.I),
         "zh": re.compile(r"可能|或许|提示|部分|仅|主要|似乎|大致")}
BOOST = {"en": re.compile(r"\b(?:demonstrat\w*|prove[sd]?|proven|clearly|caus(?:e|es|ed)|led to|leads? to|confirm\w*|establish\w*|definitively)\b", re.I),
         "zh": re.compile(r"证明|证实|导致|显然|明确表明|确立|毫无疑问")}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_labeled(items, flag):
    out = []
    for d in items or []:
        lab, sep, p = d.partition("=")
        if not sep:
            lab, p = os.path.splitext(os.path.basename(d))[0], d
        lab = lab.strip()
        if not lab or not p or not os.path.isfile(p):
            raise ValueError("%s 找不到文件：%s" % (flag, d))
        out.append((lab, os.path.abspath(p)))
    if not out:
        raise ValueError("缺少 %s" % flag)
    if len({l for l, _ in out}) != len(out):
        raise ValueError("%s 标签重复" % flag)
    return out


def load_catalog(path, lang, lex_extra=()):
    data = json.load(open(path, encoding="utf-8-sig"))
    if data.get("schema_version") != 1 or not data.get("patterns"):
        raise ValueError("模式目录格式不对：%s" % path)
    R = M.lex_rx(M.load_lexicon(lang, lex_extra), lang)
    pats = []
    for e in data["patterns"]:
        if e.get("lang", "both") not in ("both", lang):
            continue
        rxs = []
        if e.get("lex") and R.get(e["lex"]) is not None:
            rxs.append(R[e["lex"]])
        rxs += [re.compile(x, re.I | re.M) for x in e.get("regex", [])]
        if not rxs and not e.get("residue"):
            continue
        pats.append(dict(e, rxs=rxs))
    return pats


def custom_patterns(phrases, regexes):
    out = []
    for i, ph in enumerate(phrases or [], 1):
        out.append({"id": "U%d" % i, "family": "U 点名", "label": "点名句式：%s" % ph, "level": "always", "keep": "按功能判断",
                    "fix": "参照同类文献常见写法改写或保留", "rxs": [re.compile(re.escape(ph), re.I)]})
    for j, rx in enumerate(regexes or [], len(phrases or []) + 1):
        out.append({"id": "U%d" % j, "family": "U 点名", "label": "点名正则：%s" % rx, "level": "always", "keep": "按功能判断",
                    "fix": "参照同类文献常见写法改写或保留", "rxs": [re.compile(rx, re.I | re.M)]})
    return out


def units(text):
    """[(sec, para_idx, [sentences], para_text)]；参考文献不扫，图表说明单列为 caption。"""
    out, cnt = [], {}
    for b in M.parse(text):
        if b["kind"] not in ("para", "caption") or b["sec"] == "references":
            continue
        sec = "caption" if b["kind"] == "caption" else b["sec"]
        cnt[sec] = cnt.get(sec, 0) + 1
        out.append((sec, cnt[sec], M.sentences(b["text"]) or [b["text"]], b["text"]))
    return out


def group_of(sec):
    return {"discussion": "discussion_all", "limitations": "discussion_all"}.get(sec, sec)


def hits_in(pat, us):
    """[(sec, para, sent_no, sentence, match)]：模式在各单元中的命中（每句最多记一次）。"""
    out, first_disc = [], None
    for sec, pi, ss, ptext in us:
        if group_of(sec) == "discussion_all" and first_disc is None:
            first_disc = (sec, pi)
        if pat.get("scope") and group_of(sec) not in pat["scope"] and sec not in pat["scope"]:
            continue
        if pat.get("unit") == "paragraph":
            for rx in pat["rxs"]:
                m = rx.search(ptext)
                if m:
                    out.append((sec, pi, 0, ptext, m.group(0)[:80]))
                    break
            continue
        idxs = list(range(len(ss)))
        if pat.get("position") == "last":
            if pat.get("exempt_first_discussion") and (sec, pi) == first_disc:
                continue
            idxs = [len(ss) - 1]
        elif pat.get("position") == "first":
            idxs = [0]
        for k in idxs:
            s = ss[k]
            if pat.get("no_cite") and M.count_citations(s) > 0:
                continue
            for rx in pat["rxs"]:
                m = rx.search(s)
                if m:
                    out.append((sec, pi, k + 1, s, m.group(0)[:80]))
                    break
    return out


def rate_table(pat, us):
    """{节组: (率, 命中数)}；位置类与段落类为段落占比，其余为每千词。"""
    words, paras, cnt = collections.Counter(), collections.Counter(), collections.Counter()
    for sec, pi, ss, ptext in us:
        g = group_of(sec)
        if g in SECS:
            words[g] += sum(M.count_words(s) for s in ss)
            paras[g] += 1
    for sec, pi, k, s, m in hits_in(pat, us):
        if group_of(sec) in SECS:
            cnt[group_of(sec)] += 1
    share = bool(pat.get("position") or pat.get("unit") == "paragraph")
    return {g: ((cnt[g] / paras[g]) if share else 1000.0 * cnt[g] / words[g], cnt[g]) for g in SECS if words[g] >= 40}


def exemplar_paths(items):
    paths = []
    for it in items or []:
        if os.path.isdir(it):
            for ext in ("*.md", "*.txt", "*.docx"):
                paths += sorted(glob.glob(os.path.join(it, "**", ext), recursive=True))
        elif os.path.isfile(it):
            paths.append(it)
        else:
            raise ValueError("找不到对标文件：%s" % it)
    return [os.path.abspath(p) for p in paths if not os.path.basename(p).lower().startswith("readme")]


def row_key(r):
    raw = "|".join(str(r.get(k, "")) for k in ("no", "doc", "pattern", "section", "para", "sent", "sentence"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def residue_pattern(pats, kind):
    return next((p for p in pats if p.get("residue") == kind), None)


# ------------------------------------------------------------------ scan
def cmd_scan(a):
    docs = parse_labeled(a.doc, "--doc")
    texts = {lab: M.load_text(p) for lab, p in docs}
    if not texts[docs[0][0]].strip():
        raise ValueError("主文件为空，不能把零检查记为通过")
    lang = a.lang if a.lang != "auto" else M.detect_lang(texts[docs[0][0]])
    catalog = os.path.abspath(a.catalog or CATALOG)
    pats = load_catalog(catalog, lang, a.lexicon) + custom_patterns(a.phrase, a.regex)
    known = {p["id"] for p in pats}
    explicit = {x.strip() for x in (a.patterns or "").split(",") if x.strip()}
    if explicit - known:
        raise ValueError("未知或不适用于 %s 的模式：%s" % (lang, "、".join(sorted(explicit - known))))
    doc_hashes = {sha(p) for _, p in docs}
    exs = [p for p in exemplar_paths(a.exemplars) if sha(p) not in doc_hashes]
    base_rates, pack = None, None
    if a.baseline:
        pdir = a.baseline if os.path.isdir(a.baseline) else os.path.dirname(a.baseline)
        M.reject_pack_self_comparison(pdir, texts.values(), a.genre)
        tb = json.load(open(os.path.join(pdir, "texture_baseline.json"), encoding="utf-8"))
        pack = json.load(open(os.path.join(pdir, "profile.json"), encoding="utf-8"))
        if tb["lang"] != lang:
            raise ValueError("领域包语言是 %s，稿件是 %s" % (tb["lang"], lang))
        import domain_pack as DPK
        if tb.get("texture_sha") != DPK.lexicon_hash(lang):
            raise ValueError("领域包的模式出现率是用另一版模式目录或词表统计的：请用 domain_pack.py build 重建")
        papers = [p for p in tb["papers"] if not a.genre or p.get("genre") == a.genre]
        if len(papers) < 3:
            raise ValueError("领域包中可用论文不足 3 篇")
        base_rates = {pid: [{g: tuple(v) for g, v in p["rates"].get(pid, {}).items()} for p in papers] for pid in {k for p in papers for k in p["rates"]}}
    if a.exemplars and len(exs) < 3:
        raise ValueError("对标文献不足 3 篇（已排除稿件自身）；改用 --patterns 点名，或补充同类文献")
    ex_units = []
    for p in exs:
        t = M.load_text(p)
        if M.detect_lang(t) != lang:
            raise ValueError("对标文献语言与稿件不同：%s" % p)
        ex_units.append(units(t))
    main_units = units(texts[docs[0][0]])
    selected, calib = set(), {}
    for pat in pats:
        if pat["level"] != "compare" or not (ex_units or base_rates):
            continue
        ex_rates = [rate_table(pat, u) for u in ex_units] + (base_rates.get(pat["id"], []) if base_rates else [])
        for g, (r, c) in rate_table(pat, main_units).items():
            vals = [er[g][0] for er in ex_rates if g in er]
            if len(vals) < 3:
                continue
            thr = M.quantile(vals, 0.9) if len(vals) >= 10 else max(vals)
            if c >= 2 and r > thr:
                selected.add((pat["id"], g))
                unit = "（段落占比）" if (pat.get("position") or pat.get("unit") == "paragraph") else "/千词"
                calib[(pat["id"], g)] = "%s %.2f%s > 对标%s %.2f（%d 篇）" % (SEC_ZH[g], r, unit, "p90" if len(vals) >= 10 else "最大值", thr, len(vals))
    selected_ids = {pid for pid, _ in selected}
    rows, scope = [], set()
    for di, (lab, p) in enumerate(docs):
        for kind, label, ln, shown, ctx in M.residue_hits(M.load_raw(p), placeholders=True):
            pat = residue_pattern(pats, kind)
            if pat:
                rows.append({"_order": (di, -1, ln), "doc": lab, "pattern": pat["id"], "family": pat["family"], "label": pat["label"],
                             "level": pat["level"], "section": "全文", "para": "L%d" % ln, "sent": "", "sentence": ctx, "match": shown,
                             "calibration": "与语料无关", "keep_if": pat.get("keep", ""), "fix": pat.get("fix", "")})
        us = units(texts[lab])
        order = {(sec, pi): i for i, (sec, pi, _, _) in enumerate(us)}
        for pat in pats:
            if pat.get("residue"):
                continue
            for sec, pi, k, s, m in hits_in(pat, us):
                g = group_of(sec)
                if pat["level"] == "compare":
                    if pat["id"] in explicit:
                        cal = "点名"
                    elif ex_units or base_rates:
                        if (di == 0 and (pat["id"], g) not in selected) or (di > 0 and pat["id"] not in selected_ids):
                            continue
                        cal = calib.get((pat["id"], g), "与正文同类问题一并处理")
                    elif explicit:
                        continue          # 点名了模式又没给对标：只列点名的那几类
                    else:
                        cal = "未校准（未提供对标）"
                elif pat["level"] == "scope":
                    cal = "限定节：" + "、".join(SEC_ZH.get(x, x) for x in pat.get("scope", []))
                else:
                    cal = "每处裁决"
                scope.add((lab, pat["id"], g if (pat["level"] == "compare" and pat["id"] not in explicit and (ex_units or base_rates)) else "*"))
                rows.append({"_order": (di, order[(sec, pi)], k), "doc": lab, "pattern": pat["id"], "family": pat["family"], "label": pat["label"],
                             "level": pat["level"], "section": sec, "para": str(pi), "sent": str(k), "sentence": s, "match": m,
                             "calibration": cal, "keep_if": pat.get("keep", ""), "fix": pat.get("fix", "")})
    rows.sort(key=lambda r: (r["_order"], r["pattern"]))
    for i, r in enumerate(rows, 1):
        r["no"] = str(i)
        r.pop("_order")
        r.update(decision="", new_text="", reason="")
    protected = [p for _, p in docs] + exs + [catalog]
    plan = output_path(a.plan, protected)
    meta_path = output_path(a.plan + ".meta.json", protected)
    rep_path = output_path(a.report, protected + [str(plan), str(meta_path)]) if a.report else None
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in FIELDS})
    write_fresh(plan, "\ufeff" + buf.getvalue())
    meta = {"schema_version": 1, "tool": "language_plan", "created": datetime.datetime.now().isoformat(timespec="seconds"), "lang": lang,
            "docs": [{"label": lab, "path": p, "sha256": sha(p)} for lab, p in docs],
            "catalog": {"path": catalog, "sha256": sha(catalog)}, "exemplars": [{"path": p, "sha256": sha(p)} for p in exs],
            "explicit": sorted(explicit), "phrases": a.phrase or [], "regexes": a.regex or [], "lexicons": a.lexicon or [],
            "auto_selected": sorted([list(x) for x in selected]), "uncalibrated": not (ex_units or base_rates) and not explicit,
            "baseline": pack["id"] if pack else None,
            "scope": sorted([list(x) for x in scope]), "rows": [{"no": r["no"], "key": row_key(r)} for r in rows]}
    write_fresh(meta_path, json.dumps(meta, ensure_ascii=False, indent=1))
    by = collections.Counter((r["pattern"], r["label"]) for r in rows)
    L = ["# 语言修订计划：%s\n" % "、".join(lab for lab, _ in docs),
         "语言 %s；对标 %d 篇%s%s；计划 %d 行。每行填 decision（改/留/误报）、reason，改写时可填 new_text；改完运行 check。\n" % (
             lang, len(exs), "；领域基线 %s（%d 篇）" % (pack["id"], len(next(iter(base_rates.values()), []))) if pack else "",
             "（未校准：compare 级命中全部列入，很多是合理用法）" if not (ex_units or base_rates) else "", len(rows)),
         "| 模式 | 说明 | 处数 |", "|---|---|---|"]
    L += ["| %s | %s | %d |" % (pid, lab_, n) for (pid, lab_), n in sorted(by.items())]
    if calib:
        L.append("\n高于同类文献、因而列入的节：\n")
        L += ["- %s %s" % (pid, calib[(pid, g)]) for pid, g in sorted(selected)]
    L.append("\n读法：模式是线索不是黑名单。先看 keep_if，再决定改、留还是误报；理由写清楚功能（职能、准确、对标距离、规范）。"
             "同一类问题全稿一次处理，不只改被指出的那几句；拿不准就少改。")
    out = "\n".join(L) + "\n"
    if rep_path:
        write_fresh(rep_path, out)
    print("计划 %d 行（%s）。计划：%s" % (len(rows), "；".join("%s×%d" % (pid, n) for (pid, _), n in sorted(by.items())) or "无命中", plan))
    return 0


# ------------------------------------------------------------------ check
def read_plan(path):
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise ValueError("计划文件编码无法识别，请保存为 UTF-8")


def fidelity(orig, new, lang):
    out = []
    n0 = [t.replace("−", "-") for t, _ in M.number_tokens(orig)]
    n1 = [t.replace("−", "-") for t, _ in M.number_tokens(new)]
    lost = [x for x in n0 if x not in n1]
    if lost:
        out.append(("numbers", "数字丢失：%s" % "、".join(lost[:6])))
    c0, c1 = M.count_citations(orig), M.count_citations(new)
    if c1 < c0:
        out.append(("citations", "引文减少 %d → %d" % (c0, c1)))
    L = lang if lang in NEG else "en"
    a0, a1 = len(NEG[L].findall(orig)), len(NEG[L].findall(new))
    if a1 < a0:
        out.append(("neg", "否定词减少 %d → %d，确认没有改变极性" % (a0, a1)))
    h0, h1 = len(HEDGE[L].findall(orig)), len(HEDGE[L].findall(new))
    if h1 < h0:
        out.append(("hedge", "限定词减少 %d → %d，确认没有扩大主张" % (h0, h1)))
    b0, b1 = len(BOOST[L].findall(orig)), len(BOOST[L].findall(new))
    if b1 > b0:
        out.append(("boost", "强化或因果措辞增加 %d → %d，确认证据支持" % (b0, b1)))
    return out


def best_match(orig_norm, pool):
    best, br = None, 0.0
    for s in pool:
        ns = M.norm_for_match(s)
        sm = difflib.SequenceMatcher(None, orig_norm, ns, autojunk=False)
        if sm.real_quick_ratio() < 0.4 or sm.quick_ratio() < 0.4:
            continue
        r = sm.ratio()
        if r > br:
            best, br = s, r
    return (best, br) if br >= 0.4 else (None, br)


def cmd_check(a):
    meta_path = a.meta or a.plan + ".meta.json"
    if not os.path.isfile(a.plan) or not os.path.isfile(meta_path):
        raise ValueError("找不到计划或其 meta：%s / %s" % (a.plan, meta_path))
    meta = json.load(open(meta_path, encoding="utf-8-sig"))
    if meta.get("tool") != "language_plan" or meta.get("schema_version") != 1:
        raise ValueError("meta 不是 language_plan 生成的")
    rows = read_plan(a.plan)
    after = dict(parse_labeled(a.after, "--after"))
    for d in meta["docs"]:
        if d["label"] not in after:
            raise ValueError("缺少修改后文件：%s（用 --after %s=路径）" % (d["label"], d["label"]))
    errs, warns, notes = [], [], []
    keys = {row_key(r) for r in rows}
    gone = [m["no"] for m in meta["rows"] if m["key"] not in keys]
    if gone:
        errs.append("计划行被删除或原句列被改动：第 %s 行。删行不能冒充已处理；需要撤销时把 decision 写成 误报 并说明理由" % "、".join(gone[:20]))
    for d in meta["docs"]:
        if os.path.isfile(d["path"]) and sha(d["path"]) != d["sha256"]:
            notes.append("原稿「%s」在扫描后已变化（可能是就地修改）；核对使用计划中保存的原句" % d["label"])
    lang = meta.get("lang", "en")
    a_text = {lab: M.load_text(p) for lab, p in after.items()}
    a_norm = {lab: M.norm_for_match(t) for lab, t in a_text.items()}
    # 逐字文本（只合并空白）：只改标点的修订（冒号改句号、去掉破折号）在去标点比对下看不出来，须按原文再比一次
    a_ws = {lab: re.sub(r"\s+", " ", t) for lab, t in a_text.items()}
    a_units = {lab: units(t) for lab, t in a_text.items()}
    a_sents = {lab: [(sec, s) for sec, pi, ss, _ in us for s in ss] for lab, us in a_units.items()}
    revised = {(r.get("doc"), r.get("sentence")) for r in rows if DEC.get((r.get("decision") or "").strip().lower()) == "revise"}
    counts = collections.Counter()
    for r in rows:
        tag = "第%s行［%s %s %s］" % (r.get("no", "?"), r.get("doc", ""), r.get("pattern", ""), SEC_ZH.get(r.get("section", ""), r.get("section", "")))
        raw_dec = (r.get("decision") or "").strip()
        dec = DEC.get(raw_dec.lower()) or DEC.get(raw_dec)
        reason, new = (r.get("reason") or "").strip(), (r.get("new_text") or "").strip()
        if not dec:
            errs.append(tag + "：未裁决（decision 填 改 / 留 / 误报）")
            continue
        counts[dec] += 1
        if dec in ("revise", "keep") and len(reason) < 4:
            errs.append(tag + "：缺理由（说明功能：职能、准确、对标距离或规范）")
        if dec == "fp" and not reason:
            warns.append(tag + "：标为误报但没写理由")
        lab = r.get("doc")
        if lab not in a_norm:
            errs.append(tag + "：修改后文件中没有这个文件标签")
            continue
        if r.get("level") in ("hard", "placeholder"):
            continue
        orig = r.get("sentence", "")
        on = M.norm_for_match(orig)
        present = bool(on) and on in a_norm[lab]
        if dec == "revise":
            if present and re.sub(r"\s+", " ", orig.strip()) not in a_ws.get(lab, ""):
                present = False  # 标点之外的字符没变，但原句已不在文件中：这是只改标点的修订
            if present:
                errs.append(tag + "：标为“改”，但原句仍原样留在修改后文件中")
                continue
            cand = None
            if new:
                if M.norm_for_match(new) not in a_norm[lab]:
                    errs.append(tag + "：new_text 没有出现在修改后文件中")
                    continue
                cand = new
            else:
                pool = [s for sec, s in a_sents[lab] if sec == r.get("section")] or [s for _, s in a_sents[lab]]
                cand, _ = best_match(on, pool)
            if cand is None:
                if not MOVE.search(reason):
                    warns.append(tag + "：原句已不在，也找不到对应的新句；若是删除或合并，请在理由中写明")
                continue
            for kind, detail in fidelity(orig, cand, lang):
                if kind in ("numbers", "citations"):
                    (notes if MOVE.search(reason) else errs).append(tag + "：" + detail + ("（理由已说明去向）" if MOVE.search(reason) else "；理由中没有说明移到哪里或为何删除"))
                else:
                    warns.append(tag + "：" + detail)
        elif dec in ("keep", "fp") and on and not present and (lab, orig) not in revised:
            warns.append(tag + "：标为保留/误报，但原句已改动；确认是否有意")
    for lab, p in after.items():
        hard = M.residue_hits(M.load_raw(p), placeholders=(a.stage == "submission"))
        bad = [h for h in hard if h[0] != "placeholder" or a.stage == "submission"]
        if bad:
            errs.append("［%s］修改后仍有交付残留 %d 处：%s" % (lab, len(bad), "；".join("第%d行 %s %s" % (h[2], h[1], h[3]) for h in bad[:8])))
        if a.stage != "submission":
            ph = [h for h in M.residue_hits(M.load_raw(p), placeholders=True) if h[0] == "placeholder"]
            if ph:
                notes.append("［%s］占位符 %d 处：起草阶段可留，须在作者待办中列出；投稿前用 --stage submission 复查" % (lab, len(ph)))
    pats = {p["id"]: p for p in load_catalog(meta["catalog"]["path"], lang, meta.get("lexicons", [])) + custom_patterns(meta.get("phrases"), meta.get("regexes"))}
    plan_sents = collections.defaultdict(set)
    for r in rows:
        plan_sents[(r.get("doc"), r.get("pattern"))].add(M.norm_for_match(r.get("sentence", "")))
    scope = collections.defaultdict(set)
    for lab, pid, g in meta.get("scope", []):
        scope[(lab, pid)].add(g)
    fresh = []
    for (lab, pid), groups in scope.items():
        pat = pats.get(pid)
        if pat is None or lab not in a_units or pat.get("residue"):
            continue
        for sec, pi, k, s, m in hits_in(pat, a_units[lab]):
            if "*" not in groups and group_of(sec) not in groups:
                continue
            if M.norm_for_match(s) not in plan_sents[(lab, pid)]:
                fresh.append("［%s %s %s第%d段］%s：…%s…" % (lab, pid, SEC_ZH.get(sec, sec), pi, m, s[:120]))
    if fresh:
        warns.append("修改后文件中有 %d 处新出现或改写后仍含该模式的句子，需要补充裁决（可追加到计划后重查）：\n  - %s" % (len(fresh), "\n  - ".join(fresh[:15])))
    protected = [a.plan, meta_path] + list(after.values()) + [d["path"] for d in meta["docs"] if os.path.isfile(d["path"])]
    rep = output_path(a.report, protected) if a.report else None
    L = ["# 语言修订计划核对\n",
         "计划 %d 行：改 %d、留 %d、误报 %d、未裁决 %d。错误 %d、复核 %d、说明 %d。阶段：%s。\n" % (
             len(rows), counts["revise"], counts["keep"], counts["fp"], len(rows) - sum(counts.values()), len(errs), len(warns), len(notes), a.stage),
         "退出 0 只说明计划已逐条裁决、声称的修改已落到文件、核对到的数字与引文没有无故丢失；不说明改得好，语义仍需通读。\n"]
    for title, items in (("错误", errs), ("复核", warns), ("说明", notes)):
        if items:
            L.append("## %s\n" % title)
            L += ["- " + x for x in items]
            L.append("")
    out = "\n".join(L) + "\n"
    if rep:
        write_fresh(rep, out)
    print(out[:3500])
    return 1 if errs else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--doc", action="append", required=True, help="标签=路径；第一份是主稿，校准以它为准")
    s.add_argument("--plan", required=True)
    s.add_argument("--exemplars", nargs="+", default=[])
    s.add_argument("--baseline", default="", help="领域包目录：用同领域已发表论文的模式出现率校准")
    s.add_argument("--genre", default="", help="只用领域包中这一体裁的论文")
    s.add_argument("--patterns", default="")
    s.add_argument("--phrase", action="append", default=[])
    s.add_argument("--regex", action="append", default=[])
    s.add_argument("--catalog", default="")
    s.add_argument("--lexicon", action="append", default=[])
    s.add_argument("--lang", default="auto", choices=["auto", "en", "zh"])
    s.add_argument("--report", default="")
    c = sub.add_parser("check")
    c.add_argument("--plan", required=True)
    c.add_argument("--meta", default="")
    c.add_argument("--after", action="append", required=True)
    c.add_argument("--stage", default="draft", choices=["draft", "submission"])
    c.add_argument("--report", default="")
    a = ap.parse_args()
    try:
        return cmd_scan(a) if a.cmd == "scan" else cmd_check(a)
    except (ValueError, OSError, json.JSONDecodeError, re.error) as e:
        print("输入错误：%s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
