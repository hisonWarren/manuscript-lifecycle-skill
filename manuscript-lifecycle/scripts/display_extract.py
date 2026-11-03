#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
display_extract.py — 从稿件和对标文献中抽出表题、表注、图注，生成 display_profile.py 可直接读取的清单，并标出注释的功能信号。

  python display_extract.py --draft 稿件.md [--draft ...] --exemplar 对标1.md [--exemplar ...] \
         --out display/display_corpus.json [--signals display/signals.md]

为什么需要它：display_profile 要求逐条登记来源、指纹和原文摘录，手工整理负担大，实际工作中常被跳过。
本脚本自动抽取并登记；task（图表用途）和 panels（面板数）是启发式猜测，列在 needs_review 中，人工确认后再运行
display_profile.py。确认时可直接改 JSON 里的 task/panels。
功能信号只作复核提示：解释或推论（suggesting / 表明）、方法复述（were estimated / 采用…方法）、定义与缩写、
不确定性说明（CI、SD、误差线）、样本与分母（n =）。注释的任务是让图表独立可读：定义、单位、样本、区间类型和
必要条件不能删；结论解释和方法细节通常属于正文。长度不是质量，多面板复杂图的说明本来较长。
退出码：0 已写出清单；1 稿件或对标没有抽到任何条目（清单不写出）；2 输入错误。
"""
import argparse
import collections
import hashlib
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402
from output_safety import output_path, write_fresh  # noqa: E402

FIG = re.compile(r"^(?:\*\*)?\s*(?:(?:Supplementary|Supplemental)\s+)?(?:Fig\.?|Figure)\s*S?\d+|^(?:\*\*)?\s*附?图\s*S?\d+", re.I)
TAB = re.compile(r"^(?:\*\*)?\s*(?:(?:Supplementary|Supplemental)\s+)?Table\s*S?\d+|^(?:\*\*)?\s*附?表\s*S?\d+", re.I)
NOTE_START = re.compile(r"^(?:\*\*)?\s*(?:Notes?|Abbreviations?|Legend|注释?|说明|缩写)\s*(?:\*\*)?\s*[.:：]", re.I)
NOTE_INLINE = re.compile(r"\s(?:Notes?|Abbreviations?)\s*[.:]\s|\s注\s*[:：]")
PANEL = [re.compile(r"\(([A-H])\)"), re.compile(r"（([A-H])）"), re.compile(r"(?<![A-Za-z])([A-H])\)"), re.compile(r"\bpanels?\s+([A-H])\b", re.I)]
TASKS = [("flow", r"flow ?chart|flow diagram|selection|recruitment|consort|prisma|筛选|流程"),
         ("descriptive", r"characteristic|demographic|descriptive|baseline|sample description|一般资料|人口学|描述性|基线"),
         ("correlation", r"correlation|相关"),
         ("model_fit", r"model fit|fit indices|model comparison|goodness|拟合|模型比较"),
         ("invariance", r"invariance|不变性"),
         ("variance_decomposition", r"variance (?:component|decomposition|composition)|consistency|occasion specificity|方差(?:成分|分解)"),
         ("regression", r"regression|odds ratio|hazard|predictor|logistic|回归|预测"),
         ("factor", r"loading|factor|因子|载荷"),
         ("group_difference", r"difference|comparison between|compared|差异|比较")]
# 正文里提到图表的句子（Table 1 shows… / Figure 1, X is… / (Table 3).）不是表题
BODY_REF = re.compile(r"^(?:\*\*)?\s*(?:(?:Supplementary|Supplemental)\s+)?(?:Table|Fig\.?|Figure)\s*S?\d+[a-z]?\s*(?:\([^)]*\)\s*)?"
                      r"(?:shows?|displays?|presents?|reports?|summari[sz]es|lists?|gives?|illustrates?|depicts?|provides?|contains?|also|indicates?|"
                      r"describes?|demonstrates?|compares?|reveals?|was|is|were|are|[,)\]]|and\b)", re.I)
SIG = {"interpretive": r"\b(?:suggest\w*|indicat\w* that|demonstrat\w*|reveal\w*|highlight\w*|underscor\w*|impl(?:y|ies)|consistent with)\b|表明|提示|揭示|意味着|说明了",
       "method": r"\b(?:were|was) (?:estimated|fitted|computed|calculated|derived|analy[sz]ed|modelled|modeled)\b|\busing (?:a|an|the)\b|采用.{0,10}(?:方法|模型)|经.{0,6}(?:计算|拟合|估计)",
       "definitions": r"abbreviations?\s*[:：]|\b[A-Z][A-Za-z0-9\-]{1,9}\s*(?:=|,)\s*[a-z]|\bdenotes?\b|\brefers? to\b|缩写|即|指",
       "uncertainty": r"\bCI\b|confidence interval|\bSD\b|\bSE\b|standard (?:deviation|error)|error bars?|置信区间|标准差|标准误|误差线",
       "sample": r"\b[nN]\s*=\s*\d|样本量|例数|\d+\s*(?:名|例|人)"}
SIG_RX = {k: re.compile(v, re.I) for k, v in SIG.items()}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def lang_of(s):
    c, l = len(M.CJK.findall(s)), len(M.LAT.findall(s))
    return "zh" if c and c >= l else "en"


def panels_of(s):
    letters = set()
    for rx in PANEL:
        letters.update(x.upper() for x in rx.findall(s))
    return max(1, len(letters))


def task_of(s):
    low = s.lower()
    for name, rx in TASKS:
        if re.search(rx, low):
            return name
    return "other"


def zh_trim(kind, text):
    """中文 PDF 转写：表题后面常并入表头单元格（"表3 …结果 轨迹 全样本 男生"），图题后面常并入正文。
    表题取"表N + 第一段不含空格的标题"；图题在后面出现带逗号的正文片段处截断（"注："与面板说明保留）。"""
    if len(M.CJK.findall(text)) < 4:
        return text
    if kind == "table_title":
        m = re.match(r"^((?:附\s*)?表\s*S?\d+\s*\S+)", text)
        return m.group(1) if m else text
    if kind == "figure_caption":
        for m in re.finditer(r"\s+(?=\S)", text):
            rest = text[m.end():]
            if m.start() > 6 and not re.match(r"(?:注|\(?[A-Ha-h]\)|[A-H][.．、])", rest) and re.search(r"[，,]", rest[:30]):
                return text[:m.start()]
    return text


def verifiable(text, src):
    """整段对不上原文时（页眉被删、跨页），取能逐字对上的最长前缀：整句 → 前 60 字 → 前 30 字。"""
    if text in src:
        return text
    cands = [re.split(r"(?<=[。.;；])\s", text)[0], text[:60], text[:30]]
    for c in cands:
        c = c.strip()
        if len(c) >= 8 and c in src:
            return c
    return None


def extract(path):
    """[(kind, text)]：表题、表注、图注。PDF 转写常把"Table 1."单独成行、标题在下一段，这里合并。"""
    out = []
    blocks = M.parse(M.load_text(path))
    i = -1
    while i + 1 < len(blocks):
        i += 1
        b = blocks[i]
        t = b["text"].strip()
        if not (FIG.match(t) or TAB.match(t) or NOTE_START.match(t)):
            continue
        if (FIG.match(t) or TAB.match(t)) and (BODY_REF.match(t) or t.startswith("(")):
            continue
        if (FIG.match(t) or TAB.match(t)) and len(t.split()) <= 3 and i + 1 < len(blocks):
            nt = blocks[i + 1]["text"].strip()
            if blocks[i + 1]["kind"] in ("para", "caption") and 0 < len(nt.split()) <= 60 and not (FIG.match(nt) or TAB.match(nt) or NOTE_START.match(nt)):
                t = t + " " + nt
                i += 1
            else:
                continue                      # 只有编号、没有标题，不登记
        b = dict(b, kind="caption") if (FIG.match(t) or TAB.match(t)) else b
        if b["kind"] == "caption" and FIG.match(t):
            out.append(("figure_caption", t))
        elif b["kind"] == "caption" and TAB.match(t):
            m = NOTE_INLINE.search(t)
            if m:
                out.append(("table_title", t[:m.start()].strip()))
                out.append(("table_note", t[m.start():].strip()))
            else:
                out.append(("table_title", t))
        elif b["kind"] in ("para", "table", "caption") and NOTE_START.match(t):   # 紧跟表的注释现在按 caption 切出
            out.append(("table_note", t))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draft", action="append", required=True)
    ap.add_argument("--exemplar", action="append", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--signals", default="")
    a = ap.parse_args()
    try:
        files = [("draft", os.path.abspath(p)) for p in a.draft] + [("exemplar", os.path.abspath(p)) for p in a.exemplar]
        for _, p in files:
            if not os.path.isfile(p):
                raise ValueError("找不到文件：%s" % p)
        dh = {sha(p) for r, p in files if r == "draft"}
        if any(sha(p) in dh for r, p in files if r == "exemplar"):
            raise ValueError("稿件出现在对标文献中")
        protected = [p for _, p in files]
        out = output_path(a.out, protected)
        sig_path = output_path(a.signals, protected + [str(out)]) if a.signals else None
    except (ValueError, OSError) as e:
        print("输入错误：%s" % e, file=sys.stderr)
        return 2
    base = os.path.dirname(str(out))
    records, skipped, review = [], [], []
    for fi, (role, p) in enumerate(files, 1):
        src = " ".join(M.load_text(p).split())
        head = M.load_text(p)[:6000]
        m = re.search(r"10\.\d{4,9}/[^\s\"<>)\]]+", head)
        paper = m.group(0).rstrip(".,;").lower() if m else os.path.splitext(os.path.basename(p))[0]
        digest = sha(p)
        k = collections.Counter()
        for kind, text in extract(p):
            text = zh_trim(kind, " ".join(text.split()))
            if "Open in a new tab" in text:          # PMC 网页转写残留：只取其后的说明文字
                text = text.split("Open in a new tab", 1)[1].strip()
                if len(text.split()) < 4:
                    continue
            if kind == "table_title" and len(text.split()) > 40:
                m = re.search(r"(?<=\w)[.。](?=\s)", text[12:])   # PDF 转写把表头并进表题：截到第一句
                text = text[:12 + m.start() + 1] if m else " ".join(text.split()[:40])
            v = verifiable(text, src)
            if v is None:
                skipped.append("%s：%s 摘录与原文不能逐字对应（可能是断行连字或页眉夹入），已跳过：%s" % (os.path.basename(p), kind, text[:60]))
                continue
            if v != text:
                skipped.append("%s：%s 只登记了能逐字对上的前段（%d/%d 字）：%s" % (os.path.basename(p), kind, len(v), len(text), v[:40]))
            text = v
            k[kind] += 1
            rid = "%s%d-%s-%d" % (role[0], fi, kind, k[kind])
            rec = {"id": rid, "role": role, "paper_id": paper, "path": os.path.relpath(p, base), "sha256": digest, "text": text,
                   "kind": kind, "task": task_of(text), "language": lang_of(text), "panels": panels_of(text) if kind == "figure_caption" else 1,
                   "task_source": "heuristic", "signals": {name: bool(rx.search(text)) for name, rx in SIG_RX.items()}}
            rec["signals"]["words"] = M.count_words_ws(text)
            records.append(rec)
            review.append(rid)
    nd = sum(1 for r in records if r["role"] == "draft")
    ne = sum(1 for r in records if r["role"] == "exemplar")
    if not nd or not ne:
        print("没有抽到%s的表题、表注或图注；检查标题写法（Table 1 / Fig. 1 / 表1 / 图1 / Note.）后重跑。" % ("稿件" if not nd else "对标文献"), file=sys.stderr)
        for s in skipped[:10]:
            print("  " + s, file=sys.stderr)
        return 1
    data = {"schema_version": 1, "records": records,
            "_extraction": {"tool": "display_extract", "needs_review": review,
                            "note": "task 与 panels 为启发式猜测，确认后再运行 display_profile.py；signals 只作复核提示。", "skipped": skipped}}
    write_fresh(out, json.dumps(data, ensure_ascii=False, indent=1))
    if sig_path:
        L = ["# 图注与表注的功能信号\n",
             "稿件 %d 条、对标 %d 条。task/panels 为猜测，需人工确认。信号不是错误：解释句和方法复述是复核候选；定义、不确定性和样本信息通常应当保留。\n" % (nd, ne)]
        base_kind = collections.defaultdict(list)
        for r in records:
            if r["role"] == "exemplar":
                base_kind[r["kind"]].append(r)
        L.append("| 类型 | 对标篇数 | 每篇中位词数（范围） | 含解释句的条目 | 含方法复述的条目 |")
        L.append("|---|---|---|---|---|")
        for kind, rs in sorted(base_kind.items()):
            per = collections.defaultdict(list)
            for r in rs:
                per[r["paper_id"]].append(r["signals"]["words"])
            meds = [statistics.median(v) for v in per.values()]
            L.append("| %s | %d | %.0f（%d–%d） | %d/%d | %d/%d |" % (kind, len(per), statistics.median(meds), min(meds), max(meds),
                                                               sum(r["signals"]["interpretive"] for r in rs), len(rs), sum(r["signals"]["method"] for r in rs), len(rs)))
        L.append("\n| 稿件条目 | 类型 | 猜测用途 | 面板 | 词数 | 解释 | 方法复述 | 定义 | 不确定性 | 样本 | 复核提示 |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in records:
            if r["role"] != "draft":
                continue
            s = r["signals"]
            peers = [x["signals"]["words"] for x in base_kind.get(r["kind"], [])]
            tips = []
            if s["interpretive"]:
                tips.append("解释句通常属于正文")
            if s["method"]:
                tips.append("方法细节通常属于方法节")
            if peers and s["words"] > max(peers):
                tips.append("长于全部对标条目，先查是否有可移走的内容，再查必要定义是否齐全")
            if r["kind"] == "table_note" and not (s["definitions"] or s["uncertainty"]):
                tips.append("未见缩写/符号或区间说明，确认表体是否需要")
            L.append("| %s | %s | %s | %d | %d | %s | %s | %s | %s | %s | %s |" % (r["id"], r["kind"], r["task"], r["panels"], s["words"],
                     *("是" if s[x] else "" for x in ("interpretive", "method", "definitions", "uncertainty", "sample")), "；".join(tips)))
        if skipped:
            L.append("\n未能逐字对应而跳过的摘录：\n")
            L += ["- " + x for x in skipped[:20]]
        write_fresh(sig_path, "\n".join(L) + "\n")
    print("清单：稿件 %d 条、对标 %d 条，task/panels 待人工确认后运行 display_profile.py。输出：%s" % (nd, ne, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
