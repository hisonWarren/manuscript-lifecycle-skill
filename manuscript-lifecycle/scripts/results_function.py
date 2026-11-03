#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
results_function.py — 结果节的句子功能与小标题风格检查。

  python results_function.py 稿件.md|docx [--heading-style object|finding|either] [--strict] [--must-share 0.10]
         [--lang auto|en|zh] [--report out.md] [--json out.json]

为什么要有它：section_lint R1 只认 suggest、because 这类表层词，而且解释句要超过 20% 且不少于 3 句才必须处理。
它认不出“We therefore describe …”这类作者叙述决策，也认不出以否定句出现的过程或机制判断
（“do not show that early processing is irrelevant …”）。这里按句子功能分类：

  可以留在结果：DIRECT 直接报告（估计、区间、检验、样本）；TRANSLATE 把数字翻成读者的话；
              QUALIFIER 局部统计限定（区间含 0、未建立等效、两个估计之差不确定、对定义敏感）。
  要核对位置：NARRATION 作者叙述决策；INFERENCE 关于过程、机制或构念能否推出的判断（肯定、否定都算）；
              MECHANISM 机制、中介、通路与理论映射；CONSTRUCT 构念识别；DESIGN 设计限制与替代解释；
              LITERATURE 与文献比较；IMPLICATION 含义与建议。

否定句不豁免：否定只改变方向，不改变功能。短的统计限定照样保留：不能把所有不确定性都赶出结果节。

小标题风格（--heading-style）：object 分析对象或指标式（Behavioral results、P1、Response time）；finding 发现句式；
either 不限。风格来自用户偏好、目标刊与近邻论文实测（bench_profile 第六节），不来自本技能的默认。未声明时只报告分布。

级别：MUST——待核句不少于 3 句且占结果句的比例不低于 --must-share（默认 0.10），或 --strict 下至少 1 句，
或违反已声明的小标题风格；SHOULD——其余待核句，以及未声明风格时小标题全部（≥3 个）是发现句；
INFO——保留的统计限定与标题分布（两边都列，便于复核误报与漏报）。合并 Results and Discussion 的体裁只报 INFO。
退出码：0 无 MUST；1 有 MUST；2 输入错误。
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402
from output_safety import output_path, write_fresh  # noqa: E402

MUST_SHARE = 0.10
ORDER = ("NARRATION", "INFERENCE", "DESIGN", "MECHANISM", "CONSTRUCT", "IMPLICATION", "LITERATURE")
NAME = {"NARRATION": "作者叙述决策", "INFERENCE": "过程或机制能否推出的判断", "DESIGN": "设计限制或替代解释",
        "MECHANISM": "机制、中介或理论映射", "CONSTRUCT": "构念识别", "IMPLICATION": "含义或建议", "LITERATURE": "与文献比较",
        "DIRECT": "直接报告", "TRANSLATE": "数字翻译", "QUALIFIER": "局部统计限定", "OTHER": "其他"}
DEST = {"NARRATION": "删去；属于分析决策的写进方法（如“按两种纳入规则分别报告”）",
        "INFERENCE": "讨论（解释或局限）；结果只留统计状态",
        "DESIGN": "方法（设计）与讨论（局限）；结果只报告控制分析本身",
        "MECHANISM": "讨论", "CONSTRUCT": "方法（测量定义）或讨论", "IMPLICATION": "讨论", "LITERATURE": "讨论",
        "DIRECT": "保留", "TRANSLATE": "保留", "QUALIFIER": "保留（短）", "OTHER": "保留或人工判断"}
STYLE_ZH = {"object": "分析对象/指标式", "finding": "发现句式", "nominal": "名词化发现"}

STAT = re.compile(r"\b[pP]\s*[=<>≤≥]|\bCI\b|confidence interval|置信区间|\b[tFrzχ]\s*\(\s*\d[\d.,\s]*\)\s*=|\b[tFrzβbB]\s*=\s*[−-]?\.?\d"
                  r"|η²|η2|\bdz?\s*=\s*[−-]?\.?\d|\b(?:OR|HR|RR)\s*=|\d\s*(?:ms|µV|μV|uV|Hz|dB|%)|\bn\s*=\s*\d|\[\s*[−-]?\d+(?:\.\d+)?\s*,")
EN = {
    "NARRATION": re.compile(
        r"\bwe\s+(?:therefore\s+|thus\s+|hence\s+|accordingly\s+|instead\s+|here\s+|also\s+)?"
        r"(?:describe|retain|treat|regard|consider|label|refer\s+to|focus\s+on|characteri[sz]e|interpret"
        r"|do\s+not\s+(?:claim|interpret|treat|consider|regard|describe|infer)|did\s+not\s+(?:treat|interpret|claim|infer))\b"
        r"|\bwithout\s+claiming\b|\brather\s+than\s+as\b"
        r"|\b(?:is|are|was|were)\s+(?:therefore\s+|thus\s+)?(?:not\s+)?(?:treated|regarded|interpreted|labell?ed)\s+as\b", re.I),
    "DESIGN": re.compile(
        r"\b(?:was|were|is|are)\s+not\s+(?:counterbalanced|randomi[sz]ed|blinded|manipulated)\b|\bconfound\w*"
        r"|\bcannot\s+be\s+(?:separated|disentangled|distinguished|dissociated)\s+from\b|\balternative\s+(?:explanation|account|interpretation)s?\b", re.I),
    "MECHANISM": re.compile(
        r"\bmechanis\w*|\bmediat\w*|\bpathways?\b|\bcausal\w*|\bgenerators?\b|\bmapping\s+between\b|\bunderl(?:ie|ies|ying|ay)\b"
        r"|\b(?:neural|cognitive|perceptual)\s+(?:route|basis|substrate|source)s?\b|\baccounts?\s+for\b"
        r"|\bexplain(?:s|ed)?\s+(?:the|why|how|this)\b(?!\s+(?:\w+\s+){0,2}variance)", re.I),
    "CONSTRUCT": re.compile(
        r"\bcanonical\b|\bidentified\s+as\s+(?:a|an|the)\b|\bas\s+an?\s+index\s+of\b"
        r"|\breflect(?:s|ed|ing)?\s+(?:a\s+|an\s+|the\s+)?(?:[\w-]+\s+){0,2}(?:process|processing|mechanism|accumulation|attention|arousal|component|state|capacity)\b", re.I),
    "IMPLICATION": re.compile(
        r"\b(?:this|these|the|such)\s+(?:results?|findings?|patterns?|data|estimates?|associations?|effects?)\s+(?:therefore\s+)?"
        r"(?:limits?|constrains?|supports?|challenges?|argues?|favou?rs?|rules?\s+out|speaks?\s+(?:to|against)|highlights?|underscores?|impl(?:y|ies)|suggests?|indicates?)\b"
        r"|\b(?:implies|suggests|indicates|suggesting|indicating|implying)\s+that\b|\bshould\s+(?:therefore\s+)?be\s+(?:prioriti[sz]ed|targeted|considered)\b"
        r"|\b(?:probably|likely|presumably)\s+(?:because|due\s+to|reflect\w*)\b|\b(?:individual[- ]difference|mechanistic|causal|theoretical)\s+interpretation\b", re.I),
    "LITERATURE": re.compile(
        r"\b(?:consistent|in\s+line|in\s+accordance|in\s+agreement)\s+with\b|\bsimilar\s+to\s+(?:those|that|what)\b|\bunlike\b|\bcontrary\s+to\b|\breplicat\w+"
        r"|\b(?:previous|prior|earlier)\s+(?:studies|work|findings|reports|research)\b|\bas\s+(?:previously\s+)?reported\b", re.I),
    "TRANSLATE": re.compile(
        r"\bcorrespond(?:s|ed|ing)?\s+to\b|\bequivalent\s+to\b|\bthat\s+is,|\bi\.e\.|\bin\s+other\s+words\b|\b(?:values?|estimates?|coefficients?)\s+mean\s+that\b"
        r"|\babout\s+(?:one|two|three|half)[- ]\w+\s+of\b|\bon\s+the\s+original\s+scale\b", re.I),
}
INFER_EN = re.compile(
    r"\b(?:do|does|did|can|could|would)\s*(?:not|n['’]t)\s+(?:show|establish|imply|mean|indicate|demonstrate|prove|bound|identify|isolate|determine|reveal|license|support|exclude|rule\s+out)\b"
    r"|\bcannot\s+(?:be\s+)?(?:attributed|interpreted|taken|read|used|establish\w*|show\w*|determin\w*|identif\w*)\b"
    r"|\bneither\b[^.;]*\bnor\b[^.;]*\b(?:establish\w*|show\w*|demonstrat\w*|determin\w*|identif\w*|impl\w*)\b"
    r"|\bnor\s+(?:do|does|did|can)\s+(?:they|it|these|this)\s+\w+"
    r"|\b(?:is|are|was|were)\s+(?:insufficient|not\s+sufficient|not\s+enough|inadequate)\s+to\b|\bnot\s+(?:reliable|sufficient|strong|precise)\s+enough\s+to\b"
    r"|\bpreclud\w+|\bno\s+(?:inference|conclusion)\s+(?:about|follows|can)\b|\bshould\s+not\s+be\s+(?:read|interpreted|taken|presented|understood)\b"
    r"|\b(?:its|their|the)\s+interpretation\s+(?:differs|is\s+different)\b", re.I)
STAT_OBJECT = re.compile(r"\bequivalen\w*|\bprecision\b|\bdifference\s+between\b|\bsignifican\w*|\bzero\b|\binterval\b|\bpower\b|\bcorrection\b|\bthreshold\b", re.I)
PROCESS = re.compile(r"\bprocess\w*|\bmechanis\w*|\bmediat\w*|\bpathways?\b|\birrelevant\b|\bcontribut\w*|\bcaus\w*|\bgenerators?\b|\baccumulat\w*|\bclock\b"
                     r"|\bpreparation\b|\battention\w*|\barousal\b|\brecogni\w*|\binterpretation\b|\baccount\b|\bexplan\w*|\bindividual[- ]difference\w*"
                     r"|\bconstruct\b|\bcanonical\b|\babsent\b|\babsence\b|\bneural\b|\bcognitive\b|\binformation\b|\brole\b", re.I)
QUAL_EN = re.compile(r"\b(?:intervals?|CIs?)\b[^.;]{0,40}?\b(?:included|includes|contained|contains|spanned|spanning|spans|crossed)\s+zero\b|\buncertain\b"
                     r"|\bdid\s+not\s+(?:reach|meet|survive)\b|\bnot\s+(?:statistically\s+)?significant\b|\bsensitiv\w+\s+to\b"
                     r"|\bdepend\w*\s+on\s+the\s+(?:inclusion|definition|window|reference|sample)", re.I)
ZH = {
    "NARRATION": re.compile(r"(?:因此|故|所以)?(?:我们|本研究|本文)(?:将其|把它|将该|把该)?(?:仅|只)?(?:描述为|视为|看作|解释为|处理为|称为|保留为)|不(?:将|把)其?(?:视为|解释为|看作)"),
    "INFERENCE": re.compile(r"不能(?:据此)?(?:推出|推断|说明|证明|表明|认为|断定|确定|排除)|并不(?:意味着|说明|表明|代表|证明)|不足以(?:说明|支持|证明|推断|确定)|无法(?:确定|推断|说明)"),
    "DESIGN": re.compile(r"未(?:进行|做|作)?(?:平衡|随机化?|盲法)|混淆|无法(?:与|和|同).{0,12}(?:区分|分离|分开)|替代解释"),
    "MECHANISM": re.compile(r"机制|中介|通路|因果|神经基础|加工过程|认知过程"),
    "CONSTRUCT": re.compile(r"反映了?.{0,8}(?:过程|机制|注意|唤醒|加工|累积)|典型.{0,6}成分|识别为"),
    "IMPLICATION": re.compile(r"(?:这|该|此|上述)(?:一)?(?:结果|发现|模式)(?:意味着|支持了?|限制了?|挑战了?|说明了?|提示了?)|应(?:当)?(?:优先|重点)"),
    "LITERATURE": re.compile(r"与.{0,20}(?:一致|相符|相反)"),
    "TRANSLATE": re.compile(r"相当于|即每|换算为|约为.{0,6}(?:分之一|倍)"),
}
STAT_OBJECT_ZH = re.compile(r"等效|精度|差异|显著|置信区间|区间|零")
PROCESS_ZH = re.compile(r"过程|机制|中介|通路|因果|注意|唤醒|识别|解释|个体差异|成分|神经|认知|信息|作用|贡献|加工|无关")
QUAL_ZH = re.compile(r"置信区间(?:包含|包括|跨越)\s*0|未达到?(?:统计学?)?显著|差异不显著|不确定|对.{0,10}(?:定义|窗口|纳入)敏感")
LIT_CUE_ZH = re.compile(r"以往|前人|先前|既往")
# ERP 等领域在结果里给成分命名是正常的描述（“this component was termed N170”“We refer to this component as N300”）
NAMING = re.compile(r"\b(?:refer\s+to|termed|labell?ed|named|called|designated)\b[^.;]{0,40}?\b(?:component|peak|wave|deflection|potential|negativity|positivity|factor|cluster)s?\b"
                    r"|\b(?:component|peak|wave|deflection|potential|negativity|positivity|factor|cluster)s?\b[^.;]{0,40}?\b(?:was|were|is|are)\s+(?:termed|labell?ed|named|called|referred\s+to)\b", re.I)

HEAD_FIND_EN = re.compile(
    r"\b(?:was|were|is|are|did|does|do|has|have|had|remained|became|showed|shows|show|revealed|reveals|differed|differs|differ|differentiated|differentiates"
    r"|depended|depends|depend|increased|increases|decreased|decreases|reduced|reduces|enhanced|enhances|predicted|predicts|predict|tracked|tracks|track"
    r"|reflects|reflected|reflect|scale|scales|scaled|modulated|modulates|lengthened|lengthens|shortened|shortens|elicited|elicits|produced|produces"
    r"|influenced|influences|affected|affects|drove|drives|explained|explains|accompanied|accompanies|varied|varies|emerged|emerges|persisted|persists"
    r"|survived|survives|outperformed|exceeded|preceded|led|leads|caused|causes)\b|\bnot\b|\bno\b|\bthan\b", re.I)
HEAD_NOMINAL_EN = re.compile(r"\b(?:dilation|compression|lengthening|shortening|increase|decrease|reduction|enhancement|facilitation|impairment|advantage"
                             r"|disadvantage|bias|distortion|overestimation|underestimation|suppression|amplification|dissociation)\b", re.I)
HEAD_FIND_ZH = re.compile(r"显著|高于|低于|大于|小于|长于|短于|增加|减少|提高|降低|增强|减弱|预测|调节|影响|依赖|取决|相关|无关|未|没有|导致|引起|呈现|表现出|更(?:长|短|高|低|强|弱|大|小)")
HEAD_NOMINAL_ZH = re.compile(r"延长|缩短|高估|低估|偏差|分离|优势")
HEAD_STRIP = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?|[IVX]+\.|[一二三四五六七八九十]+[、.．])\s*")
EXP_PREFIX = re.compile(r"^(?:experiment|study|研究|实验)\s*[\d一二三四五六七八九十]+\s*[:：.]\s*", re.I)
COMBINED = re.compile(r"results?\s+and\s+discussion|结果与讨论|结果和讨论|结果及讨论", re.I)
TOP_RESULTS = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:\d+(?:\.\d+)*\.?\s*|[IVX]+\.\s*|[一二三四五六七八九十]+[、.．]\s*)?"
                         r"(?:results?|findings|结\s*果|研究结果|实验结果)\s*(?:\*\*)?\s*[:：.]?\s*$", re.I)


def is_top_results(h):
    """节标题本身（Results、3. Results、结果、Results and Discussion），不是结果小节。"""
    return bool(TOP_RESULTS.match(h) or COMBINED.search(h))


def heading_style(h, lang="en"):
    """分析对象/指标式（object）、发现句式（finding）、名词化发现（nominal）。"""
    t = EXP_PREFIX.sub("", HEAD_STRIP.sub("", h.replace("*", "")).strip()).strip().rstrip(".。")
    if lang == "zh" or M.CJK.search(t):
        if HEAD_FIND_ZH.search(t):
            return "finding"
        return "nominal" if HEAD_NOMINAL_ZH.search(t) else "object"
    if len(M.LAT.findall(t)) >= 3 and HEAD_FIND_EN.search(t):
        return "finding"
    return "nominal" if HEAD_NOMINAL_EN.search(t) else "object"


def classify(s, lang="en"):
    """返回 (主功能, 其他命中的功能)。"""
    hits, qual = [], False
    stat = bool(STAT.search(s))
    zh = lang == "zh"
    P = ZH if zh else EN
    if P["NARRATION"].search(s):
        hits.append("NARRATION")
    inf = P["INFERENCE"].search(s) if zh else INFER_EN.search(s)
    if inf:
        if (PROCESS_ZH if zh else PROCESS).search(s) or P["MECHANISM"].search(s):
            hits.append("INFERENCE")
        elif (STAT_OBJECT_ZH if zh else STAT_OBJECT).search(s):
            qual = True
        else:
            hits.append("INFERENCE")
    for k in ("DESIGN", "CONSTRUCT", "IMPLICATION"):
        if P[k].search(s):
            hits.append(k)
    lit_cue = LIT_CUE_ZH.search(s) if zh else re.search(r"\b(?:previous|prior|earlier)\b", s, re.I)
    if P["LITERATURE"].search(s) and (M.count_citations(s) > 0 or lit_cue):
        hits.append("LITERATURE")
    if P["MECHANISM"].search(s) and (not stat or hits):
        hits.append("MECHANISM")
    if hits and set(hits) <= {"NARRATION", "LITERATURE"} and NAMING.search(s):
        return "OTHER", []
    if hits:
        hits = sorted(set(hits), key=ORDER.index)
        return hits[0], hits[1:]
    if qual or (QUAL_ZH if zh else QUAL_EN).search(s):
        return "QUALIFIER", []
    if P["TRANSLATE"].search(s):
        return "TRANSLATE", []
    return ("DIRECT" if stat else "OTHER"), []


def analyse(text, lang, style="", strict=False, must_share=MUST_SHARE):
    blocks = M.parse(text)
    combined = any(b["kind"] == "heading" and COMBINED.search(b["text"]) for b in blocks)
    heads, sents = [], []
    for b in blocks:
        if b["sec"] != "results":
            continue
        if b["kind"] == "heading":
            if not is_top_results(b["text"]):
                heads.append({"text": b["text"], "level": b.get("level"), "style": heading_style(b["text"], lang)})
        elif b["kind"] == "para":
            for s in M.sentences(b["text"]):
                cls, also = classify(s, lang)
                sents.append({"sub": b.get("sub", ""), "text": s, "cls": cls, "also": also, "dest": DEST[cls]})
    items = []

    def add(level, code, msg, ex=()):
        items.append({"level": level, "code": code, "sec": "results", "msg": msg, "examples": [e[:240] for e in ex][:12]})

    if not sents and not heads:
        add("INFO", "RF9", "没有识别到结果节（理论或综述稿件，或切节失败）。用 mslib.py sections 核对切节。")
        return items, heads, sents, combined
    moved = [x for x in sents if x["cls"] in ORDER]
    if moved:
        cnt = collections.Counter(x["cls"] for x in moved)
        summ = "、".join("%s %d" % (NAME[k], cnt[k]) for k in ORDER if cnt[k])
        share = len(moved) / max(1, len(sents))
        if combined:
            add("INFO", "RF1", "合并 Results and Discussion：解释本来就在这一节。以下 %d 句供核对推断强度（%s）。" % (len(moved), summ), [x["text"] for x in moved])
        else:
            level = "MUST" if ((strict and moved) or (len(moved) >= 3 and share >= must_share)) else "SHOULD"
            add(level, "RF1", "结果节有 %d/%d 句（%.0f%%）需要核对位置（%s）。逐句写明移到哪里、删去，或保留的理由；否定句不因“没有过强因果”而豁免；"
                "短的统计限定（区间含 0、未建立等效）不在此列，照常保留。去向见报告的逐句表。" % (len(moved), len(sents), 100 * share, summ), [x["text"] for x in moved])
    kept = [x for x in sents if x["cls"] == "QUALIFIER"]
    if kept:
        add("INFO", "RF0", "保留的局部统计限定 %d 句（列出来便于复核：它们不该被一并删掉）。" % len(kept), [x["text"] for x in kept])
    fh = [h["text"] for h in heads if h["style"] == "finding"]
    nh = [h["text"] for h in heads if h["style"] == "nominal"]
    oh = [h["text"] for h in heads if h["style"] == "object"]
    if style == "object":
        if fh:
            add("MUST", "HS1", "已声明结果小标题用分析对象或指标式，以下 %d 个是发现句式。按分析对象、指标或比较命名"
                "（如 Behavioral results；Primary outcome；Model performance by subgroup），发现放进该小节的首句。" % len(fh), fh)
        if nh:
            add("SHOULD", "HS1b", "以下 %d 个小标题是名词化的发现（Dilation of …、Enhancement of …），与已声明的分析对象式不一致。" % len(nh), nh)
    elif style == "finding":
        if oh:
            add("SHOULD", "HS2", "已声明发现句式小标题，以下 %d 个是分析对象式。两种写法都合法，按已定风格统一即可。" % len(oh), oh)
    elif heads:
        msg = ("结果小标题 %d 个：发现句式 %d、名词化发现 %d、分析对象式 %d。风格未声明：按用户偏好、目标刊与近邻论文实测"
               "（bench_profile 第六节）选定，写进 expectations.json 或决策登记；本工具不替你判对错。" % (len(heads), len(fh), len(nh), len(oh)))
        level = "SHOULD" if (style != "either" and len(heads) >= 3 and len(fh) == len(heads)) else "INFO"
        if level == "SHOULD":
            msg = "结果小标题全部是发现句（%d 个）。这是可选写法，不是通则：确认它来自用户偏好、目标刊或近邻论文，而不是默认。" % len(heads) + msg
        add(level, "HS0", msg, [h["text"] for h in heads])
    return items, heads, sents, combined


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--heading-style", default="", choices=["", "object", "finding", "either"])
    ap.add_argument("--strict", action="store_true", help="用户已明确要求结果节只报告结果：待核句 1 句即为 MUST")
    ap.add_argument("--must-share", type=float, default=MUST_SHARE, help="待核句占结果句的比例达到多少才升为 MUST（同时要不少于 3 句）")
    ap.add_argument("--lang", default="auto", choices=["auto", "en", "zh"])
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    if not os.path.isfile(a.path):
        print("找不到文件：%s" % a.path, file=sys.stderr)
        return 2
    try:
        outs = {k: output_path(v, [a.path]) for k, v in (("report", a.report), ("json", a.json)) if v}
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    text = M.load_text(a.path)
    if not text.strip():
        print("not_verified：稿件为空，不能把零检查记为通过", file=sys.stderr)
        return 2
    lang = M.detect_lang(text) if a.lang == "auto" else a.lang
    items, heads, sents, combined = analyse(text, lang, a.heading_style, a.strict, a.must_share)
    L = ["# 结果节：句子功能与小标题风格（%s）" % os.path.basename(a.path), "",
         "语言 %s；声明的小标题风格：%s；--strict：%s；合并结果与讨论：%s。" % (lang, STYLE_ZH.get(a.heading_style, a.heading_style or "未声明"),
                                                            "是" if a.strict else "否", "是" if combined else "否"), ""]
    for lvl in ("MUST", "SHOULD", "INFO"):
        sel = [i for i in items if i["level"] == lvl]
        if sel:
            L += ["## %s" % lvl, ""]
            for i in sel:
                L.append("- **%s** %s" % (i["code"], i["msg"]))
                L += ["  - %s" % e for e in i["examples"]]
            L.append("")
    if heads:
        L += ["## 结果小标题", "", "| 小标题 | 风格 |", "|---|---|"] + ["| %s | %s |" % (h["text"].replace("|", "/"), STYLE_ZH[h["style"]]) for h in heads] + [""]
    if sents:
        L += ["## 逐句功能", "", "| 小节 | 功能 | 建议去向 | 句子 |", "|---|---|---|---|"]
        L += ["| %s | %s%s | %s | %s |" % ((x["sub"] or "")[:40].replace("|", "/"), NAME[x["cls"]], ("（另含：%s）" % "、".join(NAME[c] for c in x["also"])) if x["also"] else "",
                                         x["dest"], x["text"][:220].replace("|", "/")) for x in sents]
        L.append("")
    L.append("脚本只认形式，不认意思：每句都要人工裁决。分类用于定位，不是删句清单；科学上必要的限定换到正确的章节，而不是删掉。")
    rep = "\n".join(L) + "\n"
    if "report" in outs:
        write_fresh(outs["report"], rep)
    if "json" in outs:
        write_fresh(outs["json"], json.dumps({"items": items, "headings": heads, "sentences": sents, "lang": lang,
                                              "heading_style": a.heading_style, "combined": combined}, ensure_ascii=False, indent=1))
    must = sum(i["level"] == "MUST" for i in items)
    print("results_function：MUST %d、SHOULD %d、INFO %d；结果句 %d、待核位置 %d、小标题 %d。" % (
        must, sum(i["level"] == "SHOULD" for i in items), sum(i["level"] == "INFO" for i in items),
        len(sents), sum(x["cls"] in ORDER for x in sents), len(heads)))
    if not outs:
        print(rep[:4000])
    return 1 if must else 0


if __name__ == "__main__":
    sys.exit(main())
