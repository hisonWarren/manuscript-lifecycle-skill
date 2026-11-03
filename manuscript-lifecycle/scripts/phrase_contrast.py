#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
phrase_contrast.py — 句式对照：稿件反复使用、同类文献同一节却少用的起句和短语框架；以及同类文献这一节常用的起句。

  python phrase_contrast.py --exemplars 对标目录/ 或 文件... --draft 现稿=ms.md [--draft 旧稿=old.md]
  python phrase_contrast.py --baseline assets/domains/psychology_zh [--genre experiment] --draft 现稿=ms.md
         [--lang auto|en|zh] [--min-count 3] [--top 10] [--snippets] [--terms 术语,…|@文件] [--report phrases.md] [--json phrases.json]

回答"稿件总爱用某类句式，同类文献这里通常怎么写"。做法：
  · 词汇遮蔽：只保留功能词与学术话语词（assets/lexicons/phrase_vocab.json；领域包可追加本领域通用词），
    术语、量表名、构念名换成 X，数字换成 #，连续的 X 只记一个。英文按词切；中文按词表最长匹配切词，
    词表外的字连成一段记为一个 X。于是 "The PHQ-9 had…" 与 "The GAD-7 had…" 归为同一框架 "the X had"，
    "场合特异性高于…" 与 "时间稳定性高于…" 归为 "X 高于"；术语前后一致不会被当成重复。
  · 起句：每句前 3 个词。稿件某节某起句占比高于对标同节全部文献、占该节句子 ≥8% 且出现 ≥2 次，列为偏多。
  · 短语框架：连续 3 个通用词组成、不含〈X〉的话语骨架（"的 角度 来看""in line with"）。每千词（中文每千字）
    频率高于全部参照、至少为参照中位数的 3 倍（--ratio）、出现 ≥ --min-count 次，列为偏多；另算全文。
    含内容槽的框架随题目而变，留一法检验中每篇已发表论文会被标出数十个，所以不计。
  · 同类文献常用起句：该节有 ≥20% 文献（至少 2 篇）使用，按使用篇数排序，并标出稿件用了几次。
--baseline 使用领域包里预先统计好的起句与框架频数（不含原文），不需要手头有对标全文；领域包只保留在 ≥2 篇中出现的框架，
只在 1 篇中出现过的框架按 0 计，结果略偏敏感。只输出短框架和篇数，不摘录对标文献整句；--snippets 只对 --exemplars 可用。
读法：偏多不等于错。结果部分平行报告、方法部分固定格式的重复常是合理的；先看这句话承担的功能，再决定是否换写法。
不要为了"多样"机械替换同义词或打乱语序，那本身就是机器味。决定改写的句式，用 language_plan.py --phrase 列出全稿每一处逐条裁决。
退出码：0 报告已写出；2 输入错误（对标不足 3 篇、语言不一致、稿件混入对标、领域包与词表版本不符）。
"""
import argparse
import collections
import glob
import hashlib
import json
import math
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402
from output_safety import output_path, write_fresh  # noqa: E402

SECS = ["abstract", "introduction", "methods", "results", "discussion_all", "conclusion"]
SEC_ZH = {"abstract": "摘要", "introduction": "引言", "methods": "方法", "results": "结果", "discussion_all": "讨论(含局限)",
          "conclusion": "结论", "all": "全文"}
DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>)\]]+")
VOCAB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "lexicons", "phrase_vocab.json")
ETAL = re.compile(r"\bet al\.?", re.I)
EN_TOK = re.compile(r"[A-Za-z]+(?:[-'’][A-Za-z]+)*|\d+(?:[.,]\d+)*")
ULTRA = {"en": set("the a an of in to and for on with by as at from is was were are be been that this these those it its or their which".split()),
         "zh": set("的 了 在 与 和 及 对 为 是 中 一 这 该 其 此 等 将 被 所 从 以 于 而 并 也 都 均 上 下 内 外 间 后 前 时 个 之 者".split())}
N_OPEN = N_FRAME = 3
TOKENIZER_VERSION = "pc4-units-discourse"
UNITS = set()
TERMS = []          # 项目术语（--terms 与稿件关键词）：遮蔽为 X


def set_terms(terms):
    TERMS[:] = sorted({x.strip().strip("*#_ ").strip() for x in terms if len(x.strip().strip("*#_ ").strip()) >= 2}, key=len, reverse=True)


def load_vocab(lang, extra=(), units_extra=()):
    data = json.load(open(VOCAB, encoding="utf-8"))
    words = set(data[lang]) | set(extra)
    UNITS.clear()
    UNITS.update(set(data.get(lang + "_units", [])) | set(units_extra))
    key = "%s|%s|%s|%s" % (TOKENIZER_VERSION, lang, "\n".join(sorted(words)), "\n".join(sorted(UNITS)))
    return words, hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _merge(out):
    merged = []
    for t in out:
        if t == "X" and merged and merged[-1] == "X":
            continue
        merged.append(t)
    return merged


def tokens(s, lang, words):
    s = ETAL.sub(" ", M.strip_citations(s))
    for term in TERMS:
        s = re.sub(re.escape(term), " termmask ", s, flags=re.I)
    out = []
    if lang == "en":
        for t in EN_TOK.findall(s):
            if t[0].isdigit():
                out.append("#")
            elif sum(c.isupper() for c in t) >= 2 or re.search(r"\d", t):
                out.append("X")
            else:
                out.append(t.lower() if t.lower() in words else "X")
        return _merge(out)
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if "\u4e00" <= ch <= "\u9fff":
            lv = next((L for L in range(min(4, n - i), 0, -1) if s[i:i + L] in words), 0)
            lu = next((L for L in range(min(3, n - i), 1, -1) if s[i:i + L] in UNITS), 0)
            if lu > lv and lv <= 1:            # 实词单元只压过单字虚词，不压过多字通用词
                out.append("X"); i += lu          # 实词单元（"功能""时间"）整体遮蔽
            elif lv:
                out.append(s[i:i + lv]); i += lv
            else:
                out.append("X"); i += 1
        elif ch.isdigit():
            j = i
            while j < n and (s[j].isdigit() or s[j] in ".,"):
                j += 1
            out.append("#"); i = j
        elif ch.isascii() and ch.isalpha():
            j = i
            while j < n and s[j].isascii() and (s[j].isalnum() or s[j] in "-'’"):
                j += 1
            out.append("X"); i = j
        else:
            i += 1
    return _merge(out)


def sections_of(text, lang):
    secs = {k: [] for k in SECS}
    for b in M.parse(text):
        if b["kind"] != "para":
            continue
        g = {"discussion": "discussion_all", "limitations": "discussion_all"}.get(b["sec"], b["sec"])
        if g not in secs:
            continue
        for s in M.sentences(b["text"]):
            if M.count_words(s) > (100 if lang == "en" else 200) or M._numeric_ratio(s) > 0.3:
                continue
            secs[g].append(s)
    return secs


def informative(gr, lang):
    return any(x not in ULTRA[lang] and x not in ("X", "#") for x in gr)


def stats_from_sentences(secs, lang, words, keep_examples=True):
    """{节: {n, words, op, fr, ex_op, ex_fr}}，含"all"。"""
    stats = {}
    for g in SECS + ["all"]:
        sents = [s for gg in (SECS if g == "all" else [g]) for s in secs[gg]]
        op, fr = collections.Counter(), collections.Counter()
        ex_op, ex_fr = collections.defaultdict(list), collections.defaultdict(list)
        nw = 0
        for s in sents:
            mt = tokens(s, lang, words)
            nw += M.count_words(s)
            if len(mt) >= N_OPEN and sum(1 for x in mt[:N_OPEN] if x in ("X", "#")) <= 1 and informative(mt[:N_OPEN], lang):
                o = " ".join(mt[:N_OPEN])
                op[o] += 1
                if keep_examples and len(ex_op[o]) < 2:
                    ex_op[o].append(s)
            seen = set()
            for i in range(len(mt) - N_FRAME + 1):
                gr = mt[i:i + N_FRAME]
                # 框架只取由通用词组成、不含〈X〉的话语骨架（"的 角度 来看""in line with"）：含内容槽的框架随题目而变，
                # 留一法检验中每篇已发表论文会被标出数十个，无法区分问题
                if "#" in gr or "X" in gr or sum(1 for x in gr if x not in ULTRA[lang]) < 2:
                    continue
                f = " ".join(gr)
                fr[f] += 1
                if keep_examples and f not in seen and len(ex_fr[f]) < 2:
                    ex_fr[f].append(s)
                    seen.add(f)
        stats[g] = {"n": len(sents), "words": nw, "op": op, "fr": fr, "ex_op": ex_op, "ex_fr": ex_fr}
    return stats


class Doc:
    def __init__(self, label, path=None, lang="en", words=None, stats=None, genre=None):
        self.label, self.path, self.lang, self.genre = label, path, lang, genre
        if stats is not None:
            self.text, self.stats = "", stats
        else:
            self.text = M.load_text(path)
            self.stats = stats_from_sentences(sections_of(self.text, lang), lang, words)


def load_baseline(pack, lang_hint=None):
    """领域包：返回 (Doc 列表, 词表, 词表指纹, 包信息)。"""
    pdir = pack if os.path.isdir(pack) else os.path.dirname(pack)
    prof = json.load(open(os.path.join(pdir, "profile.json"), encoding="utf-8"))
    data = json.load(open(os.path.join(pdir, "phrase_baseline.json"), encoding="utf-8"))
    lang = data["lang"]
    if lang_hint and lang_hint != lang:
        raise ValueError("领域包语言是 %s，稿件是 %s" % (lang, lang_hint))
    words, vsha = load_vocab(lang, prof.get("phrase_vocab_extra", []))
    if data.get("vocab_sha") != vsha:
        raise ValueError("领域包的句式频数是用另一版词表或切词方式统计的（%s ≠ %s），请用 domain_pack.py build 重建" % (data.get("vocab_sha"), vsha))
    docs = []
    for p in data["papers"]:
        st = {}
        for g in SECS + ["all"]:
            s = p["sections"].get(g, {"n": 0, "words": 0, "op": {}, "fr": {}})
            st[g] = {"n": s["n"], "words": s["words"], "op": collections.Counter(s["op"]), "fr": collections.Counter(s["fr"]), "ex_op": {}, "ex_fr": {}}
        docs.append(Doc(p["id"], lang=lang, stats=st, genre=p.get("genre")))
    return docs, words, vsha, prof


def threshold(vals):
    """上界取全部参照的最大值：留一法检验中用 p90 会让每篇已发表论文多出约 1/3 的标记，而不提高对植入问题的检出。"""
    return max(vals) if vals else None


def find_flags(ds, exs, min_count=3, ratio=3.0, share_min=0.08, top=10, with_common=True):
    """一个节的判定：(偏多起句, 偏多框架, 常用起句)。ds/exs 为 stats[节]。"""
    flags_op, flags_fr, common = [], [], []
    if with_common is not None:
        for o, c in ds["op"].items():
            if c < 2:
                continue
            share = c / ds["n"]
            thr = threshold([e["op"].get(o, 0) / e["n"] for e in exs])
            if share >= share_min and share > thr:
                flags_op.append((share - thr, o, c, share, thr, sum(1 for e in exs if e["op"].get(o))))
        if with_common:
            dfo = collections.Counter(o for e in exs for o in e["op"])
            need_c = max(2, math.ceil(0.2 * len(exs)))
            common = [(o, n) for o, n in dfo.most_common() if n >= need_c][:top]
    for f, c in ds["fr"].items():
        if c < min_count:
            continue
        rate = 1000.0 * c / max(1, ds["words"])
        vals = [1000.0 * e["fr"].get(f, 0) / max(1, e["words"]) for e in exs]
        thr, med = threshold(vals), statistics.median(vals)
        if rate > thr and rate >= ratio * max(med, 0.2):
            flags_fr.append((rate / (thr + 0.05), f, c, rate, thr, med, sum(1 for e in exs if e["fr"].get(f))))
    flags_op.sort(reverse=True)
    flags_fr.sort(reverse=True)
    return flags_op, flags_fr, common


def count_flags(dstats, exstats, min_count=3, ratio=3.0):
    """一篇文献在全部节（含全文）上的标记总数，供领域包做留一法校准。"""
    n = 0
    for g in SECS + ["all"]:
        ds, exs = dstats[g], [e[g] for e in exstats if e[g]["n"] >= 3]
        if ds["n"] < 3 or len(exs) < 3:
            continue
        fo, ff, _ = find_flags(ds, exs, min_count, ratio, with_common=False if g != "all" else None)
        n += len(fo) + len(ff)
    return n


def snippet(sentence, frame, lang):
    """≤12 词（中文 ≤20 字）的出处片段，只为核对功能。"""
    if lang == "zh":
        return sentence[:20] + ("…" if len(sentence) > 20 else "")
    w = sentence.split()
    head = frame.split()[0] if frame.split() and frame.split()[0] not in ("x", "X", "#") else None
    start = next((i for i, x in enumerate(w) if head and x.lower().strip(",.;:()") == head), 0)
    return " ".join(w[start:start + 12]) + (" …" if len(w) > start + 12 else "")


def collect(items):
    paths = []
    for it in items:
        if os.path.isdir(it):
            for ext in ("*.md", "*.txt", "*.docx"):
                paths += sorted(glob.glob(os.path.join(it, "**", ext), recursive=True))
        elif os.path.isfile(it):
            paths.append(it)
        else:
            raise ValueError("找不到对标文件：%s" % it)
    return [os.path.abspath(p) for p in paths if not os.path.basename(p).lower().startswith("readme")]


def show(f):
    return f.replace("X", "〈X〉") if f else f


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exemplars", nargs="+", default=[])
    ap.add_argument("--baseline", default="", help="领域包目录（assets/domains/…）")
    ap.add_argument("--genre", default="", help="只用领域包中这一体裁的论文（如 experiment）")
    ap.add_argument("--draft", action="append", required=True, help="标签=路径，可多次")
    ap.add_argument("--lang", default="auto", choices=["auto", "en", "zh"])
    ap.add_argument("--min-count", type=int, default=3)
    ap.add_argument("--ratio", type=float, default=3.0, help="框架频率至少为参照中位数的倍数")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--snippets", action="store_true")
    ap.add_argument("--terms", default="", help="项目术语，逗号分隔，或 @文件（每行一个）；稿件关键词行会自动加入")
    ap.add_argument("--report", default="phrase_report.md")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    try:
        if not a.exemplars and not a.baseline:
            raise ValueError("需要 --exemplars 或 --baseline")
        drafts_in = []
        for d in a.draft:
            lab, sep, p = d.partition("=")
            if not sep:
                lab, p = os.path.splitext(os.path.basename(d))[0], d
            if not os.path.isfile(p):
                raise ValueError("找不到稿件：%s" % p)
            drafts_in.append((lab, os.path.abspath(p)))
        first = M.load_text(drafts_in[0][1])
        lang = a.lang if a.lang != "auto" else M.detect_lang(first)
        terms = []
        if a.terms.startswith("@"):
            terms = open(a.terms[1:], encoding="utf-8-sig").read().splitlines()
        elif a.terms:
            terms = re.split(r"[,，;；]", a.terms)
        for _, p in drafts_in:
            for line in M.load_text(p).split("\n")[:400]:
                if M.KEYWORDS.match(line.strip()):
                    body = re.split(r"[:：]|\s{2,}", line.strip(), 1)[-1]
                    terms += [x for x in re.split(r"[,，;；、]", body) if 1 < len(x.strip()) <= 40]
        set_terms(terms)
        ex, dupes, prof, src_note = [], [], None, ""
        if a.baseline:
            pdir = a.baseline if os.path.isdir(a.baseline) else os.path.dirname(a.baseline)
            M.reject_pack_self_comparison(pdir, [M.load_text(p) for _, p in drafts_in], a.genre)
            ex, words, vsha, prof = load_baseline(a.baseline, lang)
            if a.genre:
                ex = [e for e in ex if e.genre == a.genre]
            src_note = "领域包 %s（%s；共 %d 篇%s）" % (prof["id"], prof.get("label", ""), prof.get("n_papers", len(ex)),
                                                  "，本次只用体裁 %s 的 %d 篇" % (a.genre, len(ex)) if a.genre else "")
        else:
            words, vsha = load_vocab(lang)
        ex_paths = collect(a.exemplars) if a.exemplars else []
        dh = {sha(p) for _, p in drafts_in}
        if any(sha(p) in dh for p in ex_paths):
            raise ValueError("稿件出现在对标文献中；稿件不能拿来当自己的参照")
        seen = {}
        for p in ex_paths:
            t = M.load_text(p)
            if M.detect_lang(t) != lang:
                raise ValueError("对标文献语言与稿件不同（%s）：%s" % (lang, p))
            m = DOI.search(t[:6000])
            doi = m.group(0).rstrip(".,;").lower() if m else None
            if doi and doi in seen:
                dupes.append((os.path.basename(p), seen[doi]))
                continue
            if doi:
                seen[doi] = os.path.basename(p)
            ex.append(Doc(os.path.basename(p), p, lang, words))
        if len(ex) < 3:
            raise ValueError("对标不足 3 篇（去重、按体裁筛选后）")
        drafts = [Doc(lab, p, lang, words) for lab, p in drafts_in]
        for d in drafts:
            if M.detect_lang(d.text) != lang:
                raise ValueError("稿件语言不一致：%s" % d.label)
        protected = ex_paths + [p for _, p in drafts_in]
        rep = output_path(a.report, protected)
        jsn = output_path(a.json, protected + [str(rep)]) if a.json else None
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as e:
        print("输入错误：%s" % e, file=sys.stderr)
        return 2
    unit = "词" if lang == "en" else "词（中文按词表切分）"
    L = ["# 句式对照报告\n",
         "对标 %d 篇（语言 %s；%s去重跳过 %d 篇）。只保留功能词与学术话语词，术语、量表名、构念名写作〈X〉（连续的只记一个），数字写作 #，"
         "所以比较的是句式骨架；术语前后一致是对的，不会被当成重复。起句与框架都取前/连续 %d 个%s。\n" % (
             len(ex), lang, (src_note + "；") if src_note else "", len(dupes), N_OPEN, unit),
         "**读法**：偏多不等于错，先看句子承担的功能。平行报告结果、方法的固定格式可以重复；口号式收束、同一转折反复出现、"
         "每段同一起句才是要改的。不要机械换同义词或打乱语序。要改的句式用 `language_plan.py scan --phrase \"…\"` 列出全稿每一处再逐条裁决。"
         "同类文献常用起句只说明这一节通常从什么角度起笔，不是可套用的句子。\n"]
    if prof and prof.get("phrase_loo"):
        lo = prof["phrase_loo"]
        L.append("校准参照：同领域已发表论文用同样标准逐篇检验（留一法），每篇被标出中位 %d 项（最多 %d 项）。稿件标出项数与此相近时，多为个人用语习惯；"
                 "明显更多、或集中在同一类收束/评价骨架时，才值得逐处处理。\n" % (lo["median"], lo["max"]))
    if TERMS:
        L.append("已遮蔽的项目术语（--terms 与稿件关键词）：" + "、".join(TERMS[:30]) + "\n")
    if dupes:
        L.append("同 DOI 重复已跳过：" + "；".join("%s = %s" % x for x in dupes) + "\n")
    out_json = {"lang": lang, "exemplars": [e.label for e in ex], "vocab_sha": vsha, "baseline": prof["id"] if prof else None,
                "masked_terms": TERMS, "drafts": {}}
    for d in drafts:
        L.append("## %s\n" % d.label)
        dj = {}
        for g in SECS + ["all"]:
            ds = d.stats[g]
            exs = [e.stats[g] for e in ex if e.stats[g]["n"] >= 3]
            if ds["n"] < 3 or len(exs) < 3:
                continue
            flags_op, flags_fr, common = find_flags(ds, exs, a.min_count, a.ratio, top=a.top, with_common=True if g != "all" else None)
            if not (flags_op or flags_fr or common):
                continue
            L.append("### %s（稿件 %d 句；对标 %d 篇有此节）\n" % (SEC_ZH[g], ds["n"], len(exs)))
            if flags_op:
                L.append("**稿件偏多的起句**\n")
                L.append("| 起句 | 稿件次数（占该节句子） | 对标同节上界 | 用过的对标篇数 | 稿件例句 |")
                L.append("|---|---|---|---|---|")
                for _, o, c, share, thr, n_use in flags_op[:a.top]:
                    ex1 = ds["ex_op"][o][0]
                    L.append("| %s | %d（%.0f%%） | %.0f%% | %d/%d | %s |" % (show(o), c, 100 * share, 100 * thr, n_use, len(exs),
                                                                         (ex1[:150] + ("…" if len(ex1) > 150 else "")).replace("|", "/")))
                L.append("")
            if flags_fr:
                L.append("**稿件偏多的短语框架**\n")
                L.append("| 框架 | 稿件次数 | 每千词 | 对标上界 / 中位数 | 用过的对标篇数 | 稿件例句 |")
                L.append("|---|---|---|---|---|---|")
                for _, f, c, rate, thr, med, n_use in flags_fr[:a.top]:
                    ex1 = ds["ex_fr"][f][0]
                    L.append("| %s | %d | %.2f | %.2f / %.2f | %d/%d | %s |" % (show(f), c, rate, thr, med, n_use, len(exs),
                                                                              (ex1[:150] + ("…" if len(ex1) > 150 else "")).replace("|", "/")))
                L.append("")
            if common:
                L.append("**同类文献这一节的常用起句**（使用篇数；稿件次数）：" + "；".join(
                    "%s（%d 篇；稿件 %d）" % (show(o), n, ds["op"].get(o, 0)) for o, n in common) + "\n")
                if a.snippets and not a.baseline:
                    for o, n in common[:5]:
                        for e in ex:
                            if e.stats[g]["ex_op"].get(o):
                                L.append("- %s ← %s：%s" % (show(o), e.label, snippet(e.stats[g]["ex_op"][o][0], o, lang)))
                                break
                    L.append("")
            dj[g] = {"overused_openers": [{"opener": o, "count": c, "share": round(share, 3), "exemplar_upper": round(thr, 3), "exemplar_papers": n}
                                          for _, o, c, share, thr, n in flags_op[:a.top]],
                     "overused_frames": [{"frame": f, "count": c, "per1000": round(rate, 2), "exemplar_upper": round(thr, 2), "exemplar_median": round(med, 2),
                                          "exemplar_papers": n} for _, f, c, rate, thr, med, n in flags_fr[:a.top]],
                     "common_openers": [{"opener": o, "papers": n, "draft_count": ds["op"].get(o, 0)} for o, n in common]}
        out_json["drafts"][d.label] = dj
    write_fresh(rep, "\n".join(L) + "\n")
    if jsn:
        write_fresh(jsn, json.dumps(out_json, ensure_ascii=False, indent=1))
    n_flag = sum(len(v["overused_openers"]) + len(v["overused_frames"]) for dj in out_json["drafts"].values() for v in dj.values())
    print("对标 %d 篇；偏多的起句与框架共 %d 项（描述性筛查，不是质量判定）。报告：%s" % (len(ex), n_flag, rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
