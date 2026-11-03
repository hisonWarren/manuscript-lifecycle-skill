#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
table_style.py — 生成三线表，并检查表格版式与表注。

  python table_style.py build --csv 表.csv --title "表题" [--label "Table 1"] [--note "注释"]
         [--house nature|apa|zh] [--decimals 2] --out 表.docx
  python table_style.py check 表.docx|表.md [--house nature|apa|zh] [--report out.md] [--json out.json]

三线表：顶线、表头下横线、底线各一条，没有竖线，没有其他内部横线；表头跨页重复，数据行不跨页。
检查项：竖线、内部横线、表头重复、行跨页、同一列的小数位、p 值与区间写法、表注顺序（总说明 → 缩写 → 符号 → 概率）。
CSV 里含逗号的字段（如 "n = 1,032"）必须加英文双引号，否则列会错位：build 会直接拒绝并说明。

结构检查不能代替渲染后的逐页查看：列宽、断词、跨页表头、上下标、负号仍须打开 Word 或 PDF 实际看。
退出码：0 无 ERROR；1 有 ERROR；2 输入错误。
"""
import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
import json
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
HOUSES = {
    "nature": {"vertical": "error", "inside_h": "warn", "note_order": True},
    "apa": {"vertical": "error", "inside_h": "warn", "note_order": True},
    "zh": {"vertical": "error", "inside_h": "warn", "note_order": True},
}
P_BAD = re.compile(r"\b[pP]\s*[=＝]\s*0?\.0{3,}\b|\b[pP]\s*[=＝]\s*0\b(?!\.)")
P_OK_LT = re.compile(r"\b[pP]\s*[<＜]\s*0?\.001\b")
CI_BRACKET = re.compile(r"95%\s*CI\s*[\[\(]")
CI_DASH = re.compile(r"\b\d+\.\d+\s*[–~-]\s*\d+\.\d+\b")
NOTE_HEAD = re.compile(r"^\s*(?:\*\*)?\s*(?:Note[s]?\s*[.:：]|注\s*[:：])", re.I)
ABBR_RX = re.compile(r"\b[A-Z]{2,6}\b\s*(?:=|，指|：)|缩写")
SYM_RX = re.compile(r"(?:^|\s)[*†‡§¶]\s*[^p]|\ba\s*=|上标")
PROB_RX = re.compile(r"[*＊]{1,3}\s*[pP]\s*[<=＜＝]|[pP]\s*[<＜]\s*\.?0*[15]\b")


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def para(text, bold=False, size=20, after=60, keep_next=False):
    runs = ""
    for i, seg in enumerate(str(text).split("\n")):
        br = "<w:br/>" if i else ""
        runs += ('<w:r><w:rPr>%s<w:sz w:val="%d"/></w:rPr>%s<w:t xml:space="preserve">%s</w:t></w:r>'
                 % ("<w:b/>" if bold else "", size, br, esc(seg)))
    kn = "<w:keepNext/>" if keep_next else ""
    return ('<w:p><w:pPr>%s<w:spacing w:after="%d"/></w:pPr>%s</w:p>' % (kn, after, runs))


def cell(text, header=False, align="left", width=0):
    jc = {"left": "left", "right": "right", "center": "center"}[align]
    bot = '<w:tcBorders><w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/></w:tcBorders>' if header else ""
    wx = '<w:tcW w:w="%d" w:type="dxa"/>' % width if width else '<w:tcW w:w="0" w:type="auto"/>'
    return ('<w:tc><w:tcPr>%s%s</w:tcPr><w:p><w:pPr><w:jc w:val="%s"/><w:spacing w:after="0"/></w:pPr>'
            '<w:r><w:rPr>%s<w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
            % (wx, bot, jc, "<w:b/>" if header else "", esc(text)))


def build_table_xml(head, body, aligns):
    borders = ('<w:tblBorders>'
               '<w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
               '<w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
               '<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
               '<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
               '<w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
               '<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
               '</w:tblBorders>')
    x = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableNormal"/><w:tblW w:w="0" w:type="auto"/>%s</w:tblPr>' % borders]
    x.append('<w:tblGrid>' + ''.join('<w:gridCol w:w="%d"/>' % (9638 // len(head)) for _ in head) + '</w:tblGrid>')
    x.append('<w:tr><w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>%s</w:tr>'
             % "".join(cell(c, True, "left" if i == 0 else "center") for i, c in enumerate(head)))
    for row in body:
        x.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>%s</w:tr>'
                 % "".join(cell(c, False, aligns[i]) for i, c in enumerate(row)))
    x.append("</w:tbl>")
    return "".join(x)


def write_docx(path, title, label, head, body, aligns, note):
    head_p = para((label + "　" if label else "") + title, bold=False, size=20, after=80, keep_next=True)
    note_p = para(note, size=18, after=120) if note else ""
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="%s"><w:body>%s%s%s'
           '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
           '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>'
           '</w:body></w:document>' % (W, head_p, build_table_xml(head, body, aligns), note_p))
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument'
          '.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument'
          '.wordprocessingml.styles+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships'
            '/officeDocument" Target="word/document.xml"/></Relationships>')
    drels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships'
             '/styles" Target="styles.xml"/></Relationships>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<w:styles xmlns:w="%s"><w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
              '<w:name w:val="Normal"/></w:style>'
              '<w:style w:type="table" w:styleId="TableNormal"><w:name w:val="Normal Table"/></w:style>'
              '</w:styles>' % W)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/_rels/document.xml.rels", drels)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/document.xml", doc)


NUM = re.compile(r"^[−–-]?\d+(?:,\d{3})*(?:\.(\d+))?$")


def decimals(v):
    m = NUM.match(v.strip())
    return len(m.group(1)) if m and m.group(1) else (0 if m else None)


def fmt_num(v, nd):
    m = NUM.match(v.strip())
    if not m or nd is None:
        return v
    x = Decimal(v.strip().replace("−", "-").replace("–", "-").replace(",", ""))
    return format(x.quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP), "f")



def do_build(a):
    if a.decimals is not None and not 0 <= a.decimals <= 15:
        print("decimals 必须在 0–15 之间", file=sys.stderr)
        return 2
    if not os.path.exists(a.csv):
        print("找不到 %s" % a.csv, file=sys.stderr)
        return 2
    with open(a.csv, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]
    if len(rows) < 2:
        print("CSV 至少要有表头和一行数据", file=sys.stderr)
        return 2
    head = rows[0]
    bad = [(i + 1, len(r)) for i, r in enumerate(rows) if len(r) != len(head)]
    if bad:
        print("CSV 行列数不一致：表头 %d 列，第 %d 行 %d 列。含逗号的字段（如 n = 1,032）须加英文双引号。"
              % (len(head), bad[0][0], bad[0][1]), file=sys.stderr)
        return 2
    body = [list(r) for r in rows[1:]]
    aligns, nd_cols = [], []
    for j in range(len(head)):
        col = [r[j] for r in body]
        ds = [decimals(c) for c in col if c.strip()]
        numeric = ds and all(d is not None for d in ds)
        aligns.append("right" if numeric else "left")
        nd_cols.append(max(ds) if numeric else None)
    if a.decimals is not None:
        for j, nd in enumerate(nd_cols):
            if nd is None or j == 0 or re.fullmatch(r"p(?:[ _-]?(?:value|adj|adjusted))?|n|N|id|编号|样本量", head[j].strip(), re.I):
                continue
            for r in body:
                r[j] = fmt_num(r[j], a.decimals)
            nd_cols[j] = a.decimals
    if os.path.exists(a.out):
        print("已存在 %s：换一个输出文件名，不覆盖" % a.out, file=sys.stderr)
        return 2
    write_docx(a.out, a.title, a.label, head, body, aligns, a.note)
    print("已生成 %s（%d 行 × %d 列，三线表，表头跨页重复，行不跨页）" % (a.out, len(body), len(head)))
    if a.note:
        print("表注已写在表下。注释顺序建议：总说明 → 缩写 → 符号 → 概率（*p < .05）。")
    return 0


def onoff(el):
    return el is not None and el.get("{%s}val" % W, "true").lower() not in ("0", "false", "off")


def read_docx_tables(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for tbl in root.iter(W and "{%s}tbl" % W):
        pr = tbl.find("w:tblPr/w:tblBorders", NS)
        borders = {}
        if pr is not None:
            for ch in pr:
                borders[ch.tag.split("}")[1]] = ch.get("{%s}val" % W)
        for side in ("left", "right", "insideV", "start", "end"):
            for e in tbl.findall(".//w:tcBorders/w:" + side, NS):
                if e.get("{%s}val" % W) not in (None, "none", "nil"):
                    borders["insideV"] = e.get("{%s}val" % W)
        rows, header_repeat, cant = [], False, True
        for tr in tbl.findall("w:tr", NS):
            trpr = tr.find("w:trPr", NS)
            if trpr is not None and onoff(trpr.find("w:tblHeader", NS)):
                header_repeat = True
            if trpr is None or not onoff(trpr.find("w:cantSplit", NS)):
                cant = False
            cells, cbot = [], []
            for tc in tr.findall("w:tc", NS):
                cells.append("".join(t.text or "" for t in tc.iter("{%s}t" % W)))
                b = tc.find("w:tcPr/w:tcBorders/w:bottom", NS)
                cbot.append(b is not None and b.get("{%s}val" % W) not in (None, "none", "nil"))
            rows.append({"cells": cells, "bottom": cbot})
        out.append({"borders": borders, "rows": rows, "header_repeat": header_repeat, "cant_split": cant})
    return out, M.docx_to_md(path)


def read_md_tables(path):
    text = M.load_text(path)
    tables, cur = [], None
    for line in text.split("\n"):
        if M.TABLE_LINE.match(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if re.match(r"^:?-{3,}:?$", cells[0]):
                continue
            cur = cur or {"borders": {}, "rows": [], "header_repeat": None, "cant_split": None}
            cur["rows"].append({"cells": cells, "bottom": []})
        elif cur:
            tables.append(cur)
            cur = None
    if cur:
        tables.append(cur)
    return tables, text


def check_notes(text, house, err, warn, info):
    for line in text.split("\n"):
        s = line.strip()
        if not NOTE_HEAD.match(s):
            continue
        pos_abbr = next((m.start() for m in ABBR_RX.finditer(s)), None)
        pos_prob = next((m.start() for m in PROB_RX.finditer(s)), None)
        pos_sym = next((m.start() for m in SYM_RX.finditer(s)), None)
        if HOUSES[house]["note_order"] and pos_prob is not None:
            if pos_abbr is not None and pos_prob < pos_abbr:
                warn.append("表注顺序：概率说明（*p < …）写在缩写定义之前。顺序是总说明 → 缩写 → 符号 → 概率。｜%s" % s[:90])
            elif pos_sym is not None and pos_prob < pos_sym:
                warn.append("表注顺序：概率说明写在其他符号说明之前。｜%s" % s[:90])
        if len(s) > 400:
            info.append("表注 %d 字符：先问读者只看这张表能否读对，再决定删什么；不要为了短删掉样本量、单位或分母。｜%s" % (len(s), s[:80]))


def do_check(a):
    if not os.path.exists(a.path):
        print("找不到 %s" % a.path, file=sys.stderr)
        return 2
    house = a.house
    try:
        if a.path.lower().endswith(".docx"):
            tables, text = read_docx_tables(a.path)
        else:
            tables, text = read_md_tables(a.path)
    except (OSError, KeyError, ET.ParseError, zipfile.BadZipFile) as e:
        print("无法读取表格：%s" % e, file=sys.stderr)
        return 2
    has_note = any(NOTE_HEAD.match(l.strip()) for l in text.split("\n"))
    if not tables and not has_note:
        print("not_verified：文件里既没有表格也没有表注，不能把零检查项记为通过", file=sys.stderr)
        return 2
    err, warn, info = [], [], []
    for ti, t in enumerate(tables, 1):
        b = t["borders"]
        if not b and a.path.lower().endswith(".docx"):
            warn.append("表 %d 未显式定义边框；可能继承样式，当前无法判定三线表版式。" % ti)
        if b:
            for side, label in (("left", "左"), ("right", "右"), ("insideV", "内部竖")):
                if b.get(side) not in (None, "none", "nil"):
                    err.append("表 %d 有%s线。三线表只保留顶线、表头下横线和底线。" % (ti, label))
            if b.get("insideH") not in (None, "none", "nil"):
                warn.append("表 %d 有内部横线。只有分组栏头（spanner）下面才保留横线。" % ti)
            if b.get("top") in (None, "none", "nil") or b.get("bottom") in (None, "none", "nil"):
                err.append("表 %d 缺顶线或底线。" % ti)
            if t["rows"] and not any(t["rows"][0]["bottom"]):
                err.append("表 %d 的表头下面没有横线。" % ti)
        if t["header_repeat"] is False:
            warn.append("表 %d 的表头没有设成跨页重复。" % ti)
        if t["cant_split"] is False:
            warn.append("表 %d 有数据行可能被拆到两页（没有设“行不跨页”）。渲染后逐页确认。" % ti)
        rows = t["rows"]
        if rows:
            for j, h in enumerate(rows[0]["cells"]):
                if re.fullmatch(r"p(?:[ _-]?value)?", h.strip(), re.I):
                    for row in rows[1:]:
                        v = row["cells"][j].strip() if j < len(row["cells"]) else ""
                        if re.fullmatch(r"0(?:\.0+)?|\.0+", v):
                            err.append("表 %d 的 p 值列写成零；核对原始结果后按精度报告，不可凭空补值。" % ti)
        if len(rows) >= 3:
            ncol = len(rows[0]["cells"])
            for j in range(ncol):
                if re.fullmatch(r"p(?:[ _-]?(?:value|adj|adjusted))?", rows[0]["cells"][j].strip(), re.I):
                    continue  # Preserve small p values; fixed decimals can erase their magnitude.
                ds = [decimals(r["cells"][j]) for r in rows[1:] if j < len(r["cells"]) and r["cells"][j].strip()]
                ds = [d for d in ds if d is not None]
                if len(ds) >= 3 and len(set(ds)) > 1:
                    warn.append("表 %d 第 %d 列的小数位不一致（%s）。同一列用同一精度，除非各行是不同的量。"
                                % (ti, j + 1, "、".join(str(x) for x in sorted(set(ds)))))
    flat = " ".join(" ".join(r["cells"]) for t in tables for r in t["rows"]) + " " + text
    for m in P_BAD.finditer(flat):
        err.append("p 值写成 %s：p 不会等于 0，写 p < .001（或按目标刊体例）。" % m.group(0).strip())
    if CI_BRACKET.search(flat) and CI_DASH.search(flat):
        warn.append("同一文件里既有 95% CI [a, b] 又有 a–b 的写法。区间写法在表、正文和摘要里要一致。")
    check_notes(text, house, err, warn, info)
    L = ["# 表格版式检查：%s（体例 %s）\n" % (os.path.basename(a.path), house),
         "表格 %d 个；ERROR %d、WARN %d、INFO %d。结构检查不代替渲染后的逐页查看；house 只选择共同三线表惯例，不是期刊合规认证。\n" % (len(tables), len(err), len(warn), len(info))]
    L += ["- **ERROR** " + e for e in err] + ["- WARN " + w for w in warn] + ["- INFO " + i for i in info]
    L.append("\n仍需实际打开 Word 或 PDF 逐页看：列宽与断词、跨页表头是否重复、负号与上下标、"
             "黑白或色觉条件下能否区分、题注是否与表体分离。")
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    if a.json:
        with M.wfile(a.json) as f:
            json.dump({"tables": len(tables), "errors": err, "warnings": warn, "info": info}, f, ensure_ascii=False, indent=1)
    print(out if not (a.report or a.json) else
          "表格 %d 个；ERROR %d、WARN %d、INFO %d。结构检查不代替渲染后的逐页查看。" % (len(tables), len(err), len(warn), len(info)))
    return 1 if err else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--csv", required=True)
    b.add_argument("--title", required=True)
    b.add_argument("--label", default="")
    b.add_argument("--note", default="")
    b.add_argument("--house", default="nature", choices=sorted(HOUSES))
    b.add_argument("--decimals", type=int, default=None)
    b.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("path")
    c.add_argument("--house", default="nature", choices=sorted(HOUSES))
    c.add_argument("--report", default="")
    c.add_argument("--json", default="")
    a = ap.parse_args()
    return do_build(a) if a.cmd == "build" else do_check(a)


if __name__ == "__main__":
    sys.exit(main())
