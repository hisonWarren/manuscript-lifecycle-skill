#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
response_lint.py — 回复审稿人信的检查：逐条对应；每条有回应和位置；没有套话和防御；声称的新文字确实在修改稿里。

  python response_lint.py 回复信.md|docx [--manuscript 修改稿.md|docx] [--comments N] [--report out.md]
  python response_lint.py 审稿意见.docx --to-matrix comments_matrix.csv      # 只有意见、还没回复时：拆成处理表

识别的标记：
  · 审稿人分组：Reviewer 1 / Reviewer #2 / Referee 2 / Editor / 审稿人1。
  · 意见起点：Comment 1、Reviewer 1, Comment 2、R1.3、Point 2；分组内的小标题；全文没有显式意见编号时，分组内依次编号的"1."。
  · 回复起点：Response: / Answer: / Reply: / 回复：。
  · 位置：Changes: / Location: / page x, lines y / Section x / Table Sx / 第x页第y行，以及节名。
格式不同的信可能识别不全。报告开头会列出识别到的条数，先核对条数再看结论。
分组开头的总体评价（Overview、Summary，或写在 Reviewer 标题后面的概述）不要求单独回复。
三级：
  · ERROR：缺回复、占位符未填、引用的新文字在修改稿里找不到、条数与 --comments 不符。
  · WARN：既没有位置也没有"不修改＋理由"、致谢同义词轮换或附理由、非致谢开头反复出现、空泛的"已相应修改"、防御措辞；
    定位用 p./pp. 缩写或页行粒度不一致、用内部编号指文献、一条回复要靠另一条回复才读得懂（references/08 §3）。
  · INFO：统计。
退出码：0 无 ERROR；1 有 ERROR；2 输入错误，或既识别不到回复、又没有要求 --to-matrix。
"""
import argparse, collections, csv, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

H = r"^(?:#{1,6}\s*)?(?:\*\*)?\s*"
RE_GROUP = re.compile(H + r"(?:(?:Reviewer|Referee)\s*#?\s*:?\s*(\d+)|(Editor|Associate Editor|Editorial(?: office| team)?)(?:'s|’s)?(?!\s*comment\s*\d)|审稿人\s*([一二三四五六\d]+)|(编辑))\b\s*(?:\*\*)?\s*[:：]?\s*(.*)$", re.I)
RE_CMT = re.compile(H + r"(?:(?:Reviewer|Referee)\s*#?\s*\d+\s*[,，.]?\s*|Editor(?:'s|’s)?\s*)?(?:Comment|Point|Query|Concern|Issue|意见|问题)\s*#?\s*(\d+)\b", re.I)
RE_CODE = re.compile(H + r"R(\d+)\s*[.\-–]\s*(\d+)\b")
RE_NUM = re.compile(r"^(?:\*\*)?\s*(\d{1,2})\s*[.)、]\s*\S")
RE_SUBHEAD = re.compile(r"^(?:\*\*)?(?:[A-Z][A-Za-z&/-]*(?:\s+[A-Za-z&/-]+){0,2}|[\u4e00-\u9fff]{2,8})(?:\*\*)?$")
RESP_LABELS = r"Responses?|Answers?|Reply|Replies|Author(?:s'|’s|s)? (?:response|reply)|Our response|Rebuttal|作者回复|回复|答复|回应"
# 真实回复信里常见的拼写错误（实测样本用的是 Anwser:）；--resp-label 还可补充本稿自己的写法
RESP_TYPOS = r"Anwsers?|Ansewrs?|Answr|Asnwer|Respone|Reponses?|Responce|Resonse|Repsonse|Reponse"
def resp_regex(extra=()):
    labels = RESP_LABELS + "|" + RESP_TYPOS + "".join("|" + re.escape(x) for x in extra if x.strip())
    return re.compile(H + r"(?:%s)\s*(?:\*\*)*\s*[:：]\s*(?:\*\*)*\s*(.*)$" % labels, re.I)
RE_RESP = resp_regex()
RE_CHG = re.compile(H + r"(?:Changes?(?: made)?|Location|Revised text|Revisions?|Where changed|修改位置|修改内容)\s*(?:\*\*)?\s*[:：]\s*(?:\*\*)?\s*(.*)$", re.I)
RE_LOC = re.compile(r"\bpages?\s*\d+|\bp\.\s*\d+|\blines?\s*\d+|\bl\.\s*\d+|\bsections?\s*\d|\b(?:supplementary\s+)?(?:tables?|fig(?:ure)?s?\.?)\s*S?\d+|\bparagraph\s*\d|第\s*\d+\s*[页行段节]|表\s*S?\d+|图\s*S?\d+|\b(?:abstract|introduction|methods?|results|discussion|limitations?|conclusions?|highlights|references?|acknowledge?ments?|appendix|supplementary (?:material|file|table)s?|future directions?)\b|[“「](?:摘要|引言|方法|结果|讨论|局限|结论|附录|补充材料)[”」]|(?:摘要|引言|方法|结果|讨论|局限|结论|附录|补充材料|表注|图注)(?:部分|一节|节|中|第)", re.I)
RE_NOCHG = re.compile(r"\bno (?:change|changes|revision|revisions)\b|\bwe did not (?:change|revise|add|include)\b|\bwe have not (?:changed|added|included)\b|\bleft unchanged\b|\bnot (?:changed|revised)\b|未修改|不作修改|未作修改|保持不变", re.I)
RE_PH = re.compile(r"\[\s*\]|\bXX+\b|\bTBD\b|\bTODO\b|\bpage\s+[xX#?]\b|\blines?\s+[xX#?]\b|【待[^】]*】|\[待[^\]]*\]|\?\?\?")
THANKS = re.compile(r"^\W*(?:we (?:sincerely |greatly |really |truly |would like to )?(?:thank|appreciate|are (?:very )?grateful)|thank you|many thanks|感谢|谢谢)", re.I)
# 致谢附理由 / 同义词轮换：作者要逐条致谢时，固定一句朴素公式即可（08 §3）
# 仅用于已匹配 THANKS 的首句：附理由的 because/which led us / for pointing out…
THANKS_REASON = re.compile(
    r"\b(?:because|since)\b"
    r"|\bwhich\s+(?:led|helped|allowed|gave|enabled|prompted|improved|made)\b"
    r"|\bfor\s+(?:pointing\s+out|raising|highlighting|drawing\s+our\s+attention|bringing)\b"
    r"|因为|使得我们|让我们能够|促使我们",
    re.I)
THANKS_VERB = re.compile(r"\b(thank|appreciate|grateful)\b|(感谢|谢谢|感激)", re.I)
FLAT = re.compile(r"\b(?:valuable|insightful|excellent|constructive|thoughtful|helpful|great|careful|thorough|perceptive|astute|important)\s+(?:comments?|suggestions?|points?|observations?|questions?|remarks?|feedback|advice|recommendations?)\b"
                  r"|(?:宝贵|中肯|精辟|深刻|专业|富有(?:洞见|建设性))的?(?:意见|建议|见解|问题)|非常(?:好|重要|有价值)的(?:意见|建议|问题)", re.I)
DEF = re.compile(r"\bwe would like to (?:clarify|point out|emphasi[sz]e|stress|note)\b|\bthe reviewer (?:may have|might have|seems to have|has) (?:misunderstood|misread|overlooked|missed)\b|\bas (?:clearly|already|explicitly) (?:stated|mentioned|described|explained)\b|\bit should be noted that\b|\bwe (?:strongly|firmly) believe\b|\bas the reviewer will (?:surely )?agree\b|审稿人(?:可能)?误解|如前文已明确|需要(?:澄清|说明|指出)的是|我们认为审稿人|审稿人(?:可能)?(?:没有|未)(?:注意到|理解)|正如(?:文中|前文)(?:已经)?(?:明确)?(?:指出|说明)", re.I)
VAGUE = re.compile(r"\b(?:revised|modified|changed|updated|corrected|improved|edited)\s+(?:the (?:manuscript|text|paper|section)\s+)?(?:accordingly|as suggested|as requested|carefully|thoroughly|extensively)\b|\b(?:thoroughly|carefully|extensively) (?:revised|checked|proofread|edited)\b|\bha(?:s|ve) been (?:addressed|incorporated)\b|已(?:按|根据)(?:意见|要求)(?:进行了?)?修改|已全面修改|已(?:认真|仔细|逐条|全面)?(?:进行了?)?(?:修改|修正|完善)(?:完毕)?(?=\s*[。；;，,！!]|\s*$)", re.I)
QUOTE = re.compile(r"[“\"]([^”\"]{8,})[”\"]")
SUMMARY_T = re.compile(r"overview|summary|general (?:comments?|assessment)|comments to the authors?|总体|概述|总评", re.I)


def parse(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    explicit = sum(1 for l in lines if RE_CMT.match(l) or RE_CODE.match(l)) >= 2
    units, pre, group, last = [], [], "?", collections.Counter()
    cur = None

    def new(g, num, title="", intro=False):
        u = {"group": g, "num": num, "title": title, "comment": [], "response": [], "changes": [], "state": "comment", "intro": intro}
        units.append(u)
        return u

    base = collections.Counter()   # 审稿人按主题分组、每组重新编号时（Methodology 1, 2; Results 1, 2），编号累计，不算重复
    for li, l in enumerate(lines):
        nxt = lines[li + 1] if li + 1 < len(lines) else ""
        if cur is not None and cur["state"] in ("response", "changes") and RE_SUBHEAD.match(l.strip()) and RE_NUM.match(nxt) and int(RE_NUM.match(nxt).group(1)) == 1:
            base[group] = last[group]
            cur = None
            continue
        mr, mch = RE_RESP.match(l), RE_CHG.match(l)
        mg = RE_GROUP.match(l) if not (mr or mch) else None
        if mg and len(l) < 400 and not RE_CMT.match(l):
            group = ("Reviewer %s" % (mg.group(1) or mg.group(3))) if (mg.group(1) or mg.group(3)) else "Editor"
            tail = (mg.group(5) or "").strip()
            cur = new(group, None, intro=True) if len(tail) > 30 else None
            if cur:
                cur["comment"].append(tail)
            continue
        mc = RE_CMT.match(l) or RE_CODE.match(l)
        if mc:
            num = int(mc.group(mc.lastindex))
            code = RE_CODE.match(l)
            if code:
                group = "Reviewer %s" % code.group(1)
            else:
                named = re.match(H + r"(?:Reviewer|Referee)\s*#?\s*(\d+)", l, re.I)
                if named:
                    group = "Reviewer %s" % named.group(1)
            if re.match(H + r"editor", l, re.I):
                group = "Editor"
            cur = new(group, num, title=l); last[group] = num
            rest = l[mc.end():].strip(" *:：.")
            if len(rest) > 20:
                cur["comment"].append(rest)
            continue
        if mr:
            if cur is None:
                cur = new(group, None)
            cur["state"] = "response"
            if mr.group(1).strip():
                cur["response"].append(mr.group(1).strip())
            continue
        if mch:
            if cur is None:
                cur = new(group, None)
            cur["state"] = "changes"
            if mch.group(1).strip():
                cur["changes"].append(mch.group(1).strip())
            continue
        if re.match(r"^#{1,6}\s", l) and group != "?" and not explicit:
            if cur and not cur["comment"] and not cur["response"]:
                cur["title"] = l          # 连续标题：分类标题之后的具体问题标题
            else:
                cur = new(group, None, title=l)
            continue
        mn = RE_NUM.match(l)
        if mn and cur is not None and cur["state"] in ("response", "changes"):
            n = int(mn.group(1))
            sub = cur.get("sub_n", 0)
            # 回复内部的 1. 2. 分点（实测样本：编辑两条意见合并作答）不是新意见
            prev = cur[cur["state"]][-1] if cur[cur["state"]] else ""
            ours = re.search(r"\b(?:we|our|us)\b|我们", l[:80], re.I)
            # 仅当上一行以冒号引出列表、或该行是作者口吻时，才把编号当作回复内部分点；否则仍可能是下一条意见
            if (n == 1 and (re.search(r"[:：]\s*$", prev) or ours)) or (sub and n == sub + 1 and (n != last[group] + 1 or ours)):
                cur["sub_n"] = n
                cur[cur["state"]].append(l); continue
        if mn and not explicit and group != "?" and int(mn.group(1)) + base[group] == last[group] + 1:
            cur = new(group, int(mn.group(1)) + base[group]); last[group] = int(mn.group(1)) + base[group]
            cur["comment"].append(l); continue
        if cur is None and group != "?" and units and len(l) > 40:
            cur = new(group, None)       # 分组标题之后未编号的意见段归入该组，不算信件开头说明
            cur["comment"].append(l); continue
        if cur is None:
            pre.append(l)
        else:
            cur[{"comment": "comment", "response": "response", "changes": "changes"}[cur["state"]]].append(l)
    for i, u in enumerate(units):
        u["summary"] = (not u["response"] and (u["intro"] or bool(SUMMARY_T.search(u["title"])) or
                        (u["num"] is None and i + 1 < len(units) and units[i + 1]["group"] == u["group"] and units[i + 1]["num"] == 1)))
    return pre, units


COMMENT_ID = re.compile(r"^\s*(?:[-*]\s*)?(?:#+\s*)?(?:\*\*)?([A-Z]{1,3}\d+(?:[.\-]\d+)*)(?:\*\*)?(?=[.、:：）)\s])")


def comment_count(v):
    """--comments 可以是条数，也可以是审稿意见文件：数行首的意见编号（E1、R1.1、R2-3）。"""
    v = str(v).strip()
    if re.fullmatch(r"\d+", v):
        return int(v)
    if os.path.isfile(v):
        ids = []
        with open(v, encoding="utf-8-sig") as f:
            for line in f:
                m = COMMENT_ID.match(line)
                if m and m.group(1) not in ids:
                    ids.append(m.group(1))
        return len(ids)
    return None


RE_ABBR_LOC = re.compile(r"\(\s*(?:see\s+)?pp?\.\s*\d|\bpp?\.\s+\d+(?:\s*[–-]\s*\d+)?\s*\)")
RE_REFNO = re.compile(r"\b(?:new\s+)?(?:reference|ref\.?)\s+(?:no\.?\s*)?\d+\b|新增?文献\s*\d+", re.I)
RE_CROSS = re.compile(r"\bsee\s+(?:the\s+|our\s+)?(?:response|reply|answer)s?\s+to\b|\b(?:discussed|addressed|explained|described|answered)\s+under\s+(?:Reviewer|Referee|Editor|Comment)\b"
                      r"|\bsee\s+(?:Reviewer|Referee)\s*#?\d|见(?:审稿人|评审人|编辑)[^。；]{0,10}(?:回复|意见|第)", re.I)
RE_PAGE_LINE = re.compile(r"\bPages?\s+\d+\s*,\s*lines?\s+\d", re.I)
RE_PAGE_ONLY = re.compile(r"\(\s*(?:see\s+)?pages?\s+\d+(?:\s*[–-]\s*\d+)?\s*\)", re.I)


# Pointer hints inspect author prose only, not scientific meaning.
RE_OPTION_POINTER = re.compile(
    r"\b(?:the\s+)?(?:first|second|third|former|latter)(?:\s+of\s+(?:the\s+)?(?:two|three))?"
    r"\s+(?:explanations?|interpretations?|possibility|possibilities|hypothes(?:is|es))\b", re.I)
RE_RULE_POINTER = re.compile(r"\b(?:criterion|rule|condition)\s*\([a-z0-9]+\)", re.I)
RE_POINTER_GLOSS = re.compile(
    r"^\s*(?:[—–:]\s*\S|(?:[,\-]\s*)?(?:that|namely|which|requiring|required|requires|"
    r"means|meant|states|specified|covers|includes)\b|[,\-]?\s*i\.e\.)", re.I)


def reply_pointer_hints(text):
    """Return candidates, not errors; an earlier explanation may suffice."""
    quoted = [(m.start(), m.end()) for m in QUOTE.finditer(text)]
    hints = []
    for code, pattern in (("R-PTR", RE_OPTION_POINTER), ("R-RULE", RE_RULE_POINTER)):
        explained = set()
        for match in pattern.finditer(text):
            if any(start <= match.start() < end for start, end in quoted):
                continue
            key = re.sub(r"\s+", " ", match.group(0).lower())
            if RE_POINTER_GLOSS.match(text[match.end():]):
                explained.add(key)
                continue
            if key not in explained:
                hints.append("%s 指称候选「%s」：核对本条是否已解释其内容；已解释可保留，编号本身不是错误（08 §3.1）" % (code, match.group(0)))
    return hints


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("letter"); ap.add_argument("--manuscript", default=""); ap.add_argument("--comments", default="0", help="意见条数，或审稿意见文件路径（按行首编号 E1、R1.1 计数）")
    ap.add_argument("--to-matrix", default=""); ap.add_argument("--report", default="")
    ap.add_argument("--resp-label", action="append", default=[], help="本稿回复标记的写法（可多次），如 --resp-label \"Authors' reply\"")
    a = ap.parse_args()
    cc = comment_count(a.comments)
    if cc is None:
        print("--comments 要么写意见条数，要么给审稿意见文件的路径：%s" % a.comments, file=sys.stderr)
        return 2
    a.comments = cc
    global RE_RESP
    RE_RESP = resp_regex(a.resp_label)
    if not os.path.exists(a.letter):
        print("找不到 %s" % a.letter, file=sys.stderr); return 2
    if a.manuscript and (not os.path.isfile(a.manuscript) or not M.load_text(a.manuscript).strip()):
        print("not_verified：指定的修改稿不存在或为空，不能跳过核对", file=sys.stderr); return 2
    pre, units = parse(M.load_text(a.letter))
    cm = [u for u in units if not u["summary"]]
    if not cm:
        print("not_verified：没有识别到可处理意见；请核对解析范围", file=sys.stderr); return 2
    if a.to_matrix:
        with M.wfile(a.to_matrix) as f:
            w = csv.writer(f)
            w.writerow(["id", "reviewer", "comment_verbatim", "what_is_questioned", "type", "situation", "decision",
                        "action", "evidence", "location", "status"])
            k = collections.Counter()
            for u in cm:
                k[u["group"]] += 1
                w.writerow(["%s-%d" % (u["group"].replace("Reviewer ", "R").replace("Editor", "E"), u["num"] or k[u["group"]]),
                            u["group"], " ".join(([u["title"].strip("#* ")] if u["title"] else []) + u["comment"]), "", "", "", "", "", "", "", "todo"])
        print("已写出处理表：%d 条意见（%s）→ %s" % (len(cm), "，".join("%s %d" % x for x in collections.Counter(u["group"] for u in cm).items()), a.to_matrix))
        return 0
    if not any(u["response"] for u in units):
        print("没有识别到回复标记（Response:/Answer:/回复：及常见拼写错误）。若本稿用别的标记，加 --resp-label 指定；若只有审稿意见，用 --to-matrix 拆成处理表。", file=sys.stderr)
        return 2
    ms = M.norm_for_match(M.load_text(a.manuscript)) if a.manuscript and os.path.exists(a.manuscript) else None
    err, warn, info = [], [], []
    info.extend("开头：" + hint for hint in reply_pointer_hints(" ".join(pre)))
    openers, thanks_verbs, nreason, nthanks, nflat = collections.Counter(), set(), 0, 0, 0
    seen = collections.Counter((u["group"], u["num"]) for u in cm if u["num"] is not None)
    for (g, n), c in seen.items():
        if c > 1:
            err.append("%s 意见 %d 出现 %d 次（编号重复）" % (g, n, c))
    for i, u in enumerate(cm, 1):
        tag = "%s·%s" % (u["group"], u["num"] if u["num"] is not None else "#%d" % i)
        resp, chg = " ".join(u["response"]), " ".join(u["changes"])
        if not resp.strip():
            err.append("%s：没有回复" % tag); continue
        info.extend(tag + "：" + hint for hint in reply_pointer_hints(resp))
        if RE_PH.search(resp + " " + chg):
            err.append("%s：有未填的占位符：%s" % (tag, RE_PH.search(resp + " " + chg).group(0)))
        has_loc = bool(RE_LOC.search(chg) or RE_LOC.search(resp))
        if not has_loc and not RE_NOCHG.search(resp + " " + chg):
            warn.append("%s：既没有修改位置，也没有说明不修改及理由" % tag)
        if VAGUE.search(resp) and not RE_LOC.search(chg):
            warn.append("%s：空泛的修改声明「%s」，请给出具体位置与改后的文字" % (tag, VAGUE.search(resp).group(0)))
        for m in DEF.finditer(resp):
            warn.append("%s：防御或居高临下的措辞「%s」" % (tag, m.group(0)))
        first = M.sentences(resp)[:1]
        if first:
            if THANKS.match(first[0]):
                nthanks += 1
                vm = THANKS_VERB.search(first[0])
                if vm:
                    thanks_verbs.add(vm.group(0).lower())
                if THANKS_REASON.search(first[0]):
                    nreason += 1
                    warn.append("%s：致谢附了理由「%s…」。逐条致谢时用固定朴素句式，理由写进实质回复（references/08 §3）" % (tag, first[0][:48]))
            else:
                # 同一开头反复出现：只计非致谢句；固定致谢公式的重复不再报
                openers[" ".join(M.LAT.findall(first[0].lower())[:5]) or first[0][:8]] += 1
        nflat += len(FLAT.findall(resp))
        if ms is not None:
            both = resp + " " + chg
            for qm in QUOTE.finditer(both):
                q = qm.group(1)
                if re.search(r"(?:删去|删除|去掉|去除|不再|原稿|原文|原句|旧稿|改掉|deleted?|removed?|original(?:ly)?|previous(?:ly)?)[^。.;；]{0,24}$",
                             both[max(0, qm.start() - 40):qm.start()], re.I) or re.search(r"[^。]{0,40}(?:删去|删除|去掉)", both[qm.start():qm.start() + 60]) and re.search(r"等[^。]{0,12}(?:表述|说法|内容)", both[qm.end():qm.end() + 30]):
                    continue        # 引的是被删掉的旧文字
                nq = M.norm_for_match(q)
                if nq and nq not in ms:
                    err.append("%s：引用的新文字在修改稿里找不到：「%s…」" % (tag, q[:70]))
    answers = [(" ".join(u["response"]) + " " + " ".join(u["changes"])) for u in cm]
    ablob = "\n".join(answers)
    if RE_ABBR_LOC.search(ablob):
        warn.append("定位用了 p./pp. 缩写（如「%s」）：写全 page/pages（目标刊另有规定时从其规定）" % RE_ABBR_LOC.search(ablob).group(0).strip())
    if RE_PAGE_LINE.search(ablob) and RE_PAGE_ONLY.search(ablob):
        warn.append("定位粒度不一致：有的写到行，有的只写到页（如「%s」）。全信统一" % RE_PAGE_ONLY.search(ablob).group(0))
    if RE_REFNO.search(ablob):
        warn.append("用编号指文献（如「%s」）：写法与正文的文内引用一致，读者才知道是哪一篇" % RE_REFNO.search(ablob).group(0))
    if RE_CROSS.search(ablob):
        warn.append("回复靠另一条回复才读得懂（如「%s」）：审稿人可能只读自己那几条，改成本条自足" % RE_CROSS.search(ablob).group(0))
    n = len(cm)
    if a.comments and n != a.comments:
        err.append("识别到 %d 条意见，应有 %d 条：有遗漏或合并" % (n, a.comments))
    if nthanks >= 3 and len(thanks_verbs) >= 2:
        warn.append("逐条致谢轮换了同义词（%s）。固定一句朴素公式，只按意见类型换 comment/suggestion/question（references/08 §3）"
                    % " / ".join(sorted(thanks_verbs)))
    elif n >= 3 and nthanks / n > 0.5 and nreason == 0 and len(thanks_verbs) <= 1:
        info.append("有 %d/%d 条以致谢开头；句式一致时按作者习惯保留，默认仍是信首致谢一次即可" % (nthanks, n))
    rep = [(k, c) for k, c in openers.items() if c >= 3 and k]
    if rep:
        warn.append("同一开头反复出现：" + "；".join("「%s…」×%d" % x for x in rep))
    if nflat >= max(3, n / 2):
        warn.append("恭维性形容词 %d 处（valuable/insightful suggestion、宝贵意见等）。删去后回复更可信" % nflat)
    info.append("意见 %d 条（%s）；不需单独回复的总体评价 %d 段；开头说明 %d 段（%s）" % (
        n, "，".join("%s %d" % x for x in collections.Counter(u["group"] for u in cm).items()),
        sum(1 for u in units if u["summary"]), len(pre), "有" if sum(M.count_words(x) for x in pre) >= 40 else "缺少修改概述"))
    L = ["# 回复信检查：%s\n" % os.path.basename(a.letter), "ERROR %d、WARN %d。%s\n" % (len(err), len(warn), "；".join(info))]
    L += ["- **ERROR** " + e for e in err] + ["- WARN " + w for w in warn]
    L.append("\n边界：这是回复标记、位置线索与引号内文字的启发式检查，不验证回应充分、实际修改语义、图表改变或页码正确。短语命中不证明问题已解决；省略引文、无引号改写须人工核对。意见总数%s；修改稿文本%s。页码默认取正文页脚，不用系统 PDF 的 Page X of Y。" % ("已提供作数量对照" if a.comments else "未提供，不能确认无漏项", "已参与匹配" if ms is not None else "未提供，修改声明未核"))
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    print(out if not a.report else L[1].strip())
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
