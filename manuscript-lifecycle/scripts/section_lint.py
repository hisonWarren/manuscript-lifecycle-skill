#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
section_lint.py — 各节"职能"检查：内容是否放在了该放的节里，外加几类跨节问题。

  python section_lint.py 稿件.md|docx [--limits limits.json] [--bench bench.json] [--lexicon 词表.json]
         [--fragment] [--design cross_sectional] [--report out.md] [--json out.json]
--fragment：输入是稿件片段（单独的 Highlights、投稿信、图注表注、一两节），不做各节职能检查，只做全文级检查。
--design：作者声明的研究设计。非实验设计（横断面、队列、病例对照、观察性、质性）时检查因果措辞（G1）；
也可写在 limits.json 的 design 字段。不声明就不做这项检查，脚本不替作者判断设计。

limits.json 可含：abstract_words、main_words、conclusion_words、title_words、highlights_max_n、highlights_max_chars。
--bench：bench_profile.py --json 的输出。有它时，结果解释句占比、讨论数字密度、结论词数的阈值改用同类文献分布的上界
（≥20 篇 p95，10–19 篇 p90，更少用最大值）；没有 --bench 时用内置经验值。
三级：MUST（必须处理：改掉，或在作者说明写明保留理由与规则代码）；SHOULD（逐条看）；INFO（数值与提醒）。
脚本只认得形式，不认得意思：每条都是候选，判断权在人。各条的改法见 references/02_section_contracts.md。
退出码：0 无 MUST；1 有 MUST；2 输入错误。
"""
import collections
import argparse, json, os, re, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

STOP = set("""the a an and or of in on for to with by from at as is are was were be been being this that these those it its
which who whom whose than then there their our we they he she his her them also not no can could may might will would
should into over under between within across about after before during per both each other such more most less very
however therefore thus study""".split())
NONEXP = {"cross_sectional", "observational", "cohort", "case_control", "qualitative"}
RANDOMI = re.compile(r"\brandomi[sz]ed\b|\brandomly (?:assigned|allocated)\b|随机(?:对照|分组|分配|化)", re.I)
UMB = re.compile(r"statistic|data analys|analytic|analysis strategy|^analys[ie]s$|统计|数据分析|数据处理|分析策略|分析方法|数据的?处理与分析|^分析$", re.I)


def content_set(s, lang):
    if lang == "zh":
        c = "".join(M.CJK.findall(s))
        return {c[i:i + 2] for i in range(len(c) - 1)}
    return {w.lower() for w in M.LAT.findall(s) if len(w) >= 4 and w.lower() not in STOP}


def jacc(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def grams(s, lang, n):
    if lang == "zh":
        c = "".join(M.CJK.findall(s)); n = 20      # 中文 20 字≈英文 10 词；15 字在 16 篇已发表论文中 15 篇触发
        return {c[i:i + n] for i in range(len(c) - n + 1)}
    w = [x.lower() for x in M.LAT.findall(s)]
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


# 待核占位符内部的文字：[VERIFY: …]、【待核：…】
VERIFY_SLOT = re.compile(r"\[\s*(?:VERIFY|TODO|待核|待确认)\b|[【〔]\s*(?:待核|待确认|VERIFY)", re.I)

# 结果段以表图起句的补充写法。词表参与领域包指纹，不能改动，所以补充式写在这里。
# 已发表论文中这种起句很少，实测见 assets/benchmarks/display_baseline.json 的 results_opening_with_display。
TABLE_LED_MORE = re.compile(
    r"^\s*(?:\*\*)?\s*(?:(?:As|as)\s+(?:is\s+)?(?:shown|presented|displayed|reported|summari[sz]ed|can be seen|illustrated|depicted)\b"
    r"|(?:Table|Tab\.|Fig\.?|Figure)\s*S?\d+[A-Za-z]?\s*(?:and|,|&)?\s*(?:Table|Fig\.?|Figure)?\s*S?\d*[A-Za-z]?\s*"
    r"(?:shows?|presents?|displays?|reports?|summari[sz]es?|lists?|gives?|provides?|contains?|illustrates?|depicts?|indicates?)\b"
    r"|(?:The\s+)?(?:results?|findings?|estimates?|coefficients?|descriptives?)\s+(?:are|is)\s+(?:shown|presented|reported|displayed|summari[sz]ed)\s+in\s+(?:Table|Fig)"
    r"|(?:如|见|详见|参见)?\s*(?:表|图)\s*\d+\s*(?:所示|显示|呈现|列出|给出|报告|表明|中)"
    r"|(?:如|见|详见|参见)\s*(?:表|图)\s*\d)", re.I)

# 把比较写成“相同 / 等同 / 完全一致”。不显著只说明没有发现差异；报告了等效性检验或贝叶斯因子时例外。
# 只看结果陈述：同句要有统计量或组间比较的字样，并排除描述材料与程序的句子（“materials were identical to Experiment 1”）。
# 同句报告了不显著的检验时为 SHOULD，否则为 INFO（已发表论文里也有合理的“the same pattern”，见 references/16）。
NULL_EQUIV = re.compile(
    r"\b(?:were|was|are|is|remained|appeared)\s+(?:\w+ly\s+)?(?:identical|equivalent|the same|indistinguishable|invariant)\b(?!\s+(?:to|with|as|from chance)\b)"
    r"|\bno (?:real |true )?differences? (?:exists?|existed)\b"
    r"|完全(?:一致|相同)|没有任何差异|毫无差异|并无二致", re.I)
NULL_EQUIV_NEG = re.compile(r"(?:\bnot\b|n't|\bnever\b|不|未|并非)\s*$", re.I)
EQUIV_OK = re.compile(r"equivalence test|\bTOST\b|two one-sided|Bayes factor|\bBF\s*0?1\b|\bROPE\b|等效性检验|贝叶斯因子", re.I)
EQUIV_CONTEXT = re.compile(r"\b[pP]\s*[=<>]|\b[tFMSχ]\s*[=(]|\bCI\b|\bbetween\b|\bacross\b|\bgroups?\b|\bregardless\b|\bboth\b|两组|组间|各组|不同(?:组|学校|条件)", re.I)
PROCEDURAL = re.compile(r"\bexperiment\s*\d|\bprocedure|\bstimul|\bmaterials?\b|\bapparatus|\binstruction|\bquestionnaire|\bscale\b|\bsettings?\b|\bas in\b|\bdesign\b|实验\s*[一二三四五\d]|程序|材料|刺激|指导语|问卷", re.I)
NONSIG = re.compile(r"\b[pP]\s*(?:=|>|≥)\s*0?\.(?:0[5-9]|[1-9])|\bn\.s\.|not (?:statistically )?significant|non-?significant|did not (?:significantly )?differ"
                    r"|no (?:statistically )?significant|未达(?:到)?(?:统计学?)?显著|不显著|无(?:统计学?)?显著(?:性)?差异|差异不显著", re.I)


def null_equiv(s):
    """把比较写成相同。紧挨着的否定（not identical、不完全一致）、等效性检验、描述程序与材料的句子都不算。"""
    if (PROCEDURAL.search(s) and not re.search(r"\bp\s*[=<>≥]|统计|得分|scores?|\bCI\b|confidence interval|置信区间", s, re.I)) or not EQUIV_CONTEXT.search(s):
        return False
    # 只说做了等效性检验不算证明等效；落在界值内、且没有失败的检验才放过
    if EQUIV_OK.search(s) and re.search(r"within (?:a |the )?margin|within.{0,25}equivalence bounds|在.{0,15}等效界值内", s, re.I) \
            and not re.search(r"failed|not establish|not demonstrate|未通过|未证明", s, re.I):
        return False
    return any(not NULL_EQUIV_NEG.search(s[max(0, m.start() - 12):m.start()]) for m in NULL_EQUIV.finditer(s))


# 写作过程的痕迹进了稿件：工具名、内部文件、作者待办、对标与门控的说明。它们属于工作区与作者说明，
# 不属于论文（见 SKILL §8 与 references/03）。实地试写中两份稿件都把“对标未完成”“见审计列表”写进了局限或标识段。
# 目的句的补充写法（词表参与领域包指纹，不能改，补充式写在这里）：The primary question … was whether / we asked whether
AIM_MORE = re.compile(r"\b(?:primary|main|central|research|key)\s+(?:research\s+)?questions?\b[^.]{0,80}\b(?:was|were|is|are)\s+(?:whether|how|what|which)\b"
                      r"|\bwe\s+(?:asked|tested|examined|investigated)\s+whether\b|\bthe\s+(?:purpose|aim|goal|objective)s?\s+of\s+(?:this|the present|the current)\s+(?:study|trial|paper)\b"
                      r"|\bthis\s+(?:study|trial|paper)\s+(?:asked|tested|examined|compared|investigated)\s+whether\b|本研究(?:旨在|的目的是|拟|考察|检验|比较|关注|回答|探讨)"
                      r"|本研究的(?:问题|研究问题|目的|目标)(?:是|在于|为)|研究问题(?:是|为|在于)"
                      # 第五轮：近邻的“当前研究”句常带副词或用 Here we / To fill this gap, we 起句（eLife、Nat Hum Behav 实测），旧式样认不出，草稿反被报 I1
                      r"|\bwe\s+(?:then|first|next|also|further|here)\s+(?:asked|tested|examined|investigated)\b|\b(?:here|in this (?:study|work|article|paper|experiment)),?\s+we\s+(?:\w+\s+){0,2}?(?:asked|examine|examined|test|tested|investigate|investigated|recorded|measured|had|used|show|report)\b"
                      r"|\bto\s+(?:fill|address|close|bridge)\s+(?:this|that|these)\b[^.,]{0,30}\bgaps?\s*,\s*we\b|\b(?:accounts?|hypothes[ie]s|models?)\s+make\s+(?:different|distinct|opposite|competing)\s+predictions\b", re.I)
# 把不显著写成趋势的补充写法：showed a trend towards improvement / numerically favoured
SPIN_MORE = re.compile(r"\b(?:showed|show|showing|there was|with)\s+(?:a\s+)?(?:non-?significant\s+)?trends?\s+(?:towards?|for)\s+(?:an?\s+)?(?:improvement|benefit|higher|lower|better|greater|difference|advantage)\b"
                       r"|\btrend(?:ed|ing)?\s+towards?\s+significan|\bnumerically\s+(?:favou?red|higher|better|superior)", re.I)
# 稿件状态话：这些属于作者说明，不属于论文（包括“本稿未提供……”“待作者核实”“写作流程测试”）
STATUS_TALK = (r"|\bthis draft\b|\bfor this draft\b|\bin this draft\b|drafting pass|writing[- ]?(?:workflow|process|exercise)|workflow[- ](?:test|evaluation|demonstration)"
               r"|demonstration draft|author verification|pending (?:author )?verification|remains? (?:placeholders?|to be confirmed by the authors?)"
               r"|(?:were|was|are|is) not (?:supplied|provided|available) for this(?! (?:check|analysis|analyses|test|tests|comparison|step|study|purpose|sample|subset|measure|model)\b)|figure (?:is )?not drawn|\bsource notes\b|analysis package|supplied for [^.]{0,30}(?:testing|evaluation)"
               r"|本稿由|本草稿|写作流程|流程测试|写作练习|演示稿|待作者(?:核实|确认|提供)|材料(?:中|里)(?:没有|未)(?:提供|记录|写明|说明|报告)"
               r"|(?:分析|所给|提供的|作者)材料(?:中|里)?(?:没有|未)(?:提供|记录|写明|说明|报告)|作者尚未提供"
               r"|not (?:fully |yet )?(?:documented|described|reported|provided|supplied|specified|available) in the (?:analysis|supplied|provided|source) (?:materials|notes|package|files)"
               r"|(?:analysis|source) (?:materials|notes) (?:do|did) not (?:report|document|provide|specify|include)")
SYNTH_BANNER = re.compile(r"synthetic|simulated|合成数据|模拟数据|SIMULATION", re.I)
WORKFLOW_LEAK = re.compile(
    r"manuscript-lifecycle|gated-pipeline|section_lint|bench_profile|phrase_contrast|number_trace|ledger_check|journal_check|table_style"
    r"|domain[ _-]?pack|results[ _]ledger|story[ _]card|gate[ _]?log|coverage_audit|naturalness_log|verify_doi|exemplar map"
    r"|作者待办|不进入正式结论|领域包|句式分布|对标(?:语料|文献|范文|包|工作)|门控|故事卡|结果台账|审计(?:记录|日志|列表)|(?:标|写)\s*FINAL" + STATUS_TALK, re.I)
STATUS_RX = re.compile(STATUS_TALK[1:], re.I)
# 内部处理过程：重跑、合并出错、在 Excel 里清洗。研究者关心，读者不需要（必须披露的问题除外）
INTERNAL_PROC = re.compile(r"\b(?:re-?ran|were re-?run|re-?analy[sz]ed)\b[^.]{0,60}\b(?:after|following|because)\b|identifier error|merg(?:e|ing) error"
                           r"|cleaned (?:in|with|using) Excel|in Excel before|重跑|重新运行了?(?:全部|所有)?分析|合并(?:时)?(?:出错|错误)|(?:在 ?)?Excel ?(?:中|里)?(?:清洗|整理)", re.I)
# 组内剂量或使用量梯度是观察性比较：随机化只保证组间比较
DOSE_CAUSAL = re.compile(r"(?:\b(?:led to|leads to|caused|causes|resulted in|produced|drove)\b|导致|使得|带来了)", re.I)
DOSE_CTX = re.compile(r"tertile|quartile|quintile|\bdose\b|more hints|hint use|higher use|heavier use|usage|使用(?:越|更)多|使用量|剂量|三分位|四分位", re.I)
# 词表之外的补充判断，只用于本脚本，不改领域包据以建库的词表：
# 中文“提示”既是干预名（自适应提示、提示成功率），也是“表明”义的动词；解释句与“不显著但……”只认动词用法。
# 引言里写出张力或相互竞争的预测，也算空白或张力表述。
HINT_VERB = r"(?:结果|数据|分析|发现|研究|这|此|该|上述|以上|均|也|或|进一步|似乎|可能)提示(?![成使显次组后的系条级类策内信频率数量])|提示(?:着|我们)"
GAP_MORE = {"en": [r"\bremain(?:s|ed)? (?:sparse|scarce)\b", r"\bunresolved\b", r"\btension\b", r"\bcompeting (?:predictions|accounts|explanations|hypotheses)\b",
                   r"\bopen question\b", r"\bit is (?:unclear|not known|unknown) (?:whether|how|why)\b"],
            "zh": ["张力", "悬而未决", "相互竞争", "存在争议", "并不一致"]}


def adjust_lexicon(R, lang):
    if lang == "zh":
        rx = R.get("interpretive")
        if rx is not None and "(?:提示|" in rx.pattern:
            R["interpretive"] = re.compile(rx.pattern.replace("(?:提示|", "(?:%s|" % HINT_VERB, 1), rx.flags)
        rx = R.get("spin")
        if rx is not None and "倾向|提示)" in rx.pattern:
            R["spin"] = re.compile(rx.pattern.replace("倾向|提示)", "倾向|提示了|似乎提示)"), rx.flags)
    more = GAP_MORE.get(lang)
    if more and R.get("gap") is not None:
        R["gap"] = re.compile(R["gap"].pattern + "|" + "|".join("(?:%s)" % x for x in more), R["gap"].flags)
    return R


# 明确否认因果的句子（“不能推出……导致……”）不算因果措辞
CAUSAL_DENIED = re.compile(r"不能(?:据此)?(?:推出|推断|解释为|理解为|说明|认为|断定)|不(?:应|宜)(?:被)?(?:解释|理解|视|看作)为|并非|不意味着|不代表"
                           r"|cannot (?:be )?(?:interpreted|read|taken|attributed)|can ?not (?:show|establish|tell)|does not (?:imply|mean|show|establish)"
                           r"|should not be (?:interpreted|read|taken)|not (?:be )?(?:interpreted|read) as|\bno causal\b", re.I)
# 图注里只有看到图才知道的编码：线型、颜色、符号、刻度标记
VIS_ENC = re.compile(r"\b(?:solid|dashed|dotted|dash-dotted)\s+(?:lines?|curves?)\b|\btick marks?\b|\b(?:open|filled|closed|hollow)\s+(?:circles?|squares?|triangles?|symbols?|markers?|dots?)\b"
                     r"|\b(?:red|blue|green|orange|black|grey|gray|purple)\s+(?:lines?|curves?|bars?|dots?|points?|symbols?)\b"
                     r"|实线|虚线|点线|点划线|刻度线|空心|实心|(?:红|蓝|绿|橙|黑|灰|紫)色(?:的)?(?:线|曲线|柱|点|符号)", re.I)
LEGEND_START = re.compile(r"^\W{0,4}(?:Fig(?:ure)?\.?\s*S?\d|图\s*S?\d)", re.I)
NOTE_START = re.compile(r"^\W{0,4}(?:Notes?\b|注\s*[:：]|Table\s*S?\d|表\s*S?\d)", re.I)
# 注释只交代缩写、单位、样本与特殊处理：结论和软件、估计细节不属于这里
CAP_CLAIM = re.compile(r"\bdemonstrat\w*|\bprov(?:e|es|ed) that\b|\bsuperior to\b|\bconfirm(?:s|ed)? that\b|表明|证明|优于", re.I)
CAP_METHOD = re.compile(r"\b(?:fitted|estimated|imputed) (?:by|with|using)\b|\bREML\b|\blme4\b|\bnlme\b|\bcoxme\b|\bmice \d|\bMplus\b|\bSPSS\b|\bStata\b|\bR \d\.\d|限制性极大似然", re.I)
LOCAL_PATH = re.compile(r"`?(?:\.{0,2}/)?(?:[\w.-]+/)+[\w.-]+\.(?:py|R|csv|json|ipynb|md|txt)`?|`[\w.-]+\.(?:py|R|ipynb)`")


def bench_bound(bench, key, default):
    s = (bench or {}).get("summary", {}).get(key)
    b = M.upper_bound(s)
    return (b, "对标上界 %.3g（n=%d）" % (b, s["n"])) if b is not None else (default, "内置经验值 %g" % default)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path"); ap.add_argument("--limits", default=""); ap.add_argument("--bench", default="")
    ap.add_argument("--lexicon", action="append", default=[]); ap.add_argument("--lang", default="auto", choices=["auto", "en", "zh"])
    ap.add_argument("--report", default=""); ap.add_argument("--json", default="")
    ap.add_argument("--domain", default="", help="领域包目录：用其分布校准阈值，并按已发表论文的触发率调整级别")
    ap.add_argument("--fragment", action="store_true", help="输入是片段（Highlights、投稿信、图注表注）：只做全文级检查")
    ap.add_argument("--design", default="",
                    help="作者声明的研究设计（rct、cohort、cross_sectional 等；cluster-rct、randomised、横断面这类写法也认）；非实验设计时检查因果措辞")
    a = ap.parse_args()
    nd = M.normalize_design(a.design)
    if nd is None:
        print("认不出的设计名：%s。可用：%s（也认 cluster-rct、randomised、longitudinal、survey、横断面 等常见写法）" % (a.design, "、".join(M.DESIGNS)), file=sys.stderr)
        return 2
    a.design = nd
    if not os.path.exists(a.path):
        print("找不到文件", file=sys.stderr); return 2
    text = M.load_text(a.path)
    if not text.strip():
        print("not_verified：稿件为空，不能将零检查项记为通过", file=sys.stderr); return 2
    lang = M.detect_lang(text) if a.lang == "auto" else a.lang
    lex = M.load_lexicon(lang, a.lexicon)
    R = M.lex_rx(lex, lang)
    R = adjust_lexicon(R, lang)
    limits = json.load(open(a.limits, encoding="utf-8-sig")) if a.limits else {}
    bench = json.load(open(a.bench, encoding="utf-8-sig")) if a.bench else None
    rules = {}
    if a.domain:
        try:
            M.reject_pack_self_comparison(a.domain, [text])
            if bench is None:
                bench = json.load(open(os.path.join(a.domain, "bench_baseline.json"), encoding="utf-8"))
            rr = json.load(open(os.path.join(a.domain, "rule_rates.json"), encoding="utf-8"))
            rules, dom_lang = rr["rules"], rr.get("lang")
            if dom_lang != lang:
                raise ValueError("领域包语言是 %s，稿件是 %s；不能跨语言校准" % (dom_lang, lang))
        except (OSError, ValueError, KeyError) as e:
            print("领域包无法读取：%s" % e, file=sys.stderr); return 2
    blocks = M.parse(text)
    P = {}
    for b in blocks:
        if b["kind"] == "para":
            P.setdefault(b["sec"], []).append({"text": b["text"], "ss": M.sentences(b["text"]), "sub": b["sub"], "part": b.get("part", "")})
    assessed = sum(len(p["ss"]) for sec,paras in P.items() if sec not in ("front","back","references") for p in paras)
    frag = bool(a.fragment)
    if assessed == 0 and not frag:
        print("not_verified：未识别到可评估的论文节句子；核对切节和输入范围。确属片段（单独的 Highlights、投稿信、图注表注）时加 --fragment",
              file=sys.stderr); return 2
    heads = [b for b in blocks if b["kind"] == "heading"]
    items = []

    def add(level, sec, code, msg, ex=(), beyond=False):
        items.append({"level": level, "sec": sec, "code": code, "msg": msg,
                      "examples": [e[:220] for e in ex][:6], "beyond": bool(beyond)})

    def sents(sec):
        return [s for p in P.get(sec, []) for s in p["ss"]]

    def hit(key, s):
        rx = R.get(key)
        return bool(rx and rx.search(s))

    def words(sec):
        return sum(M.count_words(p["text"]) for p in P.get(sec, []))

    def nterms(s):
        return sum(len(R[k].findall(s)) for k in ("stat_terms", "domain_terms") if R.get(k))

    # ---------------- 题目与 Highlights
    title = next((b["text"] for b in blocks if b["kind"] == "heading" and b["sec"] == "front" and b["level"] == 1), None)
    if title is None:
        fp = [b["text"] for b in blocks if b["sec"] == "front" and b["kind"] == "para"]
        title = fp[0] if fp else None
    if title and lang == "en" and M.classify_heading(title) is None:
        cw = [w.lower() for w in M.LAT.findall(title) if len(w) >= 4 and w.lower() not in STOP]
        rep = sorted({w for w in cw if cw.count(w) > 1})
        tw = M.count_words(title)
        if rep:
            add("INFO", "题目", "T1", "题目中重复出现：%s。检查能否合并或换成读者关心的对象。" % "、".join(rep), [title])
        if limits.get("title_words") and tw > limits["title_words"]:
            add("SHOULD", "题目", "T2", "题目 %d 词，超过 %d。" % (tw, limits["title_words"]), [title])
    lines = text.split("\n")
    hi = next((i for i, l in enumerate(lines) if re.match(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*highlights\s*(?:\*\*)?\s*:?\s*$", l, re.I)), None)
    if hi is not None and (limits.get("highlights_max_n") or limits.get("highlights_max_chars")):
        bul = []
        for l in lines[hi + 1:]:
            if re.match(r"^\s*#{1,6}\s", l):
                break
            m = re.match(r"^\s*(?:[-*•·]|\d+[.)])\s+(.*)$", l)
            if m:
                bul.append(m.group(1).strip())
            elif l.strip() and bul:
                break
        mx_n, mx_c = limits.get("highlights_max_n", 99), limits.get("highlights_max_chars", 999)
        long_ = [b for b in bul if len(b) > mx_c]
        if len(bul) > mx_n or long_:
            add("MUST", "Highlights", "H1", "Highlights %d 条（上限 %s），超长 %d 条（每条上限 %s 字符，含空格）。" % (len(bul), mx_n, len(long_), mx_c), long_)
    # ---------------- 结果
    rs = sents("results")
    if rs:
        interp = [s for s in rs if hit("interpretive", s)]
        sh = len(interp) / len(rs)
        thr, src = bench_bound(bench, "results|interpretive_share", 0.20)
        thr = max(thr, 0.10)
        if interp:
            # 证据降级：五个领域包 86 篇已发表论文中平均 89% 触发 R1（rule_rates.json）；细的句子功能由 results_function 判断
            add("MUST" if sh > thr and len(interp) >= 3 else "INFO", "results", "R1",
                "解释或推测性句子 %d/%d（%.0f%%；MUST 阈值 %.0f%% 且不少于 3 句，%s）。结果报告发现；原因、机制、与文献的比较放讨论。"
                "\"约四分之三的方差来自…\"这类把系数翻成含义的句子可以留。" % (len(interp), len(rs), 100 * sh, 100 * thr, src), interp,
                beyond=sh > thr and len(interp) >= 3 and src.startswith("对标上界"))
        cit = [s for s in rs if M.count_citations(s) > 0]
        if cit:
            add("SHOULD" if len(cit) > 3 else "INFO", "results", "R2", "结果中有 %d 句带文献引用。方法学出处可以留；与既往研究的比较移到讨论。" % len(cit), cit)
        rp = P.get("results", [])
        led = [p["ss"][0] for p in rp if p["ss"] and (hit("table_led", p["ss"][0]) or TABLE_LED_MORE.search(p["ss"][0]))]
        if len(rp) >= 3 and len(led) / len(rp) > 0.5:
            add("SHOULD", "results", "R3", "%d/%d 个结果段以表图开头。先写发现，再在括号里指向表图。" % (len(led), len(rp)), led)
    # ---------------- 讨论
    dp = P.get("discussion", [])
    ds = sents("discussion")
    if dp:
        dw = words("discussion"); dn = sum(M.count_numbers(p["text"]) for p in dp)
        thr, src = bench_bound(bench, "discussion_all|numbers_per100", 2.5)
        if dw and 100 * dn / dw > thr:
            add("SHOULD", "discussion", "D1", "讨论数字密度 %.1f/百词（阈值 %.2f，%s）。讨论解释数字意味着什么，不复述结果。" % (100 * dn / dw, thr, src),
                beyond=src.startswith("对标上界"))
        st = [s for s in ds if hit("stat_detail", s) and M.count_numbers(s) >= 2]
        if st:
            add("SHOULD", "discussion", "D1b", "讨论中有 %d 句带检验统计量或区间。" % len(st), st)
        xr = [s for s in ds if hit("section_xref", s) or hit("backref", s) or re.search(r"\(\s*(?:see\s+)?(?:Table|Fig\.?|Figure)\s*S?\d", s, re.I)]
        if xr:
            add("SHOULD", "discussion", "D2", "讨论中有 %d 处\"见第 x 节 / 见表 x / 如前所述\"。讨论应当自足。" % len(xr), xr)
        fw = M.count_words(dp[0]["text"]); rest = [M.count_words(p["text"]) for p in dp[1:]]
        if rest and fw > 1.6 * statistics.median(rest):
            add("SHOULD", "discussion", "D3", "讨论首段 %d 词，约为其余段落中位数的 %.1f 倍。首段只概括主要发现及其含义。" % (fw, fw / statistics.median(rest)))
        if M.count_numbers(dp[0]["text"]) > 6:
            add("SHOULD", "discussion", "D3b", "讨论首段有 %d 个数字。用文字概括，关键数字最多一两个。" % M.count_numbers(dp[0]["text"]))
        if lang == "en" and not any(hit("synthesis", s) for s in dp[0]["ss"][-2:]):
            # 只对英文：16 篇中文心理学论文的讨论首段都以概括发现为主，没有这一收束语步
            add("INFO", "discussion", "D3c", "讨论首段末尾没有概括句（Taken together… / These findings suggest…）。这一语步在已发表论文中并不普遍"
                "（英文临床心理 24 篇中 23 篇没有），只有首段读起来像结果清单时才考虑补一句概括。")
        ends = [hit("negation", p["ss"][-1]) if p["ss"] else False for p in dp]
        run = best = 0
        for e in ends:
            run = run + 1 if e else 0; best = max(best, run)
        if best >= 2:
            add("SHOULD", "discussion", "D4", "有 %d 个相邻段落以否定句收尾，读起来像在防守。保留限定，同时写出数据正面支持的解释。" % best,
                [p["ss"][-1] for p, e in zip(dp, ends) if e])
        df = [s for s in ds if hit("defensive", s)]
        if len(df) >= 2:
            add("SHOULD", "discussion", "D5", "防御句式 %d 处（should not be interpreted as / does not mean …）。把否定句改成陈述所是；真正的局限放局限段。" % len(df), df)
        rsets = [content_set(s, lang) for s in rs]
        rest_ = [s for s in ds if M.count_numbers(s) >= 2 and any(jacc(content_set(s, lang), r) >= 0.5 for r in rsets)]
        if rest_:
            add("SHOULD", "discussion", "D6", "%d 句讨论几乎复述结果句（含数字且用词重合 ≥50%%）。" % len(rest_), rest_)
        fg = [s for s in ds if hit("future_generic", s)]
        if fg:
            add("INFO", "discussion", "D7", "泛泛的\"需要更多研究\" %d 处。写明什么设计能回答什么问题。" % len(fg), fg)
    # ---------------- 方法
    mp = P.get("methods", [])
    if mp:
        mh = [b["text"] for b in heads if b["sec"] == "methods"]
        if not any(UMB.search(h) for h in mh):
            # 证据降级：已发表论文触发率 9%–73%，随领域而变，是惯例不是缺陷；要不要设总节看近邻（convention_profile）
            add("INFO", "methods", "M1", "方法部分没有总的统计/数据分析小节。多数实证期刊设有：把各项分析收在其下，下级标题按分析目的命名。")
        subs = {}
        for p in mp:
            subs.setdefault(p["sub"], []).append(p)
        parent, stack = {}, []
        for b in heads:
            if b["sec"] != "methods":
                continue
            while stack and stack[-1][0] >= b["level"]:
                stack.pop()
            parent[b["text"]] = [h for _, h in stack]
            stack.append((b["level"], b["text"]))
        for sub, ps in subs.items():
            last = ps[-1]["ss"][-1] if ps[-1]["ss"] else ""
            if hit("software", last) and not UMB.search(sub or "") and len(subs) > 1:
                under = any(UMB.search(h) for h in parent.get(sub, []))
                scoped = re.search(r"\ball (?:the )?(?:\w+ ){0,3}(?:models|analyses)\b|所有|全部", last, re.I)
                if under and scoped:
                    add("INFO", "methods", "M2", "全局软件声明写在统计分析下的子节「%s」末尾；范围已写明，可移到统计分析总节开头。" % sub, [last])
                else:
                    add("SHOULD", "methods", "M2", "软件声明放在小节「%s」末尾，读者会以为只有这一节用它。改为分析部分开头的全局声明，或跟在所服务的分析后，并写明范围。" % (sub or "（无标题）"), [last])
        ms = sents("methods")
        sc = [s for s in ms if hit("scope", s)]
        if sc:
            add("INFO", "methods", "M3", "%d 句读起来覆盖\"全部分析\"。核对范围是否属实，不属实就写明是哪几项。" % len(sc), sc)
        im = [s for s in ms if hit("impl_detail", s)]
        if im:
            add("INFO", "methods", "M4", "%d 句是实现细节或内部质控。按报告分档（references/03）判断：正文、补充、回复备用还是不报。" % len(im), im)
        ana = [p for p in mp if UMB.search(p["sub"] or "")] or mp
        wp = sum(1 for p in ana if hit("purpose", p["text"]))
        if len(ana) >= 3 and wp / len(ana) < 0.3:
            add("INFO", "methods", "M5", "分析段落中写明目的的只有 %d/%d。每项分析要让读者知道它回答什么问题、为什么用它。" % (wp, len(ana)))
        pre = [s for s in ms if hit("defensive", s) or hit("backref", s)]
        if pre:
            add("SHOULD", "methods", "M6", "方法中有 %d 处预辩或回指（is not an artefact / as explained…）。陈述做了什么、为什么。" % len(pre), pre)
        heavy = [s for s in ms if nterms(s) >= 6]
        if ms and len(heavy) / len(ms) > 0.15:
            add("INFO", "methods", "M7", "%d/%d 句含 ≥6 个统计/领域术语。检查首次出现的术语是否有一句平实的解释，细节能否移入补充材料。" % (len(heavy), len(ms)), heavy)
    # ---------------- 引言
    ip = P.get("introduction", [])
    intro_texts = set(M.first_section_paras(blocks, "introduction"))
    ip = [p for p in ip if p["text"] in intro_texts]
    if ip:
        AIMSUB = re.compile(r"当前研究|本研究|研究概览|研究目的|研究假设|问题提出|the present stud|current stud|\baims?\b|hypothes|objectives?", re.I)
        late = [p for p in ip if AIMSUB.search(p["sub"] or "")] + [p for p in P.get("methods", [])[:3] if AIMSUB.search(p["sub"] or "")]
        # 先陈述问题与目的、再单列文献综述的结构（问题提出→相关研究→研究设计；Introduction→Literature Review→Method）：目的写在综述之前
        LITSUB = re.compile(r"文献综述|文献回顾|相关研究|研究现状|研究综述|理论基础|理论框架|literature review|related (?:work|research)|theoretical (?:background|framework)", re.I)
        lit = next((i for i, p in enumerate(ip) if LITSUB.search(p["sub"] or "") or LITSUB.search(p.get("part") or "")), None)
        late += ip[:lit][-2:] if lit else []
        if not any(hit("aim", p["text"]) or AIM_MORE.search(p["text"]) for p in ip[-2:]) and not any(hit("aim", p["text"]) or AIM_MORE.search(p["text"]) for p in late):
            add("MUST", "introduction", "I1", "引言最后两段（及“当前研究/研究目的”小节）都没有研究目的、问题或假设。", [ip[-1]["text"][:200]])
        if not any(hit("gap", p["text"]) for p in ip):
            add("SHOULD", "introduction", "I2", "引言没有明确的空白或张力表述。")
        isn = sents("introduction")
        nv = [s for s in isn if hit("novelty", s)]
        if nv:
            add("INFO", "introduction", "I3", "%d 处新颖性表述。每处要有检索依据，并把范围写窄到能被核实。" % len(nv), nv)
        heavy = [s for s in isn if R.get("stat_terms") and len(R["stat_terms"].findall(s)) >= 3]
        if isn and len(heavy) / len(isn) > 0.15:
            add("SHOULD", "introduction", "I4", "%d/%d 句含 ≥3 个统计/模型术语。引言的主角是问题与缺口，建模选择放方法。" % (len(heavy), len(isn)), heavy)
        rr = [s for s in isn if M.count_numbers(s) >= 2 and re.search(r"\bwe (?:found|observed)\b|本研究发现", s, re.I)]
        if rr:
            add("SHOULD", "introduction", "I5", "引言里出现了本研究的结果。引言只交代问题与目的。", rr)
        # 引言中段指路方法/结果：修订时常为回应审稿人而加，同类引言少见（07 §10）
        INTRO_PTR = re.compile(
            r"\b(?:defined|described|detailed|operationali[sz]ed|specified)\b.{0,50}\b(?:in|under)\s+the\s+Methods?\b"
            r"|\b(?:see|as (?:described|defined|shown|detailed) in)\s+the\s+Methods?\b"
            r"|\b(?:详见|见|参见)(?:本(?:研究|文)的?)?方法(?:部分|一节|节)?"
            r"|在方法(?:部分|一节|节)?(?:中|里)?(?:定义|界定|说明)",
            re.I)
        ptr = [s for s in isn if INTRO_PTR.search(s)]
        if ptr:
            add("SHOULD", "introduction", "I6", "引言有 %d 句指向方法节（defined in the Methods / 见方法）。引言用读者能懂的话交代概念边界，操作细节放方法，不在引言里指路。" % len(ptr), ptr)
    # ---------------- 结论
    cp = P.get("conclusion", [])
    if cp:
        cs = sents("conclusion")
        if limits.get("conclusion_words"):
            cw, (lim, src) = sum(M.count_words_ws(p["text"]) for p in cp), (limits["conclusion_words"], "期刊/项目上限")
        else:
            cw, (lim, src) = words("conclusion"), bench_bound(bench, "conclusion|words", 350 if lang == "zh" else 150)
        if cw > lim:
            add("SHOULD", "conclusion", "C1", "结论 %d %s、%d 句（上限 %d，%s）。结论回答研究问题、说清带来什么，不复述结果。" % (cw, "字" if lang == "zh" else "词", len(cs), lim, src),
                beyond=src.startswith("对标上界") or src.startswith("期刊"))
        # "(1)(2)"、"①"、"1." 这类列表编号不是数字结果（中文期刊结论常分条列出）
        cn = sum(M.count_numbers(re.sub(r"[（(]\s*\d{1,2}\s*[)）]|[①-⑩]|(?:^|(?<=[。；;\s]))\d{1,2}[.、)]\s*", " ", p["text"])) for p in cp)
        if cn:
            add("SHOULD", "conclusion", "C2", "结论含 %d 个数字。" % cn, [s for s in cs if M.count_numbers(s)])
        if any(M.count_citations(p["text"]) for p in cp):
            add("SHOULD", "conclusion", "C3", "结论含文献引用。")
        fg = [s for s in cs if hit("future_generic", s)]
        if fg:
            add("INFO", "conclusion", "C4", "泛泛的\"需要更多研究\"。写明什么设计能回答什么问题，或删去。", fg)
        stn = sum(len(R["stat_terms"].findall(s)) for s in cs) if R.get("stat_terms") else 0
        if cw and 100 * stn / cw > 3:
            add("SHOULD", "conclusion", "C5", "结论统计/模型术语 %.1f/百词。结论用读者的语言。" % (100 * stn / cw))
    # ---------------- 摘要
    ab = P.get("abstract", [])
    if ab:
        aw = sum(M.count_words_ws(p["text"]) for p in ab) + sum(M.count_words_ws(b["text"]) for b in heads if b["sec"] == "abstract")
        if limits.get("abstract_words") and aw > limits["abstract_words"]:
            add("MUST", "abstract", "A1", "摘要约 %d 词（含栏目名），超过上限 %d。" % (aw, limits["abstract_words"]))
        strict = re.compile(r"\([^()]*[A-Z][A-Za-z'’\-]+[^()]*(?:1[89]|20)\d\d[a-z]?[^()]*\)|\[\d+(?:\s*[-–,]\s*\d+)*\]|[⁰¹²³⁴⁵⁶⁷⁸⁹]")
        cites = [s for p in ab for s in p["ss"] if strict.search(s) and not re.search(r"journal|©|doi|http|vol\.|received|accepted", s, re.I)]
        if cites:
            add("MUST", "abstract", "A2", "摘要含文献引用。", cites)
    # ---------------- 局限
    lp = P.get("limitations", [])
    if lp:
        ls = sents("limitations")
        nm = sum(1 for s in ls if hit("limitation_marker", s))
        ng = sum(1 for s in ls if hit("negation", s))
        add("INFO", "limitations", "L1", "局限段 %d 句，序号标记 %d 处，含否定 %d 句（%.0f%%）。每条局限写清对结论的影响方向与已做的核对。" % (len(ls), nm, ng, 100 * ng / max(1, len(ls))))
        qc = [s for s in ls if hit("impl_detail", s)]
        if qc:
            add("INFO", "limitations", "L2", "局限段出现内部处理细节 %d 句。按报告分档判断是否需要在这里说。" % len(qc), qc)
    # ---------------- 跨节
    if lp:
        ptr = [s for s in sents("limitations") if M.LIMITATION_POINTER.search(s)]
        if ptr:
            add("SHOULD", "limitations", "L3", "局限段有 %d 句回指本文其他部分或补充材料。局限说哪条推断受什么限制；需要定位时先看方法或补充材料的题注能否承担。" % len(ptr), ptr)
    order = ["introduction", "methods", "results", "discussion", "limitations", "conclusion"]
    seen, pairs = {}, []
    junk = re.compile(r"journal of|©|doi|https?:|vol\.|downloaded|copyright|all rights reserved", re.I)
    for sec in order:
        for s in sents(sec):
            if junk.search(s):
                continue
            gs = {g for g in grams(s, lang, 8) if not (title and g.replace(" ", "") in (title or "").replace(" ", "").lower())}
            for g in sorted(gs):               # 固定顺序：同一输入每次报告同一对句子
                if g in seen and seen[g][0] != sec:
                    pairs.append((seen[g], (sec, s))); break
            for g in gs:
                seen.setdefault(g, (sec, s))
    if pairs:
        add("INFO", "全文", "X1", "%d 组跨节近乎逐字重复（≥8 词相同）。方法写决定，局限写后果与所需设计，不要把同一句话说两遍。" % len(pairs),
            ["[%s] %s ‖ [%s] %s" % (p[0][0], p[0][1][:90], p[1][0], p[1][1][:90]) for p in pairs])
    allb = [s for sec in order for s in sents(sec)]
    # 摘要是读者最先、也常常是唯一读到的部分：因果措辞、趋势话术、越界建议和新颖性宣称在这里代价最大，
    # 所以断言与设计这一组规则（S1、S2、G1、P1、N1）把摘要一并算进来。其余整稿规则的范围不变。
    assertb = list(dict.fromkeys(allb + sents("abstract")))
    if frag:
        allb = list(dict.fromkeys(allb + [s for sec, paras in P.items() if sec != "references" for p in paras for s in p["ss"]]))
        assertb = list(dict.fromkeys(assertb + allb))
    cnt_s = collections.Counter()
    for s in allb:
        k = M.norm_for_match(s)
        if (len(M.CJK.findall(s)) >= 20 if lang == "zh" else M.count_words(s) >= 10) and M._numeric_ratio(s) < 0.2:
            cnt_s[k] += 1
    rep_s = [k for k, c in cnt_s.items() if c >= 2]
    if rep_s:
        ex_ = [s for s in allb if M.norm_for_match(s) in rep_s]
        add("SHOULD", "全文", "X10", "%d 个句子在正文中原样出现不止一次（共 %d 次）。重复的总结句、意义句是常见的机器痕迹；同一句话只说一次。" % (
            len(rep_s), sum(cnt_s[k] for k in rep_s)), list(dict.fromkeys(ex_)))
    vg = [s for s in allb if hit("vague_ref", s)]
    if vg:
        add("INFO", "全文", "X2", "%d 句以 This/That/Here 等开头而指代不明。点名是哪个量表、哪个模型、哪一层关联。" % len(vg), vg)
    # Shared lexical scan uses independent reading scopes. Conceptual readiness
    # and evidence support still require reading the actual argument.
    import reader_readiness as RR
    for it in RR.inspect_text(text)["items"]:
        add(it["level"], it["sec"], it["code"], it["msg"], it.get("examples"))
    if lang == "en":
        body = " ".join(sents("abstract") + allb)
        mix = [("%s/%s" % (uk, us)) for uk, us in lex.get("spelling_pairs", [])
               if re.search(r"\b%s\b" % uk, body, re.I) and re.search(r"\b%s\b" % us, body, re.I)]
        if mix:
            add("SHOULD", "全文", "X4", "英美拼写混用：%s（专名除外）。" % "、".join(mix))
    dec = {}
    for sec in ("abstract", "results", "discussion", "limitations", "conclusion"):
        for p in P.get(sec, []):
            for m in re.finditer(r"(?<![\w.])[−-]?0?\.(\d+)(?![\d])", p["text"]):
                if re.search(r"\bps?\s*(?:值\s*)?[<=>≤≥]\s*$", p["text"][max(0, m.start() - 8):m.start()], re.I):
                    continue
                dec.setdefault(len(m.group(1)), []).append(p["text"][max(0, m.start() - 40):m.end() + 8])
    if len(dec.get(2, [])) >= 3 and len(dec.get(3, [])) >= 3:
        add("INFO", "全文", "X5", "小于 1 的统计量两位小数 %d 处、三位小数 %d 处。与表格保持同一精度，否则读者分不清说的是哪个数。" % (len(dec[2]), len(dec[3])),
            dec[2][:3] + dec[3][:3])
    sg = [s for s in allb if hit("significant", s) and not hit("stat_evidence", s)]
    if sg:
        add("INFO", "全文", "X6", "%d 句用了 significant/显著 但同句没有统计量。统计意义要有检验；重要性意义改用别的词。" % len(sg), sg)
    for key, code, msg in (("ai_marker", "X7", "AI 标记词"), ("template", "X8", "模板短语"), ("coinage", "X9", "自造标签/命名")):
        hs = [s for s in allb if hit(key, s)]
        if hs:
            add("INFO", "全文", code, "%s %d 句。只在与对标文献对照时有意义；先问这句话承担什么功能，再决定删、改还是保留。" % (msg, len(hs)), hs)
    # ---------------- 断言与设计：趋势话术、因果措辞、建议句、新颖性、声明
    eq = [s for s in assertb if null_equiv(s)]
    if eq:
        strong = [s for s in eq if NONSIG.search(s)]
        add("SHOULD" if strong else "INFO", "全文", "S2",
            "%d 句把比较写成“相同 / 等同 / 完全一致”（其中 %d 句同句报告了不显著的检验）。不显著只说明没有发现差异；"
            "要主张相同，需要等效性检验或贝叶斯因子。没有就写“未见差异”“差异不明显”。描述性的“同一模式”可以留。" % (len(eq), len(strong)),
            strong + [s for s in eq if s not in strong])
    sp = [s for s in assertb if hit("spin", s) or SPIN_MORE.search(s)]
    if sp:
        add("SHOULD", "全文", "S1", "%d 句把未达显著的结果说成趋势或\"接近显著\"。区间包含零就据实写未见明确差异或估计不精确，不用措辞补足。" % len(sp), sp)
    design = (a.design or limits.get("design") or "").strip().lower().replace("-", "_")
    if design in NONEXP:
        cz = [s for s in assertb if hit("causal", s) and not any(hit(k, s) for k in ("negation", "rather_than", "defensive"))]
        if cz:
            add("SHOULD", "全文", "G1", "声明的设计是 %s，但 %d 句用了因果动词（导致/引起/caused/led to 等）。这类设计支持关联，不支持因果方向；"
                "确需讨论机制时写明是推测及其依据。" % (design, len(cz)), cz)
        rd = [s for s in allb if RANDOMI.search(s)]
        if rd:
            add("MUST", "全文", "G2", "声明的设计是 %s，正文却出现随机分配/randomized。设计写错是事实错误，先核对设计再改措辞。" % design, rd)
    pr = [s for s in assertb if hit("prescriptive", s)]
    if pr:
        add("SHOULD" if design in NONEXP else "INFO", "全文", "P1",
            "%d 句建议他人采取行动（应当/建议/should）。本研究检验过这项干预吗？没检验就写成有待检验的方向，不写成建议。" % len(pr), pr)
    intro_s = set(sents("introduction"))
    nv2 = [s for s in assertb if hit("overclaim", s) and s not in intro_s]
    if nv2:
        add("INFO", "全文", "N1", "引言以外有 %d 处新颖性表述（首次/填补空白/first/groundbreaking）。每处要有检索依据，范围写窄到能被核实。" % len(nv2), nv2)
    if frag:
        # [VERIFY: 作者确认后填写…] 这类占位符是在把声明留给作者，不是代作者写声明
        dc = [s for s in allb if hit("declaration", s) and not VERIFY_SLOT.search(s)]
        if dc:
            add("SHOULD", "片段", "N2", "%d 句是声明（利益冲突、资助、伦理、数据可得性、未一稿多投、全体作者同意）。"
                "这些是事实，须由作者确认；材料没有提供就留作者待办，不代填\"无\"。" % len(dc), dc)
    mw = sum(M.count_words_ws(p["text"]) for s in order for p in P.get(s, []))
    if frag:
        mw = sum(M.count_words_ws(p["text"]) for sec, paras in P.items() if sec != "references" for p in paras)
    if limits.get("main_words") and mw > limits["main_words"] and not frag:
        add("MUST", "全文", "W1", "正文约 %d 词（引言至结论，不含标题），超过上限 %d。" % (mw, limits["main_words"]))
    # ---------------- 交付残留：对话残留、零宽字符、Word 域错误、表情符号（在未清洗文字上查）
    try:
        raw_hits = M.residue_hits(M.load_raw(a.path), placeholders=True)
    except Exception:
        raw_hits = []
    hard = [h for h in raw_hits if h[0] != "placeholder"]
    if hard:
        add("MUST", "全文", "A1", "交付残留 %d 处（%s）。这些不是写作风格问题，投稿前必须清除；零宽字符还会破坏检索、计词与查重。" % (
            len(hard), "、".join(sorted({h[1] for h in hard}))), ["第%d行 %s：%s" % (h[2], h[3], h[4]) for h in hard])
    leak, fence = [], False
    body_lines = text.split("\n")
    fm_end = 0
    if body_lines and body_lines[0].strip() == "---":  # 跳过文件头的 YAML 元数据
        fm_end = next((i + 1 for i, l in enumerate(body_lines[1:], 1) if l.strip() == "---"), 0)
    first_abs = next((i for i, l in enumerate(body_lines, 1) if re.match(r"^\s*#{1,6}\s*(?:abstract|summary|摘\s*要)\b", l, re.I)), len(body_lines))
    for ln, line in enumerate(body_lines, 1):
        if ln <= fm_end:
            continue
        if ln < first_abs and SYNTH_BANNER.search(line) and not STATUS_RX.search(line) and not re.search(r"manuscript-lifecycle|作者待办|对标", line):
            continue   # 题目下一句“合成数据，不代表真实被试”是模拟稿必需的标识
        if line.strip().startswith("```"):
            fence = not fence
            continue
        if not fence and WORKFLOW_LEAK.search(line):
            leak.append("第%d行：%s" % (ln, line.strip()[:160]))
    # 摘要与结论只写研究本身：待核占位、稿件状态话都不能放进去（读者最先、也常常只读这两处）
    slot = re.compile(r"\[\s*(?:VERIFY|TODO|TBD|待核|待补|待填)[^\]]*\]|【待[核补填][^】]*】", re.I)
    admin = re.compile(r"ethic|IRB|approv|fund|conflict|competing|data[- ]availab|consent|literature|reference|citation|伦理|批准|资助|利益冲突|数据可得|知情同意|文献|引文", re.I)
    keyleak, inline = [], []
    for sec in ("abstract", "conclusion"):
        for s in sents(sec):
            slots = slot.findall(s)
            rest = slot.sub("", s).strip(" .;；。()（）")
            if STATUS_RX.search(s) or any(admin.search(x) or x.count(";") + x.count("；") >= 1 for x in slots) or (slots and len(rest) < 12):
                keyleak.append(s)
            elif slots:
                inline.append(s)
    if keyleak:
        add("MUST", "摘要/结论", "X13", "摘要或结论里有 %d 句待办清单或稿件状态话（伦理、资助、文献待补，“本稿未提供……”等）。摘要和结论只写问题、发现与边界；"
            "这些写进作者说明，必要的占位放回方法或声明处。" % len(keyleak), keyleak)
    if inline:
        add("SHOULD", "摘要/结论", "X14", "摘要或结论里有 %d 处待核事实占位（如 [VERIFY: city]）。换成不需要该事实的说法，或把占位留在方法里。" % len(inline), inline)
    if leak:
        add("MUST", "全文", "X11", "稿件里有 %d 行写作过程的痕迹（工具名、对标或门控说明、作者待办、内部文件）。"
            "这些放进作者说明或工作记录；论文只写研究本身。局限只写影响推断的事，不写“对标未完成”。" % len(leak), leak)
    ip_ = [s for sec in ("methods", "results", "discussion", "limitations") for s in sents(sec) if INTERNAL_PROC.search(s) or M.REVISION_TRACE.search(s)]
    if ip_:
        add("SHOULD", "全文", "X15", "%d 句写了内部处理或改稿过程（重跑、合并出错、Excel 清洗、改稿时重读才发现、应审稿人要求）。读者需要的是研究本身和最终分析怎样做；过程留在工作记录或回复信。"
            "影响结论的数据问题（丢失、排除、不一致的决定）照常披露，改写成直陈事实。" % len(ip_), ip_)
    dz = [s for sec in ("abstract", "results", "discussion", "conclusion") for s in sents(sec) if DOSE_CAUSAL.search(s) and DOSE_CTX.search(s) and not CAUSAL_DENIED.search(s)]
    if dz:
        add("SHOULD", "全文", "P2", "%d 句用因果动词描述使用量或剂量梯度。即使是随机试验，组内按使用量分组的比较也是观察性的：写“与……相关”，"
            "并说明使用多的学生可能本来就不同。" % len(dz), dz)
    vis = [s for b in blocks if b.get("kind") == "caption" or LEGEND_START.match(b.get("text", "")) for s in M.sentences(b.get("text", "")) if VIS_ENC.search(s)]
    if vis:
        add("SHOULD", "图注", "V1", "图注里有 %d 句写了线型、颜色或标记。确认与实际的图一致；图还没画或你没看到图时，删去这些描述，或写成 [VERIFY: …] 留给作者。" % len(vis), vis)
    dn = [s for b in blocks if b.get("kind") == "caption" or LEGEND_START.match(b.get("text", "")) or NOTE_START.match(b.get("text", ""))
          for s in M.sentences(b.get("text", "")) if CAP_CLAIM.search(s) or CAP_METHOD.search(s)]
    if dn:
        add("SHOULD", "表注/图注", "V2", "表注或图注里有 %d 句下了结论，或写了软件与估计细节。注释只交代缩写、单位、样本与特殊处理；结论放结果或讨论，软件与估计方法放方法。" % len(dn), dn)
    paths = [s for sec in ("abstract", "results", "discussion", "limitations", "conclusion") for s in sents(sec) if LOCAL_PATH.search(s)]
    if paths:
        add("SHOULD", "全文", "X12", "摘要、结果、讨论或结论里出现了 %d 处本地文件路径或脚本名。数据与代码的位置写进“数据与代码可得性”声明，"
            "用公开仓库的地址或 DOI，不用本机路径。" % len(paths), paths)
    ph = [h for h in raw_hits if h[0] == "placeholder"]
    if ph:
        add("INFO", "全文", "A2", "占位符 %d 处。起草阶段用来标记待核事实是对的，要同时列入作者待办；投稿包检查（delivery_check）会阻断未清除的占位符。" % len(ph),
            ["第%d行 %s" % (h[2], h[4]) for h in ph])
    # ---------------- 领域校准：常见风格降为参照；发表频率不证明科学主张成立
    if rules:
        for it in items:
            r = rules.get(it["code"])
            if not r or it["code"] in ("A1", "W1", "H1", "G1", "G2", "S1", "S2", "P1", "N1", "N2", "X11", "X13"):
                continue
            if it.get("beyond"):
                # 本稿的数值已超出同领域已发表论文的上界：常见不等于可以做到这个程度
                it["msg"] += "（同领域已发表论文 %d/%d 篇也触发本规则，但本稿的数值已超出它们的上界，不降级）" % (r["papers"], r["n"])
                continue
            if r["share"] >= 0.5 and it["level"] != "INFO":
                it["level"] = "INFO"
                it["msg"] += "（领域校准：同领域已发表论文 %d/%d 篇也有此情况，降为参照）" % (r["papers"], r["n"])
            elif r["share"] >= 0.25:
                it["msg"] += "（同领域已发表论文 %d/%d 篇也有）" % (r["papers"], r["n"])
    # ---------------- 输出
    rank = {"MUST": 0, "SHOULD": 1, "INFO": 2}
    items.sort(key=lambda x: (rank[x["level"]], x["sec"]))
    nm_, ns_, ni_ = (sum(i["level"] == k for i in items) for k in ("MUST", "SHOULD", "INFO"))
    L = ["# 各节职能检查：%s\n" % os.path.basename(a.path),
         "语言 %s；正文约 %d 词（Word 口径）；MUST %d、SHOULD %d、INFO %d%s。每条都是候选：脚本只认形式，判断与改法见 references/02。\n" % (
             lang, mw, nm_, ns_, ni_, "；阈值已按对标校准" if bench else "")]
    L.append("模式：%s；声明的设计：%s。\n" % (
        ("片段（全文级检查覆盖整个文件；识别到的节仍做职能检查）" if assessed else "片段（只做全文级检查，未做各节职能检查）") if frag else "全文",
        design or "未声明（--design 或 limits.json 的 design 可启用因果措辞检查 G1）"))
    for it in items:
        L.append("- **%s %s**（%s）%s" % (it["level"], it["code"], it["sec"], it["msg"]))
        for e in it["examples"]:
            L.append("  - %s" % e)
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
        print("MUST %d、SHOULD %d、INFO %d：%s" % (nm_, ns_, ni_, " ".join("%s%s" % (i["code"], "!" if i["level"] == "MUST" else "") for i in items)))
    else:
        print(out)
    if a.json:
        with M.wfile(a.json) as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
    return 1 if nm_ else 0


if __name__ == "__main__":
    sys.exit(main())
