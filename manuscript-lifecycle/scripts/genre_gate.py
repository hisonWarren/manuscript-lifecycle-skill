#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
genre_gate.py — 体裁与节职能门：稿件读起来是不是这类期刊的研究论文，而不是实验说明或分析报告。

  python genre_gate.py 稿件.md|docx [--stage draft|submission] [--decisions benchmark_decisions.csv]
         [--placement placement_decisions.csv] [--memo genre_memo.md] [--drill reject_drill.md]
         [--concept paper_concept.md] [--survey survey_corpus.csv]
         [--neighbor-texts 近邻全文.txt|md …] [--report out.md] [--json out.json]

为什么要有它：一次投稿包的数字、引文、用语检查全部通过，作者仍判定“像实验说明文，不像研究论文”。
失败集中在几个固定位置：摘要末句讲局限、摘要堆未检出与校正细节；引言首段只有文献没有“为什么值得问”；
引言末段写成分析菜单；方法写成工序与记账；主文放了只服务于分析管理的样本总表；讨论首段复述过程而不回答
“说明了什么”；结论以“不能确立”收尾。这些不是措辞问题，是节职能问题。

脚本只认形式，所以分两层：
  一、文本信号（GG 规则）。每条都是候选，但不能静默忽略：要保留，就在 benchmark_decisions.csv 里写一行
      dimension=规则代码（如 GG7）、decision 含“保留/keep”、给出近邻与位置、绑定当前稿件指纹。没有近邻依据的“保留”不算数。
  二、必交产物（投稿阶段缺一即 MUST）：
      placement_decisions.csv  每项分析、表、图、补充条目放主文 / 补充 / 不写，各给读者问题与近邻或规则依据；
      genre_memo.md            一句话贡献、读者问题、说明了什么、近邻对照、白话复述；
      reject_drill.md          作者拒收预演：默认探针逐条判定，另加至少两条本稿特有的理由。
      思考可以短，但不能不做；它们与稿件指纹绑定，稿件改过要重新确认。

规则（submission 阶段的级别；draft 阶段标 * 的降为 SHOULD）：
  GG1  MUST  摘要末句是局限、否定或未验证（limit generalization、unverified、no measure established…）。
  GG2  MUST* 摘要里否定、未检出、不确定、探索性、可能混杂的句子 ≥3 句且 ≥30%：摘要在报告“没做成什么”。
  GG3  MUST* 摘要里有 ≥3 处校正、基线、最少试次、替代定义、逐试次对齐这类程序细节。
  GG4  MUST* 引言首段前两句没有读者能感到的对象或利害（人、行为、日常、临床、基本能力……），只有刺激与文献。
  GG4b SHOULD 引言首段有 ≥2 句“某研究做了某事”式罗列。
  GG5  MUST  引言末段有 ≥2 句分析清单（考察了哪些成分、时间窗、敏感性分析），而不是问题、预测或贡献。
  GG5b SHOULD 引言末段未识别预测：仅假设驱动研究需回查，其他体裁不据此补假设。
  IP1  SHOULD/INFO 引言结果预告的体裁提示；无明确目标刊/用户约束时不自动阻断或要求删除。
  NR1  SHOULD 叙事式承接（we first/then/next asked…）出现在摘要、引言或结果。
  GG6  MUST* 方法句里记账（日志、对齐、标记、候选试次）、防御式说明（不是累积量、不能确立成分身份）与
             敏感性罗列合计 ≥8 句且 ≥25%：工序细节应下沉补充，方法写到概念上可复现即可。
  GG7  MUST  主文有分析样本或试次总表（表头含 analysis/participants/trials/inclusion 中 ≥2 项）。
  GG8  MUST* 讨论首段有 ≥2 处程序细节，或否定与不确定句 ≥2 句且 ≥40%。
  GG8b SHOULD 讨论首段没有一句在解释“这说明了什么”。
  GG9  SHOULD 讨论小标题多数是限定或否定式（remain inseparable、does not identify、retain a motor interpretation）。
  GG10 MUST* 结论（没有结论节时取讨论最后一段）末句是局限、否定或“不能确立”。
  GG12 SHOULD 摘要、引言末段、讨论首段与结论里重复 ≥3 次、近邻全文里从未出现的自造标签（需 --neighbor-texts）。
  GG13 SHOULD 正文引用 ≥12 个不同的补充条目：逐项登记去向（PL6 在投稿阶段强制）。
  PL0–PL7、MM0–MM5、RD0–RD5：三件必交产物的格式、依据与绑定（见 references/27）。
  选材（references/29）：去向取 main / supp / reserve（备答，不进论文）/ omit（不属于本文），每行写 claim、function、
  evidence_quality、if_favorable（结果理想时的去向）、审稿人两问与 disclosure_basis（registered / claim / data / journal / ethics）。
  PL8  MUST  交代依据不认识、依据是 claim 却没写主张，或标了必须披露却没写依据（“做过”“分析失败”本身不是依据）。
  PL9  MUST  结果盲测试不过：与主张相关、结果理想时会放进论文的，实际放进了备答或不属于本文（降到补充为 PL9b SHOULD）。
  PL10 MUST  不属于本文的材料放进了论文，或 function 与 claim 自相矛盾。
  PL11 MUST* 旧版去向登记，缺选材字段。
  PL12 MUST  失败或无法解释的分析当了主文的核心证据。
  PL13 MUST* 没有交代依据的失败或无法解释的分析放进了论文。
  PL14 MUST* 缺审稿人两问。
  PL15 MUST* 去向登记里的主张编号在论文构想的主张清单里找不到。
  PC0  MUST* 没有 paper_concept.md；PC1 MUST* 构想有节没填，或主张清单没有编号的主张。
  PB1  SHOULD 主文分析或补充项超出同类论文的最大值（需 --survey）；超出 1.5 倍为 MUST*。benchmark_decisions.csv 写 PB1 保留行可降级。
  近邻校准：给了 --neighbor-texts 时，对每篇近邻跑同样的文本规则；近邻里至少两篇、且至少三分之一也触发的规则降一级
  （MUST→SHOULD，SHOULD→INFO），条目前写明“近邻 k/n 篇同样触发”。规则在一个领域校准，别的领域靠这一步按同类惯例调整；--no-calibrate 关闭。

退出码：0 没有 MUST；1 有 MUST；2 输入错误。报告与 JSON 必须是新路径。
它不判断贡献本身是否成立，也不替你写；它保证“这篇读起来像什么”在交付前被逐项想过、对照过、记下来过。
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402

CAVEAT = re.compile(
    r"\blimit(?:s|ed|ing)?\s+(?:the\s+)?(?:generali[sz]\w*|inferences?|interpretations?|conclusions?)\b|\bunverified\b"
    r"|\bnot\s+(?:been\s+)?(?:established|verified|determined|identified|detected|clearly)\b|\bno\s+(?:single\s+)?(?:measure|marker|evidence|clear|reliable)\b"
    r"|\b(?:did|does|do)\s+not\s+(?:survive|establish|identify|reach|permit|allow)\b|\bwithout\s+(?:identifying|establishing|evidence)\b"
    r"|\bremain(?:s|ed)?\s+(?:unclear|unknown|open|uncertain|unresolved|difficult)\b|\buncertain\b|\bspann(?:ing|ed)\s+zero\b"
    r"|\binterval\s+(?:included|including|spanning)\s+zero\b|\bmay\s+(?:include|reflect|contain|be\s+due)\b|\bcannot\b|\bcould\s+not\b"
    r"|\bpreclude[sd]?\b|\bis\s+insufficient\b|\bnot\s+(?:significant|reliabl\w*)\b"
    r"|局限|限制了?(?:推广|推论|解释)|未经(?:独立)?(?:验证|核实)|尚(?:不能|未能|无法)|无法(?:确定|确立|区分)|未(?:检出|发现|能确立)|不确定|没有任何(?:指标|证据)|可能包含|有待(?:进一步)?|仍不清楚", re.I)
PROC = re.compile(
    r"\bminimum[- ]trial\b|\btrial[- ]count\b|\beligibility\s+rule\b|\bcorrection\s+across\b|\bacross\s+windows\b"
    r"|\balternative\s+(?:measurement\s+)?(?:definitions?|windows?|references?)\b|\bmeasurement\s+definitions?\b"
    r"|\b(?:pre-?stimulus|local|pre-?response|response)\s+baseline\b|\bbaseline\s+(?:correction|interval|period)\b|\bpreceding\s+\d+\s*ms\b"
    r"|\baligned\s+trial\s+by\s+trial\b|\brecords\s+could\s+be\s+aligned\b|\bsign[- ]flip\b|\bGreenhouse\b|\bHolm\b|\bbootstrap\w*\b"
    r"|\bsensitivity\s+analys\w*\b|\bstricter\s+(?:eligibility|inclusion)\b|\binclusion\s+rule\b"
    r"|最少试次|跨时间窗校正|刺激前基线|按键前\s*\d+\s*ms|替代(?:测量)?定义|逐试次对齐|敏感性分析", re.I)
STAKES = re.compile(
    r"\b(?:people|persons?|humans?|observers?|animals?|individuals?|patients?|clinicians?|children|adults?|society|social"
    r"|daily|everyday|real[- ]world|life|lives|behaviou?r\w*|survival|actions?|acting|decisions?|choices?|health|fundamental|essential|central|critical|students?|teachers?|learners?|parents?|famil(?:y|ies)|nurses?|doctors?|physicians?|workers?|employees?|users?|consumers?|citizens?|residents?|communit(?:y|ies)|adolescents?|youth|infants?|women|men|schools?|classrooms?|hospitals?|clinics?|clinical|workplaces?)\b"
    r"|人们|个体|患者|儿童|日常|生活|现实|社会|行为|生存|决策|健康|基本能力|至关重要|核心问题|学生|教师|家长|家庭|护士|医生|用户|消费者|员工|居民|公众|青少年|老年人|婴儿|妇女|学校|课堂|医院|临床|工作场所", re.I)
LISTING = re.compile(
    r"^(?:In\s+(?:a|one|two|three|four|five|six|several|\d+)\s+(?:experiments?|studies|study)\b|(?:A|One|Another|A\s+recent)\s+(?:review|meta-analysis|study)\b"
    r"|[A-Z][A-Za-z\-]+(?:\s+(?:et\s+al\.|and\s+[A-Z][A-Za-z\-]+))?\s+\(\d{4}[a-z]?\)\s+(?:found|showed|reported|demonstrated|examined|investigated)"
    r"|In\s+that\s+study\b)|^(?:某|有)?(?:研究|一项研究|元分析)(?:发现|表明|考察)", re.I)
MENU_TOK = re.compile(
    r"\b(?:P1|N1|N170|N2|P2|P3|P300|MMN|CNV|CPP|LPP|LPC\w*|ERPs?|ROIs?|windows?|epochs?|baselines?|electrodes?|frontocentral|centroparietal"
    r"|occipitotemporal|parietal|posterior|onset-locked|response-locked|stimulus-locked|offset-locked|trial-wise|single-trial|sensitivity"
    r"|regressions?|ANOVAs?|mixed[- ]effects|bootstrap|permutations?|covariates?|preprocessing|exploratory|definitions?|eligibility|coverage|subgroups?|imputation|propensity|cross[- ]validation|ablations?|hyperparameters?|benchmarks?|interviews?|codebook)\b"
    r"|时间窗|基线|电极|脑区|逐试次|单试次|敏感性|回归|方差分析|探索性|亚组|插补|倾向得分|交叉验证|消融|访谈|编码方案", re.I)
MENU_VERB = re.compile(r"\b(?:examined|analy[sz]ed|measured|computed|extracted|assessed|varied|included|compared|tested|quantified|model(?:l)?ed|distinguished|conducted|performed|estimated|fitted|evaluated)\b|开展了?|估计了?|考察了?|分析了?|涉及|比较了?|变动了?", re.I)
FINDING = re.compile(r"\b(?:found|find|finding|reveal\w*|show\w*|demonstrat\w*|indicat\w*|suggest\w*|predict\w*|expect\w*|hypothes\w*|would|rule\s+out"
                     r"|support\w*|emerg\w*|occurr\w*|appear\w*|reflect\w*)\b|发现|表明|揭示|预测|假设", re.I)
PREVIEW = re.compile(r"\bwe\s+(?:show|find|found|report|reveal|demonstrate)\b|\bour\s+(?:results|findings)\b|\brevealed\b|\bshowing\s+that\b|我们发现|结果表明", re.I)
PREDICT = re.compile(r"\bpredict\w*|\bexpect\w*|\bhypothes\w*|\bwould\b|\bshould\b(?=[^.]*\bif\b)|\bif\b[^.]{0,120}\b(?:should|would)\b|预期|假设|如果", re.I)
INTERP = re.compile(r"\b(?:suggest\w*|indicat\w*|impl\w*|means?|point\w*\s+to|show\w*\s+that|reveal\w*|explain\w*|account\w*|therefore|thus|support\w*|argue\w*|reframe\w*|instead)\b"
                    r"|说明|提示|意味着|表明|因此", re.I)
BOOK = re.compile(r"\b(?:logs?|identifiers?|aligned|alignment|markers?|recovered|candidate\s+(?:trials|epochs)|capped|designed\s+count|repeated\s+epochs"
                  r"|recorded\s+(?:component|decisions)|existing\s+(?:visual\s+)?decisions|unavailable|planned\s+duration\s+cells|guard(?:ed)?\b|common\s+trials"
                  r"|retained\s+(?:condition\s+)?fits)\b|日志|标识符|对齐|标记|候选试次", re.I)
DEFENSE = re.compile(
    r"\b(?:is|are|was|were)\s+not\s+(?:an?\s+)?(?:integrated|accumulation|independent|causal|conservative|assumed|used\s+as|treated\s+as|interpreted|intended)\b"
    r"|\b(?:does|do)\s+not\s+(?:by\s+itself\s+)?(?:establish|replace|remove|imply|identify|distinguish)\b|\bcannot\s+(?:be|establish)\b"
    r"|\bdescriptive(?:ly)?\b|\bnot\s+a\s+bound\b|\bsusceptible\s+to\b|\brather\s+than\s+an?\s+independent\b|\bshould\s+not\s+be\s+(?:read|interpreted)\b"
    r"|\bnot\s+(?:new|causal)\s+(?:causal\s+)?mediation\b|不能确立|并非|不等于|不代表", re.I)
SENS = re.compile(r"\b(?:sensitivit(?:y|ies)|alternative\s+(?:windows?|references?|definitions?|trial[- ]selection)|(?:was|were)\s+also\s+(?:reported|retained|checked|measured)"
                  r"|additionally|further\s+analyses|also\s+reported)\b|敏感性|另外还|此外还报告", re.I)
HEAD_CAVEAT = re.compile(r"\b(?:not|no|cannot|remain\w*|retain\w*|partly|inseparable|limits?|uncertain\w*|need\s+not|without)\b|不能|并非|仍|局限|难以", re.I)
LIMIT_HEAD = re.compile(r"limitation|scope|strength|局限|不足", re.I)
SAMPLE_HEAD = {"analysis", "analyses", "participants", "trials", "inclusion", "exclusion", "sample", "samples", "n", "criterion", "requirement",
               "retained", "分析", "被试", "试次", "纳入", "排除", "样本"}
SAMPLE_CAP = re.compile(r"analysis\s+samples?|sample\s+sizes?|trial\s+counts?|inclusion\s+(?:criteria|requirements?)|分析样本|样本量|试次数", re.I)
SUPP_REF = re.compile(r"Supplementary\s+(Table|Figure|Section|Note)s?\s+(S?\d+[a-z]?)(?:\s*(?:[–-]|and|to)\s*(S?\d+))?|补充(?:材料)?(表|图|节)\s*(S?\d+)", re.I)
# 期刊实际使用的补充称呼（Table S1、Fig. S1、S1 Table、Appendix S1）：检查器认得的称呼不能反过来决定稿件怎么写
SUPP_EXTRA = [re.compile(r"\b(Table|Figure|Fig\.?|Appendix|Section)s?\s+(S\d+[a-z]?)(?:\s*(?:[–-]|and|to)\s*(S\d+))?"),
              re.compile(r"\b(S\d+)\s+(Table|Fig|File|Text|Appendix)\b")]
GENERIC_NOUNS = set("""information association condition choice measure measurement definition activity signal stage process level
effect pattern change relation relationship contribution component response voltage period window sample trial judgment
evidence outcome factor feature aspect dimension property mechanism account route route link difference profile estimate index
quantity value variable unit form type kind degree extent amount""".split())
GENRE_DIMS = ["abstract_ending", "intro_opening", "intro_closing", "methods_grain", "main_displays", "discussion_opening"]
# 拒收预演的探针用独立的 RJ 系列。第二十一轮前它们叫 G1–G11，与旧闸门 G0–G11、section_lint 的 G1/G2 同号异义；
# 旧项目的预演表照样认（probe_id 把旧编号换成新编号），报出的消息两个编号都写。
REVISION_PROBE = "RJ11"
DRILL_PROBES = {
    "RJ1": "摘要末句在讲局限，不是含义或贡献",
    "RJ2": "摘要在报未检出、校正与敏感性细节，主发现被淹没",
    "RJ3": "引言首段只有刺激与文献，读者不知道为什么值得问",
    "RJ4": "引言末段是分析菜单，没有问题、预测或贡献",
    "RJ5": "方法像流水账：记账、防御说明和敏感性罗列压过可复现的概念",
    "RJ6": "主文放了同类论文不会放的表或分析（样本总表、过程表）",
    "RJ7": "整篇像实验报告：讨论首段与结论不回答“说明了什么”",
    "RJ8": "补充材料堆了读者不需要的分析",
    "RJ9": "像项目档案：放了不服务主张、或会招来答不了的追问的分析",
    "RJ10": "与主张相关的不利结果被藏起或被下沉",
}
LEGACY_PROBES = {"G%d" % i: "RJ%d" % i for i in range(1, 12)}


def probe_id(cell):
    """预演表第一列的编号：旧编号 G1–G11 换成 RJ1–RJ11，其余原样。"""
    c = (cell or "").strip()
    return LEGACY_PROBES.get(c, c)


def probe_label(pid):
    """消息里写新编号，并注明旧编号，方便旧项目对照。"""
    return pid + ("（旧编号 G%s）" % pid[2:] if pid.startswith("RJ") else "")
WAIVE_WORDS = re.compile(r"保留|keep|retain|偏离|deviate", re.I)
RULE_BASIS = re.compile(r"披露义务|必须披露|reporting\s+obligation|作者须知|guideline|报告规范|用户要求|expectations|期刊要求|journal", re.I)
PL_BASE = ["item_id", "item", "kind", "reader_question", "placement", "neighbor", "locator", "reason", "manuscript_sha256"]
PL_NEW = ["claim", "function", "evidence_quality", "if_favorable", "reviewer_if_shown", "reviewer_if_absent", "disclosure_basis"]
PLACES = ("main", "supp", "reserve", "omit")
FUNCS = ("core", "support", "qualify", "preempt", "context", "out_of_scope")
QUALS = ("robust", "fragile", "failed", "uninterpretable", "descriptive")
BASES = ("registered", "claim", "data", "journal", "ethics")
YES_WORDS = ("yes", "y", "是", "true")
FIND_REPORT = re.compile(r"\bwe (?:found|find|show|showed|demonstrate[sd]?|observed|report(?:ed)?|reveal(?:ed)?)\b(?! (?:that )?(?:previous|prior|earlier))|"
                         r"\bour (?:results|findings|data) (?:show|showed|reveal|revealed|indicate[sd]?|suggest(?:ed)?)\b|\bresults (?:showed|revealed|indicated) that\b|我们发现|结果(?:显示|表明)", re.I)
NARR = re.compile(r"\bwe (?:first|then|next|subsequently|now) (?:asked|turned|wanted|set out|wondered)\b|^(?:next|then|first),? we (?:asked|turned|wanted|wondered)\b|\bwe (?:then|next) (?:tested|examined|looked)\b|"
                  r"我们(?:接着|然后|随后|首先)(?:追问|问|想知道)", re.I)
CAL_CODES = {"GG1", "GG2", "GG3", "GG4", "GG4b", "GG5", "GG5b", "GG6", "GG7", "GG8", "GG8b", "GG9", "GG10", "GG13", "IP1", "NR1", "IC1"}


def sha_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sents(paras):
    out = []
    for p in paras:
        out += M.sentences(p)
    return out


def read_csv_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def figure_coverage(text, rows, manuscript_sha256):
    """Check concrete figure records, not the scientific merit of a drawing choice.

    Accept plain/Markdown English or Chinese main-figure captions. Supplementary
    S-numbered figures and references inside prose are not main captions.
    Panel records count for their parent figure; panel completeness stays manual.
    """
    caption = re.compile(
        r"^\s*(?:#{1,6}\s*)?[*_]*(?:Figure|Fig\.?|图)\s*(\d+)"
        r"(?!\d)(?:[A-Za-z])?\s*(?:[.:：、。]|\*\*|__|$)", re.I | re.M)
    expected = {str(int(m.group(1))) for m in caption.finditer(text)}
    covered = set()

    def filled(value):
        value = (value or "").strip()
        return bool(value and value.lower() not in {"-", "—", "n/a", "na", "todo", "tbd"}
                    and not re.search(r"\[VERIFY\b|待核|待填", value, re.I))

    for row in rows:
        dim = row.get("dimension", "")
        if not dim.lower().startswith("figure:"):
            continue
        if row.get("manuscript_sha256", "").lower() != manuscript_sha256.lower():
            continue
        if not all(filled(row.get(k)) for k in ("neighbor", "locator", "observed", "decision", "reason")):
            continue
        # Named figures/panels, optionally separated by semicolons/commas.
        for token in re.split(r"[;,，；|]+", dim.split(":", 1)[1]):
            match = re.fullmatch(r"\s*(?:Figure|Fig\.?|图)?\s*(\d+)(?:[A-Za-z]|\s*\([A-Za-z]\))?\s*", token, re.I)
            if match:
                covered.add(str(int(match.group(1))))
    return expected, covered & expected


def supp_items(text):
    found = set()
    norm = {"fig": "Figure", "fig.": "Figure", "figure": "Figure", "table": "Table", "appendix": "Section", "section": "Section", "text": "Section", "file": "Section"}
    for m in SUPP_EXTRA[0].finditer(text):
        kind, a, b = norm.get(m.group(1).lower(), m.group(1).capitalize()), m.group(2), m.group(3)
        na = int(re.sub(r"\D", "", a))
        if b and 0 <= int(re.sub(r"\D", "", b)) - na <= 30:
            for k in range(na, int(re.sub(r"\D", "", b)) + 1):
                found.add("%s S%d" % (kind, k))
        else:
            found.add("%s S%d" % (kind, na))
    for m in SUPP_EXTRA[1].finditer(text):
        found.add("%s S%s" % (norm.get(m.group(2).lower(), m.group(2)), m.group(1)[1:]))
    for m in SUPP_REF.finditer(text):
        if m.group(1):
            kind, a, b = m.group(1).capitalize(), m.group(2), m.group(3)
        else:
            kind = {"表": "Table", "图": "Figure", "节": "Section"}[m.group(4)]
            a, b = m.group(5), None
        na = re.sub(r"\D", "", a)
        if b and re.sub(r"\D", "", b) and int(re.sub(r"\D", "", b)) - int(na) <= 30:
            for k in range(int(na), int(re.sub(r"\D", "", b)) + 1):
                found.add("%s S%d" % (kind, k))
        else:
            found.add("%s S%s" % (kind, a.lstrip("Ss")))
    return found


def main_tables(blocks):
    """返回 [(编号或'?', 表头单元格, 题注文字)]：稿件里出现的表格（主文文件里的表都算主文表）。"""
    out, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        if b["kind"] == "table" and b["sec"] != "references":
            head = [c.strip(" *").lower() for c in b["text"].strip().strip("|").split("|")]
            cap = " ".join(x["text"] for x in blocks[max(0, i - 3):i] if x["kind"] in ("caption", "para", "heading"))
            m = re.findall(r"Table\s*(\d+)|表\s*(\d+)", cap)
            num = (m[-1][0] or m[-1][1]) if m else "?"
            out.append((num, head, cap[-200:]))
            while i < len(blocks) and blocks[i]["kind"] == "table":
                i += 1
            continue
        i += 1
    return out


def parse_md_sections(path):
    secs, cur = {}, None
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            m = re.match(r"^#{2,3}\s*(\d+)", line)
            if m:
                cur = m.group(1)
                secs[cur] = []
                continue
            if cur is not None:
                secs[cur].append(line.rstrip("\n"))
    return secs


def filled(lines):
    body = [l for l in lines if l.strip() and not re.match(r"^\s*[（(].*[)）]\s*$", l.strip()) and "填写" not in l and not l.strip().startswith(">")]
    s = "".join(body)
    return sum(2 if "\u4e00" <= ch <= "\u9fff" else 1 for ch in s if not ch.isspace()) >= 16


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manuscript")
    ap.add_argument("--stage", default="draft", choices=["draft", "submission"])
    ap.add_argument("--decisions", default="")
    ap.add_argument("--placement", default="")
    ap.add_argument("--memo", default="")
    ap.add_argument("--drill", default="")
    ap.add_argument("--concept", default="")
    ap.add_argument("--survey", default="")
    ap.add_argument("--moves", default="", help="语步编码 JSON（move_check 格式）：关键段与近邻逐段对照（MV1）")
    ap.add_argument("--baseline", default="", help="领域包目录：文本质感的分布参照（与近邻全文合并）")
    ap.add_argument("--submitted", default="", help="上次投稿的原稿（返修时用）：改稿增量与融入（RV1、RV2、RJ11）")
    ap.add_argument("--terms", default="", help="本研究的主题词（逗号分隔或 @文件），词汇 keyness 不计")
    ap.add_argument("--texture-exemplars", nargs="*", default=None, help="只用于质感与词汇的近邻全文（默认同 --neighbor-texts）")
    ap.add_argument("--term-groups", default="", help="题目术语组，如 stimulus=biological motion|point-light;method=EEG|ERP（convention_profile）")
    ap.add_argument("--no-calibrate", action="store_true", help="不按近邻全文校准文本规则")
    ap.add_argument("--neighbor-texts", nargs="*", default=[])
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    for p in [a.manuscript] + [x for x in (a.decisions, a.placement, a.memo, a.drill, a.concept, a.survey, a.moves) if x] + a.neighbor_texts + (a.texture_exemplars or []):
        if not os.path.isfile(p):
            print("找不到输入：%s" % p, file=sys.stderr)
            return 2
    for p in (a.report, a.json):
        if p and os.path.exists(p):
            print("输出文件已存在，换一个新路径：%s" % p, file=sys.stderr)
            return 2
    text = M.load_text(a.manuscript)
    blocks = M.parse(text)
    msha = sha_file(a.manuscript)
    sub = a.stage == "submission"
    items, metrics, notrun = [], {}, []

    def add(level, code, sec, msg, ex=()):
        items.append({"level": level, "code": code, "sec": sec, "msg": msg, "examples": [e[:240] for e in ex][:6]})

    def lv(hard):
        return "MUST" if (hard or sub) else "SHOULD"

    paras = lambda keys: [b["text"] for b in blocks if b["sec"] in keys and b["kind"] == "para"]
    # ---------------- 摘要
    abs_s = sents(paras(("abstract",)))
    if not abs_s:
        notrun.append("没有识别到摘要：摘要的职能规则未检查")
    else:
        cav = [s for s in abs_s if CAVEAT.search(s)]
        proc = [m.group(0) for s in abs_s for m in PROC.finditer(s)]
        metrics.update({"abstract_sentences": len(abs_s), "abstract_caveat_sentences": len(cav), "abstract_procedural_terms": len(proc)})
        if CAVEAT.search(abs_s[-1]):
            add("MUST", "GG1", "abstract", "摘要末句在讲局限或没做成什么。同类高影响刊摘要的末句交代含义或贡献（Collectively, our findings show…）；"
                "局限放讨论，最多在摘要中段用一个短语限定。", [abs_s[-1]])
        if len(cav) >= 3 and len(cav) / len(abs_s) >= 0.30:
            add(lv(False), "GG2", "abstract", "摘要 %d/%d 句是否定、未检出、不确定或可能混杂：摘要在报告“没做成什么”，主发现被淹没。"
                "摘要只留承重发现（含出乎意料的发现）；空结果与敏感性下沉到结果节，必要时用一个从句限定。" % (len(cav), len(abs_s)), cav)
        if len(set(x.lower() for x in proc)) >= 3:
            add(lv(False), "GG3", "abstract", "摘要里有 %d 处程序细节（%s）。校正、基线、最少试次、替代定义属于方法与结果，摘要不报。"
                % (len(proc), "、".join(sorted(set(proc))[:6])))
    # ---------------- 引言
    intro = M.first_section_paras(blocks, "introduction")
    if not intro:
        notrun.append("没有识别到引言：引言首末段的职能规则未检查")
    else:
        first = M.sentences(intro[0])
        head2 = " ".join(M.strip_citations(s) for s in first[:2])
        metrics["intro_first_has_stakes"] = bool(STAKES.search(head2))
        if not STAKES.search(head2):
            add("SHOULD", "GG4", "introduction", "首段前两句未命中内置的现象/利害表达式。该词表不能覆盖各学科；请按目标读者判断问题是否已引清，"
                "可包括人、行为、临床、理论、成本、性能或其他学科后果，不据此强制套用日常情境开篇。", first[:2])
        listing = [s for s in first if LISTING.search(s.strip())]
        if len(listing) >= 2:
            add("SHOULD", "GG4b", "introduction", "引言首段有 %d 句“某研究做了某事”的罗列。把它们合成一个已知的论断，留下张力。" % len(listing), listing)
        last = M.sentences(intro[-1])
        menu = [s for s in last if MENU_VERB.search(s) and len(MENU_TOK.findall(s)) >= 2 and not FINDING.search(s)]
        metrics.update({"intro_last_sentences": len(last), "intro_last_menu_sentences": len(menu)})
        if len(menu) >= 2:
            add("MUST", "GG5", "introduction", "引言末段有 %d 句在列分析清单（成分、时间窗、敏感性设定）。引言末段写研究问题、可区分的预测或贡献；"
                "分析清单属于方法。" % len(menu), menu)
        if last and not PREDICT.search(intro[-1]):
            add("SHOULD", "GG5b", "introduction", "引言末段未识别到预测或假设。仅当本文确为假设驱动研究时，回查计划和预测是否清楚；"
                "探索性、质性、理论或新方法可用开放问题或贡献收束，不据此补造假设。", last[:1])
        # IP1 引言写出了本研究的结果：学科期刊少见（第八轮实测：类型匹配 0/5，53 篇已发表心理学论文的引言里 we found that ≤1 篇/包），
        # 综合高影响刊常见（2/2）。按目标刊所属的一类决定；近邻同样预告时由近邻校准自动降级
        tail = " ".join(intro[-2:])
        prev = [s for s in M.sentences(tail) if FIND_REPORT.search(s) and not re.search(r"\(\s*[A-Z][^()]{0,60}\d{4}|\b(?:previous|prior|earlier|other|these) (?:studies|work|research)\b|以往|既往", s)]
        if prev:
            ip_done = False
            if a.decisions:
                ip_done = any((r.get("dimension", "").lower() == "role:intro_preview" or re.match(r"move:intro\w*:fnd$", r.get("dimension", "").lower()))
                              and r.get("decision") and (r.get("manuscript_sha256", "").lower() == msha) for r in read_csv_rows(a.decisions))
            add("INFO" if ip_done else "SHOULD", "IP1", "introduction",
                "引言有本研究的结果预告（%d 句）。是否合适取决于目标刊、论文类型与作者目的；一组学科近邻的少见写法不是通用禁令。"
                "可在 benchmark_decisions 写 role:intro_preview 裁决；目标刊未定时不自动要求删除，明确约束由相应期刊/用户要求检查。" % len(prev), prev)
    # FG1 is advisory coverage, not a judgment of whether the drawing is good.
    if a.decisions:
        expected, covered = figure_coverage(text, read_csv_rows(a.decisions), msha)
        missing = sorted(expected - covered, key=int)
        metrics["figure_records"] = {"expected": sorted(expected, key=int), "covered": sorted(covered, key=int)}
        if missing:
            add("INFO", "FG1", "图", "主图缺少完整且绑定当前稿件的 figure: 裁决行：%s。每张图填写近邻、位置、观察到的画法、决定和理由；空行、陈旧指纹或另一幅图的记录不算覆盖。记录齐全不证明画法正确，面板与实际图件仍需人工核对（references/27“图的画法”）。"
                % ", ".join("Figure " + n for n in missing))
    # IC1 引言末段写成方法摘要：刺激参数与单位、逐项列出分析（“Finally, we tested whether…”）。同类论文多用一句话交代到任务层面，
    # 预测写成竞争性解释，分析留给方法与结果（第十四轮：9 篇对照中只有 1 篇写了参数，没有一篇逐项列分析）。只提示，近邻同样如此时由校准降级
    if intro:
        last_p = intro[-1]
        units = re.findall(r"\d[\d,.]*\s*(?:[–-]\s*\d[\d,.]*\s*)?(?:ms|s|Hz|µV|μV|°|cm|mm|%)(?![A-Za-z])|\d+\s+(?:trials|participants|blocks|electrodes)\b", last_p)
        listing = [s for s in M.sentences(last_p) if re.search(r"^\s*(?:Finally|Lastly|Next|Then|In addition|Additionally|Moreover|We then|We next|We also|We finally)\b[^.]{0,40}?\bwe\s+(?:tested|examined|analy[sz]ed|computed|fitted|used|compared|asked)\b|^\s*We\s+(?:then|next|finally)\s+(?:tested|examined|analy[sz]ed|computed|fitted|compared)\b", s, re.I)]
        if len(units) >= 2 or listing:
            add("INFO", "IC1", "introduction", "引言末段像方法摘要：%s%s。同类论文一般用一句话把设计交代到任务层面，预测写成两三种解释各预测什么，参数与分析步骤留给方法与结果（references/20 §1c“颗粒度”）。"
                % ("刺激参数 %d 处" % len(units) if len(units) >= 2 else "", ("；" if len(units) >= 2 and listing else "") + ("逐项列分析 %d 句" % len(listing) if listing else "")),
                (listing or units)[:2])
    # NR1 叙事式的承接（We first/then/next asked…）：已发表心理学论文的结果节少见（53 篇中 2 篇有 we then/next 起句），读起来像在讲研究经过
    narr = [s for b in blocks if b["kind"] == "para" and b["sec"] in ("results", "introduction", "abstract") for s in M.sentences(b["text"]) if NARR.search(s)]
    if narr:
        add("SHOULD", "NR1", "全文", "%d 句用叙事方式交代研究经过（we first/then/next asked…）。结果节直接报告检验与发现，引言用“本研究检验…/预期…”。" % len(narr), narr)
    # ---------------- 方法粒度
    meth = sents(paras(("methods",)))
    if meth:
        book = [s for s in meth if BOOK.search(s)]
        dfn = [s for s in meth if DEFENSE.search(s)]
        sns = [s for s in meth if SENS.search(s)]
        heavy = [s for s in meth if BOOK.search(s) or DEFENSE.search(s) or SENS.search(s)]
        share = len(heavy) / len(meth)
        metrics.update({"methods_sentences": len(meth), "methods_bookkeeping": len(book), "methods_defensive": len(dfn),
                        "methods_sensitivity": len(sns), "methods_heavy_share": round(share, 3)})
        if len(heavy) >= 8 and share >= 0.25:
            add(lv(False), "GG6", "methods", "方法 %d/%d 句（%.0f%%）是记账、防御式说明或敏感性罗列（记账 %d、防御 %d、敏感性 %d）。主文方法写到概念上可复现："
                "做了什么、为什么、按什么标准；记录对齐与筛选流水、变体清单移到补充方法，防御式解释移到讨论。在 placement_decisions.csv 逐项登记去向。"
                % (len(heavy), len(meth), 100 * share, len(book), len(dfn), len(sns)), (dfn + book)[:6])
    else:
        notrun.append("没有识别到方法节：方法粒度未检查")
    # ---------------- 主文表型
    tabs = main_tables(blocks)
    metrics["main_tables"] = len(tabs)
    for num, head, cap in tabs:
        hits = []
        for h in head:
            words = re.findall(r"[a-z\u4e00-\u9fff]+", h)
            if h in SAMPLE_HEAD or (words and words[0] in SAMPLE_HEAD and words[0] != "n"):
                hits.append(words[0] if words else h)
        if len(set(hits)) >= 2 or SAMPLE_CAP.search(cap):
            add("MUST", "GG7", "tables", "主文表 %s 是分析样本或试次总表（表头：%s）。这类表服务于分析管理，同类实证论文主文通常不放（以本稿近邻为准）；"
                "主文用一句话写清各分析的样本，完整计数放补充表。确属目标刊惯例时，在 benchmark_decisions.csv 写 GG7 行并给近邻位置。"
                % (num, " | ".join(head)[:120]), [cap])
    # ---------------- 讨论首段、小标题、结论
    disc_blocks = [b for b in blocks if b["sec"] == "discussion"]
    dparas = [b["text"] for b in disc_blocks if b["kind"] == "para" and not LIMIT_HEAD.search(b.get("sub") or "")]
    if dparas:
        ds = M.sentences(dparas[0])
        dproc = [s for s in ds if PROC.search(s)]
        dcav = [s for s in ds if CAVEAT.search(s)]
        metrics.update({"discussion_first_sentences": len(ds), "discussion_first_procedural": len(dproc), "discussion_first_caveat": len(dcav)})
        if len(dproc) >= 2 or (len(dcav) >= 2 and len(dcav) / max(1, len(ds)) >= 0.40):
            add(lv(False), "GG8", "discussion", "讨论首段 %d 句在复述程序（测量定义、校正、纳入规则），%d 句在讲不确定。讨论首段用读者的话回答研究问题，"
                "并说明它改变了什么理解；稳健性与边界放到后面的段落。" % (len(dproc), len(dcav)), dproc + dcav)
        if not any(INTERP.search(s) for s in ds):
            add("SHOULD", "GG8b", "discussion", "讨论首段没有一句在解释“这说明了什么”（suggest / indicate / therefore / point to…）。", ds[:1])
    heads = [b["text"] for b in disc_blocks if b["kind"] == "heading" and M.classify_heading(b["text"]) is None and not LIMIT_HEAD.search(b["text"])]
    cav_heads = [h for h in heads if HEAD_CAVEAT.search(h)]
    metrics.update({"discussion_subheadings": len(heads), "discussion_caveat_subheadings": len(cav_heads)})
    if len(heads) >= 2 and len(cav_heads) / len(heads) > 0.5:
        add("SHOULD", "GG9", "discussion", "讨论小标题 %d/%d 是限定或否定式：读者扫标题只看到“不能说什么”。小标题说出每段的论点（发现与它的含义），"
            "限定写进段内。" % (len(cav_heads), len(heads)), cav_heads)
    concl = paras(("conclusion",)) or dparas[-1:]
    if concl:
        cs = M.sentences(concl[-1])
        if cs and CAVEAT.search(cs[-1]):
            add(lv(False), "GG10", "conclusion", "结论末句以局限、否定或“不能确立”收尾。结论最后落在回答与含义上；不能确立的事已在讨论与局限里交代。", [cs[-1]])
    # ---------------- 自造标签（对照近邻）
    if a.neighbor_texts:
        corpus = ""
        for p in a.neighbor_texts:
            corpus += " " + M.normalize(open(p, encoding="utf-8", errors="replace").read()).lower()
        key = " ".join(paras(("abstract",)) + intro[-1:] + dparas[:1] + concl[-1:]).lower()
        words = re.findall(r"[a-z][a-z\-]{2,}", M.strip_citations(key))
        stop = set("the and for with that this from were was are which their these those into than then also been have has had its our both each".split())
        from collections import Counter
        bg = Counter("%s %s" % (x, y) for x, y in zip(words, words[1:]) if x not in stop and y not in stop)
        # 只算两个词都是泛化抽象名词的组合（condition information、choice association）：主题词（integration kernel）不是自造标签
        coined = [k for k, v in bg.items() if v >= 3 and k not in corpus and all(w.rstrip("s") in GENERIC_NOUNS for w in k.split())]
        metrics["coined_labels"] = coined
        if coined:
            add("SHOULD", "GG12", "全文", "这些标签在摘要、引言末段、讨论首段与结论里反复出现，近邻全文里一次也没有：%s。读者不认识自造标签；"
                "第一次出现时用具体对象说清，或换成领域通行说法。" % "、".join(coined[:8]))
    else:
        notrun.append("没给 --neighbor-texts：自造标签没有与近邻全文对照")
    supp = supp_items(text)
    metrics["supplementary_items_cited"] = len(supp)
    if len(supp) >= 12:
        add("SHOULD", "GG13", "全文", "正文引用了 %d 个不同的补充条目。补充材料不是“做过的都放”：每一项写明读者为什么需要它，否则不写（placement_decisions.csv）。" % len(supp),
            sorted(supp)[:8])

    # ---------------- 近邻裁决（保留须有近邻依据）
    waived = []
    # ---------------- 按近邻校准文本规则：近邻也这样写的，按同类惯例降一级（references/29 §10）
    if a.neighbor_texts and not a.no_calibrate:
        cal_sets = []
        for nbp in a.neighbor_texts:
            tmpd = tempfile.mkdtemp(prefix="gg_nb_")
            outp = os.path.join(tmpd, "nb.json")
            try:
                subprocess.run([sys.executable, os.path.abspath(__file__), nbp, "--stage", "draft", "--json", outp, "--no-calibrate"],
                               capture_output=True, text=True, encoding="utf-8", timeout=120)
                if os.path.exists(outp):
                    with open(outp, encoding="utf-8") as f:
                        nd = json.load(f)
                    cal_sets.append({x["code"] for x in nd.get("items", []) if x["level"] in ("MUST", "SHOULD") and x["code"] in CAL_CODES})
            except (subprocess.SubprocessError, OSError, ValueError):
                pass
            finally:
                shutil.rmtree(tmpd, ignore_errors=True)
        if cal_sets:
            n_nb, downgraded = len(cal_sets), {}
            for it in items:
                if it["code"] in CAL_CODES and it["level"] in ("MUST", "SHOULD"):
                    k = sum(it["code"] in s for s in cal_sets)
                    if k >= 2 and 3 * k >= n_nb:
                        it["level"] = "SHOULD" if it["level"] == "MUST" else "INFO"
                        it["msg"] = "（近邻 %d/%d 篇同样触发，按同类惯例降一级；目标刊不同就写进对标决策）" % (k, n_nb) + it["msg"]
                        downgraded[it["code"]] = "%d/%d" % (k, n_nb)
            metrics["neighbor_calibration"] = {"neighbors": n_nb, "downgraded": downgraded}
        else:
            notrun.append("近邻校准：近邻全文都没能运行体裁规则")
    if a.decisions:
        rows = read_csv_rows(a.decisions)
        ok = {r.get("dimension", "").upper() for r in rows if r.get("dimension", "").upper().startswith("GG") and WAIVE_WORDS.search(r.get("decision", ""))
              and r.get("neighbor") and r.get("locator") and (r.get("manuscript_sha256", "").lower() == msha)}
        for it in items:
            if it["code"].upper() in ok and it["level"] in ("MUST", "SHOULD"):
                it["level"], it["msg"] = "INFO", "（已按近邻裁决保留）" + it["msg"]
                waived.append(it["code"])
        dims = {r.get("dimension", "") for r in rows if r.get("neighbor") and r.get("locator")}
        miss = [d for d in GENRE_DIMS if d not in dims]
        if miss:
            add(lv(False), "BD4", "对标", "对标决策表缺这些节职能维度：%s。每一维写看了哪篇近邻的哪一处、采用 / 超越 / 不采用及理由（references/27）。" % "、".join(miss))
        nb = {r.get("neighbor") for r in rows if r.get("dimension") in GENRE_DIMS and r.get("neighbor")}
        if not miss and len(nb) < 2:
            add(lv(False), "BD5", "对标", "节职能维度只对照了 %d 篇近邻。至少两篇、且至少一篇是同类问题的旗舰刊全文（references/27 §3）。" % len(nb))
    elif sub:
        add("MUST", "BD4", "对标", "投稿阶段没有给 --decisions（benchmark_decisions.csv）：摘要末句、引言首末段、方法粒度、主文表型、讨论首段的写法依据都没有记录。")

    # ---------------- 必交产物：论文构想（references/29 §3）
    need = "MUST" if sub else "SHOULD"
    concept_claims = set()
    if a.concept:
        csecs = parse_md_sections(a.concept)
        cempty = [k for k in ("1", "2", "3", "5", "6", "7") if k not in csecs or not filled(csecs[k])]
        if cempty:
            add(need, "PC1", "构想", "paper_concept.md 第 %s 节没有填写。先写作者目的、候选构想、主张清单、审稿人预判与搁置清单，再决定用哪些材料（references/29 §3）。" % "、".join(cempty))
        concept_claims = {c.upper() for c in re.findall(r"\bC\d+\b", "\n".join(csecs.get("3", [])))}
        if "3" not in cempty and not concept_claims:
            add(need, "PC1", "构想", "主张清单（第 3 节）没有编号的主张（C1、C2…）：去向登记的 claim 列要指向它们。")
    else:
        add(need, "PC0", "构想", "没有 paper_concept.md：还没写下作者目的、候选构想与主张清单，就在决定材料放哪里。先调研、再构想、再选材（references/29 §3）。")
    # ---------------- 必交产物：去向登记（references/27 §4、29 §5）
    if a.placement:
        rows = read_csv_rows(a.placement)
        missing = [c for c in PL_BASE if rows and c not in rows[0]]
        if not rows or missing:
            add("MUST", "PL1", "去向", "placement_decisions.csv 为空或缺列：%s。" % ("、".join(missing) or "没有行"))
        else:
            legacy = [c for c in PL_NEW if c not in rows[0]]
            idf = lambda r: r.get("item_id") or (r.get("item") or "")[:30]
            low = lambda r, k: (r.get(k) or "").strip().lower()

            def basis(r):
                return [b.strip().lower() for b in re.split(r"[|;,，；/]", r.get("disclosure_basis") or "") if b.strip()]

            def claim_of(r):
                c = low(r, "claim")
                return "" if c in ("", "none", "无", "-", "–", "n/a") else c
            place = {id(r): low(r, "placement") for r in rows}
            inside = [r for r in rows if place[id(r)] in ("main", "supp")]
            bad_pl = [idf(r) for r in rows if place[id(r)] not in PLACES]
            noq = [idf(r) for r in inside if len(r.get("reader_question", "")) < 6]
            nobasis = [idf(r) for r in inside if not ((r.get("neighbor") and r.get("locator")) or RULE_BASIS.search(r.get("reason", "")) or any(b in BASES for b in basis(r)))]
            noreason = [idf(r) for r in rows if place[id(r)] in ("reserve", "omit") and len(r.get("reason", "")) < 4]
            unbound = [r for r in rows if (r.get("manuscript_sha256") or "").lower() != msha]
            if bad_pl:
                add("MUST", "PL1", "去向", "placement 只能是 main、supp、reserve（备答，不进论文）、omit（不属于本文）：%s。" % "、".join(bad_pl[:6]))
            if noq:
                add("MUST", "PL2", "去向", "%d 项放进主文或补充却没写读者问题（读者为什么需要它）：%s。写不出就是不该放。" % (len(noq), "、".join(noq[:6])))
            if nobasis:
                add("MUST", "PL3", "去向", "%d 项放进论文却没有近邻位置、规则依据或交代依据（披露义务、作者须知、报告规范、用户要求）：%s。" % (len(nobasis), "、".join(nobasis[:6])))
            if noreason:
                add(need, "PL3", "去向", "%d 项备答或不属于本文却没写理由：%s。写清它为什么不进本文、去哪里（备答、另作他文或项目档案）。" % (len(noreason), "、".join(noreason[:6])))
            if unbound:
                add(need, "PL5", "去向", "%d 行没有绑定当前稿件（指纹 %s…）：稿件改过后重新确认去向，再写入新指纹。" % (len(unbound), msha[:12]))
            if legacy:
                add(need, "PL11", "去向", "去向登记是旧版，缺选材字段：%s。每项要写服务哪条主张、证据质量、结果理想时会放哪里、审稿人两问与交代依据（references/29 §5）。" % "、".join(legacy))
                hidden = [idf(r) for r in rows if place[id(r)] in ("omit", "reserve") and low(r, "disclosure_required") in YES_WORDS]
                if hidden:
                    add("MUST", "PL4", "去向", "必须交代的项目被标为不写：%s。有依据的事只能决定放哪、写多少，不能不写（references/03）。" % "、".join(hidden[:6]))
            else:
                badval = []
                for r in rows:
                    for k, allowed in (("function", FUNCS), ("evidence_quality", QUALS), ("if_favorable", PLACES)):
                        if low(r, k) not in allowed:
                            badval.append("%s 的 %s=%s" % (idf(r), k, r.get(k) or "（空）"))
                if badval:
                    add("MUST", "PL1", "去向", "%d 处选材字段取值不认识：%s。function 取 %s；evidence_quality 取 %s；if_favorable 取 %s。" % (
                        len(badval), "；".join(badval[:6]), " / ".join(FUNCS), " / ".join(QUALS), " / ".join(PLACES)))
                bad_basis = [idf(r) for r in rows if any(b not in BASES for b in basis(r))]
                claim_basis = [idf(r) for r in rows if "claim" in basis(r) and not claim_of(r)]
                bare = [idf(r) for r in rows if low(r, "disclosure_required") in YES_WORDS and not basis(r)]
                if bad_basis or claim_basis or bare:
                    parts = (["不认识的依据：" + "、".join(bad_basis[:4])] if bad_basis else []) + \
                            (["依据是 claim 却没写主张：" + "、".join(claim_basis[:4])] if claim_basis else []) + \
                            (["标了必须披露却没写依据：" + "、".join(bare[:4])] if bare else [])
                    add("MUST", "PL8", "去向", "交代依据有问题：%s。必须交代只在五类依据之一成立：registered 预注册或公开计划；claim 本文主张依赖或被它限定；"
                        "data 影响已报告结果的数据问题；journal 期刊或规范要求；ethics 伦理与事实声明。“做过”“分析失败”本身不是依据（references/29 §2）。" % "；".join(parts))
                hidden = [idf(r) for r in rows if basis(r) and all(b in BASES for b in basis(r)) and place[id(r)] in ("reserve", "omit")]
                if hidden:
                    add("MUST", "PL4", "去向", "有交代依据的项目被放进备答或不属于本文：%s。有依据的事只能决定放哪、写多少，不能不写（references/03）。" % "、".join(hidden[:6]))
                sunk = [idf(r) for r in rows if claim_of(r) and low(r, "if_favorable") in ("main", "supp") and place[id(r)] in ("reserve", "omit")]
                if sunk:
                    add("MUST", "PL9", "去向", "结果盲测试不过：%s 与主张相关，结果理想时会放进论文，实际却不进论文。要么交代（至少放补充并在正文给入口），要么收窄主张并说明原因（references/29 §2）。" % "、".join(sunk[:6]))
                demoted = [idf(r) for r in rows if claim_of(r) and low(r, "if_favorable") == "main" and place[id(r)] == "supp"]
                if demoted:
                    add("SHOULD", "PL9b", "去向", "%s 结果理想时会进正文，实际放进补充：正文要说明这一结果并给补充入口，不能只在补充里出现。" % "、".join(demoted[:6]))
                offtopic = [idf(r) for r in inside if low(r, "function") == "out_of_scope"]
                clash = [idf(r) for r in rows if (not claim_of(r) and low(r, "function") in ("core", "support", "qualify")) or (claim_of(r) and low(r, "function") == "out_of_scope")]
                if offtopic or clash:
                    parts = (["不属于本文却放进了论文：" + "、".join(offtopic[:5])] if offtopic else []) + (["function 与 claim 矛盾：" + "、".join(clash[:5])] if clash else [])
                    add("MUST", "PL10", "去向", "%s。不属于本文问题的分析不放进论文；它服务主张就写主张编号，不服务就不是核心、佐证或限定（references/29 §5）。" % "；".join(parts))
                weakcore = [idf(r) for r in rows if low(r, "evidence_quality") in ("failed", "uninterpretable") and low(r, "function") == "core" and place[id(r)] == "main"]
                if weakcore:
                    add("MUST", "PL12", "去向", "失败或无法解释的分析当了主文的核心证据：%s。核心证据要稳健；做不到就换主张或换证据。" % "、".join(weakcore[:6]))
                weakin = [idf(r) for r in inside if low(r, "evidence_quality") in ("failed", "uninterpretable") and not [b for b in basis(r) if b in BASES]]
                if weakin:
                    add(need, "PL13", "去向", "%d 项失败或无法解释的分析没有交代依据却放进了论文：%s。不服务主张的失败分析只会招来“为什么放它”的追问；与主张相关的，写明依据（claim）并简短交代（references/29 §5）。" % (len(weakin), "、".join(weakin[:6])))
                nolens = [idf(r) for r in rows if (place[id(r)] in ("main", "supp") and len(r.get("reviewer_if_shown", "")) < 4)
                          or (place[id(r)] == "reserve" and len(r.get("reviewer_if_absent", "")) < 4)
                          or (place[id(r)] == "omit" and low(r, "function") != "out_of_scope" and len(r.get("reviewer_if_absent", "")) < 4)]
                if nolens:
                    add(need, "PL14", "去向", "%d 项缺审稿人视角：%s。放进论文的写“放了审稿人会问什么”；备答与搁置的写“不放审稿人会不会问、怎么答”。" % (len(nolens), "、".join(nolens[:6])))
                if a.concept:
                    used = set()
                    for r in rows:
                        used |= {c.upper() for c in re.findall(r"\bC\d+\b", r.get("claim", ""), re.I)}
                    unknown = sorted(c for c in used if c not in concept_claims)
                    if unknown:
                        add(need, "PL15", "去向", "去向登记用到的主张 %s 在论文构想的主张清单里找不到。" % "、".join(unknown[:6]))
            blob = " ".join(" ".join(r.values()) for r in rows)
            unreg = sorted(x for x in supp if not re.search(r"\b%s\s*S?%s\b" % (x.split()[0], re.escape(x.split()[1].lstrip("S"))), blob, re.I)
                           and not re.search(r"\bS%s\b" % re.escape(x.split()[1].lstrip("S")), blob))
            if unreg:
                add(need, "PL6", "去向", "正文引用了 %d 个补充条目却没有去向登记：%s。每个补充条目都要回答“读者为什么需要它”。" % (len(unreg), "、".join(unreg[:8])))
            for num, head, cap in tabs:
                if num != "?" and not re.search(r"\bTable\s*%s\b|表\s*%s(?!\d)" % (num, num), blob):
                    add(need, "PL7", "去向", "主文表 %s 没有去向登记：主文每张表都要写读者问题与近邻依据。" % num)
            metrics["placement_rows"] = {k: sum(place[id(r)] == k for r in rows) for k in PLACES}
            metrics["placement_schema"] = "legacy" if legacy else "r3"
            # ---------------- 材料预算（PB1）：与同类论文的范围对照
            if a.survey:
                try:
                    import survey_check as SV
                    nm = SV.norms(SV.read_rows(a.survey))
                except Exception as e:  # noqa: BLE001
                    nm = {}
                    notrun.append("材料预算：读不了调研表（%s）" % e)
                n_main = sum(1 for r in rows if place[id(r)] == "main" and low(r, "kind") == "analysis")
                n_supp = sum(1 for r in rows if place[id(r)] == "supp")
                metrics["budget"] = {"main_analyses": n_main, "supp_items": n_supp, "norms": nm}
                kept = False
                if a.decisions:
                    for d in read_csv_rows(a.decisions):
                        if (d.get("dimension", "").strip().upper() == "PB1" and WAIVE_WORDS.search(d.get("decision", "")) and d.get("neighbor")
                                and d.get("locator") and (d.get("manuscript_sha256") or "").lower() == msha):
                            kept = True
                if nm and not nm.get("n_papers"):
                    notrun.append("材料预算：调研表里没有类型匹配的全文编码论文，算不出同类范围")
                for label, n, key in (("主文分析", n_main, "n_main_analyses"), ("补充项", n_supp, "n_supp_items")):
                    mx = (nm.get(key) or {}).get("max")
                    if mx is None or n <= mx:
                        continue
                    far = n > 1.5 * max(mx, 1)
                    lvl = "INFO" if kept else (need if far else "SHOULD")
                    add(lvl, "PB1", "去向", ("（已按近邻裁决保留）" if kept else "") + "%s %d 项，超出同类论文的最大值 %s。每多一项，审稿人多一个可问的点；逐项看它服务哪条主张，不服务的移到备答或不属于本文（references/29 §5）。" % (label, n, mx))
                    if kept:
                        waived.append("PB1")
    else:
        add(need, "PL0", "去向", "没有 placement_decisions.csv：每项分析、表、图与补充条目放主文、补充、备答还是不属于本文，没有逐项想过、对照过（模板在 assets/templates/）。")
    # ---------------- 近邻可测的写法分布（CN1 惯例、MV1 关键段语步、TX1 文本质感、TX2/LX1 供看）：统一由 deviation_register 收集，
    #                  每个 adjudicate 类偏离都要在 benchmark_decisions.csv 有绑定当前稿件的裁决行（references/29 §4b–4c）
    if a.neighbor_texts or a.moves or a.baseline or a.submitted:
        try:
            import deviation_register as DR
            dev_items, dnotes, meta = DR.collect(a.manuscript, None, a.neighbor_texts, a.survey or None, a.term_groups, a.moves or None,
                                             a.baseline, a.terms, a.texture_exemplars, a.submitted)
            dec = DR.decided(read_csv_rows(a.decisions) if a.decisions else [], msha)
            codes = {"convention": "CN1", "move": "MV1", "texture": "TX1", "lexis": "LX1", "phrasing": "PH1", "revision": "RV1"}
            metrics["conventions"] = {"deviations": [x["dim"].split(":", 1)[1] for x in dev_items if x["dim"].startswith("convention:")]}
            metrics["deviation_meta"] = meta
            metrics["deviations"] = {"adjudicate": sum(1 for x in dev_items if x["class"] == "adjudicate"),
                                     "pending": sum(1 for x in dev_items if x["class"] == "adjudicate" and not DR.covered(x["dim"], dec)),
                                     "review": sum(1 for x in dev_items if x["class"] == "review")}
            for x in dev_items:
                cat = x["dim"].split(":", 1)[0]
                if x["class"] == "adjudicate" and not DR.covered(x["dim"], dec):
                    add(need, codes.get(cat, "CN1"), {"convention": "惯例", "move": "语步", "texture": "质感", "phrasing": "写法", "revision": "融入"}.get(cat, "惯例"),
                        ("改稿增量未裁决：%s。写 dimension=%s 的行：对照了哪些近邻、压缩、改写还是保留，理由（references/07 §10）。" if cat == "revision" else
                         "近邻分布之外，未裁决：%s。在 benchmark_decisions.csv 写 dimension=%s 的行，采用多数做法或保留并写理由（references/29 §4c）。")
                        % (x["msg"], x["dim"]))
                elif x["class"] == "review" and not DR.covered(x["dim"], dec):
                    add("INFO", {"texture": "TX2", "phrasing": "PH2", "move": "MV2", "revision": "RV3"}.get(cat, "LX1"), {"texture": "质感", "phrasing": "写法", "move": "语步", "revision": "融入"}.get(cat, "词汇"),
                        "供看：%s（%s）" % (x["msg"], x["dim"]))
            rv_reasons = {}
            for k_, r_ in dec.items():
                if k_.startswith("revision:"):
                    rv_reasons.setdefault(r_.get("reason", "").strip(), []).append(k_)
            for why_, ks_ in rv_reasons.items():
                if len(ks_) >= 3:
                    add("MUST", "RV2", "融入", "%d 节的改稿增量用同一句理由裁决：%s。每节的新增内容、近邻做法和去向不同，逐节写。" % (len(ks_), why_[:60]))
            for n_ in dnotes:
                notrun.append(n_)
            if a.neighbor_texts and not a.moves:
                add("SHOULD", "MV0", "语步", "给了近邻全文却没有关键段对照：引言段落职能、引言末段、讨论首段与结论没有与近邻逐段比较。"
                    "可以用 move_check 编码（--moves），也可以逐段并排阅读后在 benchmark_decisions 写 keypara:<段> 行（references/20 §1b）。")
        except Exception as e:  # noqa: BLE001
            notrun.append("偏离登记没能运行：%s" % e)
    # ---------------- 必交产物：体裁备忘
    if a.memo:
        secs = parse_md_sections(a.memo)
        body = open(a.memo, encoding="utf-8-sig").read()
        empty = [k for k in ("1", "2", "3", "4", "5", "7") if k not in secs or not filled(secs[k])]
        if empty:
            add("MUST", "MM2", "体裁备忘", "genre_memo.md 第 %s 节没有填写（只有模板提示）。写不出一句话贡献或“说明了什么”，先回去改主线，不要先润色。" % "、".join(empty))
        n_nb = len(re.findall(r"10\.\d{4,9}/\S+|et al\.|等人", "\n".join(secs.get("5", []))))
        if "5" in secs and n_nb < 2:
            add("MUST", "MM3", "体裁备忘", "备忘第 5 节（近邻对照）不到两篇近邻：写每篇怎样开篇、怎样收束摘要与讨论首段，本稿采用、超越还是偏离。")
        if "✗" in "\n".join(secs.get("7", [])):
            add(need, "MM5", "体裁备忘", "白话复述测试里还有复述不出的摘要句（✗）：这些句子仍在摘要里。")
        if msha not in body.lower():
            add(need, "MM4", "体裁备忘", "genre_memo.md 没有写当前稿件指纹（manuscript_sha256: %s…）。" % msha[:12])
    else:
        add(need, "MM0", "体裁备忘", "没有 genre_memo.md：没有写下这篇论文的一句话贡献、读者问题和“说明了什么”，也没有与近邻逐节对照。")
    # ---------------- 必交产物：拒收预演
    if a.drill:
        rows = []
        for line in open(a.drill, encoding="utf-8-sig"):
            if line.strip().startswith("|") and not re.match(r"^\s*\|\s*[-:]", line):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 5 and cells[0] not in ("#", "ID", "编号"):
                    rows.append(cells)
        ids = {probe_id(r[0]) for r in rows}
        miss = [k for k in DRILL_PROBES if k not in ids]
        if a.submitted and REVISION_PROBE not in ids:
            miss.append(REVISION_PROBE)   # 返修与修订多一条：读者读得出审稿过程吗
        own = [r for r in rows if probe_id(r[0]) not in DRILL_PROBES and probe_id(r[0]) != REVISION_PROBE]
        if miss:
            add("MUST", "RD1", "拒收预演", "默认探针没有逐条判定：%s。每条写稿中位置、状态（已消除 / 仍在 / 不适用）与证据。" % "、".join(probe_label(k) for k in miss))
        if len(own) < 2:
            add("MUST", "RD2", "拒收预演", "本稿特有的拒收理由不到两条：只填默认探针等于没有预演。")
        thin = [r[0] for r in rows if not (r[2] and r[3] in ("已消除", "仍在", "不适用") and r[4])]
        if thin:
            add("MUST", "RD3", "拒收预演", "这些行缺位置、状态或证据：%s。" % "、".join(thin[:8]))
        still = [r[0] + " " + r[1][:40] for r in rows if r[3] == "仍在"]
        if still:
            add("SHOULD", "RD4", "拒收预演", "仍在的拒收理由 %d 条，必须写进作者说明并说明为什么本轮不改：%s。" % (len(still), "；".join(still[:5])))
        if msha not in open(a.drill, encoding="utf-8-sig").read().lower():
            add(need, "RD5", "拒收预演", "reject_drill.md 没有写当前稿件指纹：预演针对的是哪一版说不清。")
    else:
        add(need, "RD0", "拒收预演", "没有 reject_drill.md：交付前没有假设作者拒收、逐条去稿件里找证据。")

    n_must = sum(i["level"] == "MUST" for i in items)
    res = {"schema_version": 1, "manuscript": os.path.basename(a.manuscript), "manuscript_sha256": msha, "stage": a.stage,
           "must": n_must, "should": sum(i["level"] == "SHOULD" for i in items), "items": items, "metrics": metrics,
           "waived": waived, "notrun": notrun, "supplementary_items": sorted(supp)}
    L = ["# 体裁与节职能（genre_gate）：%s" % os.path.basename(a.manuscript), "",
         "阶段 %s；稿件指纹 %s…；MUST %d、SHOULD %d。" % (a.stage, msha[:12], n_must, res["should"]), ""]
    for lvl in ("MUST", "SHOULD", "INFO"):
        sel = [i for i in items if i["level"] == lvl]
        if sel:
            L += ["## " + lvl, ""]
            for i in sel:
                L.append("- **%s %s**（%s）%s" % (lvl, i["code"], i["sec"], i["msg"]))
                L += ["  - " + e for e in i["examples"]]
            L.append("")
    L += ["## 指标", ""] + ["- %s：%s" % (k, v) for k, v in metrics.items()] + [""]
    if notrun:
        L += ["## 没能检查（不算通过）", ""] + ["- " + x for x in notrun] + [""]
    L += ["通过只说明这些形式信号没出现。论文有没有贡献、讨论是否讲清“说明了什么”，要靠 genre_memo、近邻对照与 reviewer_genre。", ""]
    if a.report:
        with M.wfile(a.report) as f:
            f.write("\n".join(L))
    if a.json:
        with M.wfile(a.json) as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    print("体裁门：MUST %d、SHOULD %d%s" % (n_must, res["should"], ("；报告 " + a.report) if a.report else ""))
    if not a.report:
        print("\n".join(L))
    return 1 if n_must else 0


if __name__ == "__main__":
    sys.exit(main())
