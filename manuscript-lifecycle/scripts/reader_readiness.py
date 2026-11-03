#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate terms and possible first-use problems; this is not a comprehension test.

Usage: reader_readiness.py manuscript.md|docx [--terms terms.txt] [--json out.json]
                            [--report out.md]

The public inspect_text(text, terms=None) API returns items, inventory, scopes and
limitations. Findings are non-blocking candidates. A matched expansion does not
establish that a concept, its relevance, or its supporting evidence was explained.
"""
import argparse
import bisect
import json
import re
import sys
from pathlib import Path

import mslib as M


# Units are the only built-in exceptions; there is no field-specific vocabulary.
UNITS = {"Hz", "kHz", "MHz", "GHz", "Pa", "kPa", "MPa", "GPa", "dB", "mV",
         "MV", "kV", "mA", "MA", "mW", "MW", "mL", "ML", "kJ", "MJ", "GB",
         "MB", "KB", "TB", "nm", "mm", "cm", "km", "ms", "kg", "mol", "cd"}
TOKEN = re.compile(r"(?<![A-Za-z0-9_])(?:[A-Z]{2,18}(?:[-–][A-Z0-9]{1,10})*(?:s)?|"
                   r"[A-Za-z]{1,8}\d{1,4}[A-Za-z0-9]{0,8})(?![A-Za-z0-9_])")
PAIRS = {"(": ")", "[": "]", "（": "）", "［": "］"}
BODY = {"introduction", "methods", "results", "discussion", "limitations", "conclusion"}
BOUNDARY = re.compile(r"[.!?。！？;；\n]")
CJK = re.compile(r"[\u4e00-\u9fff]")


def _heading(line):
    stripped = line.strip()
    md = re.match(r"^(#{1,6})\s+(.*)$", stripped)
    clean = M.heading_text(stripped)
    key = M.classify_heading(clean)
    if md:
        return key, len(md.group(1)), clean
    if key and len(clean) <= 85 and len(clean.split()) <= 10:
        return key, 2, clean
    return None, None, None


def _scopes(text):
    """Small line-preserving scope reader, separate from the manuscript parser.

    Unknown headings remain in one body scope. No guessed heading silently proves
    that all boundaries were recovered. Captions/tables are isolated when their
    explicit labels or Markdown table syntax make that possible.
    """
    scopes = []
    lookup = {}
    sec, abs_level, recognized = "unclassified", None, False
    section_level = None
    has_intro = any(_heading(line)[0] == "introduction" for line in text.splitlines())
    heads = [_heading(line) for line in text.splitlines()]
    imrad = any(h[0] in ("methods", "results") for h in heads)
    aim_head = any(h[0] is None and h[2] and M.INTRO_AIM_HEAD.search(h[2]) for h in heads)
    display = None
    display_count = {"figure": 0, "table": 0}
    in_code = False
    previous_blank = True
    intro_paras, para = [], []

    def add(sid, kind, line_no, line, section):
        if sid not in lookup:
            obj = {"id": sid, "kind": kind, "fragments": []}
            lookup[sid] = obj
            scopes.append(obj)
        lookup[sid]["fragments"].append({"line": line_no, "text": line, "section": section})

    def end_para():
        if para:
            intro_paras.append(tuple(para))
            para.clear()

    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not stripped:
            end_para()
            previous_blank = True
            continue
        inline_abstract = re.match(r"^\s*[*_]{0,2}(?:Abstract|摘\s*要)[*_]{0,2}\s*[:：]\s*(.+)$", line, re.I)
        if inline_abstract:
            end_para()
            sec, abs_level, recognized = "abstract", 2, True
            add("abstract", "abstract", line_no, line, sec)
            previous_blank = False
            continue
        key, level, heading = _heading(line)
        caption = bool(M.CAPTION.match(stripped))
        table_row = bool(M.TABLE_LINE.match(stripped))
        note = bool(M.NOTE_START.match(stripped))

        # Captions remain readable units even when collected after References.
        if caption:
            end_para()
            kind = "table" if re.match(r"^\W*(?:Table|表|附表)", stripped, re.I) else "figure"
            display_count[kind] += 1
            display = "%s:%d" % (kind, display_count[kind])
            add(display, kind, line_no, line, "display")
            previous_blank = False
            continue
        if table_row:
            end_para()
            if not display or not display.startswith("table:"):
                display_count["table"] += 1
                display = "table:%d" % display_count["table"]
            add(display, "table", line_no, line, "display")
            previous_blank = False
            continue
        if display and (note or (not previous_blank and key is None and level is None)):
            add(display, display.split(":")[0], line_no, line, "display")
            previous_blank = False
            continue
        display = None

        if heading is not None:
            end_para()
            if key:
                recognized = True
                if key == "abstract":
                    sec, abs_level = "abstract", level
                elif sec == "abstract" and key in BODY and key != "introduction" and (level > abs_level or has_intro):
                    pass  # Structured abstract subheadings do not open the body.
                else:
                    sec = key
                section_level = level
            # Unknown content headings may contain the first use of a term.
            elif sec in BODY or sec == "unclassified":
                # 15b: same boundary as mslib.first_section_paras (IMRaD peer subsections stay in the introduction)
                keep_intro = sec == "introduction" and imrad and (aim_head or not M.INTRO_LIT_HEAD.search(heading.strip()))
                if section_level is not None and level <= section_level and not keep_intro:
                    sec = "unclassified"
                # A leading H1 is normally the article title, not first body use.
                if recognized or level != 1:
                    add("body", "body", line_no, heading, sec)
            previous_blank = True
            continue
        if M.KEYWORDS.match(stripped):
            end_para()
            if sec == "abstract":
                sec = "front"
            previous_blank = True
            continue
        if sec in ("references", "back", "front"):
            previous_blank = False
            continue
        sid = "abstract" if sec == "abstract" else "body"
        add(sid, sid, line_no, line, sec)
        if sec == "introduction":
            para.append(line_no)
        previous_blank = False
    end_para()
    for scope in scopes:
        offsets, at = [], 0
        for frag in scope["fragments"]:
            offsets.append(at)
            at += len(frag["text"]) + 1
        scope["text"] = "\n".join(f["text"] for f in scope["fragments"])
        scope["offsets"] = offsets
    return scopes, intro_paras[-1] if intro_paras else (), recognized


def _where(scope, pos):
    idx = max(0, bisect.bisect_right(scope["offsets"], pos) - 1)
    f = scope["fragments"][idx]
    return f["line"], f["section"], f["text"].strip()


def _unit_use(term, occurrence, text):
    """Unit spelling alone is ambiguous (e.g. MA can name a degree).

    Only omit it from automatic term discovery when an adjacent numeric value
    supplies local unit syntax. Explicit --terms entries can still request it.
    """
    if term not in UNITS:
        return False
    before = text[max(0, occurrence.start() - 55):occurrence.start()]
    return bool(re.search(r"(?<![A-Za-z0-9_.])[+−-]?(?:\d+(?:\.\d+)?|\.\d+)"
                          r"(?:[eE][+−-]?\d+)?\s*$", before))


def _english_expansion(short, long):
    """Backward character alignment; the first letter must start a word.

    A syntactic candidate, not a terminology or translation validator. It allows
    internal letters (e.g. a one-word expansion) without accepting any parentheses.
    """
    chars = re.sub(r"[^A-Za-z]", "", short).lower()
    if len(chars) < 2 or not re.search(r"[A-Za-z]", long):
        return None
    if len(long) > 200:
        long = long[-200:]
    j = len(long) - 1
    for i in range(len(chars) - 1, -1, -1):
        while j >= 0 and (long[j].lower() != chars[i] or
                          (i == 0 and j > 0 and long[j - 1].isalnum())):
            j -= 1
        if j < 0:
            return None
        if i:
            j -= 1
    result = long[j:].strip(" *_:：,，-–")
    words = re.findall(r"[A-Za-z]+", result)
    if not words or len(words) > len(chars) + 5:
        return None
    # A repeated short form is not its own expansion.
    if re.sub(r"\W", "", result).lower() == chars:
        return None
    return result


def _expansion(short, long):
    # Cross-language correspondence requires human reading. Recognize the local
    # explanatory syntax without pretending to check translation from initials.
    if len(CJK.findall(long)) >= 2:
        return long.strip(" *_:：,，")[-60:]
    return _english_expansion(short, long)


def _definitions(scope, term, occurrences):
    text = scope["text"]
    defs = []
    for m in occurrences:
        before, after = text[:m.start()], text[m.end():]
        left = re.search(r"([([（［])\s*$", before)
        if left:
            close = PAIRS[left.group(1)]
            if re.match(r"\s*" + re.escape(close), after):
                prefix = before[:left.start()]
                prefix = BOUNDARY.split(prefix)[-1]
                full = _expansion(term, prefix)
                if full:
                    defs.append({"offset": m.start(), "full_form": full, "pattern": "full-form(short)"})
        right = re.match(r"\s*([([（［])", after)
        if right:
            close = PAIRS[right.group(1)]
            inner = after[right.end():].split(close, 1)
            if len(inner) == 2 and not BOUNDARY.search(inner[0]):
                full = _expansion(term, inner[0])
                if full:
                    defs.append({"offset": m.start(), "full_form": full, "pattern": "short(full-form)"})
        # Common standalone display key: "ABC, full form; DEF, ...".
        if scope["kind"] in ("figure", "table"):
            key = re.match(r"\s*[,，=:：]\s*([^;；.。\n]{2,160})", after)
            if key:
                full = _expansion(term, key.group(1))
                if full:
                    defs.append({"offset": m.start(), "full_form": full, "pattern": "display-key"})
    unique = {}
    for d in defs:
        line, _, _ = _where(scope, d["offset"])
        d["line"] = line
        d["translation_unverified"] = bool(CJK.search(d["full_form"]))
        unique[(d["offset"], d["full_form"])] = d
    return sorted(unique.values(), key=lambda d: d["offset"])


def inspect_text(text, terms=None):
    """Return auditable lexical candidates; never certify conceptual readiness."""
    scopes, last_intro_lines, recognized = _scopes(text)
    items, inventory = [], []
    extra = [t.strip() for t in (terms or []) if t.strip()]

    def add(level, code, scope, msg, example, line, term):
        at = example.find(term)
        if len(example) > 180 and at >= 0:  # 15b: an excerpt, not the whole paragraph repeated per term
            a, b = max(0, at - 80), min(len(example), at + len(term) + 80)
            example = ("…" if a else "") + example[a:b] + ("…" if b < len(example) else "")
        items.append({"level": level, "code": code, "sec": scope["id"], "msg": msg,
                      "examples": ["L%d: %s" % (line, example)], "line": line, "term": term})

    for scope in scopes:
        found = {}
        # Editorial placeholders are not terms in the scientific argument. Keep
        # offsets intact; residual placeholders are audited by delivery checks.
        scan_text = re.sub(r"\[(?:VERIFY|TODO|FIXME|TBD)(?::[^\]\n]*)?\]",
                           lambda m: " " * len(m.group()), scope["text"], flags=re.I)
        for m in TOKEN.finditer(scan_text):
            term = m.group()
            base = term[:-1] if term.endswith("s") and term[:-1].isupper() else term
            if base not in extra and _unit_use(base, m, scope["text"]):
                continue
            found.setdefault(base, []).append(m)
        for term in extra:
            if term not in found:
                rx = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(term) + r"(?![A-Za-z0-9_])")
                matches = list(rx.finditer(scope["text"]))
                if matches:
                    found[term] = matches
        for term, matches in sorted(found.items(), key=lambda p: p[1][0].start()):
            first = matches[0]
            line, section, example = _where(scope, first.start())
            kind = "label_or_symbol" if re.search(r"\d", term) else (
                "acronym_candidate" if re.fullmatch(r"[A-Z]{2,18}(?:[-–][A-Z0-9]+)*", term)
                else "named_term")
            definitions = _definitions(scope, term, matches) if kind == "acronym_candidate" else []
            status = "not_applicable_to_name_or_symbol"
            if kind == "acronym_candidate":
                if not definitions:
                    status = "no_matching_expansion"
                    add("SHOULD", "RR1", scope,
                        "%s：本阅读范围未找到匹配的邻近展开式。请判断是否需解释、是否为惯用名或允许的例外；这不是已确认的缺陷。" % term,
                        example, line, term)
                elif scope["kind"] in ("figure", "table"):
                    status = "expansion_within_display"
                elif definitions[0]["offset"] > first.start():
                    status = "expansion_after_first_use"
                    add("SHOULD", "RR2", scope,
                        "%s：首次使用在 L%d，匹配的展开式在 L%d；核对读者能否在此之前理解它。" %
                        (term, line, definitions[0]["line"]), example, line, term)
                else:
                    status = "expansion_at_first_use"
                if definitions and definitions[0]["translation_unverified"]:
                    status = "possible_cross_language_" + status
                    add("INFO", "RR5", scope,
                        "%s 有邻近的跨语言解释形式；全称与缩写是否确实对应未自动核实，不能据此认定定义正确。" % term,
                        example, line, term)
            else:
                add("INFO", "RR3", scope,
                    "%s：%s首次定位。名称、符号或构念未必有“全称”；需按目标读者判断其含义与用途是否交代。" %
                    (term, "字母数字标签/符号" if kind == "label_or_symbol" else "补充命名术语"),
                    example, line, term)
            if section == "introduction" and line in last_intro_lines:
                add("INFO", "RR4", scope,
                    "%s 在引言末段才首次具名：请回读此前是否已用全称、同义表述或通行知识交代含义、相关性和依据。首次具名本身不构成缺陷。" % term,
                    example, line, term)
            inventory.append({"term": term, "kind": kind, "scope": scope["id"],
                              "first_line": line, "first_section": section, "count": len(matches),
                              "formal_status": status, "definitions": definitions,
                              "conceptual_readiness": "not_automatically_assessed"})
    limitations = [
        "本工具只定位形式候选；未自动核实概念含义、测量效度、相关性、文献支持或预测是否可区分。无发现不等于这些维度通过。",
        "自动词元只覆盖大写缩写及部分字母数字名称；普通词构念、混合大小写词和同义表述可能漏掉，可用 --terms 补充定位。",
        "与数值相邻的常见单位不自动列作术语；同形词在其他上下文仍列为候选，--terms 可覆盖该省略。",
        "展开式只按局部句法与字母对应识别，不能证明展开正确；跨语言全称的翻译对应未核实。",
        "摘要与正文分开，正文跨节沿用定义；仅对显式标签或 Markdown 表格识别独立图表，图内文字、图片、复杂排版与未标记图注需另查。",
        "行号针对读取后的文本；Word 文件为提取文本行号，不是排版后的页码行号。",
    ]
    if not recognized:
        limitations.append("未识别标准章节边界：非图表文字按单一正文范围扫描，摘要/声明等范围是否独立需人工核对。")
    if not scopes:
        limitations.append("没有可扫描文字范围；未执行有效的词元覆盖检查。")
    return {"items": items, "inventory": inventory,
            "scopes": [{"id": s["id"], "kind": s["kind"],
                        "lines": [f["line"] for f in s["fragments"]]} for s in scopes],
            "limitations": limitations, "semantic_status": "not_automatically_assessed"}


def report(result):
    lines = ["# 术语形式与阅读前提候选", "", "形式扫描不等于概念、依据或论证已检查。所有发现均待裁决，均非自动阻断。", "",
             "| 范围 | 术语 | 首次行 | 类型 | 形式状态 |", "|---|---|---:|---|---|"]
    for row in result["inventory"]:
        lines.append("| %s | %s | %d | %s | %s |" % (row["scope"], row["term"].replace("|", "\\|"),
                     row["first_line"], row["kind"], row["formal_status"]))
    lines += ["", "## 待核候选", ""]
    for item in result["items"]:
        lines += ["- %s %s [%s] %s" % (item["level"], item["code"], item["sec"], item["msg"]),
                  "  - " + item["examples"][0]]
    if not result["items"]:
        lines.append("未发现形式候选；概念与文献依据未由本工具验证。")
    lines += ["", "## 覆盖边界", ""] + ["- " + s for s in result["limitations"]]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manuscript")
    ap.add_argument("--terms", default="", help="可选补充术语文本，每行一个；只补充定位，不自定缺陷")
    ap.add_argument("--json", default="")
    ap.add_argument("--report", default="")
    args = ap.parse_args()
    try:
        terms = [s.strip() for s in Path(args.terms).read_text(encoding="utf-8-sig").splitlines()
                 if s.strip() and not s.lstrip().startswith("#")] if args.terms else []
        result = inspect_text(M.load_text(args.manuscript), terms=terms)
        for dest, value in ((args.json, json.dumps(result, ensure_ascii=False, indent=2)),
                            (args.report, report(result))):
            if dest:
                Path(dest).parent.mkdir(parents=True, exist_ok=True)
                Path(dest).write_text(value, encoding="utf-8")
        if not args.report:
            print(report(result))
        # Candidates are advisory; input/execution errors are distinct (exit 2).
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
