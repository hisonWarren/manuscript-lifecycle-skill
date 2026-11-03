#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deviation_register.py — 偏离登记：凡是能从近邻测出来的写法分布，稿件落在多数做法之外的，一并列出并要求裁决（references/29 §4c）。

  python deviation_register.py --draft 稿件.md [--supplement 补充.md]
         [--neighbors 近邻全文.md …] [--survey survey_corpus.csv] [--term-groups "stimulus=…;method=…"]
         [--moves moves_coding.json] [--baseline assets/domains/<包>] [--terms 术语,…|@文件]
         [--submitted 上次投稿的原稿] [--decisions benchmark_decisions.csv] [--stage draft|submission] [--report out.md] [--json out.json] [--todo 待裁决.csv]

四类偏离，同一个裁决口径（benchmark_decisions.csv 的 dimension 列）：
  convention:<维度>          题目形式与长度、是否点名方法与刺激、补充称呼、局限版式、讨论小标题、摘要结构（convention_profile）
  move:<单元>:<语步>         关键段的语步：近邻常见而稿件没有，或稿件有而近邻少见（move_check；单元如 intro_paras、disc_first）
  texture:<节>:<指标>        标点（冒号、分号、破折号、括号）、句长与长句、段长变异、连接词、限定与强化语、第一人称、否定、
                             rather than 等文本质感，落在近邻分布之外（bench_profile；节可写 * 表示全部节）
  phrasing:<单元>:<语步>:<起句>  同一语步在类型匹配近邻里怎样起句（目的句、假设句……），稿件的写法近邻没人用时列出近邻的写法
  lexis:<词>                 稿件反复使用、近邻少用的词（对数似然 keyness，只对近邻全文计算；--terms 与题目里的词不算）
  revision:<节>:growth       给了 --submitted 时，相对上次投稿原稿明显变长的节或小节（累计，不是相对上一轮）；变长的节，其文风类质感偏离在近邻少于 10 篇时也要裁决，
                             一行 revision:<节>:growth 可同时裁决该节质感。revision:trace 是新增句里读得出审稿或改稿过程的；revision:repeat:<数> 是改稿后在四节以上重复的百分数（供看）
类别：convention、move 与“文风类”texture（散文节的标点、句长、连接词、人称、否定，方法与结果节的标点与连接词；参照 ≥10 篇时）是 adjudicate，
投稿阶段不裁决不放行（genre_gate CN1/MV1/TX1）；内容驱动的 texture（数字、引文、统计词密度）与 lexis 是 review，列出供看（TX2、LX1）。
裁决行要写 decision（采用多数做法 / 保留）、locator 或 reason，并绑定当前稿件指纹（manuscript_sha256）。
为什么要有它：前四轮每轮由用户点出一类违和（题目、补充称呼、局限版式、引言末段、标点与连接词），技能就加一维检查。
这里把“近邻能测的写法”统一成一张偏离表：新维度只要能测，就自动进入同一个裁决流程，不再等用户发现。
退出码：0 没有待裁决的 adjudicate 项；1 有；2 输入错误。报告与 JSON 必须是新路径。
"""
import argparse, collections, csv, hashlib, json, math, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mslib as M  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# 必须裁决的只是读者会“感到”的文风指标（标点、句长、转折、人称、否定与防御、模板与自造标签），且只在散文节。
# 第七轮模拟：二十多个指标、五个节一起要求裁决时，同分布的干净稿也会因多重比较被报十几项；
# 方法与结果的标点、数字和术语密度主要由内容决定，只列出供看。
STYLE = {"sent_mean", "semicolons_per1000", "colons_per1000", "dashes_per1000", "rather_than_per1000", "connectives_per1000",
         "we_per1000", "negation_share", "defensive_per1000", "template_per1000", "ai_marker_per1000", "coinage_per1000"}
STYLE_TECH = set()
PROSE = {"abstract", "introduction", "discussion_all", "limitations", "conclusion"}
NAMES = {"sent_mean": "平均句长", "sent_p90": "句长90分位", "long_share": "长句占比", "para_cv": "段长变异系数", "connectives_per1000": "连接词/千词",
         "hedges_per1000": "限定语/千词", "boosters_per1000": "强化语/千词", "dashes_per1000": "破折号/千词", "colons_per1000": "冒号/千词",
         "semicolons_per1000": "分号/千词", "parens_per100": "括号/百词", "we_per1000": "第一人称/千词", "we_initial_share": "We开头句占比",
         "negation_share": "含否定句占比", "rather_than_per1000": "rather than/千词", "contrast_neg_per1000": "否定对照句式/千词",
         "defensive_per1000": "防御句式/千词", "numbers_per100": "数字/百词", "cites_per100": "引文/百词", "stat_terms_per100": "统计词/百词",
         "words": "词数", "para_final_neg_share": "段末否定占比"}
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*[A-Za-z]")
STOP_REF = re.compile(r"^#{1,6}\s*(references|bibliography|参考文献)\b", re.I | re.M)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def read_rows(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def decided(rows, msha):
    out = {}
    for r in rows:
        dim = r.get("dimension", "")
        if dim and r.get("decision") and (r.get("locator") or r.get("reason")) and r.get("manuscript_sha256", "").lower() == msha:
            # 改稿增量的裁决要说得出和谁比、为什么：只写“保留”不算比过（decision 可以是不改）
            if dim.lower().startswith("revision:") and not (r.get("neighbor") and len(r.get("reason", "")) >= 15):
                continue
            out[dim.lower()] = r
    return out


def covered(dim, dec):
    d = dim.lower()
    if d in dec:
        return True
    parts = d.split(":")
    if parts[0] == "texture" and len(parts) == 3:
        sec = {"discussion_all": "discussion"}.get(parts[1], parts[1])
        return ("texture:*:%s" % parts[2]) in dec or ("texture:%s:*" % parts[1]) in dec or ("revision:%s:growth" % sec) in dec
    return False


# ---------------------------------------------------------------- 改稿增量：每轮只看改动处时，看不见的累计效应
REV_SECS = ("abstract", "introduction", "methods", "results", "discussion", "limitations", "conclusion")
REV_ZH = {"abstract": "摘要", "introduction": "引言", "methods": "方法", "results": "结果", "discussion": "讨论", "limitations": "局限", "conclusion": "结论"}
PCT = re.compile(r"(?<![\d.])\d+(?:\.\d+)?\s?%")


def _rev_profile(path):
    sec, sub, sents, pct = {}, {}, set(), {}
    for b in M.parse(M.load_text(path)):
        if b.get("kind") != "para" or b.get("sec") not in REV_SECS:
            continue
        n = M.count_words(b["text"])
        sec[b["sec"]] = sec.get(b["sec"], 0) + n
        if b.get("sub"):
            sub[(b["sec"], b["sub"])] = sub.get((b["sec"], b["sub"]), 0) + n
        for x in PCT.findall(b["text"]):
            pct.setdefault(x.replace(" ", ""), set()).add(b["sec"])
    return sec, sub, pct


def revision_items(draft, submitted):
    """相对上次投稿原稿的累计增量。变长不等于错：它决定哪些节必须重新和近邻比一次。"""
    s0, sub0, pct0 = _rev_profile(submitted)
    s1, sub1, pct1 = _rev_profile(draft)
    items, grown = [], set()
    for sec in REV_SECS:
        a, b = s0.get(sec, 0), s1.get(sec, 0)
        if b - a >= 50 and (a == 0 or (b - a) / a >= 0.20):
            grown.add(sec)
            items.append({"dim": "revision:%s:growth" % sec, "class": "adjudicate",
                          "msg": "%s %d → %d 词（%+.0f%%）。和近邻的同一节重新比一次：读者会不会觉得这节相对其他节失衡，新增内容放这里、放补充还是只写在回复信" % (
                              REV_ZH[sec], a, b, 100.0 * (b - a) / max(a, 1))})
    for (sec, name), b in sorted(sub1.items()):
        a = sub0.get((sec, name), 0)
        if b - a >= 100 and (a == 0 or (b - a) / a >= 0.50) and name.strip().lower() != sec:
            items.append({"dim": "revision:%s:growth" % name.strip().replace(":", " ").lower(), "class": "adjudicate",
                          "msg": "小节“%s”%d → %d 词（%+.0f%%）" % (name.strip(), a, b, 100.0 * (b - a) / max(a, 1))})
    old = M.norm_for_match(M.load_text(submitted))
    trace = []
    for b in M.parse(M.load_text(draft)):
        if b.get("kind") == "para" and b.get("sec") in REV_SECS:
            for s in M.sentences(b["text"]):
                hit = M.REVISION_TRACE.search(s) or (b["sec"] == "limitations" and M.LIMITATION_POINTER.search(s))
                if hit and M.norm_for_match(s) not in old:
                    trace.append(s)
    if trace:
        items.append({"dim": "revision:trace", "class": "adjudicate",
                      "msg": "新增句里 %d 句读得出审稿或改稿过程，或在局限里回指别处：%s" % (len(trace), " / ".join(t[:90] + "…" for t in trace[:4]))})
    for x, secs in sorted(pct1.items()):
        if len(secs) >= 4 and len(secs) > len(pct0.get(x, ())):
            items.append({"dim": "revision:repeat:%s" % x, "class": "review",
                          "msg": "%s 改稿后出现在 %d 节（%s）：每一处都在为那一节的论证服务吗" % (x, len(secs), "、".join(REV_ZH[k] for k in REV_SECS if k in secs))})
    return items, grown


# ---------------------------------------------------------------- 文本质感（bench_profile）
def texture(draft, exemplars, baseline, lang="auto"):
    if not exemplars and not baseline:
        return None, "没有近邻全文或领域包，文本质感没测"
    with tempfile.TemporaryDirectory() as td:
        args = [sys.executable, os.path.join(HERE, "bench_profile.py"), "--draft", "draft=" + draft, "--report", os.path.join(td, "b.md"),
                "--json", os.path.join(td, "b.json"), "--lang", lang]
        if exemplars:
            args += ["--exemplars"] + exemplars
        if baseline:
            args += ["--baseline", baseline]
        p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0 or not os.path.exists(os.path.join(td, "b.json")):
            return None, (p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip() else "bench_profile 退出码 %d" % p.returncode
        with open(os.path.join(td, "b.json"), encoding="utf-8") as f:
            d = json.load(f)
    dr = d["drafts"][0]["sections"]
    out = []
    for key, st in d["summary"].items():
        sec, met = key.split("|", 1)
        v = (dr.get(sec) or {}).get(met)
        n = st.get("n", 0)
        if v is None or n < 3:
            continue
        lo, hi = (st["min"], st["max"]) if n < 10 else ((st["p10"], st["p90"]) if n < 20 else (st["p05"], st["p95"]))
        if lo <= v <= hi:
            continue
        # 同分布的新稿件落在 n 篇范围之外的概率是 2/(n+1)：n=3 时一半指标会“偏离”，二十个指标就有十个假警报。
        # 所以近邻少于 10 篇时质感偏离只供看；≥10 篇才要求裁决（第七轮模拟：3 篇近邻时干净稿被报 21 项）。
        styl = (sec in PROSE and met in STYLE) or (sec in ("methods", "results") and met in STYLE_TECH)
        cls = "adjudicate" if (styl and n >= 10) else "review"
        out.append({"dim": "texture:%s:%s" % (sec, met), "class": cls, "value": v, "median": st["median"], "lo": lo, "hi": hi, "n": n,
                    "msg": "%s·%s = %s，近邻%s %.3g–%.3g（中位 %.3g，n=%d）" % (sec, NAMES.get(met, met), v, "范围" if n < 10 else "参考区间",
                                                                     lo, hi, st["median"], n)})
    return out, ""


# ---------------------------------------------------------------- 词汇 keyness（对数似然，Dunning 1993）
def body_words(path):
    t = M.load_text(path)
    m = STOP_REF.search(t)
    t = t[:m.start()] if m else t
    t = re.sub(r"\[(?:VERIFY|ref)[^\]]*\]", " ", t)
    t = re.sub(r"\([^()]*\d{4}[a-z]?[^()]*\)", " ", t)    # 作者–年份引文
    return [w.lower().replace("’", "'") for w in WORD.findall(t)]


def lexis(draft, exemplars, exclude, top=20, min_count=3):
    if len(exemplars) < 2:
        return None, "近邻全文不足 2 篇，词汇 keyness 没算（领域包不存单词频数）"
    if M.detect_lang(M.load_text(draft)) == "zh":
        # 中文没有可靠的分词时，单字或二元组的 keyness 噪声大；改用 phrase_contrast 的中文框架对照（它按词表最长匹配切词）
        return None, "中文稿的词汇分布没有用 keyness 计算：请用 phrase_contrast.py（中文按词表切词的句式框架对照）"
    dw = body_words(draft)
    docs = [collections.Counter(body_words(p)) for p in exemplars]
    ref = collections.Counter()
    for c in docs:
        ref.update(c)
    n1, n2, dc = len(dw), sum(ref.values()), collections.Counter(dw)
    out = []
    for w, a in dc.items():
        if a < min_count or w in exclude or len(w) < 3:
            continue
        b = ref.get(w, 0)
        e1, e2 = n1 * (a + b) / (n1 + n2), n2 * (a + b) / (n1 + n2)
        ll = 2 * (a * math.log(a / e1) + (b * math.log(b / e2) if b else 0))
        df = sum(1 for c in docs if c.get(w))
        if ll >= 15.13 and a / n1 >= 3 * (b + 0.5) / n2 and df <= max(1, len(docs) // 3):
            out.append({"dim": "lexis:%s" % w, "class": "review", "count": a, "per1000": round(1000 * a / n1, 2),
                        "ref_per1000": round(1000 * b / n2, 3), "ref_docs": df, "ll": round(ll, 1),
                        "msg": "“%s” 稿件 %d 次（%.2f/千词），近邻 %d/%d 篇用过（%.3f/千词），LL=%.1f" % (w, a, 1000 * a / n1, df, len(docs), 1000 * b / n2, ll)})
    out.sort(key=lambda x: -x["ll"])
    return out[:top], ""


def parse_terms(s, draft):
    out = set()
    if s:
        items = open(s[1:], encoding="utf-8").read().split("\n") if s.startswith("@") else s.split(",")
        for x in items:
            out.update(w.lower() for w in WORD.findall(x))
    title = next((l.lstrip("#").strip() for l in M.load_text(draft).split("\n") if l.startswith("# ")), "")
    out.update(w.lower() for w in WORD.findall(title))
    return out


# ---------------------------------------------------------------- 汇总
def collect(draft, supplement=None, neighbors=(), survey=None, term_groups="", moves=None, baseline="", terms="", texture_exemplars=None, submitted=""):
    items, notes = [], []
    grown = set()
    if submitted:
        rev, grown = revision_items(draft, submitted)
        items += rev
    if neighbors:
        import convention_profile as CP
        try:
            prof = CP.profile(list(neighbors), draft, supplement, survey, term_groups, 0.25)
            for d in prof["deviations"]:
                items.append({"dim": "convention:%s" % d["dim"], "class": "adjudicate", "msg": d["msg"]})
            if prof["na"]:
                notes.append("惯例画像没能测：%s" % "、".join(prof["na"]))
        except Exception as e:  # noqa: BLE001
            notes.append("惯例画像没能运行：%s" % e)
    mv_meta = None
    if moves:
        import move_check as MC
        try:
            data = json.load(open(moves, encoding="utf-8-sig"))
            errs, _w, _ok, res, _m = MC.analyze(data, os.path.dirname(os.path.abspath(moves)))
            mv_meta = {"errors": len(errs), "sections": {k: v["n_exemplars"] for k, v in res["sections"].items()}}
            if errs:
                items.append({"dim": "move:coding", "class": "adjudicate", "msg": "语步编码有 %d 处线索对不上原文（先修编码）：%s" % (len(errs), errs[0])})
            for sec, s in res["sections"].items():
                if s["n_exemplars"] < 3:
                    notes.append("语步单元 %s 只有 %d 篇类型匹配的近邻编码（至少 3 篇）；比例不作数，按段落职能与目标刊判断" % (sec, s["n_exemplars"]))
                    continue
                cond = s.get("conditional", {})
                fam_txt = lambda m: "、".join("%s %.0f%%" % (f, 100 * v) for f, v in cond[m].items())
                for d in s["drafts"]:
                    for m in d["missing_common"]:
                        items.append({"dim": "move:%s:%s" % (sec, m), "class": "adjudicate",
                                      "msg": "%s：类型匹配的近邻 %.0f%% 有语步 %s，稿件没有（%s）" % (sec, 100 * s["presence"][m], m, MC.MOVES.get(m, ""))})
                    for m in d["rare_present"]:
                        msg = "%s：稿件有语步 %s，类型匹配的近邻只有 %.0f%% 有（%s）" % (sec, m, 100 * s["presence"].get(m, 0), MC.MOVES.get(m, ""))
                        if m in cond:
                            msg += "；各类期刊做法不同（%s），按目标刊所属的那一类决定，目标刊未定时按类型匹配的多数做法" % fam_txt(m)
                        items.append({"dim": "move:%s:%s" % (sec, m), "class": "adjudicate", "msg": msg})
                    for m in d.get("conditional_absent", []):
                        items.append({"dim": "move:%s:%s" % (sec, m), "class": "review",
                                      "msg": "%s：稿件没有语步 %s；各类期刊做法不同（%s），投那一类期刊时再加" % (sec, m, fam_txt(m))})
                    # 语步怎么写：同一语步在类型匹配近邻里怎样起句。证据够（该语步 ≥4 处实现）且稿件的首词没人用时要裁决
                    for r in d.get("realizations", []):
                        if not r["neighbor_keys"] or r["attested_by"]:
                            continue
                        neigh = [x for x in s.get("realizations", {}).get(r["move"], [])]
                        firsts = {x["key"].split(" ")[0] for x in neigh if x["key"]}
                        first = r["key"].split(" ")[0]
                        # 证据够才要求裁决：该语步在近邻里有 ≥3 处实现，起句首词集中（最常见的首词占一半以上），而稿件的首词没人用。
                        # 首词分散的语步（设计句、假设句常常如此）说明近邻本来就各写各的，只列出供看
                        fw = collections.Counter(x["key"].split(" ")[0] for x in neigh if x["key"])
                        top = fw.most_common(1)[0][1] / sum(fw.values()) if fw else 0
                        strong = len(neigh) >= 3 and top > 0.5 and first not in firsts
                        items.append({"dim": "phrasing:%s:%s:%s" % (sec, r["move"], r["key"].replace(" ", "_")), "class": "adjudicate" if strong else "review",
                                      "msg": "%s：语步 %s 写成“%s…”，类型匹配的近邻这样起句：%s" % (sec, r["move"], r["start"][:60], "；".join(sorted({x["key"] for x in neigh})[:8]))})
        except (OSError, ValueError, KeyError) as e:
            notes.append("语步编码读不了：%s" % e)
    tex_ex = list(texture_exemplars if texture_exemplars is not None else neighbors)
    tx, why = texture(draft, tex_ex, baseline)
    if tx is None:
        notes.append(why)
    else:
        for t in tx:   # 变长的节是事先指定的比较，不是多重比较里碰巧落在范围外的那种，所以近邻少于 10 篇也要裁决
            _, sec, met = t["dim"].split(":", 2)
            if {"discussion_all": "discussion"}.get(sec, sec) in grown and (met in STYLE or met == "numbers_per100"):
                t["class"] = "adjudicate"
        items += tx
    lx, why = lexis(draft, tex_ex, parse_terms(terms, draft))
    if lx is None:
        notes.append(why)
    else:
        items += lx
    return items, notes, {"moves": mv_meta, "texture": tx is not None, "lexis": lx is not None, "n_texture_exemplars": len(tex_ex),
                          "baseline": os.path.basename(baseline.rstrip("/\\")) if baseline else "",
                          "submitted": os.path.basename(submitted) if submitted else "", "grown": sorted(grown)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draft", required=True)
    ap.add_argument("--supplement", default="")
    ap.add_argument("--neighbors", nargs="*", default=[])
    ap.add_argument("--texture-exemplars", nargs="*", default=None, help="只用于质感与词汇的近邻全文（默认同 --neighbors）")
    ap.add_argument("--survey", default="")
    ap.add_argument("--term-groups", default="")
    ap.add_argument("--moves", default="")
    ap.add_argument("--baseline", default="")
    ap.add_argument("--submitted", default="", help="上次投稿的原稿（返修时用）：按累计增量找变长的节与读得出改稿过程的新增句")
    ap.add_argument("--terms", default="")
    ap.add_argument("--decisions", default="")
    ap.add_argument("--stage", default="draft", choices=["draft", "submission"])
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--todo", default="", help="把待裁决项写成 benchmark_decisions.csv 格式的空行，裁决后并入")
    a = ap.parse_args()
    for p in [a.draft] + a.neighbors + (a.texture_exemplars or []) + [x for x in (a.supplement, a.survey, a.moves, a.decisions, a.submitted) if x]:
        if not os.path.exists(p):
            print("找不到 %s" % p, file=sys.stderr)
            return 2
    for p in (a.report, a.json, a.todo):
        if p and os.path.exists(p):
            print("输出文件已存在：%s" % p, file=sys.stderr)
            return 2
    msha = sha(a.draft)
    items, notes, meta = collect(a.draft, a.supplement or None, a.neighbors, a.survey or None, a.term_groups, a.moves or None,
                                 a.baseline, a.terms, a.texture_exemplars, a.submitted)
    dec = decided(read_rows(a.decisions), msha)
    for it in items:
        it["decided"] = covered(it["dim"], dec)
    pend = [i for i in items if i["class"] == "adjudicate" and not i["decided"]]
    L = ["# 偏离登记（deviation_register）", "", "稿件指纹 %s…；阶段 %s。待裁决 %d 项（adjudicate），供看 %d 项（review）。" % (
        msha[:12], a.stage, len(pend), sum(1 for i in items if i["class"] == "review")), ""]
    for cat, title in (("revision", "改稿增量与融入"), ("convention", "表面惯例"), ("move", "关键段语步"), ("phrasing", "语步的写法"), ("texture", "文本质感"), ("lexis", "词汇")):
        rows = [i for i in items if i["dim"].startswith(cat + ":")]
        L += ["## %s（%d）" % (title, len(rows)), ""]
        L += ["- [%s%s] `%s` %s" % (i["class"], "，已裁决" if i["decided"] else "", i["dim"], i["msg"]) for i in rows] or ["没有。"]
        L.append("")
    if notes:
        L += ["## 没能测的", ""] + ["- " + n for n in notes] + [""]
    L += ["裁决写进 benchmark_decisions.csv：dimension 照抄上面反引号里的名字（质感可用 texture:*:<指标> 一行管全部节），decision 写“采用多数做法”或“保留”，",
          "reason 写为什么（例如“结果节逐项报告统计量，数字密度高是内容决定的”），locator 写近邻依据或报告位置，manuscript_sha256 写当前指纹。",
          "偏离不等于错误；分布只说明同类论文通常怎么写，不能替代判断。改的时候改原因（拆句、换连接、把限定移到它限定的句子），不要为了指标换同义词。"]
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    if a.json:
        with M.wfile(a.json) as f:
            json.dump({"schema_version": 1, "manuscript_sha256": msha, "stage": a.stage, "items": items, "notes": notes, "meta": meta,
                       "pending": len(pend)}, f, ensure_ascii=False, indent=1)
    if a.todo:
        with M.wfile(a.todo) as f:
            w = csv.writer(f)
            w.writerow(["dimension", "section", "neighbor", "doi_or_file", "locator", "observed", "decision", "reason", "manuscript_sha256"])
            for i in pend:
                w.writerow([i["dim"], i["dim"].split(":")[1] if i["dim"].count(":") >= 1 else "", "distribution", "", "deviation_register",
                            i["msg"], "", "", msha])
    print(out if not a.report else "待裁决 %d 项；报告 %s" % (len(pend), a.report))
    return 1 if pend else 0


if __name__ == "__main__":
    sys.exit(main())
