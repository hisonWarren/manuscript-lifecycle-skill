#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
display_terms.py — 读者看到的表、图、图注和正文里，有没有分析代码、内部分类值，以及前后不一的数字写法。

  python display_terms.py scan 稿件.md|docx [补充材料.md|docx …] [--tables 表.csv|md …] [--legends 图注.md …]
         [--figures 图.svg|pdf|png …] [--figure-text 图内文字.txt …] [--terms display_terms.csv] [--report out.md] [--json out.json]
  python display_terms.py apply 分析表.csv --terms display_terms.csv --out 投稿表.csv
         [--columns 列名,…] [--p-columns 列名,…] [--p-style apa|leading] [--decimals 列名=2,…] [--minus unicode] [--draft]
  python display_terms.py template [--scan scan.json] [--from-tables 分析表.csv …] [--terms 已有登记表.csv] --out 待填登记表.csv

为什么要有它：分析 CSV 的分类值（all_retained、arm_b_pp、primary、vpp）会原样流进投稿表格。只禁下划线不够：
primary、vpp 没有下划线照样难懂；公式里的 a_i、DOI 和数据字段说明里的下划线又是合理的。做法：数据与代码保留原 ID；
读者看到的表头、行名、图例、坐标轴、图注一律用登记过的显示名（display_terms.csv：internal_id、publication_label、
definition、source_locator、applies_to、status、aliases）；未登记的 ID 不原样输出，报待处理。
登记过的 ID 怎样算出现：代码式 ID（含下划线、加号、数字或驼峰）在表、图注、图内文字和正文里都查；普通单词式 ID
（primary、average）只在表头和单元格里按整格匹配，免得把图注里正常的 primary measure 当成代码。

scan 的规则（每条都是候选，裁决权在人）：
  DT1 MUST   表、图注、图内文字里有代码式标识（下划线或加号连接）且未登记。
  DT2 MUST   已登记的内部 ID 出现在读者看到的位置，没有换成显示名（primary、vpp 这种没有下划线的也算）。
  DT3 MUST   用到的 ID 显示名为空或未核实（status 不是 verified / author_confirmed）。
  DT8 MUST   p 值写成 0 / 0.000。
  DT2b、DT4、DT5、DT6、DT9–DT12 SHOULD：正文里的内部 ID 或代码式标识；行名是原始分类值写法（全小写、连字符、x 代替 ×）；
             非标准记号（pGG、pHolm）；分析过程史进了稿件；表格 ≥4 位小数；负号或 p 值前导零写法前后不一。
  DT7 INFO   公式变量写成下划线（a_i），排版时改下标。
  没能运行：给了图片却没法提取图内文字（无 OCR、SVG 文字已转路径）——不能算通过，逐图打开看坐标轴、图例与面板标签。
template：把 scan 查到的未登记 ID 与分析表里的分类值（--from-tables：下划线、加号、全小写短标签）列成待填登记表，
一次把整批分析输出里的内部标签列全，而不是等读者在某一张表里发现。
退出码：0 无 MUST；1 有 MUST；2 输入错误。apply 遇到未登记或未核实的标签时退出 1、不写输出；--draft 允许用未核实的显示名起草。
"""
import argparse
import collections
import csv
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402
from output_safety import output_path, write_fresh  # noqa: E402

OK_STATUS = {"verified", "author_confirmed", "confirmed", "已核实", "作者确认"}
SNAKE = re.compile(r"(?<![\w./@\\-])[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+(?![\w@\\-])")
PLUS = re.compile(r"(?<![\w+])[a-z][a-z0-9]*(?:\+[a-z][a-z0-9]*)+(?![\w+])")
CAMEL = re.compile(r"(?<![\w-])[a-z]{1,3}[A-Z][A-Za-z]+(?![\w-])")  # 至少三个字母：pGG、pHolm；OCR 噪声 oO、uV 不算
CAMEL_OK = {"pH", "mRNA", "miRNA", "siRNA", "lncRNA", "eLife", "iOS", "mV", "kHz", "mA", "dB", "kDa", "mmHg", "eGFR", "fMRI", "rTMS",
            "tDCS", "iPad", "iPhone", "mGluR", "cAMP", "cGMP", "nM", "mM", "pM", "kB", "kN", "mL", "dL", "cDNA", "tRNA", "rRNA", "mPFC", "dlPFC", "vmPFC"}
MATHVAR = re.compile(r"^[A-Za-zα-ωΑ-Ω]_")
URLDOI = re.compile(r"https?://\S+|\bdoi\s*:\s*\S+|\b10\.\d{4,9}/\S+|\S+@\S+\.\w+", re.I)
LATEX = re.compile(r"\$[^$]+\$|\\\(.+?\\\)")
REFHEAD = re.compile(r"^(?:\*\*)?\s*(?:(?:supplementary\s+)?references?|bibliography|literature\s+cited|参考文献)\b", re.I)
CAPLINE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:(?:Supplementary\s+)?(?:Table|Fig\.?|Figure)\s*S?\d+|(?:表|图)\s*S?\d+)", re.I)
NOTELINE = re.compile(r"^\s*(?:\*\*)?\s*(?:Notes?|注)\s*(?:\*\*)?\s*[.:：]", re.I)
SEP = re.compile(r"\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?")
LOWER_LABEL = re.compile(r"^[a-z][a-z]{2,}(?:[ \-+/][a-z]+)*$")
PLAIN_OK = {"yes", "no", "none", "all", "total", "mean", "median", "n/a", "na", "and", "or", "not applicable"}
X_TIMES = re.compile(r"\b[A-Za-z]+ x [A-Za-z]+\b")
NUM = re.compile(r"^[<>≤≥]?\s*[−\-]?(?:\d+\.?\d*|\.\d+)(?:[eE][−\-+]?\d+)?$")
PTEXT = re.compile(r"\bp(?:GG|Holm|perm|adj)?\s*[=<>≤≥]\s*(0?\.\d+|0|1(?:\.0+)?)(?!\d)(?!\.\d)")
PROV = re.compile(
    r"\b(?:original|existing|pre-existing|earlier|historical|legacy|prior|previous)\s+(?:project\s+)?(?:outputs?|exports?|scripts?|pipelines?|implementations?"
    r"|routines?|decomposition|(?:trial\s+)?models?|sensitivity\s+outputs?|analysis\s+files?|source\s+(?:tables?|figures?|panels?))\b"
    r"|\bsource\s+(?:tables?|figures?|panels?|outputs?|files?)\b|\b(?:was|were)\s+not\s+(?:reconstructed|retained|recovered)\b"
    r"|\bexport(?:s|ed)?\b|\bre-?run\b|\bnew\s+(?:trial\s+)?model\b|\bthe\s+added\s+(?:[\w-]+\s+)?(?:analysis|measure)\b"
    r"|\badded\s+after\s+(?:the\s+)?(?:existing|prior|previous|earlier)\b|\bhistorical\b|\bpreviously\s+established\s+(?:aligned\s+)?(?:dataset|data\s+set|pipeline)\b"
    r"|原(?:项目|始)?(?:输出|导出|脚本)|既有(?:导出|输出|脚本|分解)|源图|新增分析|未(?:重建|保留)", re.I)
DISPLAY = ("header", "cell", "caption", "figure")
LEVEL = {"DT1": "MUST", "DT2": "MUST", "DT3": "MUST", "DT8": "MUST", "DT2b": "SHOULD", "DT4": "SHOULD", "DT5": "SHOULD", "DT6": "SHOULD",
         "DT9": "SHOULD", "DT10": "SHOULD", "DT11": "SHOULD", "DT7": "INFO"}
MSG = {
    "DT1": "代码式标识出现在读者看到的表、图注或图内文字里，且没有登记显示名：%s。数据与代码保留原 ID；在 display_terms.csv 登记 publication_label、"
           "definition、source_locator 并核实后，用 display_terms.py apply 生成投稿表。同类标识要在全部表图里一起扫，不要只改被点到的那张表。",
    "DT2": "已登记的内部 ID 仍出现在读者看到的位置（没有下划线的也算）：%s。换成登记的显示名。",
    "DT3": "用到的 ID 显示名为空或未核实：%s。显示名要能在方法或原结果表里找到依据（source_locator），核实后 status 写 verified。",
    "DT2b": "正文里出现内部 ID：%s。正文用读者的说法，首次出现给定义。",
    "DT4": "表格行名像原始分类值（全小写、连字符、用 x 代替 ×）：%s。写成读者用语（Upright、Happy − neutral、Emotion × orientation），与正文和其他表一致。",
    "DT5": "正文里有代码式标识：%s。改成读者的说法；确属公式就用正式记号。",
    "DT6": "非标准记号或驼峰写法：%s。用通行写法，校正方法写进表注或括号（p, Greenhouse–Geisser corrected）。",
    "DT7": "公式变量用下划线写成代码样式：%s。排版时写成下标，变量本身不改。",
    "DT8": "p 值写成 0：%s。p 不会等于 0，写 p < .001（或按目标刊体例）。",
    "DT9": "分析过程史进了稿件：%s。读者需要的是研究做了什么（exploratory、post hoc、哪些试次纳入），不是项目里先有哪个导出、脚本或源图。保留必要披露，换成研究本身的说法。",
    "DT10": "表格里有 ≥4 位小数：%s。按量的类型统一精度（p 三位、F 两位、估计与其区间同精度），与正文一致。",
    "DT11": "负号写法不一致，表格用连字符 -，正文用 −：%s。全稿统一。",
}


def code_like(tid):
    return bool(re.search(r"[_+\d]", tid)) or any(m.group(0) not in CAMEL_OK for m in CAMEL.finditer(tid))


def is_p_header(h):
    t = h.replace("*", "").strip()
    return bool(re.search(r"(?i)(?:^|[\s(_])p(?:[\s)_]|$)", t) or re.match(r"(?i)^p(?:gg|holm|perm|adj|corr|value)", t)
                or re.search(r"(?i)p[_ ]?(?:gg|holm|value)$", t))


def load_terms(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and ("internal_id" not in rows[0] or "publication_label" not in rows[0]):
        raise ValueError("显示名登记表缺 internal_id 或 publication_label 列（模板见 assets/templates/display_terms.csv）")
    out = collections.OrderedDict()
    for r in rows:
        k = (r.get("internal_id") or "").strip()
        if k:
            out[k] = {"label": (r.get("publication_label") or "").strip(), "status": (r.get("status") or "").strip().lower(),
                      "applies_to": (r.get("applies_to") or "").strip(), "definition": (r.get("definition") or "").strip()}
    return out


def doc_segments(path):
    text = M.load_text(path)
    name = os.path.basename(path)
    segs, tables = [], []
    in_refs, prev, cur = False, "", None
    for i, raw in enumerate(text.split("\n"), 1):
        line = raw.strip()
        if not line:
            if cur is not None:
                tables.append(cur)
                cur, prev = None, "table_end"
            continue
        if line.startswith("|"):
            if SEP.fullmatch(line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            kind = "header" if cur is None else "cell"
            if cur is None:
                cur = {"file": name, "line": i, "rows": []}
            cur["rows"].append(cells)
            segs += [{"kind": kind, "file": name, "line": i, "text": c} for c in cells]
            prev = "table"
            continue
        if cur is not None:
            tables.append(cur)
            cur, prev = None, "table_end"
        if line.startswith("#"):
            ht = line.lstrip("#").strip()
            in_refs = bool(REFHEAD.match(ht))
            if CAPLINE.match(line):
                segs.append({"kind": "caption", "file": name, "line": i, "text": ht})
                prev = "caption"
            else:
                prev = "heading"
            continue
        if in_refs:
            continue
        kind = "caption" if (CAPLINE.match(line) or NOTELINE.match(line) or prev == "table_end") else "prose"
        segs.append({"kind": kind, "file": name, "line": i, "text": line})
        prev = kind
    if cur is not None:
        tables.append(cur)
    return segs, tables


def csv_segments(path):
    name = os.path.basename(path)
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f, delimiter="\t" if path.lower().endswith(".tsv") else ",") if any(c.strip() for c in r)]
    segs = [{"kind": "header" if i == 1 else "cell", "file": name, "line": i, "text": c} for i, r in enumerate(rows, 1) for c in r]
    return segs, ([{"file": name, "line": 1, "rows": rows}] if rows else [])


def line_segments(path, kind):
    name = os.path.basename(path)
    if path.lower().endswith((".docx", ".md")):
        text = M.load_text(path)
    else:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            text = f.read()
    return [{"kind": kind, "file": name, "line": i, "text": l.strip()} for i, l in enumerate(text.split("\n"), 1) if l.strip()]


def figure_segments(path, notrun):
    name, ext = os.path.basename(path), os.path.splitext(path)[1].lower()
    text = ""
    if ext == ".svg":
        with open(path, encoding="utf-8", errors="replace") as f:
            raw = f.read()
        parts = re.findall(r"<text\b[^>]*>(.*?)</text>", raw, re.S)
        if not parts:
            notrun.append("%s：SVG 里没有文本元素（文字已转成路径），图内文字没核；用 OCR 或逐图人工看" % name)
            return []
        text = "\n".join(html.unescape(re.sub(r"<[^>]+>", " ", p)) for p in parts)
    elif ext == ".pdf":
        exe = shutil.which("pdftotext")
        if not exe:
            notrun.append("%s：没有 pdftotext，图内文字没核" % name)
            return []
        p = subprocess.run([exe, "-layout", path, "-"], capture_output=True, timeout=120)
        text = p.stdout.decode("utf-8", "replace")
        if not text.strip():
            notrun.append("%s：PDF 里没有文字层，图内文字没核；用 OCR 或逐图人工看" % name)
            return []
    else:
        try:
            import pytesseract
            from PIL import Image
            text = pytesseract.image_to_string(Image.open(path))
        except Exception as e:  # 没装 OCR 时不能当作通过
            notrun.append("%s：没法 OCR（%s），图内文字没核；逐图打开看坐标轴、图例与面板标签" % (name, type(e).__name__))
            return []
    return [{"kind": "figure", "file": name, "line": i, "text": l.strip()} for i, l in enumerate(text.split("\n"), 1) if l.strip()]


def cmd_scan(a):
    paths = list(a.docs) + list(a.tables) + list(a.legends) + list(a.figure_text) + list(a.figures)
    missing = [p for p in paths + ([a.terms] if a.terms else []) if not os.path.isfile(p)]
    if missing:
        print("找不到输入：%s" % "、".join(missing), file=sys.stderr)
        return 2
    try:
        outs = {k: output_path(v, paths + ([a.terms] if a.terms else [])) for k, v in (("report", a.report), ("json", a.json)) if v}
        terms = load_terms(a.terms) if a.terms else {}
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    segs, tables, notrun = [], [], []
    for p in a.docs:
        s, t = doc_segments(p)
        segs, tables = segs + s, tables + t
    for p in a.tables:
        if p.lower().endswith((".csv", ".tsv")):
            s, t = csv_segments(p)
        else:
            s, t = doc_segments(p)
            s = [dict(x, kind=("caption" if x["kind"] == "prose" else x["kind"])) for x in s]
        segs, tables = segs + s, tables + t
    for p in a.legends:
        segs += line_segments(p, "caption")
    for p in a.figure_text:
        segs += line_segments(p, "figure")
    for p in a.figures:
        segs += figure_segments(p, notrun)
    if not segs and not notrun:
        print("not_verified：输入里没有可检查的文字", file=sys.stderr)
        return 2
    acc, unknown = collections.OrderedDict(), collections.OrderedDict()

    def put(code, f, x):
        acc.setdefault((code, f), []).append(x)
    rx_terms = {tid: re.compile(r"(?<![\w+\-])%s(?![\w+\-])" % re.escape(tid)) for tid in terms}
    for sg in segs:
        t = LATEX.sub(" ", URLDOI.sub(" ", sg["text"].replace("**", "")))
        k = sg["kind"]
        disp = k in DISPLAY
        where = "%s 第 %d 行" % (sg["file"], sg["line"])
        for tok in [m.group(0) for m in SNAKE.finditer(t)] + [m.group(0) for m in PLUS.finditer(t)]:
            if tok in terms:
                continue
            if disp:
                put("DT1", sg["file"], tok)
                unknown.setdefault(tok, where)
            else:
                put("DT7" if MATHVAR.match(tok) else "DT5", sg["file"], tok)
        for m in CAMEL.finditer(t):
            if m.group(0) not in CAMEL_OK and m.group(0) not in terms:
                put("DT6", sg["file"], m.group(0))
        for tid, row in terms.items():
            lab = row["label"]
            if lab == tid or (lab and lab in t):
                continue
            exact = t.strip() == tid
            if not (exact or rx_terms[tid].search(t)):
                continue
            if k in ("header", "cell"):
                hit = exact or code_like(tid)
            elif k in ("caption", "figure"):
                hit = code_like(tid) or bool(re.search(r"caption|figure|legend|图注|图内", row["applies_to"], re.I))
            else:
                hit = code_like(tid) or bool(re.search(r"prose|正文", row["applies_to"], re.I))
            if not hit:
                continue
            if not disp:
                put("DT2b", sg["file"], tid)
            elif not lab or row["status"] not in OK_STATUS:
                put("DT3", sg["file"], tid)
                unknown.setdefault(tid, where)
            else:
                put("DT2", sg["file"], tid)
        if k == "cell":
            c = sg["text"].replace("*", "").strip()
            if (LOWER_LABEL.match(c) or X_TIMES.search(c)) and c.lower() not in PLAIN_OK and c not in terms and not (SNAKE.search(c) or PLUS.search(c)):
                put("DT4", sg["file"], c)
        if k in ("prose", "caption"):
            for m in PROV.finditer(t):
                put("DT9", sg["file"], "…%s…（第 %d 行）" % (t[max(0, m.start() - 35):m.end() + 35].strip(), sg["line"]))
    prose_minus = any(re.search(r"−\s?\d", s["text"]) for s in segs if s["kind"] in ("prose", "caption"))
    p_styles = collections.defaultdict(list)
    for sg in segs:
        if sg["kind"] in ("prose", "caption"):
            for m in PTEXT.finditer(sg["text"]):
                v = m.group(1)
                if re.fullmatch(r"0(?:\.0+)?|\.0+", v):
                    put("DT8", sg["file"], "p = %s（第 %d 行）" % (v, sg["line"]))
                p_styles["leading" if v.startswith("0.") else "bare"].append("%s：p = %s" % (sg["file"], v))
    for tb in tables:
        rows = tb["rows"]
        if len(rows) < 2:
            continue
        header = [h.replace("*", "").strip() for h in rows[0]]
        for j, h in enumerate(header):
            isp = is_p_header(h)
            for r in rows[1:]:
                if j >= len(r):
                    continue
                v = r[j].replace("*", "").strip().replace(",", "")
                if not NUM.match(v):
                    continue
                core = v.lstrip("<>≤≥ ")
                if isp:
                    try:
                        x = float(core.replace("−", "-"))
                    except ValueError:
                        x = None
                    if x == 0 and v[:1] not in "<≤":
                        put("DT8", tb["file"], "%s 列 %s" % (h, r[j].strip()))
                    p_styles["leading" if re.match(r"^0\.\d", core) else "bare"].append("%s：%s 列 %s" % (tb["file"], h, r[j].strip()))
                d = re.search(r"\.(\d+)$", core)
                if d and len(d.group(1)) >= 4 and "e" not in core.lower():
                    put("DT10", tb["file"], "%s 列 %s" % (h, r[j].strip()))
                if core.startswith("-") and prose_minus:
                    put("DT11", tb["file"], "%s 列 %s" % (h, r[j].strip()))
    items = []
    for (code, f), ex in acc.items():
        uniq = list(dict.fromkeys(ex))
        items.append({"level": LEVEL[code], "code": code, "file": f, "msg": MSG[code] % "、".join(uniq[:8]) + ("（共 %d 种）" % len(uniq) if len(uniq) > 8 else ""),
                      "examples": uniq[:8], "count": len(uniq)})
    if p_styles.get("leading") and p_styles.get("bare"):
        items.append({"level": "SHOULD", "code": "DT12", "file": "全部输入", "msg": "p 值前导零写法不一致（如 %s 与 %s）。按目标刊体例全稿统一。" % (
            p_styles["leading"][0], p_styles["bare"][0]), "examples": p_styles["leading"][:3] + p_styles["bare"][:3], "count": 2})
    order = {"MUST": 0, "SHOULD": 1, "INFO": 2}
    items.sort(key=lambda i: (order[i["level"]], i["code"], i["file"]))
    must = sum(i["level"] == "MUST" for i in items)
    L = ["# 读者用语与数字写法（display_terms）", "", "检查了 %d 个文件；显示名登记 %d 条。表、图注与图内文字是读者看到的位置，按 MUST 处理；正文按 SHOULD。" % (
        len(paths), len(terms)), ""]
    for lvl in ("MUST", "SHOULD", "INFO"):
        sel = [i for i in items if i["level"] == lvl]
        if sel:
            L += ["## %s" % lvl, ""] + ["- **%s**（%s）%s" % (i["code"], i["file"], i["msg"]) for i in sel] + [""]
    if notrun:
        L += ["## 没能运行（不能算通过）", ""] + ["- " + x for x in notrun] + [""]
    L.append("通过只说明这些形式问题没被看到；表图是否独立可读，仍要渲染后逐张看。")
    rep = "\n".join(L) + "\n"
    data = {"items": items, "notrun": notrun, "unknown_ids": [{"id": k, "where": v} for k, v in unknown.items()],
            "files": [os.path.basename(p) for p in paths], "terms": len(terms)}
    if "report" in outs:
        write_fresh(outs["report"], rep)
    if "json" in outs:
        write_fresh(outs["json"], json.dumps(data, ensure_ascii=False, indent=1))
    print("display_terms：MUST %d、SHOULD %d、没能运行 %d；未登记或未核实的 ID %d 个。" % (
        must, sum(i["level"] == "SHOULD" for i in items), len(notrun), len(unknown)))
    if not outs:
        print(rep[:4000])
    return 1 if must else 0


def fmt_p(v, style):
    s = v.strip()
    try:
        x = float(s.lstrip("<>≤≥ ").replace("−", "-"))
    except ValueError:
        return v
    if s[:1] in "<>≤≥":
        return v
    lead = "0" if style == "leading" else ""
    if x < 0.001:
        return "<%s.001" % lead
    if x >= 0.9995:
        return ">%s.999" % lead
    out = "%.3f" % x
    return out if style == "leading" else out[1:] if out.startswith("0") else out


def fmt_dec(v, d):
    s = v.strip()
    neg = s.startswith(("-", "−"))
    try:
        x = abs(float(s.replace("−", "-")))
    except ValueError:
        return v
    return ("−" if neg and round(x, d) != 0 else "") + ("%.*f" % (d, x))


def cmd_apply(a):
    for p in [a.table] + ([a.terms] if a.terms else []):
        if not os.path.isfile(p):
            print("找不到输入：%s" % p, file=sys.stderr)
            return 2
    try:
        out = output_path(a.out, [a.table] + ([a.terms] if a.terms else []))
        terms = load_terms(a.terms) if a.terms else {}
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    with open(a.table, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]
    if len(rows) < 2:
        print("表格为空或只有表头", file=sys.stderr)
        return 2
    header, data = rows[0], rows[1:]

    def num(v):
        return bool(v.strip()) and bool(NUM.match(v.strip().replace(",", "")))
    if a.columns:
        names = [c.strip() for c in a.columns.split(",") if c.strip()]
        bad = [c for c in names if c not in header]
        if bad:
            print("表头里没有这些列：%s" % "、".join(bad), file=sys.stderr)
            return 2
        cols = [header.index(c) for c in names]
    else:
        cols = [j for j in range(len(header)) if sum(1 for r in data if j < len(r) and r[j].strip() and not num(r[j])) >= max(1, len(data) // 2)]
    unresolved = []

    def map_cell(v, where):
        key = v.strip()
        if not key:
            return v
        t = terms.get(key)
        if t:
            if not t["label"]:
                unresolved.append("%s（%s：没有显示名）" % (key, where))
                return v
            if t["status"] not in OK_STATUS and not a.draft:
                unresolved.append("%s（%s：显示名未核实，status=%s）" % (key, where, t["status"] or "空"))
                return v
            return t["label"]
        if SNAKE.search(key) or PLUS.search(key) or any(m.group(0) not in CAMEL_OK for m in CAMEL.finditer(key)):
            unresolved.append("%s（%s：未登记）" % (key, where))
        return v
    new_header = [map_cell(h, "表头") for h in header]
    pcols = {header.index(c.strip()) for c in (a.p_columns or "").split(",") if c.strip() in header}
    dec = {}
    for x in (a.decimals or "").split(","):
        if "=" in x and x.split("=")[0].strip() in header:
            dec[header.index(x.split("=")[0].strip())] = int(x.split("=")[1])
    new_rows = []
    for i, r in enumerate(data, 2):
        r = r + [""] * (len(header) - len(r))
        nr = list(r)
        for j in cols:
            nr[j] = map_cell(r[j], "第 %d 行 %s 列" % (i, header[j]))
        for j in pcols:
            nr[j] = fmt_p(r[j], a.p_style)
        for j, d in dec.items():
            nr[j] = fmt_dec(r[j], d)
        if a.minus == "unicode":
            nr = [re.sub(r"(?<![\w.])-(?=\d|\.\d)", "−", c) for c in nr]
        new_rows.append(nr)
    if unresolved:
        u = list(dict.fromkeys(unresolved))
        print("没有写出 %s：%d 个标签不能转成正式显示名。在显示名登记表里补齐 publication_label、definition、source_locator，核实后 status 写 verified 再重跑：" % (a.out, len(u)))
        for x in u[:40]:
            print("- " + x)
        return 1
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(new_header)
    w.writerows(new_rows)
    write_fresh(out, buf.getvalue())
    print("已写出 %s（%d 行）；原表未改动。%s" % (out, len(new_rows), "注意：--draft 用了未核实的显示名，投稿前核实后重跑。" if a.draft else ""))
    return 0


def table_ids(paths):
    """从分析表里收集像内部标签的分类值与列名：下划线、加号、x 代替 ×、全小写短标签。"""
    ids = collections.OrderedDict()
    for p in paths:
        _, tabs = csv_segments(p) if p.lower().endswith((".csv", ".tsv")) else doc_segments(p)
        name = os.path.basename(p)
        for tb in tabs:
            rows = tb["rows"]
            if not rows:
                continue
            for j, raw in enumerate(rows[0]):
                h = raw.strip()
                if h and (SNAKE.search(h) or PLUS.search(h) or (LOWER_LABEL.match(h) and h.lower() not in PLAIN_OK)):
                    ids.setdefault(h, "%s 表头" % name)
            for r in rows[1:]:
                for j, c in enumerate(r):
                    v = c.strip()
                    if not v or NUM.match(v.replace(",", "")):
                        continue
                    col = rows[0][j] if j < len(rows[0]) else str(j + 1)
                    toks = [m.group(0) for m in SNAKE.finditer(v)] + [m.group(0) for m in PLUS.finditer(v)]
                    for tok in toks:
                        ids.setdefault(tok, "%s 的 %s 列" % (name, col))
                    if not toks and ((LOWER_LABEL.match(v) and v.lower() not in PLAIN_OK) or X_TIMES.search(v)):
                        ids.setdefault(v, "%s 的 %s 列" % (name, col))
    return ids


def cmd_template(a):
    srcs = ([a.scan] if a.scan else []) + list(a.from_tables) + ([a.terms] if a.terms else [])
    if not (a.scan or a.from_tables):
        print("template 要给 --scan（scan 的 JSON）或 --from-tables（分析表）", file=sys.stderr)
        return 2
    miss = [p for p in srcs if not os.path.isfile(p)]
    if miss:
        print("找不到输入：%s" % "、".join(miss), file=sys.stderr)
        return 2
    try:
        out = output_path(a.out, srcs)
        known = load_terms(a.terms) if a.terms else {}
        ids = collections.OrderedDict()
        if a.scan:
            with open(a.scan, encoding="utf-8") as f:
                data = json.load(f)
            for u in data.get("unknown_ids", []):
                ids.setdefault(u["id"], u.get("where", ""))
    except (ValueError, OSError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 2
    for k, v in table_ids(a.from_tables).items():
        ids.setdefault(k, v)
    rows = [(k, v) for k, v in ids.items() if k not in known]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["internal_id", "publication_label", "definition", "source_locator", "applies_to", "status", "aliases"])
    for k, v in rows:
        w.writerow([k, "", "", "（待替换为定义出处）见于 " + v, "", "pending", ""])
    write_fresh(out, buf.getvalue())
    print("已写出 %s：%d 个待登记 ID（已登记的 %d 个跳过）。publication_label 与 definition 要从方法、原结果表或分析代码核实后填写，"
          "不要凭标签猜；读者用语本来就合适的，publication_label 照抄 internal_id 并写 verified。" % (out, len(rows), len(ids) - len(rows)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("scan")
    s.add_argument("docs", nargs="*", default=[])
    s.add_argument("--tables", nargs="*", default=[])
    s.add_argument("--legends", nargs="*", default=[])
    s.add_argument("--figures", nargs="*", default=[])
    s.add_argument("--figure-text", nargs="*", default=[])
    s.add_argument("--terms", default="")
    s.add_argument("--report", default="")
    s.add_argument("--json", default="")
    p = sub.add_parser("apply")
    p.add_argument("table")
    p.add_argument("--terms", default="")
    p.add_argument("--out", required=True)
    p.add_argument("--columns", default="")
    p.add_argument("--p-columns", default="")
    p.add_argument("--p-style", default="apa", choices=["apa", "leading"])
    p.add_argument("--decimals", default="")
    p.add_argument("--minus", default="", choices=["", "unicode"])
    p.add_argument("--draft", action="store_true")
    t = sub.add_parser("template")
    t.add_argument("--scan", default="")
    t.add_argument("--from-tables", nargs="*", default=[])
    t.add_argument("--terms", default="")
    t.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "scan":
        if not (a.docs or a.tables or a.legends or a.figures or a.figure_text):
            print("scan 至少要给一个稿件、表格、图注或图片", file=sys.stderr)
            return 2
        return cmd_scan(a)
    if a.cmd == "apply":
        return cmd_apply(a)
    if a.cmd == "template":
        return cmd_template(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
