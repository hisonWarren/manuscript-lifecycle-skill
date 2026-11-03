#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ref_check.py — 引文与参考文献双向核对（作者–年份制、方括号数字制），以及 DOI 格式与重复。

  python ref_check.py 稿件.md|docx [--style auto|ay|num] [--online] [--report out.md]

--online：逐条向 Crossref 查询注册记录。需要联网；请求失败时标 not_verified，不能当作已核查。
脚本只核对"对得上"，不核对"引得对"。引文是否支持所在句的论断、转述是否忠实，必须读原文，
并记录核对程度（全文 / 只读摘要 / 未核），见 references/05_language.md §引用。
上标数字引文无法可靠识别，会在报告中提示。
退出码：0 无问题；1 有缺失、未被引用、重复或格式问题；2 输入错误。
"""
import argparse, collections, os, re, sys, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

SKIP = {"see", "e", "eg", "cf", "for", "in", "and", "table", "tables", "figure", "fig", "supplementary", "section", "note",
        "data", "model", "study", "ci", "or", "hr", "rr", "sd", "se", "version", "accessed", "but", "also", "review", "with", "the", "a"}
YR = r"(?:1[89]|20)\d\d[a-z]?"


def split_doc(text):
    lines = text.split("\n")
    ri = None
    for i, l in enumerate(lines):
        if re.match(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:references?|bibliography|literature cited|works cited|参\s*考\s*文\s*献)\s*(?:\*\*)?\s*:?\s*$", l, re.I):
            ri = i
    if ri is None:
        return text, []
    end = len(lines)
    for j in range(ri + 1, len(lines)):
        if re.match(r"^\s*#{1,6}\s", lines[j]) and M.classify_heading(M.heading_text(lines[j])) == "back":
            end = j; break
        # 中文期刊参考文献之后是英文题名页与英文摘要（无标题样式），到 Abstract / Key words / 附录 为止
        if j > ri + 3 and re.match(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:abstract|key\s*words?|附\s*录|appendix)\b", lines[j], re.I):
            end = j; break
    body = "\n".join(lines[:ri] + lines[end:])
    entries, cur = [], ""
    prev = ""
    heads = M._running_heads(text)       # 文献表跨页时夹入的页眉（"心理学报 … 1917"）
    for l in lines[ri + 1:end]:
        s = l.strip()
        if s in heads or M.PAGE_MARK.match(s):
            continue
        if not s:
            if cur:
                entries.append(cur); cur = ""
            prev = ""
            continue
        # PDF 转写的文献表常按版面换行而不空行：带首字母缩写的作者、编号、机构作者+年份、中文作者才算新条目；
        # 宽松的"大写词, "只在上一行已经以句点/括号/DOI 结束时才算（避免把"Psychological Measurement, 1(3)"切成新条目）
        prev_done = bool(re.search(r"(?:[.)\]]|\d{4,}|doi\.org/\S+|10\.\d{4,9}/\S+)\s*$", prev))
        first = not prev
        starts = (re.match(r"^(?:[-*]\s+)?(?:\[\d+\]|\d+\.\s|\d+\s+[A-Z])", s) or
                  ((prev_done or first) and (re.match(AUTHOR_START, s) or
                                             re.match(r"^(?:[-*]\s+)?[A-Z][A-Za-z&,'’\-\s]{2,80}\.\s*\(%s" % YR, s) or
                                             re.match(r"^[\u4e00-\u9fff]{2,4}(?:[，,、]|\.\s*\()", s) or
                                             (not cur and re.match(r"^(?:[-*]\s+)?[A-Z\u00C0-\u024F][A-Za-z\u00C0-\u024F'’\-]+(?:\s[A-Z][a-z]+)?,\s", s)))))
        if starts and cur:
            entries.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
        prev = s
    if cur:
        entries.append(cur)
    return body, [e for e in entries if re.search(r"(?<!\d)%s(?!\d)" % YR, e) or re.search(r"10\.\d{4,9}/", e)]


AUTHOR_START = (r"^(?:[-*]\s+)?(?:(?:van|von|de|der|den|di|da|du|la|le|del|dos|el|al)\s+)*"
                r"[A-Z\u00C0-\u024F][A-Za-z\u00C0-\u024F'’\-]+(?:[\s\-][A-Z][A-Za-z'’\-]+)?,\s(?:[A-Z\u00C0-\u024F]\.|[A-Z][a-z]?\.?\s?[A-Z]\.)")


def surname(seg):
    for tok in re.findall(r"[A-Z\u00C0-\u024F][A-Za-z\u00C0-\u024F'’\-]+|[\u4e00-\u9fff]{2,30}", seg):
        if re.match(r"[\u4e00-\u9fff]", tok):
            tok = re.sub(r"(?:等人|等|和|与|及)$", "", tok)   # "（杨之旭等, 2023）"
            if len(tok) < 2:
                continue
        if M.fold(tok) not in SKIP:
            return M.fold(tok)
    return None


ID_CONTEXT = re.compile(r"(?:\bno\.?|\bnumber|\bnr\.?|#|\bapproval|\bprotocol|\bregistration|\bgrant|批准号|编号|批号|审批号|伦理号|注册号)\s*[:：]?\s*$", re.I)


MONTHS = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"


def intext_ay(body, with_ctx=False):
    keys = []
    body = re.sub(r"(?<=[\u4e00-\u9fff])\s*\n\s*(?=[\u4e00-\u9fff])", "", body)
    body = re.sub(r"([A-Za-z])-[ \t]*\n[ \t]*([a-z])", r"\1\2", body)       # Sin-\ngelis → Singelis
    body = re.sub(r"([A-Za-z])-[ \t]*\n[ \t]*([A-Z])", r"\1-\2", body)      # Krieger-\nRedwood → Krieger-Redwood
    body = re.sub(r"[ \t]*\n[ \t]*", " ", body)
    for m in re.finditer(r"[（(]([^()（）]*?%s[^()（）]*)[）)]" % YR, body):
        inner = m.group(1)
        if re.fullmatch(r"\s*(?:1[89]|20)\d\d\s*[–-]\s*(?:1[89]|20)\d\d\s*", inner):
            continue
        for seg in re.split(r"[;；]", inner):
            years = []
            for ym in re.finditer(r"\b(%s)\b" % YR, seg):
                head, tail = seg[:ym.start()], seg[ym.end():ym.end() + 2]
                # 伦理批准号、注册号、方案号里的"2021"不是出版年：(no. 2021-49)、(ChiCTR2021...)、(2021/123)
                if re.match(r"[-–/]\d", tail) or re.search(r"\d[-–/]$", head) or ID_CONTEXT.search(head):
                    continue
                # 日期不是出版年：（2021 年 5 月）、（Time 1 = May 2021）、（t1 = 2021…）
                if (re.match(r"\s*年", seg[ym.end():ym.end() + 3]) or re.search(r"(?:%s\s*|[=~～至]\s*)$" % MONTHS, head, re.I)
                        or re.match(r"\s*[×xX*]\s*\d", seg[ym.end():ym.end() + 6])):
                    continue
                years.append(ym.group(1))
            if not years:
                continue
            sn = surname(re.sub(r"\b(?:e\.g\.|i\.e\.|see|cf\.)", "", seg, flags=re.I))
            if not sn:
                before = body[max(0, m.start() - 80):m.start()]
                mm = (re.search(r"([A-Z\u00C0-\u024F][A-Za-z\u00C0-\u024F'’\-]+)(?:\s+(?:et al\.?|and|&)\s*(?:[A-Z][A-Za-z'’\-]+)?)?\s*$", before)
                      or re.search(r"([\u4e00-\u9fff]{2,4})等?\s*$", before))
                sn = M.fold(mm.group(1)) if mm else None
            ctx = M.fold(body[max(0, m.start() - 40):m.start()] + " " + seg)
            if sn or with_ctx:
                keys += [((sn, y, ctx) if with_ctx else (sn, y)) for y in years if sn or with_ctx]
    return keys


def entry_names(e):
    """一条文献可被引用的姓名：首作者英文姓；中文期刊的"英文译文 + [中文原文]"格式里，中文原文首作者全名。"""
    names = set()
    sn, y = ref_key(e)
    if sn:
        names.add(sn)
    e = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", e)
    for m in re.finditer(r"\[\s*([\u4e00-\u9fff]{2,30}?)\s*(?:[，,、.．]|等)", e):
        names.add(M.fold(m.group(1)))
    m = re.match(r"^\s*(?:[-*]\s+)?(?:\[\d+\]\s*)?([\u4e00-\u9fff]{2,4})(?:[，,、.．]|等)", e)
    if m:
        names.add(M.fold(m.group(1)))
    return names, y


def ref_key(e):
    e2 = re.sub(r"^(?:[-*]\s+)?(?:\[\d+\]|\d+\.)\s*", "", e)
    sn = surname(e2[:60])
    y = re.search(r"\b(%s)\b" % YR, e2)
    return (sn, y.group(1) if y else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path"); ap.add_argument("--style", default="auto", choices=["auto", "ay", "num"]); ap.add_argument("--online", action="store_true")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    if not os.path.exists(a.path):
        print("找不到文件", file=sys.stderr); return 2
    body, refs = split_doc(M.load_text(a.path))
    issues, notes = [], []
    if not refs:
        issues.append("没有找到参考文献表（需要 References / 参考文献 标题）")
    nbr = len(re.findall(r"\[\d+(?:\s*[-–,]\s*\d+)*\]", body)); nay = len(intext_ay(body))
    style = a.style if a.style != "auto" else ("num" if nbr > nay else "ay")
    if style == "ay":
        rk = [ref_key(e) for e in refs]
        rset = collections.Counter(rk)
        names = [entry_names(e) for e in refs]
        alias = collections.defaultdict(set)          # (姓名, 年) → 条目序号；含中文原文作者
        for i, (ns, y) in enumerate(names):
            for n_ in ns:
                alias[(n_, y)].add(i)
        cited_idx, missing = set(), {}
        unresolved = 0
        for sn, y, ctx in intext_ay(body, with_ctx=True):
            if sn and re.match(r"[\u4e00-\u9fff]", sn) and (len(sn) > 4 or re.search(r"[的了在是为对其这那年月日个]", sn)) and not any(k[0] == sn for k in alias):
                sn = None          # 括号里的中文短语不是作者名（如"…广泛的影响 2013"），只做窗口匹配，不报缺失
            hit = alias.get((sn, y)) if sn else None
            if not hit:   # 叙述式引用（于肖楠和张建新(2005)）：同年条目的任一姓名出现在引文前后即算对上
                hit = {i for i, (ns, yy) in enumerate(names) if yy == y and any(n_ and n_ in ctx for n_ in ns)}
            if hit:
                cited_idx |= hit
            elif sn:
                missing[(sn, y)] = 1
            else:
                unresolved += 1
        for k in sorted(missing):
            alt = [r for r in rset if r[0] == k[0] and r[1] and k[1] and r[1][:4] == k[1][:4]]
            issues.append("正文引了 %s %s，文献表没有%s" % (k[0], k[1], ("（文献表有 %s，后缀不一致）" % "/".join(x[1] for x in alt)) if alt else ""))
        for i, k in enumerate(rk):
            if k[0] and i not in cited_idx:
                issues.append("文献表有 %s %s，正文没有引用" % k)
        authseg = [M.fold(re.split(r"\(\s*%s" % YR, re.sub(r"^(?:[-*]\s+)?(?:\[\d+\]|\d+\.)\s*", "", e), 1)[0])[:160] for e in refs]
        for k, c in rset.items():
            if c > 1 and k[0]:
                segs = [re.sub(r"[\W_]+", "", authseg[i]) for i, kk in enumerate(rk) if kk == k]
                if len(set(segs)) < len(segs):
                    issues.append("文献表中 %s %s 出现 %d 次：作者与年份相同，可能是重复条目或缺少 a/b 后缀" % (k[0], k[1], c))
                else:
                    notes.append("%s %s 有 %d 篇首作者相同、合作者不同的文献：正文若都写 et al.，读者无法区分（APA 第 7 版要求写出足以区分的作者）" % (k[0], k[1], c))
        if unresolved:
            notes.append("%d 处括号含年份但识别不出作者（多为中文叙述或日期），未计入问题，需人工确认" % unresolved)
    else:
        nums = []
        for m in re.finditer(r"\[(\d+(?:\s*[-–,]\s*\d+)*)\]", body):
            for part in re.split(r"\s*,\s*", m.group(1)):
                r = re.match(r"(\d+)\s*[-–]\s*(\d+)", part)
                if r:
                    lo, hi = int(r.group(1)), int(r.group(2))
                    if hi < lo or hi - lo > 10000:
                        issues.append("引文编号范围无效或过大：%s" % part)
                    else:
                        nums += list(range(lo, hi + 1))
                else:
                    nums.append(int(part))
        n = len(refs)
        explicit_labels = []
        for entry in refs:
            m = re.match(r"^(?:[-*]\s+)?(?:\[(\d+)\]|(\d+)\.)\s*", entry)
            explicit_labels.append(int(m.group(1) or m.group(2)) if m else None)
        if any(x is not None for x in explicit_labels):
            if any(x is None for x in explicit_labels):
                issues.append("参考文献编号混合缺失，无法可靠核对")
            if explicit_labels != list(range(1, n + 1)):
                issues.append("参考文献显式编号不是从 1 起连续且唯一：%s" % explicit_labels)
            reference_numbers = {x for x in explicit_labels if x is not None}
        else:
            reference_numbers = set(range(1, n + 1))
        firsts = list(dict.fromkeys(nums))
        for x in sorted(set(nums)):
            if x not in reference_numbers:
                issues.append("正文引了 [%d]，文献表中没有对应编号" % x)
        for i in sorted(reference_numbers):
            if i not in set(nums):
                issues.append("文献表第 %d 条正文没有引用" % i)
        if firsts and firsts != sorted(firsts):
            notes.append("首次引用的编号不是按出现顺序递增（多数数字制期刊要求按出现顺序编号）")
        if re.search(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]", body):
            notes.append("检测到上标数字，无法可靠识别为引文，请人工核对")
    dois = [d.rstrip(".,;)") for e in refs for d in re.findall(r"10\.\d{4,9}/\S+", e)]
    for d, c in collections.Counter(d.lower() for d in dois).items():
        if c > 1:
            issues.append("DOI 重复：%s（%d 次）" % (d, c))
    for d in dois:
        if re.search(r"[\s,]|\.$", d):
            issues.append("DOI 格式可疑：%s" % d)
    online = "未查询（加 --online 才查 Crossref）"
    if a.online and dois:
        okn, bad, unreach = 0, [], False
        for d in dois:
            try:
                req = urllib.request.Request("https://api.crossref.org/works/" + d, headers={"User-Agent": "manuscript-lifecycle/1.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    okn += r.status == 200
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    bad.append(d)
                else:
                    unreach = True; break
            except Exception:
                unreach = True; break
        if unreach:
            online = "Crossref 不可达，只做了格式检查；DOI 是否存在需另行核实"
            issues.append("not_verified：请求了在线核对，但 Crossref 未完成；不能降级宣称已核实")
        else:
            online = "Crossref 查到 %d 个，查不到 %d 个" % (okn, len(bad))
            issues += ["not_verified：Crossref 未检索到 DOI（也可能由其他机构注册，不能直接判为虚假）：%s" % d for d in bad]
    elif a.online and not dois:
        issues.append("not_verified：请求在线核对，但没有识别到任何 DOI")
    L = ["# 引文核对：%s\n" % os.path.basename(a.path),
         "引文体例：%s；文献表 %d 条；DOI %d 个；%s。问题 %d 条。\n" % ({"ay": "作者–年份", "num": "数字编号"}[style], len(refs), len(dois), online, len(issues)),
         "只核对可识别的对应关系与格式。Crossref 响应只证明注册记录可检索，未比对作者/题名/年份，也不证明支持主张。引文语义必须读原文并记录全文 / 摘要 / 未核及审查依据。退出 0 不是引用内容验证通过。\n"]
    L += ["- " + x for x in issues] or ["- 未发现对应问题"]
    if notes:
        L += ["\n提示："] + ["- " + x for x in notes]
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    print(out[:3000] if not a.report else L[1].strip())
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
