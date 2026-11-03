#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
move_check.py — 语步（rhetorical move）对照：先核实编码有原文依据，再比较稿件与同类文献的段落功能结构。

  python move_check.py 编码.json [--report out.md] [--min-common 0.6] [--max-rare 0.2]

编码文件格式见 assets/templates/moves_coding_example.json。每个单元是一篇文献（或稿件）的一个目标段落，
例如 intro_last 引言末段、disc_first 讨论首段、conclusion 结论。逐句给出 [语步代码, 该句中逐字出现的线索短语]。
为什么要线索短语：模型给范文"编码"时最容易凭印象编。线索短语必须逐字（忽略大小写与标点）出现在该段，且按句序排列；
脚本只核对线索是否存在及顺序，不能验证语义标签。必须提供单独的 source 文件；内嵌 text 也须能在该源中找到。
编码条数与该段句数相差应 ≤1，否则提示漏编、合并编码或断句失败。
比较内容：各语步在对标文献中的出现比例，首句与末句的语步分布；稿件缺少的常见语步（≥min-common），稿件有而对标少见的语步（≤max-rare）。
段落级单元（"granularity": "paragraph"）：一段一条编码，线索取自该段首句；不给 text/hint 时整个 source 文件就是这一节（例如引言全文），
段落数按空行切分，必须与编码条数相等；一段承担几项职能就用“+”连写（如 AIM+DES+HYP），每一项都要有线索支持（线索放在该段）。用它比较一节的段落职能序列（引言有没有交代测量依据的段落 SIG、有没有张力段 TEN……）。
--json 输出机器可读的偏离（genre_gate MV1 读它：每个偏离都要在 benchmark_decisions.csv 有 move:<节>:<语步> 的裁决行）。
关键段（intro_closing 引言收束段、intro_paras 引言段落序列、disc_first、conclusion）由 S2 编码近邻、S5 编码稿件（references/20 §1b、28）。
退出码：0 文本线索核对完成（语义未验证）；1 有找不到的线索、非法代码或覆盖问题；2 输入错误或零覆盖。
"""
import argparse, collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

MOVES = {
    "CTX": "背景/重要性/公认看法", "LIT": "既往研究", "DEF": "概念/定义", "GAP": "空白/未知", "TEN": "张力/相反证据",
    "STK": "后果/为何重要", "AIM": "目的/问题", "HYP": "假设/预期", "DES": "设计/数据（引言预告或讨论重述）",
    "SCO": "范围/探索性说明", "VAL": "价值/新颖性", "FND": "主要发现", "INT": "解释/含义收束", "CMP": "与既往研究比较",
    "MEC": "可能机制", "IMP": "临床/实践含义", "QUA": "限定/局限", "FUT": "未来研究（具体）", "GEN": "一般性结论",
    "MTH": "方法学解释", "MDS": "研究设计", "MSRC": "数据来源/场所", "MREC": "招募", "MELG": "纳入排除",
    "MNUM": "人数/流程/人口学", "METH": "伦理/知情同意", "MTIME": "时间/日程", "MINS": "测量工具", "MANA": "分析步骤",
    "MRAT": "分析理由/目的", "MFIT": "拟合/显著性标准", "MMIS": "缺失数据", "MSW": "软件", "MSEN": "敏感性分析",
    "MTRN": "透明度/预注册声明", "MREF": "引用他处细节", "MORD": "结果呈现顺序", "RSUM": "结果：发现陈述",
    "RNUM": "结果：数字与区间", "RPTR": "结果：指向表图", "RCMP": "结果：组间/模型比较",
    "SIG": "测量依据：候选指标/成分反映什么、为什么能检验本文问题、各解释对它预测什么",
}


def locate(unit, base):
    src = unit.get("source", "")
    path = src if os.path.isabs(src) else os.path.join(base, src)
    if not src or not os.path.isfile(path):
        return None
    source_text = M.load_text(path)
    if not unit.get("text") and not unit.get("hint"):
        return source_text      # 没给 text/hint：source 文件本身就是这个单元（一段或一节的原文摘录）
    if unit.get("text"):
        # The supplied excerpt is evidence only when located in a separate source.
        return unit["text"] if M.norm_for_match(unit["text"]) in M.norm_for_match(source_text) else None
    hint = M.norm_for_match(unit.get("hint", ""))
    for b in M.parse(source_text):
        if b["kind"] in ("para", "caption") and hint and hint in M.norm_for_match(b["text"]):
            return b["text"]
    return None


LEAD = re.compile(r"^(?:(?:thus|therefore|hence|furthermore|moreover|besides|however|finally|first(?:ly)?|second(?:ly)?|third(?:ly)?|"
                  r"in addition|additionally|accordingly|correspondingly|specifically|consequently|as such|in sum|in summary|in conclusion|to summarize|to sum up|taken together|collectively|overall|together|"
                  r"based on (?:the|these) (?:above )?(?:evidence|findings|considerations)|given (?:this|these))\s*,?\s+)+", re.I)


def opener_key(sentence, n=3):
    """语步的实现方式：去掉句首连接语后的前几个词（小写）。比较的是同一语步在近邻里怎么起句，不是内容。"""
    s = LEAD.sub("", sentence.strip().lstrip("（(\"'“"))
    if M.CJK.search(s[:6]):
        return re.sub(r"[，,：:、\s]", "", s)[:4]
    return " ".join(re.findall(r"[A-Za-z][A-Za-z'’-]*", s.lower())[:n])


def analyze(data, base, min_common=0.6, max_rare=0.2):
    """核对编码并比较；返回 (errors, warns, ok_units, result)。result 是 --json 的内容。"""
    moves = dict(MOVES); moves.update(data.get("moves", {}))
    errors, warns, ok_units = [], [], []
    for u in data.get("units", []):
        if not isinstance(u, dict) or u.get("role") not in ("draft", "exemplar", "ex") or not isinstance(u.get("codes"), list) or not u["codes"]:
            errors.append("单元缺少有效 role 或非空 codes"); continue
        tag = "%s·%s" % (u.get("paper", "?"), u.get("section", "?"))
        if any(not isinstance(c, list) or len(c) != 2 or not all(isinstance(x, str) and x.strip() for x in c) for c in u["codes"]):
            errors.append("%s：每条编码须为非空的 [代码, 原文线索]" % tag); continue
        para = locate(u, base)
        if para is None:
            errors.append("%s：找不到段落（检查 source 与 hint）" % tag); continue
        np_ = M.norm_for_match(para); pos = -1; uerr = False
        for code, cue in u.get("codes", []):
            parts = code.split("+") if u.get("granularity") == "paragraph" else [code]
            if any(c not in moves for c in parts):
                errors.append("%s：未定义的语步代码 %s" % (tag, code)); uerr = True; continue
            cues = [x.strip() for x in cue.split("||") if x.strip()]
            if u.get("granularity") == "paragraph" and len(cues) < len(parts):
                errors.append("%s：%s 有 %d 项职能，只给了 %d 条线索（用 || 分隔，每项一条）" % (tag, code, len(parts), len(cues))); uerr = True; continue
            for one in cues:
                nc = M.norm_for_match(one)
                nw = len(nc.split()) if not M.CJK.search(one) else len(M.CJK.findall(one)) / 2
                if nw < 2 or nw > 20:
                    warns.append("%s：线索「%s」长度不合适（2–20 词）" % (tag, one[:40]))
                i = np_.find(nc, max(pos, 0))
                if i < 0:
                    if np_.find(nc) >= 0:
                        errors.append("%s：线索「%s」与句序不符" % (tag, one[:40])); uerr = True; continue
                    errors.append("%s：线索「%s」不在原文中" % (tag, one[:60])); uerr = True; continue
                pos = i + 1
        if u.get("granularity") != "paragraph":
            ss = M.sentences(para)
            real = []
            for code, cue in u.get("codes", []):
                nc = M.norm_for_match(cue.split("||")[0])
                hit = next((s for s in ss if nc and nc in M.norm_for_match(s)), "")
                if hit:
                    real.append([code, hit[:160], opener_key(hit)])
            u["_realizations"] = real
        if u.get("granularity") == "paragraph":
            npara = len([x for x in re.split(r"\n\s*\n", para) if x.strip()])
            if npara != len(u["codes"]):
                errors.append("%s：段落级编码 %d 条，该节 %d 段（一段一条）" % (tag, len(u["codes"]), npara)); uerr = True
        else:
            ns = len(M.sentences(para))
            if abs(ns - len(u.get("codes", []))) > 1:
                errors.append("%s：编码 %d 条，该段 %d 句（应逐句编码；断句异常须先修复）" % (tag, len(u.get("codes", [])), ns)); uerr = True
        if not uerr:
            ok_units.append(u)
    by = collections.defaultdict(lambda: {"ex": [], "draft": []})
    for u in ok_units:
        by[u.get("section", "?")]["draft" if u.get("role") == "draft" else "ex"].append(u)
    result = {"schema_version": 2, "min_common": min_common, "max_rare": max_rare, "errors": errors, "sections": {}}
    for sec, g in by.items():
        # 比例只用类型匹配的近邻算（type_match 为 false 的只进分层对照）；第八轮：两篇综合刊混进 3 篇近邻，
        # 让“引言末段预告结果”看起来是多数做法，而类型匹配的学科期刊 5/5 都不预告
        allex = g["ex"]
        ex = [u for u in allex if u.get("type_match") is not False]
        venues = collections.Counter(re.split(r"[\s.]+", (u.get("venue") or "").strip())[0].lower() for u in ex if (u.get("venue") or "").strip())
        if venues and len(ex) >= 3:
            top, k = venues.most_common(1)[0]
            if k / len(ex) > 0.5:
                warns.append("%s：类型匹配的近邻有 %d/%d 篇来自同一刊物或出版社（%s…）；写法可能反映这一家的惯例，补其他来源的近邻再下结论" % (sec, k, len(ex), top))
        unknown = [u.get("paper", "?") for u in ex if "type_match" not in u]
        if unknown:
            warns.append("%s：%d 个近邻单元没标 type_match（%s），按类型匹配计；请注明，并写 family（discipline / general 等）" % (sec, len(unknown), "、".join(unknown[:4])))
        n = len(ex)
        parts = lambda c: c.split("+")
        fams = collections.defaultdict(list)
        for u in allex:
            fams[u.get("family") or ("type_matched" if u.get("type_match") is not False else "other")].append(u)
        fam_presence = {f: {m: round(sum(1 for u in us if m in {x for c, _ in u["codes"] for x in parts(c)}) / len(us), 3)
                            for m in {x for u in us for c, _ in u["codes"] for x in parts(c)}} for f, us in fams.items()}
        fam_n = {f: len(us) for f, us in fams.items()}
        conditional = {}
        big = [f for f in fams if fam_n[f] >= 2]
        for m in {x for f in big for x in fam_presence[f]}:
            vals = {f: fam_presence[f].get(m, 0.0) for f in big}
            if len(vals) >= 2 and max(vals.values()) >= min_common and min(vals.values()) <= max_rare:
                conditional[m] = vals
        pres = collections.Counter(m for u in ex for m in {x for c, _ in u["codes"] for x in parts(c)})
        first = collections.Counter(x for u in ex if u["codes"] for x in parts(u["codes"][0][0]))
        last = collections.Counter(x for u in ex if u["codes"] for x in parts(u["codes"][-1][0]))
        rz = collections.defaultdict(list)
        for u in ex:
            for code, sent, key in u.get("_realizations", []):
                rz[code].append({"paper": u.get("paper", "?"), "key": key, "start": sent[:90]})
        srec_real = {m: v for m, v in rz.items()}
        srec = {"n_exemplars": n, "presence": {m: round(c / n, 3) for m, c in pres.items()} if n else {}, "realizations": srec_real,
                "first": dict(first), "last": dict(last), "drafts": [], "families": {f: {"n": fam_n[f], "presence": fam_presence[f]} for f in fams},
                "conditional": conditional}
        for d in g["draft"]:
            dm = [c for c, _ in d["codes"]]
            dset = {x for c in dm for x in parts(c)}
            common = sorted(m for m, c in pres.items() if n and c / n >= min_common and m not in dset)
            rare = sorted({m for m in dset if n and pres.get(m, 0) / n <= max_rare})
            srec["drafts"].append({"paper": d.get("paper", "稿件"), "sequence": dm, "missing_common": common, "rare_present": rare,
                                   "conditional_present": sorted(m for m in conditional if m in dset),
                                   "realizations": [{"move": code, "key": key, "start": sent[:90],
                                                     "attested_by": [r["paper"] for r in srec_real.get(code, []) if r["key"] == key],
                                                     "neighbor_keys": sorted({r["key"] for r in srec_real.get(code, [])})}
                                                    for code, sent, key in d.get("_realizations", [])],
                                   "conditional_absent": sorted(m for m in conditional if m not in dset),
                                   "first": dm[0] if dm else "", "last": dm[-1] if dm else ""})
        result["sections"][sec] = srec
    return errors, warns, ok_units, result, moves


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("coding"); ap.add_argument("--report", default=""); ap.add_argument("--json", default="")
    ap.add_argument("--min-common", type=float, default=0.6); ap.add_argument("--max-rare", type=float, default=0.2)
    a = ap.parse_args()
    try:
        data = json.load(open(a.coding, encoding="utf-8-sig"))
    except Exception as e:
        print("编码文件读取失败：%s" % e, file=sys.stderr); return 2
    if not isinstance(data, dict) or not isinstance(data.get("units"), list) or not data["units"]:
        print("not_verified：units 必须是非空列表", file=sys.stderr); return 2
    if not isinstance(data.get("moves", {}), dict):
        print("moves 必须是对象", file=sys.stderr); return 2
    base = os.path.dirname(os.path.abspath(a.coding))
    errors, warns, ok_units, result, moves = analyze(data, base, a.min_common, a.max_rare)
    L = ["# 语步对照报告\n", "单元 %d 个，文本线索匹配 %d 个；错误 %d、提示 %d。\n" % (len(data.get("units", [])), len(ok_units), len(errors), len(warns))]
    if errors:
        L.append("## 编码错误（必须修正：线索必须逐字来自原文）\n"); L += ["- " + e for e in errors]
    if warns:
        L.append("\n## 提示\n"); L += ["- " + w for w in warns]
    for sec, s in result["sections"].items():
        n = s["n_exemplars"]
        if not n:
            continue
        L.append("\n## %s（对标 %d 篇）\n" % (sec, n))
        L.append("| 语步 | 含义 | 出现比例 | 作首句/首段 | 作末句/末段 |\n|---|---|---|---|---|")
        for m, share in sorted(s["presence"].items(), key=lambda x: -x[1]):
            L.append("| %s | %s | %.0f%% | %d | %d |" % (m, moves.get(m, ""), 100 * share, s["first"].get(m, 0), s["last"].get(m, 0)))
        if len(s.get("families", {})) > 1:
            L.append("\n分层（每层篇数）：%s" % "；".join("%s %d 篇" % (f, v["n"]) for f, v in s["families"].items()))
            for m, vals in sorted(s.get("conditional", {}).items()):
                L.append("- %s %s 在各层差别大：%s。这一项取决于目标刊属于哪一层。" % (m, moves.get(m, ""), "、".join("%s %.0f%%" % (f, 100 * v) for f, v in vals.items())))
        for d in s["drafts"]:
            L.append("\n**%s**：语步序列 %s" % (d["paper"], " → ".join(d["sequence"])))
            L.append("- 对标中常见（≥%.0f%%）而稿件没有：%s" % (100 * a.min_common, "、".join("%s %s" % (m, moves.get(m, "")) for m in d["missing_common"]) or "无"))
            L.append("- 稿件有而对标少见（≤%.0f%%）：%s" % (100 * a.max_rare, "、".join("%s %s" % (m, moves.get(m, "")) for m in d["rare_present"]) or "无"))
            for r in d.get("realizations", []):
                if r["neighbor_keys"] and not r["attested_by"]:
                    L.append("- 语步 %s 的起句“%s”近邻没人这样起（近邻：%s）" % (r["move"], r["key"], "；".join(r["neighbor_keys"][:8])))
            if s["first"] and d["sequence"]:
                L.append("- 首：稿件 %s；对标最常见 %s。末：稿件 %s；对标最常见 %s。" % (
                    d["first"], max(s["first"], key=s["first"].get), d["last"], max(s["last"], key=s["last"].get)))
    L.append("\n语步比例是对照，不是配方：缺一个常见语步，先问这一段是否需要承担那项功能；有一个少见语步，先问它是否属于别的节。")
    L.append("文本匹配不验证语步标签是否恰当、来源是否真实或是否为同类文献。需保存外部来源及独立语义复核；本脚本不能防止把真实短语故意标错类。")
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    if a.json:
        with M.wfile(a.json) as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    print(out[:4000] if not a.report else L[1].strip())
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
