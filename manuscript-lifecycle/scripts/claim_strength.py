#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
claim_strength.py — 概括位置的主张强度与文献概括：题目、摘要、讨论首段与末段、结论和图注最容易写得比结果强（spin）；
引言里“前人研究做了什么 / 没做什么”的概括最容易写窄。这里按推断谬误的类型查，不按单个词打补丁（references/22 §9、23 §7）。

  python claim_strength.py 稿件.md [--concept paper_concept.md] [--citations 引文台账.csv] [--stage draft|submission]
         [--report out.md] [--json out.json]

规则（概括位置 = 题目、摘要、讨论首段、讨论末段、结论；图注另列）：
  IF1 SHOULD 显著性之差当作差异的显著性：only when/in、confined to、restricted to、absent、abolished、disappeared、no longer、
             but not in……。两条件“一个显著、一个不显著”不等于两者有差（Gelman & Stern 2006；Nieuwenhuis et al. 2011）。
  IF2 INFO   用不显著证明“不存在”或“等效”：at chance、no effect、did not differ、equivalent。核对区间及等效检验。
  IF3 INFO   用簇检验的边界说时程：from/after/at N ms 与 cluster 同段。簇检验不确立效应的起止时刻（Sassenhagen & Draschkow 2019）。
  IF4 SHOULD 分离、不同机制、两条通路一类的结论：要么有两者差异的直接检验，要么写成“观测到不同的轮廓”。
  IF5 SHOULD 把相关写成来源或因果：振幅/信号/活动 led to、drives、determines、judgments are made/read out from……
  FW1 MUST   paper_concept.md 写了“禁用表述：……”的说法出现在稿件里（作者自己登记的边界）。
  LG1 引言或讨论里概括一组前人研究的句子（These studies…、Previous studies…、no study has…、remains unknown）：这是比较性主张，
      要对所概括的研究读全文，并在引文台账登记 claim_type=comparison、citation_access=fulltext 的行（claim_location 写到段）。
      给了 --citations 而找不到这样的行：draft 为 SHOULD，submission 为 MUST；没给台账时列为 SHOULD。
退出码：0 没有 MUST；1 有 MUST；2 输入错误。它只认措辞信号：命中不等于错，没命中也不等于主张与证据相称。
"""
import argparse, csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

IF1 = re.compile(r"\bonly (?:when|in|for|with|if)\b|\bconfined to\b|\brestricted to\b|\bno longer\b|\bbut not (?:when|in|for|with)\b|\bexclusively\b|"
                 r"\b(?:effects?|differences?|modulations?|bias(?:es)?|interactions?|advantages?)\b(?:\s+\w+){0,4}\s+(?:disappear\w*|vanish\w*|(?:was|were) (?:absent|abolished|eliminated))", re.I)
IF2 = re.compile(r"\bat chance\b|\bno (?:information|effect|difference|relation(?:ship)?|association)\b|\bdid not differ\b|\bwas absent\b|\bthe same as\b", re.I)
IF3 = re.compile(r"\b(?:from|after|by|at|beginning at|onset (?:at|of)|emerg\w+ (?:at|after|from))\s+(?:about\s+|around\s+|~\s*)?\d{2,4}\s*ms\b", re.I)
IF4 = re.compile(r"\bdissociat\w*|\b(?:were|are|was|is|be)\s+(?:\w+\s+)?distinct\b|\bdistinct\s+(?:[\w-]+\s+){0,2}(?:signals?|stages?|mechanisms?|processes|pathways?|systems?|routes?)\b|\bseparate (?:stages?|mechanisms?|signals?|processes|routes?|pathways?)\b|"
                 r"\btwo (?:separate |distinct )?(?:stages|routes|pathways|mechanisms|processes)\b|\bindependent (?:mechanisms|processes|stages)\b", re.I)
IF5 = re.compile(
    # 被测量（不是被操纵）的量写成原因：比较级主语（longer hesitation led to …）或信号类主语（amplitude drove …）。
    # 第七轮：只认脑电词会漏掉其他领域；放开到任何主语又会把“刺激扰动导致……”这类操纵写法也报出来（已发表论文实测 6 处误报）
    r"\b(?:longer|shorter|higher|lower|greater|larger|smaller|stronger|weaker|more|less|faster|slower)\s+(?:[\w-]+\s+){0,2}?(?:led to|leads to|lead to|caused|causes|drove|drives|determined|determines|resulted in|results in|produced|produces)\b|"
    r"\b(?:amplitudes?|signals?|activity|activities|components?|potentials?|ERPs?|P1|N1|CNV|conductance|hesitation|latenc(?:y|ies))\b[^.;]{0,60}?\b(?:led to|leads to|lead to|caused|causes|drove|drives|determines|underlies|underlie)\b(?!\s+(?:this|that)\s+way)|"
    r"\bfrom which (?:each |every |the )?(?:judg\w+|decisions?|choices?|estimates?) (?:is|are|was|were) (?:made|read(?: out)?|formed)\b|"
    r"\b(?:judg\w+|decisions?|choices?|estimates?) (?:is|are|was|were) (?:made|read(?: out)?) from\b", re.I)
LG = re.compile(r"^(?:These|Such|Previous|Prior|Earlier|Most|Many|Existing|Past|Other) (?:EEG |ERP |behavioural |behavioral |neuroimaging )?(?:studies|work|research|experiments|accounts|reports)\b|"
                r"\bno (?:previous |prior |earlier )?(?:study|studies|work|research) (?:has|have)\b|\bhas (?:not|never) been (?:tested|examined|studied|addressed)\b|"
                r"\bremains? (?:unknown|unclear|untested|unexplored)\b|\bfirst (?:study|studies|to)\b", re.I)


# IF1 只在句子讲的是效应或差异时才算（已发表论文里 “rarely confined to discrete trials” 这类说法不是条件限定）
EFFECT = re.compile(r"\b(?:effects?|differences?|differed|interact\w*|bias\w*|modulat\w*|chang(?:e|es|ed|ing)|alter\w*|affect(?:s|ed|ing)?|influenc\w*|estimates?|judgments?|lengthen\w*|shorten\w*|increas\w*|decreas\w*|judged|estimated|associat\w*|predict\w*|benefit\w*|improv\w*|effective|respond\w*|larger|smaller|longer|shorter|higher|lower)\b|效应|差异|影响|交互|偏差|增加|减少|延长|缩短|高估|低估|有效|获益|改善", re.I)


# 中文写法（第六轮：原先只有英文式样，中文稿“没有命中”其实是没查）
ZH = {
    "IF1": re.compile(r"仅在|只在|仅对|只对|仅限于|局限于|只出现在|仅出现在|(?:效应|差异|作用|影响)[^，。；]{0,8}(?:消失|不复存在)"),
    "IF2": re.compile(r"(?:没有|不存在|无)(?:任何)?(?:差异|影响|效应|关联|作用)|处于随机水平|两者相同|完全一致"),
    "IF4": re.compile(r"(?:相互)?分离|不同的(?:机制|阶段|通路|过程)|两(?:条|种|个)[^，。；]{0,6}(?:通路|机制|阶段|过程)|相互独立的(?:机制|过程|通路)"),
    "IF5": re.compile(r"(?:振幅|信号|活动|成分|指标)[^，。；]{0,30}(?:导致|引起|决定了|驱动)|判断(?:是|就是)?(?:从|由)[^，。；]{0,20}(?:读出|产生|形成)"),
    "IF3": re.compile(r"(?:从|自|始于|在)\s*\d{2,4}\s*(?:ms|毫秒)\s*(?:开始|起|出现)"),
    "LG": re.compile(r"^(?:以往|既往|现有|已有|前人|这些|大多数|多数)(?:的)?(?:研究|文献|工作)|尚(?:无|未有)研究|鲜有研究|未见(?:相关)?报道|首次"),
}


# 新式样仍是人工复核入口；不从“一个显著、另一个未检出”自动判定交互不存在。
CONTRAST = re.compile(r"\b(?:but|whereas|while)\b|而|但|却|相比之下", re.I)
NEG_RESULT = re.compile(
    r"\b(?:fail(?:ed|s)? to|did not|does not|do not)\s+(?:emerge|appear|benefit|improve|respond|show|yield|reach)\b|"
    r"\b(?:not (?:statistically )?significant|non[- ]?significant|no (?:benefit|improvement|effect|advantage))\b|"
    r"(?:没有|未(?:能)?|无)(?:显著)?(?:获益|改善|效应|作用)|不显著", re.I)
METHOD_LIMIT = re.compile(
    r"\b(?:computed|calculated|collected|recruited|sampled|recorded|measured|analy[sz]ed|fitted|estimated)\s+only\s+(?:in|with|when|for)\b|"
    r"(?:只在|仅在|只对|仅对)[^，。；]{0,25}(?:进行|开展|计算|采集|测量|招募|抽样|分析)", re.I)
CAUSAL_VERB = re.compile(
    r"\b(?:led to|leads? to|cause[sd]?|drove|drive[sn]?|determine[sd]?|"
    r"result(?:ed|s)? in|produce[sd]?|generate[sd]?|induce[sd]?|underlie[sd]?)\b|"
    r"导致|引起|决定了|驱动|产生了", re.I)
RANDOMIZED = re.compile(r"\brandom(?:ly|i[sz]ed|i[sz]ation)?\b|随机", re.I)
ASSIGNED = re.compile(r"\b(?:assign\w*|allocat\w*|manipulat\w*|administer\w*|randomi[sz]ed to)\b|分配|操纵|给予", re.I)
OBSERVATIONAL = re.compile(r"\b(?:observational|cross[- ]sectional|cohort|case[- ]control)(?:[ -]\w+){0,2}\s+(?:study|design|analysis)\b|(?:study|design)\s+(?:was|is)\s+(?:an? )?observational\b|观察性研究|横断面研究|队列研究", re.I)
MEASURED_ACTIVE = re.compile(r"\b(?:measured|assessed|recorded|quantified|surveyed)\s+([^.;]{1,100})", re.I)
MEASURED_PASSIVE = re.compile(r"([^.;]{1,100}?)\s+(?:was|were|is|are)\s+(?:measured|assessed|recorded|quantified|surveyed)\b", re.I)
TECHNICAL_SOURCE = re.compile(r"\b(?:missing data|data loss|file corruption|(?:equipment|software|hardware|technical) (?:failure|error|issue)|equipment|apparatus|software|hardware|sample size|synthetic data)\b", re.I)
SUBJECT_STOP = set("the a an these those this that our their its two both higher lower greater larger smaller stronger weaker more less longer shorter faster slower findings results show showed shows suggest suggested suggests indicate indicated indicates demonstrate demonstrated demonstrates was were is are have has had group groups participants patients students in of to for with and or".split())
EQUIVALENT = re.compile(
    r"\b(?:is|are|was|were|be|been|proved)\s+(?:\w+\s+){0,3}equivalent\b|"
    r"\b(?:showed|demonstrated|established|confirmed)\s+(?:\w+\s+){0,2}equivalence\b|"
    r"\bequivalent\s+(?:effects?|outcomes?|results?|performance)\b|"
    r"(?:等效|等同|两者相同|完全一致)", re.I)
EQ_TEST = re.compile(r"\bTOST\b|\btwo one[- ]sided (?:tests?|testing)\b|\bequivalence test\w*\b|等效(?:性)?检验|双单侧检验", re.I)
EQ_BOUNDS = re.compile(r"\b(?:prespecified|pre[- ]specified|equivalence) (?:bounds?|margins?|limits?)\b|预(?:先)?设(?:定)?的?(?:等效)?(?:界值|界限|范围)|等效(?:界值|界限|范围)", re.I)
EQ_SUCCESS = re.compile(
    r"\b(?:confirmed|established|demonstrated|supported|passed)\s+(?:\w+\s+){0,3}equivalence\b|"
    r"\b(?:both|two) (?:one[- ]sided )?p[- ]values?\s*(?:(?:were|are)\s+)?(?:<\s*0?\.05\b|(?:below|less than)\s+0?\.05\b)|"
    r"\b(?:CI|confidence interval)\b[^.;]{0,80}\b(?:entirely|wholly) within\b|"
    r"(?:证实|支持|确立|通过)[^。；]{0,12}等效|(?:置信区间)[^。；]{0,35}(?:完全|全部)位于", re.I)


def grouped_claim(s, rule):
    """条件限制或正负结果的并列。方法/采集范围本身不是条件效应结论。"""
    if not EFFECT.search(s):
        return False
    if rule.search(s):
        # 仅在同一小句里明确是计算/采集范围时略过，另一小句的效应限制仍查。
        if not METHOD_LIMIT.search(s):
            return True
        if any(rule.search(c) and EFFECT.search(c) and not METHOD_LIMIT.search(c)
               for c in re.split(r"[,;，；]", s)):
            return True
    return bool(CONTRAST.search(s) and NEG_RESULT.search(s))


def source_words(prefix):
    # 只用于与明确随机操纵的表述对照，不把“全文出现 randomized”当作所有量都被操纵。
    prefix = re.split(r"[,;，；]|\bthat\b", prefix, flags=re.I)[-1]
    prefix = re.split(r"\b(?:in|with|among|for|under|of)\b", prefix, maxsplit=1, flags=re.I)[0]
    return {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z-]+", prefix)[-6:]
            if w.lower() not in SUBJECT_STOP}


def positive_randomization(s):
    """否定的随机分配不是支持因果的设计证据。"""
    if re.search(r"\b(?:previous|prior|earlier|other|published)\s+(?:studies|study|research|work|experiments?)\b|以往|既往|前人|其他研究", s, re.I):
        return False
    random = RANDOMIZED.search(s)
    assigned = ASSIGNED.search(s)
    if not random or not assigned:
        return False
    for m in (random, assigned):
        if re.search(r"\b(?:not|no|never|without|non[- ]?)\b(?:\s+\w+){0,3}\s*$|(?:未|没有|并非|不曾)[^，。；]{0,8}$", s[:m.start()], re.I):
            return False
    return not re.search(r"\b(?:assignment|allocation|randomization)\b[^.;]{0,30}\b(?:not|never)\s+(?:used|performed|implemented|possible)\b", s, re.I)


def measured_sources(text):
    """仅取明确测量/相关表述中的变量名，避免把刺激修饰语也当作被测来源。"""
    sources = []
    for b in M.parse(text):
        if b["kind"] != "para":
            continue
        for s in M.sentences(b["text"]):
            phrases = [m.group(1) for m in MEASURED_ACTIVE.finditer(s)]
            phrases += [m.group(1) for m in MEASURED_PASSIVE.finditer(s)]
            phrases += re.findall(r"\bbetween\s+([^.;]{1,80}?)\s+(?:was|were|is|are|showed|revealed|yielded)\b", s, re.I) if re.search(r"\b(?:correlation|association)\b", s, re.I) else []
            for phrase in phrases:
                phrase = re.split(r"\b(?:in response to|in|from|using|during|after|before|with|for|to)\b", phrase, maxsplit=1, flags=re.I)[0]
                for part in re.split(r",|\band\b|\bor\b", phrase, flags=re.I):
                    words = source_words(part)
                    if words:
                        sources.append(words)
    return sources


def causal_claim(s, rule, manipulation_evidence, measured_evidence=(), observational=False):
    """返回因果措辞复核信号；未知设计继续复核，明确操纵且指向同一来源才抑制。"""
    old_signal = bool(rule.search(s))
    candidates = list(CAUSAL_VERB.finditer(s))
    if not candidates:
        return old_signal       # judgments are read out from 等来源断言
    for m in candidates:
        prefix = s[:m.start()]
        if re.search(r"\b(?:may|might|could)(?:\s+have)?\s*$|\b(?:did|does|do|can|could|would)\s+not\s*$|\bnever\s*$|\bfailed? to\s*$|可能(?:已经)?$|并?不(?:会)?$|未(?:能)?$", prefix, re.I):
            continue
        if re.match(r"\s+by\b", s[m.end():], re.I) or re.search(r"\b(?:was|were|is|are|be|been)\s*$", prefix, re.I):
            continue        # induced by / was caused 等被动或缩减关系从句不走新增主动来源规则。
        local_prefix = re.split(r"[,;，；]", prefix)[-1]
        if TECHNICAL_SOURCE.search(local_prefix):
            continue
        # 明确的局部刺激扰动（旧回归的合法例外），而不是任何含有 stimulus 的句子。
        if re.search(r"\b(?:perturbations? (?:in|of) the stimulus|stimulus perturbations?|experimentally manipulated [\w -]+)\s*$", prefix, re.I):
            continue
        if re.fullmatch(r"\s*(?:we|the researchers|the authors|our (?:analysis|analyses|model|simulation))\s*", prefix, re.I) and re.match(r"(?:generate|produce|determine)", m.group(0), re.I):
            continue        # 生成模拟数据/确定样本量一类研究操作，不是变量间的因果断言。
        words = source_words(prefix)
        exposures = []
        for e in manipulation_evidence:
            assigned = ASSIGNED.search(e)
            exposure = e[assigned.end():] if assigned else ""
            exposure = re.split(r"[,;，；]|\b(?:to (?:assess|measure|evaluate|test|examine)|and (?:then )?(?:measured|assessed|recorded))\b", exposure, flags=re.I)[0]
            exposures.append({w.lower() for w in re.findall(r"[A-Za-z][A-Za-z-]+", exposure) if w.lower() not in SUBJECT_STOP})
        if words and any(words & exposure for exposure in exposures):
            continue
        if old_signal:
            return True
        # 新增分支需要来源线索，不能见到任意 induced/caused 就加警告。
        if words and (any(words <= evidence for evidence in measured_evidence) or observational):
            return True
        # 未知设计下只保留很窄的“抽象量名词 + generated + 比较结果”复核入口。
        # 它不扩展到任意因果动词、刺激来源、被动关系从句或研究操作。
        if (len(words) <= 2 and re.fullmatch(r"generate[sd]?", m.group(0), re.I)
                and any(re.search(r"(?:ment|ness|ity|ence|ance)$", w) for w in words)
                and re.match(r"\s+(?:higher|lower|greater|better|worse|more|less|larger|smaller)\b", s[m.end():], re.I)):
            return True
    return False


def mechanism_claim(s, rule):
    if not rule.search(s):
        return False
    # “条件/位置在物理上不同”不能自动升级成机制分离。信号、通路等主张仍保留复核。
    physical = re.search(r"\b(?:study |experimental )?(?:conditions|groups|locations|stimuli|clusters)\s+(?:were|are|was|is)\s+(?:physically |spatially |spatiotemporally )?distinct\b|(?:实验|研究)?条件[^。；]{0,8}(?:物理|空间)[^。；]{0,6}(?:分离|不同)", s, re.I)
    mechanism = re.search(r"\b(?:signals?|mechanisms?|pathways?|processes|routes?|systems?)\b|机制|通路|过程|信号", s, re.I)
    return not (physical and not mechanism)


CONCEPTUAL_EQ = re.compile(r"\b(?:models?|formulations?|definitions?|equations?|expressions?|parameteri[sz]ations?|components?|"
                          r"(?:decision )?variables?|terms?|notations?|algorithms?|estimators?|representations?)\b|模型|成分|变量|定义|公式|方程", re.I)
STAT_OUTCOME = re.compile(r"\b(?:effects?|outcomes?|performance|accuracy|scores?|responses?|groups?|conditions?|treatments?|interventions?|"
                          r"differences?|efficacy|results?)\b|效应|结果|疗效|组间|条件", re.I)


def equivalence_claim(s, paragraph):
    """正面等效断言且本段未给明确等效证据时提示；不把未拒绝零假设当等效证据。
    模型、成分、变量、定义之间的概念等价（“this model would be equivalent to the DDM”）不是统计等效结论，不提示。"""
    for m in EQUIVALENT.finditer(s):
        window = s[max(0, m.start() - 90):m.end() + 60]
        if CONCEPTUAL_EQ.search(window) and not STAT_OUTCOME.search(window):
            continue
        before = s[max(0, m.start() - 65):m.end()]
        if re.search(r"\b(?:not(?! only)|non[- ]?)\b[^,;.!?]{0,35}\b(?:equivalent|equivalence)\b|"
                     r"\b(?:cannot|can't|could not|failed to|did not|no evidence|insufficient evidence)\b[^,;.!?]{0,55}\b(?:equivalent|equivalence)\b|"
                     r"(?:不能|无法|不应|未能|尚未|没有证据|并不|并非|不是|不等效)[^，。；]{0,25}(?:等效|等同|相同|一致)?$", before, re.I):
            continue
        # TOST/等效检验关键词本身不构成豁免，须同段有界值和肯定的检验结果。
        if EQ_TEST.search(paragraph) and EQ_BOUNDS.search(paragraph) and EQ_SUCCESS.search(paragraph):
            if not re.search(r"\b(?:not|never|failed to|did not|no evidence)\b[^.;]{0,35}(?:confirmed|established|demonstrated|supported|passed)\b|(?:未能|没有|不能)[^。；]{0,12}(?:证实|支持|确立|通过)", paragraph, re.I):
                continue
        return True
    return False


def summary_blocks(text):
    blocks = M.parse(text)
    title = next((l.lstrip("#").strip() for l in text.split("\n") if l.startswith("# ")), "")
    ab = [b["text"] for b in blocks if b["sec"] == "abstract" and b["kind"] == "para"]
    dis = [b["text"] for b in blocks if b["sec"] == "discussion" and b["kind"] == "para"]
    con = [b["text"] for b in blocks if b["sec"] == "conclusion" and b["kind"] == "para"]
    intro = [b["text"] for b in blocks if b["sec"] == "introduction" and b["kind"] == "para"]
    legends = [b["text"] for b in blocks if b["kind"] in ("para", "caption") and re.match(r"^\**(?:Fig(?:ure)?\.?|Table)\s*\d", b["text"])]
    res = [b["text"] for b in blocks if b["sec"] == "results" and b["kind"] == "para"]
    loc = [("title", [title] if title else [])] + [("abstract", ab), ("discussion_first", dis[:1]), ("discussion_last", dis[-1:] if len(dis) > 1 else []), ("conclusion", con)]
    return loc, legends, intro, dis, res


def forbidden(concept):
    out = []
    if concept and os.path.exists(concept):
        for line in open(concept, encoding="utf-8"):
            m = re.search(r"(?:禁用表述|禁用说法|Forbidden wording|Do not write)\s*[:：]\s*(.+)", line, re.I)
            if m:
                out += [x.strip(" “”\"'`") for x in re.split(r"[;；|、]", m.group(1)) if len(x.strip(" “”\"'`")) >= 4]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manuscript")
    ap.add_argument("--concept", default="")
    ap.add_argument("--citations", default="")
    ap.add_argument("--stage", default="draft", choices=["draft", "submission"])
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    for p in [a.manuscript] + [x for x in (a.concept, a.citations) if x]:
        if not os.path.exists(p):
            print("找不到 %s" % p, file=sys.stderr)
            return 2
    for p in (a.report, a.json):
        if p and os.path.exists(p):
            print("输出文件已存在：%s" % p, file=sys.stderr)
            return 2
    text = M.load_text(a.manuscript)
    lang = M.detect_lang(text)
    # 每次调用独立选语言；不替换公开英文正则，避免中文调用污染同进程的下次英文扫描。
    rules = ZH if lang == "zh" else {"IF1": IF1, "IF2": IF2, "IF3": IF3, "IF4": IF4, "IF5": IF5, "LG": LG}
    loc, legends, intro, dis, res = summary_blocks(text)
    # Only the current study's reported design can justify a design exception.
    # Background literature in the introduction cannot randomize this study.
    manipulation_evidence = [s for b in M.parse(text) if b["kind"] == "para" and b["sec"] in ("methods", "abstract")
                             for s in M.sentences(b["text"]) if positive_randomization(s)]
    measured_evidence = measured_sources(text)
    observational = any(OBSERVATIONAL.search(b["text"]) for b in M.parse(text)
                        if b["kind"] == "para" and b["sec"] in ("methods", "abstract"))
    items = []

    def add(level, code, where, msg, ex):
        items.append({"level": level, "code": code, "where": where, "msg": msg, "example": ex[:220]})

    for where, paras in loc + [("legend", legends), ("results", res)]:
        for p in paras:
            for s in M.sentences(p) if where != "title" else [p]:
                hedged = bool(re.search(r"\b(?:may|might|could)\s+have\b|可能(?:已经)?(?:导致|引起)", s))   # 只放过推测语气；“whether … is the activity from which judgments are made”仍是预设，照报
                if where == "results":
                    if causal_claim(s, rules["IF5"], manipulation_evidence, measured_evidence, observational) and not hedged:
                        add("SHOULD", "IF5", where, "因果或来源措辞：人工核对来源变量是否被操纵及设计能否支持因果；观测关联用 was associated with / predicted。", s)
                    continue
                if grouped_claim(s, rules["IF1"]):
                    add("SHOULD", "IF1", where, "限定在某一条件（only/confined/absent…）：核对两条件之差本身是否检验过；没检验就写“在 A 中检出、在 B 中未检出，两者之差不确定”。", s)
                if mechanism_claim(s, rules["IF4"]) and where != "legend":
                    add("SHOULD", "IF4", where, "分离或不同机制的结论：给出两者差异的直接检验，或改写成观测到的不同轮廓。", s)
                if causal_claim(s, rules["IF5"], manipulation_evidence, measured_evidence, observational) and not hedged:
                    add("SHOULD", "IF5", where, "因果或来源措辞：人工核对来源变量是否被操纵及设计能否支持因果；观测关联用 was associated with / predicted。", s)
    for p in res + [x for _w, ps in loc for x in ps]:
        for s in M.sentences(p):
            if rules["IF2"].search(s) or equivalence_claim(s, p):
                add("INFO", "IF2", "results/summary", "不存在/等效措辞：人工核对是否仅凭未显著作结论；报告区间，正面等效结论需等效界值与检验支持。", s)
    for p in res + dis:
        if re.search(r"\bcluster|簇", p, re.I):
            for s in M.sentences(p):
                if rules["IF3"].search(s):
                    add("INFO", "IF3", "results/discussion", "簇检验的边界不是效应的起止时刻：写“显著簇覆盖 X–Y ms”，不写“从 X ms 开始”。", s)
    low = text.lower()
    for ph in forbidden(a.concept):
        if ph.lower() in low:
            add("MUST", "FW1", "全文", "作者登记的禁用表述出现在稿件里：%s" % ph, ph)
    ledger = []
    if a.citations:
        ledger = list(csv.DictReader(open(a.citations, encoding="utf-8-sig", newline="")))
    for sec, paras in (("introduction", intro), ("discussion", dis)):
        for pi, p in enumerate(paras, 1):
            for s in M.sentences(p):
                if rules["LG"].search(s):
                    ok = any(re.search(sec[:5], r.get("claim_location", ""), re.I) and re.search(r"\bpara(?:graph)?\s*%d\b" % pi, r.get("claim_location", ""), re.I)
                             and r.get("claim_type") == "comparison" and r.get("citation_access") == "fulltext" and r.get("relation") in ("supports", "partially_supports")
                             for r in ledger)
                    if not ok:
                        lvl = "MUST" if (ledger and a.stage == "submission") else "SHOULD"
                        add(lvl, "LG1", "%s para %d" % (sec, pi), "概括前人研究的句子是比较性主张：对所概括的研究读全文，在引文台账登记 claim_type=comparison、fulltext、claim_location 写到段。", s)
    L = ["# 主张强度与文献概括（claim_strength）", "", "语言 %s；阶段 %s；MUST %d、SHOULD %d、INFO %d。" % (lang, a.stage, sum(i["level"] == "MUST" for i in items), sum(i["level"] == "SHOULD" for i in items), sum(i["level"] == "INFO" for i in items)), ""]
    for it in items:
        L.append("- **%s %s**（%s）%s 例：%s" % (it["level"], it["code"], it["where"], it["msg"], it["example"]))
    if not items:
        L.append("没有命中。")
    L += ["", "措辞信号不是判决：命中的句子逐条看主张与证据是否相称；没有命中也不说明主张合适。"]
    out = "\n".join(L) + "\n"
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write(out)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"schema_version": 1, "stage": a.stage, "lang": lang, "items": items}, f, ensure_ascii=False, indent=1)
    print(out if not a.report else "MUST %d、SHOULD %d；报告 %s" % (sum(i["level"] == "MUST" for i in items), sum(i["level"] == "SHOULD" for i in items), a.report))
    return 1 if any(i["level"] == "MUST" for i in items) else 0


if __name__ == "__main__":
    sys.exit(main())
