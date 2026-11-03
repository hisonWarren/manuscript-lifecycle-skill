#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mslib.py — manuscript-lifecycle 各脚本共用的文本工具（仅标准库，Python 3.8+）。

读取 md/txt/docx。docx 默认取"接受全部修订"后的文字；--original 取"拒绝全部修订"，即修改前的文字（批注者在修订里
插入的说明也一并去掉）。保留标题层级与表格行。正文顶层内容控件照读；文本框只读一次并单独成段；
段落标记与表格行的修订按两种读法分别合并或去掉；Symbol 字体的符号转成对应字符。
清洗 PDF 转写的常见污染：连字、软连字符、行末断词、数字角标、表格残留。
按 IMRaD 切节：识别中英文标题，含结构式摘要的栏目；缺少 Introduction 标题时按位置补回。
另提供分段、分句、计词，数字与引文识别，分位数与中位秩，以及词表加载（assets/lexicons/*.json，可用 --lexicon 扩展）。

自检：
  python mslib.py totext 稿件.docx [--original] > 稿件.md   # Word 转 Markdown
  python mslib.py sections 文件.md                          # 看切节结果
  python mslib.py annotations 稿件.docx [--json 批注.json]   # 批注（锚定文字、回复、是否解决）与逐条修订
切错的节会污染全部指标，对标前必须先核对切节。
"""
import collections
import json, os, re, sys, zipfile, statistics, unicodedata, hashlib
from xml.etree import ElementTree as ET

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
LEX_DIR = os.path.join(os.path.dirname(HERE), "assets", "lexicons")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CJK = re.compile(r"[\u4e00-\u9fff]")
LAT = re.compile(r"[A-Za-z]+(?:[-'’][A-Za-z]+)*")
DIG = re.compile(r"\d+(?:[.,]\d+)*")
NUMTOK = re.compile(r"(?<![A-Za-z0-9_.])[−-]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?:[eE][+−-]?\d+)?%?")
YEAR = re.compile(r"^(?:1[89]\d\d|20\d\d)$")


# ------------------------------------------------------------------ 读取
def _docx_styles(z):
    names = {}
    try:
        root = ET.fromstring(z.read("word/styles.xml"))
    except KeyError:
        return names
    for st in root.iter(W + "style"):
        sid, nm = st.get(W + "styleId"), st.find(W + "name")
        if sid and nm is not None:
            names[sid] = nm.get(W + "val", "")
    return names


def _heading_level(name):
    s = (name or "").lower().replace(" ", "")
    if s == "title":
        return 1
    m = re.match(r"(?:heading|标题)(\d)", s)
    return int(m.group(1)) if m else 0


MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
MATH = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
# 段内不算文字的部分：段落/字符属性（含制表位定义与段落标记的修订标记）、内容控件属性、域代码。
# 文本框内容另行成段（见 _textboxes），不并进锚定它的段落。
_NOT_TEXT = {W + "pPr", W + "rPr", W + "sdtPr", W + "sdtEndPr", W + "instrText", W + "delInstrText",
             W + "fldData", W + "txbxContent"}

# Symbol 字体（Adobe Symbol 编码）：Word 用“插入符号”放进的 ≤ ± χ 等是 <w:sym w:font="Symbol" w:char="F0A3"/>，
# 老稿件也常把 a、b、c 设成 Symbol 字体来显示 α、β、χ。按编码表转成 Unicode，避免丢字或读成拉丁字母。
_SYMBOL = dict(zip(list(range(0x20, 0x7F)) + list(range(0xA0, 0xFF)), [
    0x20, 0x21, 0x2200, 0x23, 0x2203, 0x25, 0x26, 0x220B, 0x28, 0x29, 0x2217, 0x2B, 0x2C, 0x2212, 0x2E, 0x2F,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,
    0x2245, 0x391, 0x392, 0x3A7, 0x394, 0x395, 0x3A6, 0x393, 0x397, 0x399, 0x3D1, 0x39A, 0x39B, 0x39C, 0x39D, 0x39F,
    0x3A0, 0x398, 0x3A1, 0x3A3, 0x3A4, 0x3A5, 0x3C2, 0x3A9, 0x39E, 0x3A8, 0x396, 0x5B, 0x2234, 0x5D, 0x22A5, 0x5F,
    0x203E, 0x3B1, 0x3B2, 0x3C7, 0x3B4, 0x3B5, 0x3C6, 0x3B3, 0x3B7, 0x3B9, 0x3D5, 0x3BA, 0x3BB, 0x3BC, 0x3BD, 0x3BF,
    0x3C0, 0x3B8, 0x3C1, 0x3C3, 0x3C4, 0x3C5, 0x3D6, 0x3C9, 0x3BE, 0x3C8, 0x3B6, 0x7B, 0x7C, 0x7D, 0x223C,
    0x20AC, 0x3D2, 0x2032, 0x2264, 0x2044, 0x221E, 0x192, 0x2663, 0x2666, 0x2665, 0x2660, 0x2194, 0x2190, 0x2191, 0x2192, 0x2193,
    0xB0, 0xB1, 0x2033, 0x2265, 0xD7, 0x221D, 0x2202, 0x2022, 0xF7, 0x2260, 0x2261, 0x2248, 0x2026, 0x23D0, 0x23AF, 0x21B5,
    0x2135, 0x2111, 0x211C, 0x2118, 0x2297, 0x2295, 0x2205, 0x2229, 0x222A, 0x2283, 0x2287, 0x2284, 0x2282, 0x2286, 0x2208, 0x2209,
    0x2220, 0x2207, 0xAE, 0xA9, 0x2122, 0x220F, 0x221A, 0x22C5, 0xAC, 0x2227, 0x2228, 0x21D4, 0x21D0, 0x21D1, 0x21D2, 0x21D3,
    0x25CA, 0x27E8, 0xAE, 0xA9, 0x2122, 0x2211, 0x239B, 0x239C, 0x239D, 0x23A1, 0x23A2, 0x23A3, 0x23A7, 0x23A8, 0x23A9, 0x23AA,
    None, 0x27E9, 0x222B, 0x2320, 0x23AE, 0x2321, 0x239E, 0x239F, 0x23A0, 0x23A4, 0x23A5, 0x23A6, 0x23AB, 0x23AC, 0x23AD]))
_SYMBOL = {k: chr(v) for k, v in _SYMBOL.items() if v is not None}
# Wingdings 只收清单里常见的勾选框与项目符号；其他符号字体的私用区编码无法可靠还原，记为 U+FFFD 供人工核对。
_WINGDINGS = {0x6C: "\u25cf", 0x6E: "\u25a0", 0x6F: "\u25a1", 0xA7: "\u25aa", 0xA8: "\u25fb", 0xD8: "\u27a2",
              0xFB: "\u2717", 0xFC: "\u2713", 0xFD: "\u2612", 0xFE: "\u2611"}


def _sym_char(font, code):
    try:
        v = int(code or "", 16)
    except ValueError:
        return "\ufffd"
    low = v - 0xF000 if 0xF000 <= v <= 0xF0FF else v
    f = (font or "").strip().lower()
    if f == "symbol":
        return _SYMBOL.get(low, "\ufffd")
    if f == "wingdings":
        return _WINGDINGS.get(low, "\ufffd")
    if 0xE000 <= v <= 0xF8FF:
        return "\ufffd"
    return chr(v) if 0 < v < 0x110000 else "\ufffd"


def _symbol_text(s):
    return "".join(_SYMBOL.get(ord(c) - 0xF000 if 0xF000 <= ord(c) <= 0xF0FF else ord(c), c) for c in s)


def _symbol_run(r):
    rf = r.find(W + "rPr/" + W + "rFonts")
    return rf is not None and any((rf.get(W + a) or "").strip().lower() == "symbol" for a in ("ascii", "hAnsi"))


def _mc_branch(ac):
    """mc:AlternateContent 只取一支：有 Choice 取第一个 Choice，否则取 Fallback（同一图形 DrawingML 与 VML 各存一份）。"""
    for ch in ac:
        if ch.tag == MC + "Choice":
            return ch
    return ac.find(MC + "Fallback")


def _skipped(mode):
    return (W + "del", W + "moveFrom") if mode == "accept" else (W + "ins", W + "moveTo")


def _ptext(p, mode="accept"):
    """一段的文字。accept：接受全部修订（删除与移出的不算）；reject：拒绝全部修订，即修改前的文字（插入与移入的不算）。"""
    skip = _skipped(mode)
    out = []

    def walk(node, symbol):
        for ch in node:
            tag = ch.tag
            if tag in skip or tag in _NOT_TEXT:
                continue
            if tag == MC + "AlternateContent":
                br = _mc_branch(ch)
                if br is not None:
                    walk(br, symbol)
            elif tag in (W + "t", MATH + "t") or (tag == W + "delText" and mode == "reject"):
                out.append(_symbol_text(ch.text or "") if symbol else (ch.text or ""))
            elif tag in (W + "tab", W + "ptab"):
                out.append("\t")
            elif tag in (W + "br", W + "cr"):
                out.append("\n")
            elif tag == W + "sym":
                out.append(_sym_char(ch.get(W + "font"), ch.get(W + "char")))
            elif tag == W + "noBreakHyphen":
                out.append("-")
            elif tag == W + "r":
                walk(ch, _symbol_run(ch))
            else:
                walk(ch, symbol)

    walk(p, False)
    return "".join(out)


paragraph_text = _ptext


def iter_paragraphs(root):
    """root 下所有段落（含表格、文本框、脚注、批注里的），同一图形的两份只走一份。配合 paragraph_text 逐段取字。"""
    for ch in root:
        if ch.tag == MC + "AlternateContent":
            br = _mc_branch(ch)
            if br is not None:
                yield from iter_paragraphs(br)
            continue
        if ch.tag == W + "p":
            yield ch
        yield from iter_paragraphs(ch)


def _children(container, tag):
    """直接子元素中的 tag；穿过内容控件（w:sdt）与 customXml 包装，不进入嵌套表格。"""
    for ch in container:
        if ch.tag in tag:
            yield ch
        elif ch.tag == W + "sdt":
            c = ch.find(W + "sdtContent")
            if c is not None:
                yield from _children(c, tag)
        elif ch.tag in (W + "customXml", W + "sdtContent"):
            yield from _children(ch, tag)
        elif ch.tag == MC + "AlternateContent":
            br = _mc_branch(ch)
            if br is not None:
                yield from _children(br, tag)


def _textboxes(p, mode):
    found, skip = [], _skipped(mode)

    def walk(n):
        for ch in n:
            if ch.tag in skip:
                continue
            if ch.tag == MC + "AlternateContent":
                br = _mc_branch(ch)
                if br is not None:
                    walk(br)
            elif ch.tag == W + "txbxContent":
                found.append(ch)
            else:
                walk(ch)

    walk(p)
    return found


def _joins_next(p, mode):
    """段落标记的修订：接受时被删除（或移出）的标记、拒绝时被插入（或移入）的标记消失，本段与下一段合为一段。"""
    rpr = p.find(W + "pPr/" + W + "rPr")
    return rpr is not None and any(rpr.find(t) is not None for t in _skipped(mode))


def _plevel(p, styles, mode):
    ppr = p.find(W + "pPr")
    if ppr is not None and mode == "reject" and ppr.find(W + "pPrChange") is not None:
        ppr = ppr.find(W + "pPrChange").find(W + "pPr")   # 拒绝属性修订：取修订前的段落属性
    if ppr is None:
        return 0
    lvl, ps = 0, ppr.find(W + "pStyle")
    if ps is not None:
        sid = ps.get(W + "val", "")
        lvl = _heading_level(styles.get(sid, sid))
    ol = ppr.find(W + "outlineLvl")
    if not lvl and ol is not None and ol.get(W + "val", "9").isdigit() and int(ol.get(W + "val")) < 9:
        lvl = int(ol.get(W + "val")) + 1
    return lvl


def _table(tbl, styles, mode):
    """表格行列。接受时去掉被删除的行与单元格，拒绝时去掉被插入的；嵌套表格并入所在单元格，只读一次。"""
    row_mark = W + ("del" if mode == "accept" else "ins")
    cell_mark = W + ("cellDel" if mode == "accept" else "cellIns")
    rows = []
    for tr in _children(tbl, (W + "tr",)):
        trpr = tr.find(W + "trPr")
        if trpr is not None and trpr.find(row_mark) is not None:
            continue
        cells = []
        for tc in _children(tr, (W + "tc",)):
            tcpr = tc.find(W + "tcPr")
            if tcpr is not None and tcpr.find(cell_mark) is not None:
                continue
            parts = []
            for item in _flow(tc, styles, mode):
                if item[0] == "p":
                    parts.append(item[2].strip())
                else:
                    parts.extend(" ".join(c for c in row if c) for row in item[1])
            cells.append(" ".join(x for x in parts if x))
        rows.append(cells)
    return rows


def _flow(container, styles, mode):
    """容器（正文、单元格、文本框）→ [("p", 级别, 文字) | ("tbl", 行)]。
    段落标记被删除时与下一段合并，级别取合并后第一个有文字的段；文本框内容排在锚定段之后单独成段。"""
    items, group, boxes = [], [], []

    def flush():
        if group:
            items.append(("p", next((l for l, t in group if t.strip()), group[-1][0]), "".join(t for _, t in group)))
            group.clear()
        for box in boxes:
            items.extend(box)
        boxes.clear()

    for blk in _children(container, (W + "p", W + "tbl")):
        if blk.tag == W + "tbl":
            flush()
            rows = _table(blk, styles, mode)
            if rows:
                items.append(("tbl", rows))
            continue
        group.append((_plevel(blk, styles, mode), _ptext(blk, mode)))
        boxes.extend(_flow(tx, styles, mode) for tx in _textboxes(blk, mode))
        if not _joins_next(blk, mode):
            flush()
    flush()
    return items


def docx_to_md(path, mode="accept"):
    with zipfile.ZipFile(path) as z:
        styles = _docx_styles(z)
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    out = []
    for item in (_flow(body, styles, mode) if body is not None else []):
        if item[0] == "p":
            t = item[2].strip()
            if t:
                out.append(("#" * min(item[1], 6) + " " + t) if item[1] else t)
                out.append("")
        else:
            for cells in item[1]:
                out.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
            out.append("")
    return "\n".join(out)


W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"
# 批注者常把意见直接写成修订插入正文（“这一段是否……”“我也不确定”）；接受全部修订会把这些话变成正文。
_REMARK = re.compile(r"你|您|我(?![们国])|是否|吗|感觉|看看|不确定|建议(?:改|删|写|再)|请(?:作者|核|再|注意|确认)|[？?]\s*[)）\]]?\s*$"
                     r"|\b(?:I think|I'?m not sure|not sure|please|should we|could you|can you|do you|maybe we|TODO|check (?:this|whether|if))\b", re.I)
_REV_KIND = {W + "ins": "插入", W + "moveTo": "移入", W + "del": "删除", W + "moveFrom": "移出"}


def _comment_anchors(body):
    """按文档顺序收集每条批注锚定的文字（先取接受修订后的读法，为空再取修改前的）及批注所在段落。"""
    acc, rej, para, open_ids, cur = {}, {}, {}, set(), [""]

    def walk(node, rev):
        for ch in node:
            tag = ch.tag
            if tag in _NOT_TEXT:
                continue
            if tag == MC + "AlternateContent":
                br = _mc_branch(ch)
                if br is not None:
                    walk(br, rev)
            elif tag == W + "commentRangeStart":
                i = ch.get(W + "id")
                open_ids.add(i); acc.setdefault(i, []); rej.setdefault(i, []); para.setdefault(i, cur[0])
            elif tag == W + "commentRangeEnd":
                open_ids.discard(ch.get(W + "id"))
            elif tag == W + "commentReference":
                para.setdefault(ch.get(W + "id"), cur[0])
            elif tag in (W + "t", MATH + "t", W + "delText"):
                for i in open_ids:
                    if rev != "del" and tag != W + "delText":
                        acc[i].append(ch.text or "")
                    if rev != "ins":
                        rej[i].append(ch.text or "")
            elif tag in (W + "ins", W + "moveTo"):
                walk(ch, "ins")
            elif tag in (W + "del", W + "moveFrom"):
                walk(ch, "del")
            elif tag == W + "p":
                cur[0] = (_ptext(ch, "accept") or _ptext(ch, "reject")).strip()
                walk(ch, rev)
                for i in open_ids:
                    acc[i].append("\n"); rej[i].append("\n")
            else:
                walk(ch, rev)

    walk(body, None)
    clean = lambda parts: re.sub(r"\s*\n\s*", " / ", "".join(parts)).strip(" /")
    return {i: clean(acc[i]) or clean(rej[i]) for i in acc}, para


def _revision_list(body):
    """逐条修订（文档顺序）：插入、删除、移动、段落合并/拆分、表格行增删、格式。同一段里相邻、同类、同作者的碎片合为一条。"""
    out, rows = [], {}
    for tr in body.iter(W + "tr"):
        trpr = tr.find(W + "trPr")
        for tag, kind, mode in ((W + "ins", "插入表格行", "accept"), (W + "del", "删除表格行", "reject")):
            m = trpr.find(tag) if trpr is not None else None
            first = next(tr.iter(W + "p"), None)
            if m is not None and first is not None:
                cells = [" ".join(_ptext(q, mode).strip() for q in tc.iter(W + "p")).strip() for tc in _children(tr, (W + "tc",))]
                rows[id(first)] = dict(type=kind, author=m.get(W + "author", ""), date=m.get(W + "date", ""), text=" | ".join(cells))
    for p in iter_paragraphs(body):
        ctx = (_ptext(p, "accept") or _ptext(p, "reject")).strip()[:160]
        if id(p) in rows:
            out.append(dict(rows.pop(id(p)), paragraph=ctx))
        ppr = p.find(W + "pPr")
        if ppr is not None:
            mark = ppr.find(W + "rPr")
            for tag, kind in ((W + "del", "段落合并"), (W + "moveFrom", "段落合并"), (W + "ins", "段落拆分"), (W + "moveTo", "段落拆分")):
                m = mark.find(tag) if mark is not None else None
                if m is not None:
                    out.append(dict(type=kind, author=m.get(W + "author", ""), date=m.get(W + "date", ""), text="", paragraph=ctx))
            m = ppr.find(W + "pPrChange")
            if m is not None:
                out.append(dict(type="段落格式", author=m.get(W + "author", ""), date=m.get(W + "date", ""), text="", paragraph=ctx))
        last = [None]

        def push(kind, el, text):
            prev = out[last[0]] if last[0] is not None else None
            if prev is not None and prev["type"] == kind and prev["author"] == el.get(W + "author", ""):
                prev["text"] += text
            else:
                out.append(dict(type=kind, author=el.get(W + "author", ""), date=el.get(W + "date", ""), text=text, paragraph=ctx))
                last[0] = len(out) - 1

        def walk(node):
            for ch in node:
                tag = ch.tag
                if tag in _NOT_TEXT or tag == W + "p":
                    continue
                if tag == MC + "AlternateContent":
                    br = _mc_branch(ch)
                    if br is not None:
                        walk(br)
                elif tag in _REV_KIND:
                    push(_REV_KIND[tag], ch, _ptext(ch, "accept" if _REV_KIND[tag] in ("插入", "移入") else "reject"))
                elif tag == W + "r":
                    rpr = ch.find(W + "rPr")
                    chg = rpr.find(W + "rPrChange") if rpr is not None else None
                    if chg is not None:
                        push("格式", chg, _ptext(ch, "accept"))
                    elif _ptext(ch, "accept").strip():
                        last[0] = None
                else:
                    walk(ch)

        walk(p)
    return out


def docx_annotations(path):
    """Word 的批注与逐条修订。批注给出锚定文字、所在段落、回复关系与是否已解决；修订中疑似把说明写进正文的插入标 remark。"""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
        croot = ET.fromstring(z.read("word/comments.xml")) if "word/comments.xml" in names else None
        xroot = ET.fromstring(z.read("word/commentsExtended.xml")) if "word/commentsExtended.xml" in names else None
    if body is None:
        return {"language": "", "comments": [], "revisions": []}
    lang = detect_lang(docx_to_md(path, "accept"))
    anchors, paras = _comment_anchors(body)
    comments, by_para = [], {}
    for c in (croot.findall(W + "comment") if croot is not None else []):
        cid, ps = c.get(W + "id", ""), list(iter_paragraphs(c))
        item = dict(id=cid, author=c.get(W + "author", ""), date=c.get(W + "date", ""),
                    text="\n".join(t for t in (_ptext(q, "accept").strip() for q in ps) if t),
                    anchor=anchors.get(cid, ""), paragraph=paras.get(cid, "")[:200], reply_to="", done=False)
        for q in ps:
            if q.get(W14 + "paraId"):
                by_para[q.get(W14 + "paraId")] = item
        comments.append(item)
    for ex in (xroot.iter(W15 + "commentEx") if xroot is not None else []):
        item = by_para.get(ex.get(W15 + "paraId"))
        if item is not None:
            parent = by_para.get(ex.get(W15 + "paraIdParent"))
            item["reply_to"] = parent["id"] if parent is not None else ""
            item["done"] = ex.get(W15 + "done") in ("1", "true")
    revisions = _revision_list(body)
    for e in revisions:
        e["remark"] = e["type"] in ("插入", "移入") and bool((lang == "en" and CJK.search(e["text"])) or _REMARK.search(e["text"]))
    return {"language": lang, "comments": comments, "revisions": revisions}


def _annotations_cli(path, json_out=None):
    res = docx_annotations(path)
    cut = lambda s, n=160: (s[:n] + "…") if len(s) > n else s
    cs, rv = res["comments"], res["revisions"]
    print("批注 %d 条（已标记解决 %d）" % (len(cs), sum(c["done"] for c in cs)))
    for c in cs:
        head = "[%s] %s %s%s%s" % (c["id"], c["author"], c["date"][:10], "，回复 [%s]" % c["reply_to"] if c["reply_to"] else "", "，已解决" if c["done"] else "")
        print(head)
        print("    锚定：" + (cut(c["anchor"]) if c["anchor"] else "（无锚定范围）所在段落：" + cut(c["paragraph"])))
        print("    批注：" + cut(c["text"].replace("\n", " / "), 300))
    kinds = collections.Counter(e["type"] for e in rv)
    flagged = [e for e in rv if e["remark"]]
    print("\n修订 %d 条：%s；疑似把说明写进正文的插入 %d 条（⚑），接受全部修订前先单独处理。" % (
        len(rv), "、".join("%s %d" % kv for kv in kinds.most_common()) or "无", len(flagged)))
    for e in rv:
        print("- %s%s［%s］%s" % ("⚑ " if e["remark"] else "", e["type"], e["author"], "：「%s」" % cut(e["text"]) if e["text"] else ""))
        print("      段落：" + cut(e["paragraph"], 90))
    if json_out:
        try:
            with wfile(json_out) as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
        except FileExistsError:
            print("输出文件已存在，不覆盖：" + json_out, file=sys.stderr)
            return 2
    return 0


LIG = {"\ufb01": "fi", "\ufb02": "fl", "\ufb00": "ff", "\ufb03": "ffi", "\ufb04": "ffl"}


# PDF 符号字体常把空格、项目符号转成私用区字符（如 U+F020、U+F0B7）；它们粘在标题末尾时会让「引言」识别失败。
PUA = re.compile("[\ue000-\uf8ff]")


def normalize(t):
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    for k, v in LIG.items():
        t = t.replace(k, v)
    t = re.sub("\u00ad\\s*", "", t)
    t = PUA.sub(" ", t)
    t = re.sub("[\u00a0\u2009\u2002\u2003\u202f\u3000]", " ", t)
    return re.sub(r"<!--.*?-->", "", t, flags=re.S)


def load_raw(path, original=False):
    """未经清洗的文字：查零宽字符、对话残留等交付痕迹时用，清洗会把它们抹掉。"""
    if os.path.splitext(path)[1].lower() == ".docx":
        return docx_to_md(path, "reject" if original else "accept")
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def load_text(path, original=False):
    if os.path.splitext(path)[1].lower() == ".docx":
        return normalize(docx_to_md(path, "reject" if original else "accept"))
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return normalize(f.read())


# ------------------------------------------------------------------ 切节
NUM_PREFIX = re.compile(r"^(?:#{1,6}\s*)?(?:\*\*)?\s*(?:\d+(?:\.\d+)*\.?|[IVXLC]+\.|[一二三四五六七八九十]+[、.．]|（[一二三四五六七八九十]+）|第[一二三四五六七八九十\d]+[章节部分])?\s*")
SECTION_RULES = [
    ("references", r"references?|bibliography|literature cited|works cited|reference list|参\s*考\s*文\s*献"),
    ("abstract", r"abstract|structured abstract|summary|摘\s*要|中文摘要"),
    ("introduction", r"introduction|background|引\s*言|前\s*言|绪\s*论|问题提出|研究背景"
     r"|问题的提出|研究缘起|文献综述|文献回顾|研究综述|相关研究|研究现状|理论基础|理论框架|研究假设"
     r"|(?:文献综述|文献回顾|理论基础|问题提出)与(?:研究假设|分析框架|理论框架)"),
    ("methods", r"methods?|materials? and methods?|methods? and materials?|methodology|patients and methods|subjects and methods|participants and methods|研究方法|对象与方法|材料与方法|资料与方法|研究对象与方法|实验方法|方法与材料|方\s*法"
     r"|研究设计|研究框架|研究设计与方法|(?:研究)?(?:数据|资料)(?:来源)?与(?:研究)?方法|研究方法与(?:过程|数据|结果)|(?:研究|实验)设计与实施"),
    ("results", r"results?(?: and discussion)?|findings|结\s*果|研究结果|实验结果|结果与分析|结果分析"
     r"|结果呈现|研究发现|主要发现|调查(?:结果|发现)|元分析结果|(?:数据)?分析(?:与)?结果|实证(?:结果|分析)|研究结果与分析|实验结果与分析|结果与讨论"),
    ("discussion", r"(?:general )?discussion(?: and conclusions?)?|讨\s*论|总讨论|综合讨论|总体讨论|一般讨论|讨论与分析|讨论与结论|讨论和结论|讨论与展望|讨论首段|讨论第一段"
     r"|讨论与(?:思考|反思|启示|建议)|分析与讨论|研究讨论|简要讨论|结论与讨论|结论与局限|研究结论与展望"),
    ("limitations", r"(?:strengths?,? (?:and|&) )?limitations?(?: (?:and|&) strengths?)?(?: of (?:the|this|our) study)?|study limitations(?: and generali[sz]ability)?|(?:研究)?(?:的)?局限(?:性)?(?:与|和|及)?(?:未来)?(?:研究)?(?:展望|方向)?|研究意义、局限与展望|(?:研究)?不足(?:与|和|及)?(?:未来)?(?:研究)?(?:展望)?|(?:当前)?研究(?:的)?(?:贡献|意义)?(?:、局限)?(?:及|与|和)(?:未来)?(?:研究)?展望|优势与局限|研究的?优势与局限"),
    ("conclusion", r"conclusions?|concluding remarks|summary and conclusions?|结\s*论|小\s*结|结论与展望|研究结论|主要结论|结论与建议|结论与启示"
     r"|结\s*语|结束语|总结与展望|研究结论与(?:启示|建议)|结论与(?:思考|反思)|结论和启示|启示与建议|对策与建议|研究启示"),
    ("front", r"highlights|keywords?(?:\s*[:：].*)?|key\s*words(?:\s*[:：].*)?|关键词.*"),
    ("back", r"acknowledge?ments?|funding.*|role of (?:the )?funding source.*|sources? of funding.*|declarations?.*|conflicts? of interest.*|competing interests?.*|author(?:s'?)? contributions?.*|credit author.*|data (?:and code )?availability.*|ethic.*|supplementary (?:material|materials|information|data).*|supporting information|appendix.*|abbreviations|tables?|figures?|figure (?:legends|captions)|table (?:legends|captions)|declaration of .*|致\s*谢|基金.*|利益冲突.*|作者贡献.*|附\s*录.*|伦理.*"),
]
_RULES = [(k, re.compile(r"(?:%s)\s*[:：.]?$" % p, re.I)) for k, p in SECTION_RULES]
METHODS_SUB = re.compile(r"(?:participants?|patients|subjects|sample|samples|setting|study (?:design|population|sample)|design|procedures?|measures?|measurements?|instruments?|materials|data (?:collection|sources?)|statistical analys[ie]s|data analys[ie]s|analytic(?:al)? (?:strategy|approach)|analysis strategy|analyses|被试|研究对象|对象|样本|程序|测量(?:工具)?|研究工具|统计(?:学)?分析|数据分析|研究设计|实验设计|实验材料|实验流程|实验程序|材料与程序|刺激材料)\b.*", re.I)
TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$|^\s*\|?\s*:?-{3,}:?\s*\|")
CAPTION = re.compile(r"^(?:\*\*)?\s*(?i:(?:Supplementary\s+|Supplemental\s+)?(?:Table|Fig\.?|Figure))\s*S?\d+[A-Za-z]?(?:\s*[.:：|]|\s*\*\*|\s*$|\s+[A-Z(\[])"
                     r"|^(?:\*\*)?\s*(?:表|图|附表|附图)\s*S?\d+[A-Za-z]?(?:\s*[.:：|]|\s*$|\s+(?![显表列给呈可为中示])\S)")
# 中文期刊常写成“[摘要]”“【关键词】”，方括号后只跟一个空格
KEYWORDS = re.compile(r"^(?:\*\*)?\s*(?:(?:keywords?|key words|关键词|关键字)\s*(?:\*\*)?\s*(?:[:：]|\s{2,})|[\[［【〔]\s*(?:关键词|关键字)\s*[\]］】〕])", re.I)
INLINE_ABS = re.compile(r"^(?:\*\*)?\s*(?:[\[［【〔]\s*摘\s*要\s*[\]］】〕]|摘\s*要)\s*(?:\*\*)?\s*[:：]?\s*(.*)$")
ABS_LABELS = {"introduction", "methods", "results", "conclusion", "limitations", "discussion"}
# PDF 转写的分页标记与期刊页眉：跳过整行且不打断段落，否则页面边界会伪造段落、标题和"跨节重复"。
PAGE_MARK = re.compile(r"^(?:#{1,6}\s*)?(?:第\s*\d+\s*页|page\s+\d+(?:\s+of\s+\d+)?|\d{1,4})\s*$", re.I)
RUNNING_HEAD = re.compile(r"^\d{4}\s*年\s*\d{1,2}\s*月\s*$|^\d{1,4}\s+(?:[\u4e00-\u9fff]\s*){2,14}第\s*\d+\s*卷\s*$|^(?:[\u4e00-\u9fff]\s*){2,14}第\s*\d+\s*卷.{0,20}\d{1,4}\s*$")
# 中文期刊常不用标题样式：行首“一、”“（一）”的短行是标题，包括“结果呈现”“落地方向”这类主题式标题
ZH_HEAD = re.compile(r"^\s*(?:\*\*)?\s*(?:[一二三四五六七八九十]+[、．.]|（[一二三四五六七八九十]+）)\s*\S")
ZH_NUM_LINE = re.compile(r"^[−–\-+±<>=*]?\s*\d[\d.,%]*\s*(?:[<>=≤≥]\s*\d[\d.,%]*)?\s*\**$")
# 多实验/多研究论文的容器标题（实验 1、Study 2）：块内先是方法，遇到"结果"再切出
EXP_CONTAINER = re.compile(r"^(?:(?:实验|研究)\s*[一二三四五六七八九十\d]+|(?:experiment|study)\s+\d+)\b(?!.*(?:结果|讨论|result|discussion))", re.I)


def heading_text(line):
    s = NUM_PREFIX.sub("", line.strip(), count=1)
    return s.strip("*_ #").strip()


def classify_heading(h):
    # 期刊 PDF 常将整行文献表标题放进方括号；不剥普通正文的括号。
    if re.fullmatch(r"[\[［【〔]\s*参\s*考\s*文\s*献\s*[\]］】〕]\s*[:：]?", h):
        return "references"
    for k, rx in _RULES:
        if rx.match(h):
            return k
    return None


def _numeric_ratio(s):
    toks = s.split()
    if not toks:
        return 0.0
    num = sum(1 for t in toks if re.fullmatch(r"[(\[]?[−–-]?(?:\d[\d.,]*|\.\d+)%?[)\],;]*|[<>=±≤≥]+|\*+", t))
    return num / len(toks)


_STAT_IN_PROSE = re.compile(r"\b(?:[tFrzχ]|chi)\s*[²2]?\s*\(\s*\d|\bp\s*[<=>≤≥]\s*0?\.\d|Cohen|\bBF\s*\d|\b95%\s*CI|η²|\bSD\b", re.I)


def _cjk_run(s):
    return max((len(m) for m in re.findall(r"[\u4e00-\u9fff]+", s)), default=0)


def _stat_prose(s):
    """PDF 转写把结果段切成短行后，满是统计量的行看起来像表格行。含长汉字串或中文标点的行、
    以标点结尾的行内统计（t(37) = 4.35, p < 0.001,）是正文。表格行标签通常很短、没有中文句读。"""
    if _cjk_run(s) >= 8 or (len(CJK.findall(s)) >= 2 and re.search(r"[，。；：、]", s)):
        return True
    return bool(_STAT_IN_PROSE.search(s)) and bool(re.search(r"[,;.)=\[\]。，；]\s*$", s))


def _prose_block(t):
    """整段判断：中文句读或带统计量的英文句子说明这是正文段，即使数字比例高。"""
    if len(CJK.findall(t)) >= 6 and re.search(r"[，。；]", t):
        return True
    return bool(_STAT_IN_PROSE.search(t)) and len(re.findall(r"[A-Za-z]{3,}", t)) >= 4 and bool(re.search(r"[.;](?:\s|$)", t))


def _collapse_cjk(h):
    """"参  考  文  献""摘  要"这类排版空格只影响识别，归并后再判断。"""
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", h)


def _num_depth(s):
    m = re.match(r"^(?:#{1,6}\s*)?(?:\*\*)?\s*(\d+(?:\.\d+)*)\.?\s", s)
    return m.group(1).count(".") + 1 if m else None


def _running_heads(text):
    """PDF 转写的页眉页脚（期刊名、卷期、"作者 等: 题目"）在全文重复出现。出现 ≥3 次、较短、
    不是节标题、不是图表或注释开头、不以句号结尾的整行，按页眉处理。"""
    cnt = collections.Counter(l.strip() for l in text.split("\n") if 0 < len(l.strip()) <= 60)
    out = set()
    for l, c in cnt.items():
        if c < 3 or l.startswith(("|", "#")) or re.search(r"[。.!?！？;；]$", l) or re.fullmatch(r"[a-z]{1,4}", l):
            continue
        if re.match(r"^(?:\*\*)?\s*(?:notes?|注|表|图|附表|附图|table|fig|figure|supplementary)", l, re.I):
            continue
        h = _collapse_cjk(heading_text(l))
        if classify_heading(h) or METHODS_SUB.fullmatch(h) or EXP_CONTAINER.match(h):
            continue
        out.add(l)
    return out


def _mark_foreign(blocks):
    """中文稿里的英文摘要等大段外文：不计入中文各节的统计（参考文献除外）。"""
    paras = [b for b in blocks if b["kind"] == "para"]
    cj = sum(len(CJK.findall(b["text"])) for b in paras)
    la = sum(len(LAT.findall(b["text"])) for b in paras)
    if cj < 500 or cj < 2 * la:
        return
    for b in paras:
        if b["sec"] != "references":
            c, l = len(CJK.findall(b["text"])), len(LAT.findall(b["text"]))
            if l >= 20 and c <= 0.05 * l:
                b["kind"] = "foreign"


NOTE_START = re.compile(r"^\s*[*_]{0,2}\s*(?:Notes?|Abbreviations?|Source)\s*[*_]{0,2}\s*[.:：]|^\s*[*_]{0,2}\s*(?:注|资料来源)\s*[*_]{0,2}\s*[：:]", re.I)

# 研究设计的规范名与常见写法。section_lint、check_all 共用；认不出的设计名直接报错并列出可用名称。
DESIGNS = ("rct", "experiment", "quasi_experiment", "cohort", "cross_sectional", "case_control", "observational",
           "qualitative", "simulation", "review")
_DESIGN_ALIASES = {
    "rct": r"rct|crt|cluster[ _-]?(?:rct|randomi[sz]ed(?:[ _-]?(?:controlled[ _-]?)?trial)?|trial)|randomi[sz]ed(?:[ _-]?controlled)?(?:[ _-]?trial)?|随机对照试验|整群随机(?:对照)?试验|随机试验",
    "experiment": r"experiment(?:al)?|lab(?:oratory)?[ _-]?experiment|within[ _-]?subjects?|between[ _-]?subjects?|实验",
    "quasi_experiment": r"quasi[ _-]?experiment(?:al)?|准实验",
    "cohort": r"cohort|longitudinal|prospective(?:[ _-]?cohort)?|panel|队列|纵向|追踪",
    "cross_sectional": r"cross[ _-]?sectional|survey|横断面|问卷调查",
    "case_control": r"case[ _-]?control|病例对照",
    "observational": r"observational|registry|secondary[ _-]?data|bibliometric|scientometric|观察性|二次数据|文献计量|科学计量",
    "qualitative": r"qualitative|interview|focus[ _-]?group|质性|访谈",
    "simulation": r"simulation|monte[ _-]?carlo|模拟",
    "review": r"review|meta[ _-]?analysis|systematic[ _-]?review|scoping[ _-]?review|综述|元分析|荟萃分析",
}


def normalize_design(name):
    """把 cluster-rct、randomised、横断面 等写法映射到规范名；空串返回空串，认不出返回 None。"""
    n = (name or "").strip().lower()
    if not n:
        return ""
    for key, rx in _DESIGN_ALIASES.items():
        if re.fullmatch(rx, n, re.I):
            return key
    return None


INTRO_AIM_HEAD = re.compile(r"当前研究|本研究|研究概览|研究目的|研究假设|研究问题|问题提出|present stud|current stud|\baims?\b|hypothes|objectives?|research questions?", re.I)
INTRO_LIT_HEAD = re.compile(r"文献综述|文献回顾|相关研究|相关工作|研究现状|研究综述|理论基础|理论框架|literature review|related (?:work|research|literature)|theoretical (?:background|framework)|^background$", re.I)


def first_section_paras(blocks, sec="introduction"):
    """Paragraphs that belong to the section itself (round 15; boundary corrected in 15b).

    The parser lets unknown headings inherit the preceding section. Without a later
    methods or results heading (law, theory, engineering-method papers) the first peer
    heading ends the section. When methods or results follow (IMRaD), peer headings
    still assigned to the introduction are its subsections (theory, "The present
    study") and stay; a related-work or literature-review peer ends the introduction
    only when no aims-type peer heading exists. 15b: round 15 cut every IMRaD
    introduction at its first peer subsection (false I1 MUST, GG5 checked the wrong
    closing paragraph).
    """
    start = next((i for i, b in enumerate(blocks) if b["kind"] == "heading" and b["sec"] == sec), None)
    if start is None:
        return [b["text"] for b in blocks if b["sec"] == sec and b["kind"] == "para"]
    level = blocks[start].get("level") or 2
    rest = blocks[start + 1:]

    def peer(b):
        return b["kind"] == "heading" and (b.get("level") or 2) <= level

    peers = [b for b in rest if peer(b)]
    stop = None
    if not any(b["kind"] == "heading" and b["sec"] in ("methods", "results") for b in rest):
        stop = peers[0] if peers else None
    else:
        inner = []
        for b in peers:
            if b["sec"] != sec:
                break
            inner.append(b)
        if not any(INTRO_AIM_HEAD.search(b["text"]) for b in inner):
            stop = next((b for b in inner if INTRO_LIT_HEAD.search(b["text"].strip())), None)
    out = []
    for b in rest:
        if b is stop or (peer(b) and b["sec"] != sec):
            break
        if b["kind"] == "para" and b["sec"] == sec:
            out.append(b["text"])
    return out

def parse(text):
    """把文本切成块列表：{sec, sub, kind(heading/para/table/caption), text, level}。"""
    blocks, buf = [], []
    st = {"sec": "front", "sub": "", "abs_level": 0, "seen_refs": False, "body_seen": False, "in_study": False, "study_depth": None, "study_md": None}
    heads = _running_heads(text)
    zh_doc = detect_lang(text) == "zh"

    def flush():
        if not buf:
            return
        t = ""
        for ln in buf:
            ln = ln.strip()
            if t.endswith("-") and re.search(r"[A-Za-z]{2}-$", t) and re.match(r"[a-z]", ln):
                t = t[:-1] + ln
            else:
                t = (t + " " + ln) if t else ln
        buf.clear()
        kind, sec = "para", st["sec"]
        if KEYWORDS.match(t):
            sec = "front"            # 关键词行不计入摘要
            if st["sec"] == "abstract" and CJK.search(t):
                st["sec"] = "front"   # 中文稿关键词之后（分类号等）不算摘要
        elif CAPTION.match(t):
            kind = "caption"
        elif NOTE_START.match(t) and blocks and blocks[-1]["kind"] in ("table", "caption"):
            kind = "caption"               # 紧跟表或题注的“注 / Note.”是表注，不算所在节的正文
        elif _numeric_ratio(t) > 0.4 and len(t.split()) >= 4 and not _prose_block(t):
            kind = "table"
        blocks.append({"sec": sec, "sub": st["sub"], "kind": kind, "text": t, "level": 0, "part": st.get("part", "")})

    for raw in text.split("\n"):
        s = raw.strip()
        if not s:
            flush(); continue
        if PAGE_MARK.match(s) or RUNNING_HEAD.match(s) or s in heads:
            continue
        if zh_doc and ZH_NUM_LINE.match(s):     # 中文 PDF 转写里表格、图轴拆出来的孤立数字行
            flush()
            blocks.append({"sec": st["sec"], "sub": st["sub"], "kind": "table", "text": s, "level": 0})
            continue
        ma = INLINE_ABS.match(s)
        if ma and st["sec"] == "front":       # 中文期刊"摘  要  正文…"写在同一行
            flush()
            st["sec"], st["sub"], st["abs_level"] = "abstract", "", 0
            blocks.append({"sec": "abstract", "sub": "", "kind": "heading", "text": "摘要", "level": 2})
            if ma.group(1).strip():
                buf.append(ma.group(1).strip())
            continue
        if zh_doc and st["seen_refs"] and re.match(r"^Abstract\s*[:：]", s, re.I):
            flush()
            st["sec"], st["sub"] = "back", ""
            buf.append(s)
            continue
        if TABLE_LINE.match(s) or s.count(" | ") >= 2 or s.count("\t") >= 3 or (len(s.split()) >= 3 and _numeric_ratio(s) > 0.5 and not _stat_prose(s)):
            flush()
            blocks.append({"sec": st["sec"], "sub": st["sub"], "kind": "table", "text": s, "level": 0})
            continue
        md = re.match(r"^(#{1,6})\s+(.*)$", s)
        h = _collapse_cjk(heading_text(s))
        short = len(h.split()) <= 8 and len(h) <= 80 and not re.search(r"[.。;；]\s*$", s.rstrip("*").rstrip(":"))
        if not md and re.search(r"[，。；！？]", h):
            short = False                      # 带中文句读的是正文折行（如“伦理关怀……。高校要……”），不是标题
        zh_head = (not md) and short and len(h) <= 30 and bool(ZH_HEAD.match(s))
        key = classify_heading(h) if (md or short) else None
        if (zh_doc and st.get("mixed_methods_results") and short
                and (md or _num_depth(s) is not None or zh_head) and h.endswith("结果")
                and not re.search(r"(?:与|和|及)结果$", h)):
            key = "results"                    # 合并方法/结果节内，明确编号的结果小节另算
        if (zh_doc and not md and key == "limitations" and re.fullmatch(r"limitations?", h, re.I)
                and _num_depth(s) is None):
            key = None                         # 中文图表中的裸英文标签不转为论文局限节
        if zh_doc and not md and key in ("introduction", "methods", "results", "discussion") and not NUM_PREFIX.match(s).group(0).strip():
            key = None                         # 中文稿正文标题都有编号或样式；不带编号的“讨论”“结果”多是图中文字
        if zh_doc and key == "introduction" and st["sec"] in ("methods", "results", "discussion", "conclusion", "limitations", "study_discussion"):
            key = None                         # 方法之后的“研究假设”“文献综述”是小节，不倒回引言
        is_head = bool(md) or (key is not None and short)
        msub = (not key) and len(h.split()) <= 6 and len(h) <= 60 and bool(METHODS_SUB.fullmatch(h)) and not re.search(r"[.。]$", s)
        if zh_doc and not md and re.search(r"[,，。;；！？]", h):
            msub = False                       # “研究设计……, 要求……”是摘要/正文折行，不是小标题
        if msub and (md or short):
            is_head = True
        if zh_head:
            is_head = True                     # “一、……”“（一）……”：中文期刊不用样式的标题，主题式标题也要断开段落
        # 无标题样式的多实验容器行（"3  实验 2：认知负荷"）也是标题，否则第二个实验的方法会被并入上一个实验的结果
        if (not key) and short and len(h) <= 40 and EXP_CONTAINER.match(h) and re.match(r"^(?:#{1,6}\s*)?\d", s):
            is_head = True
        if not is_head:
            if zh_doc and KEYWORDS.match(s):
                flush()                        # 关键词行另起一段，摘要在这里结束
            buf.append(s); continue
        flush()
        level = len(md.group(1)) if md else (3 if zh_head and s.lstrip().startswith("（") else 2)
        numbered = bool(re.match(r"^(?:#{1,6}\s*)?\d", s)) or zh_head   # “一、引言”是编号标题，不是结构式摘要的栏目
        sec = st["sec"]
        if sec == "abstract" and key in ABS_LABELS:
            inside = (md and level > st["abs_level"] > 0) or (not md and not numbered) or (key == "introduction" and h.lower().startswith("background"))
            if inside:   # 结构式摘要的栏目，不切出摘要
                blocks.append({"sec": "abstract", "sub": h, "kind": "heading", "text": h, "level": level}); st["sub"] = h
                continue
        depth = _num_depth(s)
        if key == "abstract" and st["seen_refs"]:
            key = "back"                       # 中文稿参考文献后的英文摘要
        if key in ("discussion", "conclusion") and st["in_study"]:
            general = re.search(r"总|综合|总体|一般|general", h, re.I)
            deeper = ((depth is not None and st["study_depth"] is not None and depth > st["study_depth"])
                      or (md is not None and st["study_md"] is not None and level > st["study_md"])
                      or (depth is None and md is None and st["study_depth"] is None))
            if key == "conclusion" and not re.match(r"小\s*结", h):
                deeper = False
            if deeper and not general:
                key = "study_discussion"       # 多研究论文中各研究自己的讨论/小结，不并入总讨论
            else:
                st["in_study"] = False
        if key in ("references", "back"):
            st["in_study"] = False
        if key:
            st["mixed_methods_results"] = key == "methods" and h == "研究方法与结果"
            # 中文期刊常在“引言/问题提出”之后另设“相关研究/文献综述”：仍属引言，记为小节，便于区分问题陈述与综述
            st["sec"] = key; st["sub"] = h if (zh_doc and key == "introduction" and sec == "introduction") else ""
            st["part"] = h                     # 段落所在的一级标题（如“相关研究”），小节标题不覆盖它
            if key == "abstract":
                st["abs_level"] = level if md else 0
            if key in ("introduction", "methods", "results", "discussion", "conclusion"):
                st["body_seen"] = True
            if key == "references":
                st["seen_refs"] = st["body_seen"]   # 文首"Reference: YJADR…"之类的稿件信息行不算
        elif EXP_CONTAINER.match(h) and sec not in ("references", "back", "front", "abstract"):
            st["sec"] = "methods"; st["sub"] = h
            st["in_study"], st["study_depth"], st["study_md"] = True, depth, (level if md else None)
        elif msub and sec in ("front", "introduction", "abstract"):
            st["sec"] = "methods"; st["sub"] = h
        else:
            st["sub"] = h
            if zh_head and level == 2:
                st["part"] = h
        blocks.append({"sec": st["sec"], "sub": st["sub"], "kind": "heading", "text": h, "level": level})
    flush()
    _recover_intro(blocks)
    _mark_foreign(blocks)
    return blocks


def _recover_intro(blocks):
    """PDF 转写常缺 Introduction 标题：摘要（或关键词）之后、方法之前的段落归入引言。"""
    if any(b["sec"] == "introduction" and b["kind"] == "para" for b in blocks):
        return
    im = next((i for i, b in enumerate(blocks) if b["sec"] == "methods"), None)
    if im is None:
        return
    pre = [i for i in range(im) if blocks[i]["kind"] == "para" and blocks[i]["sec"] in ("front", "abstract", "back")]
    absi = [i for i in pre if blocks[i]["sec"] == "abstract"]
    if absi:
        aw = sum(count_words(blocks[i]["text"]) for i in absi)
        keep, acc = [], 0
        if aw > 450:          # 摘要吞掉了引言：只留前约 150 词作摘要
            for i in absi:
                keep.append(i); acc += count_words(blocks[i]["text"])
                if acc >= 150:
                    break
        else:
            keep = absi
        cand = [i for i in pre if i > max(keep) and i not in keep] + [i for i in absi if i not in keep]
    else:
        long_ = [i for i in pre if count_words(blocks[i]["text"]) >= 60]
        cand = long_[1:]
    for i in sorted(set(cand)):
        blocks[i]["sec"] = "introduction"; blocks[i]["sub"] = "(无标题，按位置归入)"


def section_paras(blocks, keys, kinds=("para",)):
    return [b["text"] for b in blocks if b["sec"] in keys and b["kind"] in kinds]


# ------------------------------------------------------------------ 交付残留（在未清洗文字上查）
RESIDUE = [
    ("chat", "对话残留", re.compile(
        r"\b(?:certainly|absolutely|sure)!|\bI hope this helps\b|\bas an AI(?: language model| assistant)?,? I\b|\bas a (?:large )?language model,? I\b"
        r"|\bhere is (?:a|the|your) (?:revised|rewritten|updated|improved|polished|edited) (?:version|text|paragraph|draft|manuscript)\b"
        r"|\blet me know if\b|\bfeel free to\b|\bI(?:'d| would) be (?:happy|glad) to\b|\bgreat question\b|\bknowledge cut-?off\b"
        r"|当然可以[！!，,]|希望(?:这些|以上)?(?:内容|修改|回答)?(?:对你|对您)?有(?:所)?帮助|以下是(?:修改|改写|润色|优化|修订)后的"
        r"|作为(?:一个|一名)?(?:AI|人工智能)(?:语言模型|助手|模型)?[，,]?\s*我|如有(?:需要|任何问题)[，,]?(?:请)?(?:随时)?(?:告诉|联系)我", re.I)),
    ("invisible", "零宽或不可见字符", re.compile("[\u200b\u200c\u200d\u2060\ufeff]")),
    ("field_error", "Word 域错误残留", re.compile(r"Error! (?:Reference source not found|Bookmark not defined)|错误！未找到引用源|错误！未定义书签")),
    ("emoji", "表情符号", re.compile("[\U0001F300-\U0001FAFF\u2705\u274C\u2B50]")),
]
PLACEHOLDER = re.compile(
    r"\[(?:VERIFY|TODO|TBD|INSERT|CITATION NEEDED|REF|待核|待补|待填)[^\]]*\]"
    r"|【待[补核填][^】]*】"
    # 方括号里的作者待办：[Authors to add: …]、[full reference to be added]、[待作者确认…]
    r"|\[[^\]\n]{0,120}?(?:to be (?:added|confirmed|completed|determined|supplied|filled(?: in)?|updated|inserted|provided)"
    r"|authors? to \w+|to add|to confirm|to supply|to complete"
    r"|待(?:核|补|填|定|确认|补充|填写|作者))[^\]\n]{0,120}?\]"
    r"|\bTODO\b|\bTBD\b|\bXXX+\b|待补充|待填写", re.I)


def residue_hits(raw, placeholders=False):
    """返回 [(kind, label, 行号, 命中, 上下文)]。raw 必须是未经 normalize 的文字，否则零宽字符已被抹掉。"""
    out = []
    pats = RESIDUE + ([("placeholder", "占位符", PLACEHOLDER)] if placeholders else [])
    for i, line in enumerate(raw.split("\n"), 1):
        for kind, label, rx in pats:
            for m in rx.finditer(line):
                ctx = line[max(0, m.start() - 50):m.end() + 50].strip()
                shown = m.group(0) if kind != "invisible" else "U+%04X" % ord(m.group(0))
                out.append((kind, label, i, shown, ctx))
    return out


# ------------------------------------------------------------------ 句、词、数字、引文
ABBR = ["et al.", "e.g.", "i.e.", "Fig.", "Figs.", "fig.", "vs.", "cf.", "No.", "no.", "approx.", "ca.", "Eq.", "Eqs.",
        "Ref.", "Refs.", "Vol.", "pp.", "p.", "Dr.", "Prof.", "Supp.", "Suppl.", "St.", "Inc.", "Ltd.", "Co.", "Jr.",
        "Mr.", "Ms.", "U.S.", "U.K.", "a.m.", "p.m.", "etc.", "resp.", "incl.", "esp.", "min.", "max.", "Ch."]
_ABBR_RX = re.compile("|".join(re.escape(a) for a in sorted(ABBR, key=len, reverse=True)))
SENT_EN = re.compile(r"(?<=[.!?])[\"”’)\]]*\s+(?=[A-Z0-9“\"'(\[−])")


_KEEP_ALNUM = {"lme", "nlme", "ggplot", "python", "log", "utf", "sha", "ipv", "base", "hdf"}


def _strip_glued(m):
    """词尾粘连的角标去掉；lme4、ggplot2、log10 这类名字和紧跟版本号的写法保留。"""
    if m.group(1).lower() in _KEEP_ALNUM or re.match(r"\s+v?\d+\.\d", m.string[m.end():]):
        return m.group(0)
    return m.group(1)


def strip_markers(s):
    """去掉数字角标（[12]、上标、句号后紧贴的 .12、词尾粘连的 disorders12,13），PDF 转写最常见的断句干扰。"""
    s = re.sub(r"\[\d+(?:\s*[-–,]\s*\d+)*\]", "", s)
    s = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+(?:[,–-][⁰¹²³⁴⁵⁶⁷⁸⁹]+)*", "", s)
    s = re.sub(r"(?<=[a-z)\]])\.(\d{1,3}(?:\s*[,–-]\s*\d{1,3})*)(?=\s+[A-Z])", ".", s)
    s = re.sub(r"\b([A-Za-z]*[a-z]{3})(\d{1,3}(?:[,–-]\d{1,3})*)(?=[\s,.;:)])", _strip_glued, s)
    return re.sub(r"(?<=[a-z]),\d{1,3}(?:[,–-]\d{1,3})*(?=\s)", ",", s)


# 读者看得出“审稿或改稿过程”的句子（section_lint X15、deviation_register 的 revision:trace 共用）。只是候选：
# 重新核查本身可以是方法，要写的是核查的做法与结果，不是“这次改稿时才发现”。
REVISION_TRACE = re.compile(
    r"\bre-?(?:read|reading|examin\w+|inspect\w+)\b[^.;]{0,80}\b(?:identified|revealed|showed|found|uncovered)\b"
    r"|\bwhen re-?read\b"
    r"|\b(?:during|in the course of)\s+(?:the\s+)?(?:revision(?!\s+of)|peer[- ]review|resubmission)\b"
    r"|\bin response to (?:the\s+|a\s+|an\s+)?(?:anonymous\s+)?(?:reviewers?|referees?|editors?)\b"
    r"|\b(?:as\s+)?(?:suggested|requested|pointed out|raised|noted)\s+by\s+(?:the\s+|a\s+|an\s+)?(?:anonymous\s+)?(?:reviewers?|referees?)\b"
    r"|(?:返修|修回|复审|审稿)(?:时|过程中|期间)|(?:审稿人|评审人|审稿专家)(?:提出|指出|建议|要求)|重新阅读[^。；]{0,30}(?:发现|识别)", re.I)
# 局限里回指本文其他部分或补充材料：局限只说哪条推断受什么限制，不当索引用
LIMITATION_POINTER = re.compile(
    r"\b(?:advanced|made|presented|proposed|offered|discussed|reported)\s+(?:in|above in)\s+the\s+(?:Discussion|Results|Introduction)\b"
    r"|\bSupplementary\s+(?:Tables?|Figures?|Files?|Materials?)\b|\bTables?\s+S\d|\bFigures?\s+S\d"
    r"|(?:讨论|结果|引言)(?:部分|一节|中)(?:提出|给出|报告)的|补充(?:表|图|材料)\s*S?\d*", re.I)


def count_words(s):
    return len(LAT.findall(s)) + len(DIG.findall(s)) + len(CJK.findall(s))


def count_words_ws(s):
    """期刊和 Word 的计词口径：英文按空白分隔（PHQ-9、.587–.796 各算一个词），中文按字。用于字数上限检查。"""
    c = len(CJK.findall(s))
    if c:
        return c + len(LAT.findall(CJK.sub(" ", s)))
    return len([w for w in s.split() if re.search(r"[A-Za-z0-9]", w)])


def sentences(text):
    t = strip_markers(re.sub(r"\s+", " ", text).strip())
    out = []
    for chunk in re.split(r"(?<=[。！？])", t):
        if not chunk.strip():
            continue
        prot = _ABBR_RX.sub(lambda m: m.group(0).replace(".", "\u2024"), chunk)
        prot = re.sub(r"(?<=\d)\.(?=\d)", "\u2024", prot)
        prot = re.sub(r"\b([A-Z])\.(?=\s+[A-Z][a-z])", "\\1\u2024", prot)
        for p in SENT_EN.split(prot):
            p = p.replace("\u2024", ".").strip()
            if p and count_words(p) >= 2:
                out.append(p)
    return out


def detect_lang(text):
    """短片段（中文 Highlights、投稿信、图注）也要判对语言：长文看比例，短文看是否几乎全是汉字。"""
    c, l = len(CJK.findall(text)), len(LAT.findall(text))
    return "zh" if (c > 50 and c > 1.5 * l) or (c >= 8 and c > 3 * l) else "en"


AY_PAREN = re.compile(r"[(（]([^()（）]*?(?:1[89]\d\d|20\d\d)[a-z]?[^()（）]*?)[)）]")
LABEL_BEFORE = re.compile(r"(?:tables?|figs?\.?|figures?|sections?|§|supplementary|eq\.?|equations?|step|model|study|studies|wave|time|visit|occasion|phase|hypothesis|chapter|appendix|panel|cluster|#|第|表|图)\s*[A-Z]?$", re.I)


def strip_citations(s):
    s = AY_PAREN.sub(lambda m: " " if re.search(r"[A-Za-z\u4e00-\u9fff]", m.group(1)) else m.group(0), s)
    return strip_markers(s)


def count_citations(s):
    n = 0
    for m in AY_PAREN.finditer(s):
        inner = m.group(1)
        if re.fullmatch(r"\s*(?:1[89]|20)\d\d\s*[–-]\s*(?:1[89]|20)\d\d\s*", inner):
            continue
        if re.search(r"[A-Za-z\u4e00-\u9fff]", inner):
            n += len(re.findall(r"(?:1[89]\d\d|20\d\d)[a-z]?", inner))
        else:
            n += 1
    for m in re.finditer(r"\[(\d+(?:\s*[-–,]\s*\d+)*)\]", s):
        for part in re.split(r"\s*,\s*", m.group(1)):
            r = re.match(r"(\d+)\s*[-–]\s*(\d+)", part)
            n += (int(r.group(2)) - int(r.group(1)) + 1) if r and int(r.group(2)) >= int(r.group(1)) else 1
    n += len(re.findall(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+", s))
    n += len(re.findall(r"(?<=[a-z)\]])\.\d{1,3}(?:\s*[,–-]\s*\d{1,3})*(?=\s+[A-Z])", s))
    n += len(re.findall(r"(?<=[a-z]{3})\d{1,3}(?:[,–-]\d{1,3})*(?=[\s,.;:)])", s))
    return n


VERSION = re.compile(r"(?:\b(?:version|v\.?|R|Python|SPSS|Stata|SAS|Mplus|lavaan|lme4|brms|MATLAB|JASP|jamovi|semTools|Stan)\s*\d+(?:[.\-]\d+)+|\b\d+\.\d+\.\d+(?:[.\-]\d+)*)")


def number_tokens(s):
    """返回 [(原文, 起点)]：统计意义上的数字。排除年份、表图节号、引文、软件版本号、量表名里的数字（PHQ-9、DSM-5）。"""
    t = strip_citations(s)
    t = VERSION.sub(lambda m: " " * len(m.group(0)), t)
    t = re.sub(r"\b[A-Za-z]+[-–]?\d+[A-Za-z]*\b", lambda m: " " * len(m.group(0)), t)
    out = []
    for m in NUMTOK.finditer(t):
        core = m.group(0).strip("−-%").replace(",", "")
        if YEAR.match(core):
            continue
        if LABEL_BEFORE.search(t[max(0, m.start() - 16):m.start()].rstrip()):
            continue
        out.append((m.group(0), m.start()))
    return out


def count_numbers(s):
    return len(number_tokens(s))


# ------------------------------------------------------------------ 统计
def quantile(vals, q):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    k = (len(v) - 1) * q
    f = int(k); c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def median_rank_pct(x, vals):
    v = [y for y in vals if y is not None]
    if x is None or not v:
        return None
    lo = sum(1 for y in v if y < x); eq = sum(1 for y in v if y == x)
    return round(100.0 * (lo + 0.5 * eq) / len(v), 1)


def summarize(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return None
    return {"n": len(v), "median": statistics.median(v), "q1": quantile(v, .25), "q3": quantile(v, .75),
            "min": min(v), "max": max(v), "p05": quantile(v, .05), "p95": quantile(v, .95),
            "p10": quantile(v, .10), "p90": quantile(v, .90)}


def upper_bound(s):
    """对标分布的判定上界：≥20 篇用 p95，10–19 篇用 p90，更少用最大值。"""
    if not s:
        return None
    return s["p95"] if s["n"] >= 20 else (s["p90"] if s["n"] >= 10 else s["max"])


# ------------------------------------------------------------------ 词表
def load_lexicon(lang, extra=()):
    with open(os.path.join(LEX_DIR, lang + ".json"), encoding="utf-8") as f:
        lex = json.load(f)
    for p in extra or ():
        with open(p, encoding="utf-8-sig") as f:
            add = json.load(f)
        for k, v in add.items():
            if isinstance(v, list) and isinstance(lex.get(k), list):
                lex[k] = lex[k] + v
            else:
                lex[k] = v
    return lex


def _rx_words(words, lang):
    words = [w for w in dict.fromkeys(words) if isinstance(w, str) and w]
    if not words:
        return None
    alt = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    if lang == "zh":
        return re.compile("(?:%s)" % alt, re.I)
    return re.compile(r"(?<![A-Za-z])(?:%s)(?![A-Za-z])" % alt, re.I)


def lex_rx(lex, lang):
    """词表 → 正则。键名以 _re 结尾按正则（不区分大小写），_re_cs 区分大小写，其余按词语列表。"""
    R = {}
    for k, v in lex.items():
        if isinstance(v, str) and not k.startswith("_"):
            v = [v]          # 单个正则写成字符串也接受，避免整条规则被静默跳过
        if k.startswith("_") or not isinstance(v, list) or not v or not isinstance(v[0], str):
            continue
        if k.endswith("_re_cs"):
            R[k[:-6]] = re.compile("|".join("(?:%s)" % p for p in v))
        elif k.endswith("_re"):
            R[k[:-3]] = re.compile("|".join("(?:%s)" % p for p in v), re.I | re.M)
        else:
            R[k] = _rx_words(v, lang)
    return R


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def norm_for_match(s):
    s = fold(s).replace("−", "-").replace("–", "-").replace("—", "-")
    s = re.sub(r"[^\w\u4e00-\u9fff]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def corpus_body_sha256(text):
    """论文内容指纹不含私有 YAML 目录信息；换文件名或目录标签不产生新论文。"""
    text = re.sub(r"^\ufeff?---\s*\n.*?\n---[ \t]*(?:\n|$)", "", text, count=1, flags=re.S)
    return hashlib.sha256(norm_for_match(text).encode("utf-8")).hexdigest()


def reject_pack_self_comparison(pack_dir, texts, genre=""):
    """全部基线消费者共用：原文及只改 YAML 的副本不能拿自己作参照。旧包仍核原指纹。"""
    with open(os.path.join(pack_dir, "bench_baseline.json"), encoding="utf-8") as f:
        examples = json.load(f)["exemplars"]
    examples = [e for e in examples if not genre or e.get("genre") == genre]
    full = {e.get("content_sha256") for e in examples}
    body = {e.get("body_sha256") for e in examples}
    for text in texts:
        if (hashlib.sha256(norm_for_match(text).encode("utf-8")).hexdigest() in full
                or corpus_body_sha256(text) in body):
            raise ValueError("not_verified：稿件本身或其文本副本不能作为对标文献；留一法需排除该论文并重建领域包")


def wfile(path):
    """Create a fresh report; never truncate an input or an earlier audit artifact."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    return open(path, "x", encoding="utf-8")


# ------------------------------------------------------------------ 命令行
def _cli():
    args = [a for a in sys.argv[1:] if a != "--original"]
    orig = "--original" in sys.argv
    if len(args) >= 2 and args[0] == "annotations":
        return _annotations_cli(args[1], args[args.index("--json") + 1] if "--json" in args[:-1] else None)
    if len(args) >= 2 and args[0] == "totext":
        print(load_text(args[1], original=orig)); return 0
    if len(args) >= 2 and args[0] == "sections":
        blocks = parse(load_text(args[1], original=orig))
        stats = {}
        for b in blocks:
            if b["kind"] == "heading":
                print("[%-12s] %s %s" % (b["sec"], "#" * max(b["level"], 1), b["text"][:90]))
            s = stats.setdefault(b["sec"], {"para": 0, "words": 0, "table": 0, "caption": 0})
            if b["kind"] == "para":
                s["para"] += 1; s["words"] += count_words(b["text"])
            elif b["kind"] in ("table", "caption"):
                s[b["kind"]] += 1
        print("\n%-12s%8s%8s%8s%8s" % ("节", "段落", "词数", "表格", "题注"))
        for k, s in stats.items():
            print("%-12s%8d%8d%8d%8d" % (k, s["para"], s["words"], s["table"], s["caption"]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
