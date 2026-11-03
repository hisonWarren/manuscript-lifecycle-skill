#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
density_check.py — 信息量检查：空句候选、术语负荷、跨节重复的数字、无锚点的论证段。

  python density_check.py 稿件.md|docx [--lexicon 领域词表.json] [--max-terms 4] [--report out.md] [--json out.json]

删句测试：一句话删掉，这一段少了什么事实（数字、引文、缩写或专名、术语、统计量）？什么都不少、又与相邻句高度重合
的句子，是候选空句；什么都不少、又是套话或元话语的句子，也是候选。总起句、承接句本来就不带新事实，脚本只负责挑出来。
术语负荷：一句里统计/领域术语 ≥ --max-terms 个。结论、讨论首段、摘要结论句出现这样的句子按 MUST 报——这几处要用读者的语言。
跨节重复：同一个数字（两位以上小数或百分数）出现在 ≥3 个节，多半是在复述而不是解释。
无锚点论证段：引言、讨论里既无引文、也无数字或专名的段落。
领域术语：用 --lexicon 传入 {"domain_terms": [...]}，否则只按通用统计词计。
退出码：0 无 MUST；1 有 MUST；2 输入错误。
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

ACR = re.compile(r"\b[A-Z][A-Z0-9\-]{1,9}\b")
CAPW = re.compile(r"(?<!^)(?<![.!?]\s)\b[A-Z][a-z]{2,}\b")


def anchors(s, R):
    a = M.count_numbers(s) + M.count_citations(s) + len(ACR.findall(s))
    for k in ("stat_terms", "domain_terms"):
        if R.get(k):
            a += len(R[k].findall(s))
    return a


def cset(s, lang):
    if lang == "zh":
        c = "".join(M.CJK.findall(s)); return {c[i:i + 2] for i in range(len(c) - 1)}
    return {w.lower() for w in M.LAT.findall(s) if len(w) >= 4}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path"); ap.add_argument("--lexicon", action="append", default=[]); ap.add_argument("--max-terms", type=int, default=4)
    ap.add_argument("--lang", default="auto", choices=["auto", "en", "zh"]); ap.add_argument("--report", default=""); ap.add_argument("--json", default="")
    a = ap.parse_args()
    if not os.path.exists(a.path):
        print("找不到文件", file=sys.stderr); return 2
    text = M.load_text(a.path)
    if not text.strip():
        print("not_verified：稿件为空，不能将零检查项记为通过", file=sys.stderr); return 2
    lang = M.detect_lang(text) if a.lang == "auto" else a.lang
    R = M.lex_rx(M.load_lexicon(lang, a.lexicon), lang)
    blocks = M.parse(text)
    P = {}
    for b in blocks:
        if b["kind"] == "para":
            P.setdefault(b["sec"], []).append(M.sentences(b["text"]))
    assessed = sum(len(ss) for sec,paras in P.items() if sec not in ("front","back","references") for ss in paras)
    if assessed == 0:
        print("not_verified：未识别到可评估的论文节句子；核对切节和输入范围", file=sys.stderr); return 2
    items = []

    def add(level, code, msg, ex=()):
        items.append({"level": level, "code": code, "msg": msg, "examples": [e[:220] for e in ex][:8]})

    def terms(s):
        found = set()
        for k in ("stat_terms", "domain_terms"):
            if R.get(k):
                found.update(x.lower() for x in R[k].findall(s))
        return found

    # 1 空句候选
    empty = []
    for sec in ("introduction", "discussion", "limitations", "conclusion"):
        for para in P.get(sec, []):
            for i, s in enumerate(para):
                if anchors(s, R) > 0:
                    continue
                nb = [para[j] for j in (i - 1, i + 1) if 0 <= j < len(para)]
                ov = max([len(cset(s, lang) & cset(x, lang)) / max(1, len(cset(s, lang) | cset(x, lang))) for x in nb] or [0])
                tpl = any(R.get(k) and R[k].search(s) for k in ("template", "meta", "future_generic"))
                if ov >= 0.35 or tpl:
                    empty.append("[%s] %s" % (sec, s))
    if empty:
        add("SHOULD", "E1", "候选空句 %d 句：删掉后这一段不少任何事实，且与相邻句高度重合或属于套话、元话语。逐句判断删、并，还是补一个具体锚点。" % len(empty), empty)
    # 2 术语负荷
    heavy = {}
    for sec, paras in P.items():
        if sec in ("references", "back", "front"):
            continue
        for k, para in enumerate(paras):
            for s in para:
                t = terms(s)
                if len(t) >= a.max_terms:
                    heavy.setdefault(sec, []).append((k, s, sorted(t)))
    must = []
    for k, s, t in heavy.get("conclusion", []):
        must.append("[结论] %s（%s）" % (s, "、".join(t)))
    for k, s, t in heavy.get("discussion", []):
        if k == 0:
            must.append("[讨论首段] %s（%s）" % (s, "、".join(t)))
    absp = P.get("abstract", [])
    if absp:
        for s in absp[-1][-2:]:
            t = terms(s)
            if len(t) >= a.max_terms:
                must.append("[摘要结论句] %s（%s）" % (s, "、".join(sorted(t))))
    if must:
        add("MUST", "E2", "结论、讨论首段或摘要结论句里有术语负荷高的句子（≥%d 个统计/领域术语）。这几处要让同领域非方法专家一读就懂。" % a.max_terms, must)
    other = ["[%s] %s" % (sec, s) for sec, lst in heavy.items() if sec not in ("conclusion",) for k, s, t in lst if not (sec == "discussion" and k == 0)]
    if other:
        add("INFO", "E3", "其余各节术语负荷高的句子 %d 句。方法里可以出现，但首次出现的术语要有一句平实解释；引言和讨论里要少。" % len(other), other)
    dist = {sec: len({x for para in P.get(sec, []) for s in para for x in terms(s)}) for sec in ("introduction", "methods", "results", "discussion", "conclusion")}
    add("INFO", "E4", "各节不同术语数：" + "；".join("%s %d" % (k, v) for k, v in dist.items() if P.get(k)))
    # 3 跨节重复数字
    where = {}
    for sec in ("abstract", "introduction", "results", "discussion", "limitations", "conclusion"):
        for para in P.get(sec, []):
            for s in para:
                for tok, _ in M.number_tokens(s):
                    if re.search(r"\.\d{2,}", tok) or tok.endswith("%"):
                        where.setdefault(tok.replace("−", "-").lstrip("0"), set()).add(sec)
    rep = sorted(((t, sorted(v)) for t, v in where.items() if len(v) >= 3), key=lambda x: -len(x[1]))
    if rep:
        add("SHOULD", "E5", "%d 个数字出现在 ≥3 个节。摘要和结果报告数字；讨论解释它意味着什么；结论一般不需要数字。" % len(rep),
            ["%s：%s" % (t, "、".join(v)) for t, v in rep])
    # 4 无锚点论证段
    bare = []
    for sec in ("introduction", "discussion"):
        for k, para in enumerate(P.get(sec, [])):
            txt = " ".join(para)
            if (sec == "discussion" and k == 0) or (sec == "introduction" and k == 0) or (R.get("aim") and R["aim"].search(txt)):
                continue          # 讨论首段、引言首段（GG4 要求的现象与利害）与目的段本来就以陈述为主
            if len(para) >= 2 and M.count_citations(txt) == 0 and M.count_numbers(txt) == 0 and not ACR.search(txt):
                bare.append("[%s] %s" % (sec, txt[:160]))
    if bare:
        add("SHOULD", "E6", "%d 个引言/讨论段落既无引文也无数字或专名。论证段需要依据；纯过渡段请并入相邻段。" % len(bare), bare)
    rank = {"MUST": 0, "SHOULD": 1, "INFO": 2}
    items.sort(key=lambda x: rank[x["level"]])
    nm = sum(i["level"] == "MUST" for i in items)
    L = ["# 信息量检查：%s\n" % os.path.basename(a.path),
         "MUST %d、SHOULD %d、INFO %d。删不删、补不补由作者判断；判断框架见 references/06_information_depth.md。\n" % (
             nm, sum(i["level"] == "SHOULD" for i in items), sum(i["level"] == "INFO" for i in items))]
    for it in items:
        L.append("- **%s %s** %s" % (it["level"], it["code"], it["msg"]))
        L += ["  - %s" % e for e in it["examples"]]
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
        print("MUST %d：%s" % (nm, " ".join(i["code"] + ("!" if i["level"] == "MUST" else "") for i in items)))
    else:
        print(out)
    if a.json:
        with M.wfile(a.json) as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
    return 1 if nm else 0


if __name__ == "__main__":
    sys.exit(main())
