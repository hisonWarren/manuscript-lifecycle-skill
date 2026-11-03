#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
revision_diff.py — 两版稿件的段落级差异：哪里改了、改前改后原文、改动量。"声称已改"必须有这里的证据。

  python revision_diff.py 旧稿.md|docx 新稿.md|docx [--report changes.md] [--csv changes.csv] [--full]

输出每处改动的位置（节 / 小标题 / 段号）、类型（修改 / 新增 / 删除）、改前、改后、词数变化与相似度，以及各节汇总。
用途：修改记录（改前原文、改后原文、位置）；核对回复信里的 Changes；确认"已改"真的落盘；检查局部修改有没有波及别处。
它不能替代 Word 的修订模式：投稿要求修订稿时，仍需在 Word 中生成真实修订（用当前环境的 Word 文档工具）。
退出码：0 有改动；1 两版相同（不得声称已修改）；2 输入错误。

包级一致性扫描（references/07 §9 第 7 条）：改动常常只落在一个文件里，别的文件还在说旧话。

  python revision_diff.py package 旧包目录|- 新包目录 [--letter 回复信] [--corrections corrections.csv] [--report r.md] [--json r.json]

读入两个目录里的 docx（按接受修订）、xlsx、md、txt、csv，同文的 clean/highlighted/tracked 只算一份。列出：
  · 悬空引用（MUST）：旧包里有、新包里已撤掉的表、图或补充文件，新包正文仍在提及（回复信里提及只提示）；
  · 已登记更正的旧说法仍在（MUST）：corrections.csv 每行 old,new[,note]，old 出现在回复信以外的任何文件；
  · 改动对象的其他提及（核对）：题注或工作表内容本轮改过的表、图，新包里一字未改的句子对它的每一处描述；
  · 改了说法的数字（核对）：同一数字在改动段里换了说法，别处一字未改、也不用新说法的出现；
  · 同一对象多种写法（核对）：同一文件里 Table S3 与 Supplementary Table S3 混用、同一软件多个版本号、统计量等号两侧空格不一；
  · 不存在的文件名（核对）：文字里写的文件名在新包里没有；
  · 包里找不到的补充对象（核对）：被引用的补充表、图在包里没有题注或工作表（不给旧包时也查）；
  · 回复信的节名（核对）：回复点名的节，正文本轮没有改动；报告另附各条点名的节，逐条对照改动所在。
xlsx 只读题注、注释行做写法检查，数据单元格（编码记录、摘要）不当作者措辞。
它只给候选，不判断哪句该改；"核对"项要逐条看过并写进修改清单。退出码：0 无发现；1 有发现；2 输入错误。
"""
import argparse, csv, difflib, hashlib, json, os, re, sys, zipfile
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

SEC_ZH = {"front": "题名页", "abstract": "摘要", "introduction": "引言", "methods": "方法", "results": "结果", "discussion": "讨论",
          "limitations": "局限", "conclusion": "结论", "references": "参考文献", "back": "文末声明/表图"}


def items(path):
    out, cnt = [], {}
    for b in M.parse(M.load_text(path)):
        if b["kind"] == "heading":
            out.append((b["sec"], b["sub"], "标题", b["text"])); continue
        cnt[b["sec"]] = cnt.get(b["sec"], 0) + 1
        out.append((b["sec"], b["sub"], "第%d段" % cnt[b["sec"]], b["text"]))
    return out


def loc(it):
    return "%s / %s / %s" % (SEC_ZH.get(it[0], it[0]), it[1] or "—", it[2])


def pair_rows(na, nb):
    """Paragraph-level alignment shared by the two-version diff and the package scan: (type, i, j, similarity)."""
    rows = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, na, nb, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        used = set()
        for i in range(i1, i2):
            best, bj = 0.0, None
            for j in range(j1, j2):
                if j in used:
                    continue
                r = difflib.SequenceMatcher(None, na[i], nb[j], autojunk=False).ratio()
                if r > best:
                    best, bj = r, j
            if bj is not None and best >= 0.45:
                used.add(bj); rows.append(("修改", i, bj, best))
            else:
                rows.append(("删除", i, None, 0.0))
        for j in range(j1, j2):
            if j not in used:
                rows.append(("新增", None, j, 0.0))
    return rows


# ------------------------------------------------------------------ 包级一致性扫描
PKG_EXT = (".docx", ".xlsx", ".md", ".txt", ".csv")
XNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
LETTER_NAME = re.compile(r"response|rebuttal|reply|回复|答复", re.I)
SUPP_NAME = re.compile(r"supp|补充|appendix|附录", re.I)
MS_NAME = re.compile(r"manuscript|main.?text|正文|稿件|paper", re.I)
VERSION_TOKEN = re.compile(r"(?:^|[_\-\s])(?:r\d+|v\d+(?:\.\d+)*|round\d+|rev\d*|clean|tracked(?:_changes)?|highlighted|marked|final|draft|\d{6,8})(?=$|[_\-\s])", re.I)
LABEL = re.compile(r"\b(Supplementary\s+|Supplemental\s+)?(Tables?|Fig(?:ure)?s?\.?|Files?|Notes?)\s+(S?\d+[a-z]?)(?:\s*(?:[–—-]|to|and)\s*(S?\d+[a-z]?))?", re.I)
ZH_LABEL = re.compile(r"(补充|附)?(表|图|文件)\s*(S?\d+[a-z]?)")
CAPTION_START = re.compile(r"^(?:\*\*)?\s*(?:(?:Supplementary|Supplemental)\s+)?(?:Table|Fig(?:ure)?\.?|File|Note)\s+S?\d", re.I)
NUMBER = re.compile(r"(?<![\w.])(\d+\.\d+%?|\d+%)(?![\w])")
FILENAME = re.compile(r"(?<![/\w])([\w\-]+\.(?:xlsx|xls|docx|doc|csv|zip|pdf|txt|tsv|R|py|sav|dta))\b", re.I)
VERSION = re.compile(r"\b([A-Z][A-Za-z+#\-]{1,24})\s+(?:version\s+|v\.?\s?)?(\d+(?:\.\d+){1,3})((?:\s+(?:Advanced|Desktop|Pro|Basic|Standard))?)\b")
NOT_SOFTWARE = {"Table", "Tables", "Figure", "Figures", "Fig", "Section", "Page", "Pages", "Supplementary", "Reviewer", "Comment",
                "Version", "Chapter", "Model", "Step", "Phase", "Wave", "Study", "Line", "Lines", "Item", "Items", "Cluster", "Theme",
                "CI", "OR", "HR", "RR", "AUC", "AUROC", "AUPRC", "PR", "APC", "AAPC", "SD", "SE", "IQR", "ICC", "MD", "SMD", "RMSE"}
# xlsx data cells (coded records, abstracts) are content, not the authors' wording: surface-form checks read captions and notes only
XLSX_PROSE = re.compile(r"^(?:\[sheet\]|(?:Supplementary\s+)?Table\s+S?\d|Notes?\b|Source\b|Abbreviations?\b)", re.I)
EQ_SPACING = re.compile(r"(?<![\w=<>!])([A-Za-zκχβαρτ][²2]?)(\s*)=(\s*)(?=[−\-]?\d)")
SECTION_CLAIMS = [("abstract", r"\babstract\b"), ("introduction", r"\bintroduction\b"), ("methods", r"\bmethods?\b(?! of)"),
                  ("results", r"\bresults section\b|\bin the results\b"), ("discussion", r"\bdiscussion\b"),
                  ("limitations", r"\blimitations?\b"), ("future directions", r"\bfuture directions?\b"),
                  ("conclusion", r"\bconclusions?\b"), ("highlights", r"\bhighlights?\b"),
                  ("data availability", r"\bdata availability\b"), ("acknowledgements", r"\backnowledge?ments?\b")]


def _xlsx_lines(path):
    out = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(XNS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(XNS + "t")))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels}
        for sh in wb.iter(XNS + "sheet"):
            part = target.get(sh.get(RNS + "id"), "").lstrip("/")
            part = part if part.startswith("xl/") else "xl/" + part
            out.append("[sheet] " + sh.get("name"))
            if part not in names:
                continue
            for c in ET.fromstring(z.read(part)).iter(XNS + "c"):
                if c.get("t") == "s":
                    v = c.find(XNS + "v")
                    text = shared[int(v.text)] if v is not None and v.text and v.text.isdigit() and int(v.text) < len(shared) else ""
                elif c.get("t") == "inlineStr":
                    text = "".join(t.text or "" for t in c.iter(XNS + "t"))
                else:
                    continue
                if text.strip():
                    out.append(text.strip())
    return out


def _file_lines(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        return _xlsx_lines(path)
    return [ln.strip() for ln in M.load_text(path).split("\n") if ln.strip()]


def _role(name):
    if LETTER_NAME.search(name):
        return "letter"
    if SUPP_NAME.search(name):
        return "supplement"
    if MS_NAME.search(name):
        return "manuscript"
    return "other"


def _key(name):
    stem = os.path.splitext(name)[0]
    prev = None
    while prev != stem:
        prev, stem = stem, VERSION_TOKEN.sub("", stem)
    return re.sub(r"[\s_\-]+", "_", stem).strip("_").lower() + os.path.splitext(name)[1].lower()


def load_package(d):
    """{key: {name, role, lines}}; identical texts (clean / highlighted / tracked) are kept once, preferring 'clean'.
    Keys drop version tokens and the prefix shared by every file name (manuscript ID), so rounds can be paired."""
    files = sorted((f for f in os.listdir(d) if f.lower().endswith(PKG_EXT) and not f.startswith("~$")),
                   key=lambda f: (0 if re.search(r"clean", f, re.I) else 1, f))
    stems = [os.path.splitext(f)[0] for f in files]
    common = os.path.commonprefix(stems) if len(stems) > 1 else ""
    common = re.sub(r"[^_\-\s]*$", "", common) if len(common) >= 4 else ""
    pkg, seen = {}, {}
    for f in files:
        lines = _file_lines(os.path.join(d, f))
        h = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
        if h in seen:
            pkg[seen[h]]["same_as"].append(f)
            continue
        k = _key(f[len(common):])
        while k in pkg:
            k += "+"
        pkg[k] = {"name": f, "role": _role(f), "lines": lines, "same_as": []}
        seen[h] = k
    return pkg, set(os.listdir(d))


def pair_files(old, new):
    """new key -> old key: same key, else the most similar old file of the same type (name and content together)."""
    out = {}
    for k, f in new.items():
        if k in old:
            out[k] = k
            continue
        ext = os.path.splitext(f["name"])[1].lower()
        head = " ".join(f["lines"])[:6000]
        best, bk = 0.0, None
        for ok, o in old.items():
            if os.path.splitext(o["name"])[1].lower() != ext:
                continue
            s = (0.35 * difflib.SequenceMatcher(None, k, ok).ratio()
                 + 0.65 * difflib.SequenceMatcher(None, head, " ".join(o["lines"])[:6000], autojunk=False).quick_ratio()
                 + (0.1 if o["role"] == f["role"] else 0.0))
            if s > best:
                best, bk = s, ok
        if bk is not None and best >= 0.6:
            out[k] = bk
    return out


def objects(pkg, names):
    """label -> signature of what the package shows for it: caption text, plus the worksheet content for workbook tables.
    A changed signature means the object itself changed; sentences elsewhere that describe it must be re-read."""
    sig = {}
    for f in pkg.values():
        sheet, body = None, []
        lines = f["lines"] + ["[sheet] __end__"] if f["name"].lower().endswith(".xlsx") else f["lines"]
        for ln in lines:
            if ln.startswith("[sheet] "):
                if sheet:
                    lab = sheet
                    sig.setdefault(lab, set()).add("sheet:" + hashlib.sha256("\n".join(body).encode("utf-8")).hexdigest()[:16])
                sheet, body = None, []
                m = re.match(r"\[sheet\] (?:Supplementary[_\s]*)?Table[_\s]*(S?\d+[a-z]?)(?![a-z])", ln, re.I)
                if m:
                    sig.setdefault("table %s" % m.group(1).upper(), set()).add("sheetname")
                continue
            m = re.match(r"^(?:\*\*)?\s*(?:(?:Supplementary|Supplemental)\s+)?(Table|Fig(?:ure)?\.?|File|Note)\s+(S?\d+[a-z]?)\b(?=\s*(?:\*\*)?\s*(?:[.:：|—–-]|$|(?-i:[A-Z])))", ln, re.I)
            if m:
                kind = {"fig": "figure", "fig.": "figure", "figure": "figure"}.get(m.group(1).lower(), m.group(1).lower())
                lab = "%s %s" % (kind, m.group(2).upper())
                sig.setdefault(lab, set()).add("cap:" + M.norm_for_match(ln))
                if f["name"].lower().endswith(".xlsx") and sheet is None:
                    sheet = lab
            if sheet:
                body.append(ln)
    for n in names:
        m = re.search(r"(?:supplementary|supplemental)[_\s\-]*(?:file|data)[_\s\-]*(\d+)", n, re.I)
        if m:
            sig.setdefault("file %s" % m.group(1), set()).add("file")
    return sig


def _labels(text):
    out = set()
    for m in LABEL.finditer(text):
        kind = m.group(2).lower().rstrip(".s")
        kind = {"fig": "figure", "figure": "figure", "table": "table", "file": "file", "note": "note"}.get(kind, kind)
        a, b = m.group(3).upper(), (m.group(4) or "").upper()
        out.add("%s %s" % (kind, a))
        ma, mb = re.match(r"(S?)(\d+)$", a), re.match(r"(S?)(\d+)$", b)
        if ma and mb and ma.group(1) == mb.group(1) and int(ma.group(2)) < int(mb.group(2)) <= int(ma.group(2)) + 20:
            out.update("%s %s%d" % (kind, ma.group(1), n) for n in range(int(ma.group(2)) + 1, int(mb.group(2)) + 1))
        elif b:
            out.add("%s %s" % (kind, b))
    for m in ZH_LABEL.finditer(text):
        out.add("%s %s" % ({"表": "table", "图": "figure", "文件": "file"}[m.group(2)], m.group(3).upper()))
    return out


def _after(text, num, n=4):
    i = text.find(num)
    if i < 0:
        return None
    rest = re.split(r"[.;!?。；](?:\s|$)", text[i + len(num):], maxsplit=1)[0]
    return " ".join(re.findall(r"[^\W\d_]+", rest)[:n]).lower()


def _snip(s, k=0, w=110):
    a = max(0, k - w // 2)
    return ("…" if a else "") + s[a:a + w].replace("|", "/") + ("…" if a + w < len(s) else "")


def package_scan(argv):
    ap = argparse.ArgumentParser(prog="revision_diff.py package")
    ap.add_argument("old"); ap.add_argument("new")
    ap.add_argument("--letter", default=""); ap.add_argument("--corrections", default="")
    ap.add_argument("--report", default=""); ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    for p in ([a.new] + ([a.old] if a.old != "-" else [])):
        if not os.path.isdir(p):
            print("不是目录：%s" % p, file=sys.stderr); return 2
    new, new_names = load_package(a.new)
    if not new:
        print("新包目录里没有可读文件（%s）" % ", ".join(PKG_EXT), file=sys.stderr); return 2
    old, old_names = load_package(a.old) if a.old != "-" else ({}, set())
    if a.letter:
        lk = [k for k, f in new.items() if f["name"] == os.path.basename(a.letter) or os.path.basename(a.letter) in f["same_as"]]
        if lk:
            for k in new:
                if new[k]["role"] == "letter" and k not in lk:
                    new[k]["role"] = "other"
            new[lk[0]]["role"] = "letter"
        else:
            new["__letter__"] = {"name": os.path.basename(a.letter), "role": "letter", "lines": _file_lines(a.letter), "same_as": []}
    F = {"MUST": [], "核对": []}
    add = lambda lvl, kind, where, text: F[lvl].append({"kind": kind, "where": where, "text": text})

    pairs = pair_files(old, new) if old else {}
    changed = []                           # (file, old paragraph, new paragraph) within paired files
    for k, f in new.items():
        o = old.get(pairs.get(k, ""))
        if o is None:
            continue
        na = [M.norm_for_match(x) for x in o["lines"]]
        nb = [M.norm_for_match(x) for x in f["lines"]]
        for t, i, j, _ in pair_rows(na, nb):
            changed.append((f["name"], o["lines"][i] if i is not None else "", f["lines"][j] if j is not None else ""))
    old_sents = {M.norm_for_match(s) for o in old.values() for ln in o["lines"] for s in M.sentences(ln)}

    def mentions(pred):
        """Sentences of the new package that already stood, word for word, somewhere in the old package."""
        for f in new.values():
            if f["role"] == "letter":
                continue
            xlsx = f["name"].lower().endswith(".xlsx")
            for ln in f["lines"]:
                if xlsx and not XLSX_PROSE.match(ln):
                    continue
                for s in M.sentences(ln):
                    if M.norm_for_match(s) in old_sents and pred(s):
                        yield f, s

    nsig = objects(new, new_names)
    gone = set()
    if old:
        osig = objects(old, old_names)
        gone = set(osig) - set(nsig)
        for lab in sorted(gone):
            for f in new.values():
                for ln in f["lines"]:
                    if lab in _labels(ln):
                        add("核对" if f["role"] == "letter" else "MUST", "悬空引用", f["name"],
                            "%s 已不在新包里，仍被提及：%s" % (lab.title(), _snip(ln)))
        for lab in sorted(l for l in nsig if l in osig and osig[l] != nsig[l]):
            hits = [(f["name"], s) for f, s in mentions(lambda s: lab in _labels(s) and not CAPTION_START.match(s))]
            for fn, s in hits[:12]:
                add("核对", "改动对象的其他提及", fn, "%s 的题注或内容本轮改了；这句一字未改，核对它的描述是否仍然准确：%s" % (
                    lab.title(), _snip(s)))
            if len(hits) > 12:
                add("核对", "改动对象的其他提及", "多处", "%s 另有 %d 处提及未列出" % (lab.title(), len(hits) - 12))
        seen = set()
        for fn, o_, n_ in changed:
            if not o_ or not n_:
                continue
            for num in sorted(set(NUMBER.findall(n_)) & set(NUMBER.findall(o_))):
                if num in seen or ("%" not in num and len(re.sub(r"\D", "", num)) < 3):
                    continue
                rx = re.compile(r"(?<![\w.])%s(?![\w])" % re.escape(num))
                octx = {_after(o_[m.start():], num) for m in rx.finditer(o_)}
                nctx = {_after(n_[m.start():], num) for m in rx.finditer(n_)}
                if not octx - nctx:
                    continue
                seen.add(num)
                fresh = {w for c in nctx - octx for w in c.split() if len(w) >= 4} - {w for c in octx for w in c.split()}
                for f, s in mentions(lambda s: rx.search(s) and _after(s[rx.search(s).start():], num) not in nctx
                                     and not fresh & set(re.findall(r"[^\W\d_]+", s.lower()))):
                    add("核对", "改了说法的数字", f["name"], "%s 在 %s 里改了说法（%s → %s）；这句仍是旧说法：%s" % (
                        num, fn, "；".join(sorted(octx - nctx)), "；".join(sorted(nctx - octx)) or "删去", _snip(s, s.find(num))))

    if any(re.search(r" S\d", l) for l in nsig):
        missing = {}
        for f in new.values():
            if f["role"] == "letter":
                continue
            for ln in f["lines"]:
                for lab in _labels(ln):
                    if re.search(r" S\d", lab) and lab not in nsig and lab not in gone:
                        missing.setdefault(lab, (f["name"], ln))
        for lab, (fn, ln) in sorted(missing.items()):
            k = ln.upper().find(lab.split()[1])
            add("核对", "包里找不到的补充对象", fn, "%s 被引用，但包里没有它的题注或工作表：%s" % (lab.title(), _snip(ln, max(k, 0))))

    if a.corrections:
        with open(a.corrections, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                pat = (row.get("old") or "").strip()
                if not pat:
                    continue
                for k, f in new.items():
                    if f["role"] == "letter":
                        continue
                    for ln in f["lines"]:
                        i = ln.lower().find(pat.lower())
                        if i >= 0:
                            add("MUST", "已登记更正的旧说法仍在", f["name"],
                                "“%s”应为“%s”：%s" % (pat, row.get("new", ""), _snip(ln, i)))

    # one object, several surface forms
    for k, f in new.items():
        if f["role"] in ("supplement", "letter") or f["name"].lower().endswith(".xlsx"):
            continue
        text = "\n".join(f["lines"])
        for kind, rx in (("Table", r"Tables?"), ("Figure", r"Fig(?:ure)?s?\.?")):
            bare = re.findall(r"(?<!Supplementary )(?<!Supplemental )\b%s\s+S\d+" % rx, text)
            pref = re.findall(r"\b(?:Supplementary|Supplemental)\s+%s\s+S\d+" % rx, text)
            if bare and pref:
                add("核对", "同一对象多种写法", f["name"], "补充%s前缀混用：%d 处“%s”，%d 处“%s”" % (
                    "表" if kind == "Table" else "图", len(bare), bare[0], len(pref), pref[0]))
        sp = {}
        for m in EQ_SPACING.finditer(text):
            sp.setdefault(m.group(1), set()).add("spaced" if (m.group(2) or m.group(3)) else "tight")
        mixed = sorted(s for s, v in sp.items() if len(v) > 1)
        if mixed:
            add("核对", "同一对象多种写法", f["name"],
                "等号两侧空格不一（%s）；摘要为字数限制紧凑书写时写明理由" % ", ".join(mixed))
    ver = {}
    for k, f in new.items():
        xlsx = f["name"].lower().endswith(".xlsx")
        for ln in f["lines"]:
            if xlsx and not XLSX_PROSE.match(ln):
                continue
            for m in VERSION.finditer(ln):
                name, v = m.group(1), m.group(2)
                if name in NOT_SOFTWARE or v.startswith("0.") or (name.isupper() and re.fullmatch(r"\d+\.\d{2,}", v)):
                    continue
                ver.setdefault(name, {}).setdefault((v + m.group(3)).strip(), f["name"])
    for name, vs in sorted(ver.items()):
        if len(vs) > 1:
            add("核对", "同一对象多种写法", "；".join(sorted(set(vs.values()))),
                "%s 写成了 %s" % (name, "、".join("%s %s" % (name, v) for v in sorted(vs))))

    # file names that the package does not contain
    low = {n.lower() for n in new_names}
    for k, f in new.items():
        for ln in f["lines"]:
            for m in FILENAME.finditer(ln):
                if m.group(1).lower() not in low and not re.search(r"https?://\S*" + re.escape(m.group(1)), ln):
                    add("核对", "不存在的文件名", f["name"], "文中写了 %s，新包里没有同名文件：%s" % (m.group(1), _snip(ln, m.start())))

    # section names in each answer of the response letter: a table to read against the changes, plus sections
    # that the letter names but the manuscript did not change at all
    letters = [f for f in new.values() if f["role"] == "letter"]
    ms = next((f for f in new.values() if f["role"] == "manuscript"), None)
    claims = []
    if letters:
        changed_secs = set()
        if ms is not None and old:
            ms_changed = {M.norm_for_match(n_) for fn, o_, n_ in changed if fn == ms["name"] and n_}
            for b in M.parse("\n\n".join(ms["lines"])):
                if M.norm_for_match(b["text"]) in ms_changed:
                    changed_secs.add(b["sec"]); changed_secs.add((b.get("sub") or "").lower())
        text = "\n".join(letters[0]["lines"])
        blocks = re.split(r"(?im)^\s*(?:\*\*)?\s*(?:Answer|Response|Reply|回复|答复)\s*(?:\*\*)?\s*[:：]", text)[1:]
        for n, blk in enumerate(blocks, 1):
            blk = re.split(r"(?im)^\s*(?:\*\*)?\s*(?:\d+\.|Comment|Reviewer|Editor)\b", blk)[0]
            named = [s for s, rx in SECTION_CLAIMS if re.search(rx, blk, re.I)]
            if named:
                claims.append((n, named, _snip(blk.strip(), 0, 90)))
            if changed_secs:
                for s in named:
                    if s in ("highlights", "data availability", "acknowledgements"):
                        continue
                    if not any(s in c or c.startswith(s[:6]) for c in changed_secs if c):
                        add("核对", "回复信的节名", letters[0]["name"], "第 %d 条回复提到 %s，但正文这一节本轮没有改动" % (n, s))

    res = {"old": a.old, "new": a.new, "files": [f["name"] + (" (= %s)" % ", ".join(f["same_as"]) if f["same_as"] else "") for f in new.values()],
           "changed_paragraphs": len(changed), "findings": F,
           "files_sha256": {n: hashlib.sha256(open(os.path.join(a.new, n), "rb").read()).hexdigest()
                            for n in sorted(new_names) if n.lower().endswith(PKG_EXT) and os.path.isfile(os.path.join(a.new, n))}}
    L = ["# 包级一致性扫描：%s → %s\n" % (a.old, a.new),
         "读入 %d 份（同文合并后）：%s\n" % (len(new), "；".join(res["files"])),
         "改动段落 %d；MUST %d；核对 %d。“核对”是候选，不是错误：逐条看过，改或写明不改的理由，记进修改清单。\n" % (
             len(changed), len(F["MUST"]), len(F["核对"]))]
    for lvl in ("MUST", "核对"):
        if F[lvl]:
            L += ["## %s\n" % lvl, "| 类别 | 文件 | 内容 |", "|---|---|---|"]
            L += ["| %s | %s | %s |" % (x["kind"], x["where"], x["text"].replace("\n", " ")) for x in F[lvl]]
            L.append("")
    if claims:
        L += ["## 回复信各条点名的节（对照用，不计入发现）\n",
              "逐条确认：每个节名都是本条改动真正所在的节，而不是“相应的局限”这类顺手的说法。\n",
              "| 条 | 点名的节 | 开头 |", "|---|---|---|"]
        L += ["| %d | %s | %s |" % (n, "、".join(s), t) for n, s, t in claims]
        L.append("")
    res["letter_sections"] = [{"answer": n, "sections": s} for n, s, _ in claims]
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as fh:
            fh.write(out)
    if a.json:
        with M.wfile(a.json) as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
    print(L[2].strip())
    if not a.report:
        print(out)
    return 1 if (F["MUST"] or F["核对"]) else 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "package":
        return package_scan(sys.argv[2:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("--report", default=""); ap.add_argument("--csv", default="")
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    for p in (a.old, a.new):
        if not os.path.exists(p):
            print("找不到 %s" % p, file=sys.stderr); return 2
    A, B = items(a.old), items(a.new)
    na, nb = [M.norm_for_match(x[3]) for x in A], [M.norm_for_match(x[3]) for x in B]
    rows = [(t, A[i] if i is not None else None, B[j] if j is not None else None, r) for t, i, j, r in pair_rows(na, nb)]
    wa = sum(M.count_words(x[3]) for x in A if x[0] != "references")
    wb = sum(M.count_words(x[3]) for x in B if x[0] != "references")
    summ = {}
    for t, o, n, r in rows:
        s = SEC_ZH.get((n or o)[0], (n or o)[0]); summ.setdefault(s, {"修改": 0, "新增": 0, "删除": 0})[t] += 1
    cut = (lambda s: s) if a.full else (lambda s: s if len(s) <= 400 else s[:400] + "…")
    L = ["# 修改差异：%s → %s\n" % (os.path.basename(a.old), os.path.basename(a.new)),
         "改动 %d 处；词数（不含参考文献）%d → %d（%+d）。\n" % (len(rows), wa, wb, wb - wa),
         "| 节 | 修改 | 新增 | 删除 |\n|---|---|---|---|"]
    L += ["| %s | %d | %d | %d |" % (s, v["修改"], v["新增"], v["删除"]) for s, v in summ.items()]
    L.append("\n| # | 类型 | 位置（新稿；删除为旧稿） | 改前 | 改后 | 词数变化 | 相似度 |\n|---|---|---|---|---|---|---|")
    for k, (t, o, n, r) in enumerate(rows, 1):
        before, after = (o[3] if o else ""), (n[3] if n else "")
        L.append("| %d | %s | %s | %s | %s | %+d | %s |" % (k, t, loc(n or o), cut(before).replace("|", "/"), cut(after).replace("|", "/"),
                                                         M.count_words(after) - M.count_words(before), ("%.2f" % r) if t == "修改" else "—"))
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    if a.csv:
        with M.wfile(a.csv) as f:
            cw = csv.writer(f); cw.writerow(["no", "type", "location", "before", "after", "word_delta", "similarity"])
            for k, (t, o, n, r) in enumerate(rows, 1):
                cw.writerow([k, t, loc(n or o), o[3] if o else "", n[3] if n else "",
                             M.count_words(n[3] if n else "") - M.count_words(o[3] if o else ""), round(r, 3)])
    print(L[1].strip())
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
