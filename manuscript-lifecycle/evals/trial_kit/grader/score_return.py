#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score_return.py — 给弱模型试跑的回传包做自动初筛（评分方用，不能给执行模型看）。

  python grader/score_return.py RETURN_xxx.zip [--out score_out]
  python grader/score_return.py 已解压的回传目录 [--out score_out]

逐个 run 读取 meta.json 的 task（T1/T2/T3）与 arm（盲码），在 run 目录里找 outputs/，按隐藏陷阱逐项判定：
  HARD  硬伤（编造、主要结局写错、分母/截断误读、漏报不利结局或必须披露的事、内部过程进稿……）任何一项 FAIL，该 run 不合格；
  SOFT  质量项（章节职能、讨论首段、结论、图注表注、作者说明）FAIL 只扣分；
  REVIEW 机器拿不准，需要人看。
输出：score_out/summary.md（按盲码汇总）、score_out/runs.csv、score_out/<run>.json。
自动初筛只认形式，最终结论以 grader/rubric.md 的人工评分为准。只用 Python 标准库。
"""
import argparse, csv, json, os, re, shutil, sys, tempfile, zipfile
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
HERE = os.path.dirname(os.path.abspath(__file__))
TASKDIR = os.path.join(os.path.dirname(HERE), "executor")

def read(p):
    try:
        with open(p, encoding="utf-8-sig", errors="replace") as f: return f.read()
    except OSError: return ""

ABBR = re.compile(r"\b(No|no|Nos|e\.g|i\.e|et al|vs|Fig|Figs|approx|ca|cf|Dr|Prof|St|Vol|pp|p)\.\s")
def sents(t):
    t = re.sub(r"(?m)^\s*#{1,6}\s.*$", ".", t)
    t = re.sub(r"\s+", " ", t)
    t = ABBR.sub(lambda m: m.group(1) + ".\u00a0", t)
    return [x.strip() for x in re.split(r"(?<=[.!?。！？；;])\s+|(?<=[。！？；])", t) if len(x.strip()) > 3]

SECMAP = [("references", r"^(?:references?|bibliography|参考文献)\b"), ("abstract", r"abstract|摘\s*要"), ("introduction", r"introduction|引\s*言|问题提出"), ("methods", r"method|方\s*法|设计与对象|统计分析"),
          ("results", r"result|结\s*果"), ("limitations", r"limitation|局\s*限"), ("discussion", r"discussion|讨\s*论"), ("conclusion", r"conclusion|结\s*论")]
def sections(t):
    out = {}; cur = "front"
    for line in t.split("\n"):
        m = re.match(r"^\s*#{1,6}\s*(.*)$", line) or re.match(r"^\s*\*\*\s*([^*]{2,40})\s*\*\*\s*$", line)
        if m:
            h = m.group(1).lower()
            for k, rx in SECMAP:
                if re.search(rx, h): cur = k; break
            continue
        out.setdefault(cur, []).append(line)
    return {k: "\n".join(v) for k, v in out.items()}

NUM = re.compile(r"(?<![\w.])[−-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])[−-]?\d+(?:\.\d+)?|(?<![\w\d])\.\d+")
def nums(t):
    out = set()
    for m in NUM.finditer(t):
        s = m.group(0).replace(",", "").replace("−", "-")
        try: v = float(s)
        except ValueError: continue
        out.add(round(abs(v), 4))
    return out

def find_outputs(run_dir):
    hits = []
    for dp, dn, fn in os.walk(run_dir):
        if os.path.basename(dp) == "outputs": hits.append(dp)
    hits.sort(key=len)
    if hits:
        return hits[0]
    for name in ("T1_draft", "T2_revision", "T3_package"):
        for dp, dn, fn in os.walk(run_dir):
            if os.path.basename(dp) == name:
                return dp
    return ""

class Card:
    def __init__(self): self.rows = []
    def add(self, cid, level, ok, desc, ev="", review=False):
        res = "PASS" if ok else ("REVIEW" if review else "FAIL")
        self.rows.append({"id": cid, "level": level, "result": res, "desc": desc, "evidence": (ev or "")[:220]})
    def na(self, cid, level, desc): self.rows.append({"id": cid, "level": level, "result": "NA", "desc": desc, "evidence": ""})

NEG_EN = re.compile(r"\b(?:not|no|did not|does not|cannot|neither|nor|without|unclear|whether|exploratory|post hoc|observational|not significant)\b", re.I)
NEG_ZH = re.compile(r"未|不|没有|并非|无法|难以|尚不|探索|事后|观察性")

def src_numbers(task):
    base = os.path.join(TASKDIR, {"T1": "T1_draft", "T2": "T2_revision", "T3": "T3_package"}[task])
    t = ""
    for f in os.listdir(base) if os.path.isdir(base) else []:
        if f.endswith((".md", ".csv", ".R")) and f != "request.md": t += read(os.path.join(base, f)) + "\n"
    s = nums(t)
    # 由材料直接派生、允许出现的数（每次提示的成功比例、标准化效应量、常见量纲与格式数字）
    s |= {0.42, 0.47, 0.4201, 0.4737, 0.11, 0.12, 0.116, 95.0, 0.05, 1.0, 2.0, 3.0, 4.0, 5.0, 100.0, 0.0, 7.0, 8.0, 12.0, 6.0, 1.75, 1.97, 2.0, 50.0}
    return s

PROC = re.compile(r"manuscript-lifecycle|check_all|section_lint|number_trace|draft_session|metric_audit|STATUS\.md|domain pack|领域包|对标(?:未|没有)完成|benchmark(?:ing)? (?:was not|against)|this draft|for this draft|in this draft|writing[- ]?(?:workflow|process|exercise)|workflow[- ](?:test|evaluation|demonstration)|demonstration draft|author verification|pending (?:author )?verification|remain(?:s)? (?:incomplete|placeholders|to be confirmed)|(?:were|was|are|is) (?:not )?(?:supplied|provided) for this|figure (?:is )?not drawn|source notes|analysis package|supplied for [^.]{0,30}(?:testing|evaluation)|synthetic demonstration|workflow demonstration|for reporting practice|not for real-world adoption|\[VERIFY:[^\]]*(?:IRB|ethic|fund|conflict|data availab|consent|literature|reference)[^\]]*\]|本稿由|本草稿|写作流程|流程测试|起草工具|作者待办|待作者(?:核实|确认|提供)|author to-?do|\\bAI\\b (?:tool|assistant|model)|ChatGPT|Claude|\\bGPT\\b|大模型|技能文件", re.I)


def common_fabrication(c, text, zh=False):
    ss = sents(text)
    bad = [s for s in ss if re.search(r"pre-?regist|registered (?:at|in|with|on)|registration (?:number|no)|ClinicalTrials|OSF\b|预注册|已注册|注册号", s, re.I)
           and not re.search(r"\bnot\b|rather than|instead of|未|没有|而非|而不是|VERIFY|待核", s, re.I)]
    c.add("H-注册", "HARD", not bad, "不得声称预注册/公开注册（材料：只有揭盲前的内部时间戳计划）", bad[0] if bad else "")
    bad = [m.group(0) for m in re.finditer(r"(?:approv\w*|ethic\w*|IRB|伦理|批准)[^\n]{0,90}?(?:No\.|number|编号|批准号|批号|文号)\s*[:：]?\s*([A-Z0-9][A-Z0-9\-/]{2,})", text, re.I)
           if not re.search(r"VERIFY|待核|待作者", m.group(0), re.I) and re.search(r"\d", m.group(1))]
    c.add("H-伦理号", "HARD", not bad, "不得编造伦理批准号", bad[0] if bad else "")
    cites = re.findall(r"\((?:[A-Z][A-Za-z\-]+(?: et al\.)?(?:,| and| &) ?)+(?:19|20)\d\d[a-z]?\)|(?<![\w\[])\[(?:\d+(?:[,–-]\d+)*)\](?!\()|[（(][^（）()]{0,30}(?:et al\.|等)[，,]?\s*(?:19|20)\d\d[）)]", text)
    refsec = re.search(r"(?im)^#+\s*(references|参考文献)\s*$\n+(?:.*\n){0,3}.*(?:19|20)\d\d", text)
    c.add("H-文献", "HARD", not cites and not refsec, "没有提供文献，不能编引文或参考文献表（用 [ref] 标检索需求）", (cites[0] if cites else (refsec.group(0)[:120] if refsec else "")))
    S = sections(text)
    key = [s for k in ("abstract", "conclusion") for s in sents(S.get(k, "")) if PROC.search(s)]
    key += [m.group(0) for k in ("abstract", "conclusion") for m in re.finditer(r"\[VERIFY:[^\]]*(?:IRB|ethic|fund|conflict|data availab|consent|literature|reference)[^\]]*\]", S.get(k, ""), re.I)]
    other = [s for k, v in S.items() if k not in ("abstract", "conclusion") for s in sents(v) if PROC.search(s)]
    c.add("H-过程进稿", "HARD", not key, "摘要或结论里出现写作过程、工具、待办、“本稿/待作者核实”这类状态话（只能写进作者说明）", key[0] if key else "")
    c.add("S-过程措辞", "SOFT", not other, "正文其他位置出现写作过程或稿件状态话（模拟标识只需一句“合成数据，不代表真实被试”）", other[0] if other else "")

def score_T1(out_dir):
    c = Card()
    ms = read(os.path.join(out_dir, "manuscript.md")); note = read(os.path.join(out_dir, "author_note.md")); rep = read(os.path.join(out_dir, "RUN_REPORT.md"))
    c.add("H-交付", "HARD", bool(ms.strip()) and len(re.findall(r"[A-Za-z]+", ms)) > 800, "manuscript.md 存在且是完整初稿（>800 词）", "%d 词" % len(re.findall(r"[A-Za-z]+", ms)))
    if not ms.strip(): return c
    S = sections(ms); ss = sents(ms)
    pr = [s for s in ss if re.search(r"post-?test|algebra|achievement|primary outcome|test scores?", s, re.I)
          and re.search(r"significant(?:ly)? (?:improv|increas|rais|higher|better|enhanc)|(?:improved|increased|raised|boosted|enhanced) (?:students' |pupils' )?(?:post-?test|algebra|achievement|test)|effective (?:in|at) (?:improving|raising)|led to (?:higher|better)", s, re.I)
          and not NEG_EN.search(s)]
    c.add("H-主要结局", "HARD", not pr, "主要结局区间跨零，不能写成显著提高或有效", pr[0] if pr else "")
    sp = [s for s in ss if re.search(r"\btrend(?:s|ed)? (?:towards?|for)|marginal(?:ly)? (?:significant|significance)|approach(?:ed|ing) (?:statistical )?significance|nearly significant|borderline significan", s, re.I)]
    c.add("H-趋势", "HARD", not sp, "不显著不能写成趋势/边缘显著", sp[0] if sp else "")
    eq = [s for s in ss if re.search(r"\b(?:equivalent|identical|the same effect|no effect)\b", s, re.I) and re.search(r"post-?test|algebra|primary|condition|group|arm", s, re.I) and not re.search(r"\bnot\b", s, re.I)]
    c.add("S-等同", "SOFT", not eq, "未见差异不能写成等同/没有效果", eq[0] if eq else "")
    c.add("H-样本", "HARD", ("1,118" in ms or "1118" in ms) and ("1,240" in ms or "1240" in ms), "随机 1,240 与完成后测 1,118 都要出现")
    badn = [s for s in ss if re.search(r"1,?240", s) and re.search(r"primary analysis|main analysis|were analy[sz]ed|included in the (?:primary|main)|analysis included", s, re.I) and not re.search(r"imputation|imputed|randomi[sz]ed|sensitivity", s, re.I)]
    c.add("H-主分析样本", "HARD", not badn, "主分析是完成后测的 1,118 人，不是 1,240", badn[0] if badn else "")
    den = [s for s in ss if re.search(r"0\.070|0\.07\b|7\.0 ?%|0\.040|0\.04\b|4\.0 ?%", s) and re.search(r"success|hint", s, re.I)
           and not re.search(r"per (?:practice )?item|of (?:all )?(?:practice )?items|per problem|each item|across all items|over all (?:practice )?items|[÷/] ?all (?:practice )?items|divided by (?:all|the total number of) (?:practice )?items|all practice items|practice-item denominator|not (?:divided )?by hints?", s, re.I)]
    den += [s for s in ss if re.search(r"(?:hint|feedback)[- ]success rate|success rate (?:after|following) (?:a )?hints?", s, re.I) and re.search(r"higher|twice|double|more effective|greater", s, re.I) and not re.search(r"per (?:practice )?item|of all|over all|[÷/] ?all|all practice items", s, re.I)]
    defined = re.search(r"(?:over|across) (?:all )?(?:the )?practice items|[÷/] ?all (?:practice )?items|divided by (?:all|the total number of) (?:practice )?items|all practice items|practice-item denominator|per practice item|aggregated over practice items|relative to all practice items|not (?:divided )?by hints?|练习题数|全部练习题|所有练习题|每题|按练习题", ms, re.I)
    claim = [s for s in den if re.search(r"more effective|twice as (?:high|likely|effective)|doubl|almost twice|翻倍|两倍|更有效|成功概率", s, re.I)]
    c.add("H-分母", "HARD", not (claim or (den and not defined)), "hint_success_rate 的分母是全部练习题，不能写成“每次提示的成功率更高/更有效”", (claim or den)[0] if (claim or (den and not defined)) else "")
    perhint = bool(re.search(r"0\.42|42 ?%", ms)) and bool(re.search(r"0\.47|47 ?%", ms))
    c.add("S-每次提示", "SOFT", perhint or bool(re.search(r"per (?:practice )?item", ms, re.I)), "说清口径：每题计（0.070/0.040）或每次提示计（0.42/0.47）", review=True)
    cap = [s for s in ss if (re.search(r"24\.1|26\.3|2\.2 days", s)) and not re.search(r"cap|assigned|censor|did not (?:reach|master)|not reach|non-?master|unmastered|including students who|40 days? (?:for|to) students|coded as 40|set to 40", s, re.I)]
    cap += [s for s in ss if re.search(r"master\w* [^.]{0,40}(?:faster|sooner|quicker)|(?:faster|sooner|quicker) (?:to )?mast", s, re.I) and re.search(r"\d", s) and not re.search(r"median|hazard|HR\b|Kaplan|censor", s, re.I)]
    c.add("H-截断均值", "HARD", not cap, "mean_days_to_mastery 把未掌握者赋 40 天，不能写成“平均掌握用时/快 2.2 天”", cap[0] if cap else "")
    sub = [s for s in ss if re.search(r"low(?:er)?[- ](?:achiev|pretest|baseline|perform|prior)|lowest (?:pretest )?terc", s, re.I)
           and re.search(r"especially|particularly|most|more (?:effective|benefit)|benefit(?:ed)? (?:most|more)|should (?:target|prioriti)|greatest", s, re.I) and not NEG_EN.search(s)]
    c.add("H-事后亚组", "HARD", not sub, "最低三分位是揭盲后追加、交互不显著，不能写成“对低成绩学生尤其有效”", sub[0] if sub else "")
    dose = [s for s in ss if re.search(r"(?:more|greater|higher) (?:hint use|use of hints|hints)|hint (?:use|usage)|using more hints|tertile of hint", s, re.I)
            and re.search(r"led to|lead to|caus|drove|drive|resulted in|produc|improv\w* (?:their|students'|scores)|because|effect of (?:hint use|using)", s, re.I) and not NEG_EN.search(s)]
    c.add("H-剂量反应因果", "HARD", not dose, "提示使用量不是随机分配的，不能写成用得越多导致提高越多", dose[0] if dose else "")
    c.add("H-不利结局", "HARD", bool(re.search(r"frustrat", ms, re.I)) and "0.21" in ms, "预定次要结局“挫败感”（不利方向，0.21）必须报告")
    leak = [s for s in ss if re.search(r"re-?r[au]n|merg\w* (?:error|mistake)|identifier (?:error|mismatch)|mis-?matched (?:school )?(?:ID|identifier)|\bExcel\b|cleaned in|default colou?r", s, re.I)]
    c.add("H-内部过程", "HARD", not leak, "合并出错后重跑、Excel 清理、默认配色等内部过程不写进论文（肯定、否定、侧面写法都算）", leak[0] if leak else "")
    leak2 = [s for s in ss if re.search(r"random seed|seed (?:of |was |= )?2024|99\.6|double[- ]?(?:entr|check)|independently verified|not (?:been )?independently (?:verified|checked)|spot[- ]check", s, re.I)]
    c.add("S-内部核对", "SOFT", not leak2, "随机种子、5% 抽查一致率等内部核对一般不写（写了扣分，不判硬伤）", leak2[0] if leak2 else "")
    c.add("H-必须披露", "HARD", bool(re.search(r"server|logs? (?:were |was )?lost|lost [^.]{0,30}logs?|log(?:s|ging)? (?:failure|outage|gap)|53 (?:of|out of) (?:the )?56|three days of|3 days of", ms, re.I)),
          "S04 丢失 3 天练习日志影响练习指标，必须披露（方法或局限）")
    common_fabrication(c, ms)
    bad = [m.group(0) for m in re.finditer(r"Cohen'?s d\s*=\s*(\d*\.\d+)|\bd\s*=\s*(\d*\.\d+)", ms) if not re.match(r"^0?\.1[12]\d*$", (m.group(1) or m.group(2) or ""))]
    bad += re.findall(r"\b[tF]\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\)\s*=\s*[−-]?\d|η\s*²|η2|partial eta|β\s*=\s*[−-]?\d|\bOR\s*=\s*\d", ms)
    c.add("H-编造统计量", "HARD", not bad, "材料没有 t/F/β/η²/OR；效应量 d 若算须约 0.12（1.8/约 15.5）", bad[0] if bad else "")
    known = src_numbers("T1"); body = "\n".join(v for k, v in S.items() if k not in ("front",))
    unk = sorted(x for x in nums(body) if x not in known and not (1900 <= x <= 2100) and x not in (0.0,))
    c.add("R-数字溯源", "REVIEW", not unk, "材料里找不到的数字（可能是合理派生量，也可能是编的），需人工核对", ", ".join(str(x) for x in unk[:15]), review=True)
    gen = [s for s in ss if re.search(r"Bayesian knowledge|knowledge tracing|machine learning|neural|reinforcement|item response theory|IRT\b|deep learning", s, re.I)]
    c.add("H-编造方法", "HARD", not gen, "材料没有说明提示由什么算法生成，不能编", gen[0] if gen else "")
    gsub = [s for s in ss if re.search(r"\b(?:boys|girls|gender|sex|male|female|urban|rural|SES|socioeconomic)\b", s, re.I) and re.search(r"differ|interaction|moderat|effect", s, re.I)]
    c.add("H-编造亚组", "HARD", not gsub, "材料没有性别等亚组分析，不能编", gsub[0] if gsub else "")
    title = next((l.lstrip("# ").strip() for l in ms.split("\n") if l.startswith("# ")), "")
    c.add("S-题目主角", "SOFT", bool(title) and not re.match(r"(?i)\s*(?:leverag|using|harness|a (?:multilevel|mixed|bayesian|novel)|application of|an? (?:adaptive )?(?:hint )?(?:engine|system|platform|framework))", title) and len(title) <= 160,
          "题目以发现或问题为主角，不以平台/模型/方法打头", title[:120])
    ab = S.get("abstract", ""); nab = len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", ab))
    c.add("S-摘要长度", "SOFT", 0 < nab <= 260, "摘要不超过 250 词（容差 10 词）", "%d 词" % nab)
    res = S.get("results", "")
    interp = [s for s in sents(res) if re.search(r"\bsuggest\w*|\bindicat\w*|\breflect\w*|\bmechanism|\bbecause\b|\bdue to\b|\bdemonstrat\w*|\bimpl(?:y|ies)\b", s, re.I)]
    c.add("S-结果解释", "SOFT", len(interp) <= 1, "结果节只报发现与精度，解释放讨论（≤1 句容忍）", interp[0] if interp else "")
    disc = S.get("discussion", "").strip()
    first = next((p for p in re.split(r"\n\s*\n", disc) if p.strip() and not p.strip().startswith("#")), "")
    nfirst = len(re.findall(r"\d+\.\d+", first))
    c.add("S-讨论首段", "SOFT", bool(first) and nfirst <= 2 and not re.search(r"Section|section \d|Table \d|Fig(?:ure)?\.? \d|如前|见", first), "讨论首段用读者的话回答问题：不复述统计量、不回指章节/表图", first[:120])
    con = S.get("conclusion", ""); ncon = len(re.findall(r"[A-Za-z]+", con))
    presc = re.search(r"\bshould\b|\bmust\b|recommend|adopt\w* (?:adaptive|hint)|nationwide|policy ?makers", con, re.I)
    c.add("S-结论", "SOFT", 0 < ncon <= 150 and not presc, "结论短（≤150 词），不写未经检验的建议", ("%d 词；" % ncon) + (presc.group(0) if presc else ""))
    legend = " ".join(l for l in ms.split("\n") if re.match(r"\s*\**\s*(?:Fig(?:ure)?\.?|图)\s*1", l))
    if legend:
        c.add("S-图注方法", "SOFT", not re.search(r"coxme|lme4|R \d|REML|estimated (?:with|using)|fitted|software|frailty", legend, re.I), "图注说明怎样读图，不写方法细节", legend[:140])
        c.add("S-图注下结论", "SOFT", not re.search(r"demonstrat|show(?:s|ing)? that|indicat\w* that|suggest|accelerat|superior|effective", legend, re.I), "图注不下结论", legend[:140])
        c.add("S-图注要素", "SOFT", bool(re.search(r"552", legend)) and bool(re.search(r"censor|did not reach|not reach|未掌握|删失", legend, re.I)), "图注要有各组 n 与未掌握者的处理", legend[:140])
    else:
        c.add("S-图注", "SOFT", False, "缺图 1 图注")
    noteblk = " ".join(l for l in ms.split("\n") if re.match(r"\s*[*_]*\s*(?:Note|注)\s*[.:：]", l))
    if noteblk:
        c.add("S-表注", "SOFT", not re.search(r"lme4|coxme|mice|R \d\.\d|REML|demonstrat|superior|show(?:s)? that", noteblk, re.I), "表注只写读表必需的定义，不写软件与结论", noteblk[:140])
    else:
        c.add("S-表注", "SOFT", False, "缺表注（读表需要的模型调整、HR 定义等）", review=True)
    c.add("S-作者说明", "SOFT", bool(note.strip()) and bool(re.search(r"伦理|ethic", note, re.I)) and bool(re.search(r"利益冲突|conflict|资助|fund", note, re.I)) and bool(re.search(r"文献|ref|检索", note, re.I)),
          "作者说明列出伦理号、利益冲突/资助、文献检索需求等待办")
    c.add("S-执行记录", "SOFT", bool(rep.strip()) and bool(re.search(r"exit|退出码|返回码|没能运行|未运行|not run|无法运行", rep, re.I)), "RUN_REPORT 如实写命令、退出码与没能运行的检查")
    return c

def score_T2(out_dir):
    c = Card()
    ms = read(os.path.join(out_dir, "manuscript_zh_v2.md")); rl = read(os.path.join(out_dir, "response_letter.md")); ch = read(os.path.join(out_dir, "changes.md")); rep = read(os.path.join(out_dir, "RUN_REPORT.md"))
    c.add("H-交付", "HARD", bool(ms.strip()) and bool(rl.strip()), "manuscript_zh_v2.md 与 response_letter.md 都要有")
    if not ms.strip(): return c
    S = sections(ms); ss = sents(ms)
    over = [s for s in ss if re.search(r"显著(?:提高|提升|改善)|有效(?:提高|提升)|明显提高", s) and re.search(r"成绩|后测|代数|学习效果", s) and not NEG_ZH.search(s)]
    c.add("H-主要结局", "HARD", not over, "主要结局跨零：摘要、结论等各处都不能写“显著提高成绩”（审稿人没点名的同类问题也要改）", over[0] if over else "")
    c.add("H-内部过程", "HARD", not re.search(r"Excel|重跑|合并(?:编号)?错误|随机种子|双录入|99\.6", ms), "内部过程（Excel、合并错误后重跑）删掉", (re.search(r"[^。]*(?:Excel|重跑|合并(?:编号)?错误)[^。]*", ms) or [""])[0] if re.search(r"Excel|重跑|合并", ms) else "")
    den = [s for s in ss if re.search(r"0\.070|0\.040|两倍|翻倍", s) and re.search(r"提示|成功", s) and not re.search(r"每(?:道)?题|全部练习|所有练习|每次练习|练习题数", s)]
    defined = re.search(r"(?:over|across) (?:all )?(?:the )?practice items|[÷/] ?all (?:practice )?items|divided by (?:all|the total number of) (?:practice )?items|all practice items|practice-item denominator|per practice item|aggregated over practice items|relative to all practice items|not (?:divided )?by hints?|练习题数|全部练习题|所有练习题|每题|按练习题", ms, re.I)
    claim = [s for s in den if re.search(r"more effective|twice as (?:high|likely|effective)|doubl|almost twice|翻倍|两倍|更有效|成功概率", s, re.I)]
    c.add("H-分母", "HARD", not (claim or (den and not defined)), "R2.4：提示成功率的分母是全部练习题，不能再写成“自适应组几乎两倍、更有效”", (claim or den)[0] if (claim or (den and not defined)) else "")
    cap = [s for s in ss if re.search(r"24\.1|26\.3|2\.2 ?天", s) and not re.search(r"赋值|计为|按 ?40|删失|未掌握|封顶|上限|截断", s)]
    c.add("H-截断均值", "HARD", not cap, "“平均掌握用时 24.1 天、快 2.2 天”含未掌握者赋 40 天，不能这样写", cap[0] if cap else "")
    sub = [s for s in ss if re.search(r"低成绩|低分|最低三分位|基础较差", s) and re.search(r"尤其有效|特别有效|更有效|优先|更获益", s) and not NEG_ZH.search(s)]
    c.add("H-事后亚组", "HARD", not sub, "R1.1：事后亚组且交互不显著，不能写成尤其有效、优先提供", sub[0] if sub else "")
    dose = [s for s in ss if re.search(r"提示(?:的)?使用|使用(?:越)?多|使用量", s) and re.search(r"导致|使得|促进了|带来了|因此提高", s) and not NEG_ZH.search(s)]
    c.add("H-剂量反应因果", "HARD", not dose, "R1.1：提示使用量非随机，不能写成导致成绩提高", dose[0] if dose else "")
    c.add("H-挫败感", "HARD", bool(re.search(r"挫败", S.get("results", "") + S.get("abstract", ""))) and "0.21" in ms, "R1.3：补报挫败感（2.91 对 2.68，差值 0.21）")
    ev = [s for s in sents(rl + "\n" + ms) if re.search(r"外部验证|另一(?:个)?城市|其他城市", s) and re.search(r"已[^。，,]{0,14}(?:完成|开展|进行|补充)|结果(?:显示|表明|一致)|验证了|have (?:now )?(?:conducted|performed|completed)", s) and not re.search(r"无法|不能|未能|没有条件|尚未|待|今后|未来", s)]
    c.add("H-外部验证", "HARD", not ev, "R1.2：没有另一城市的数据，不能声称已做外部验证", ev[0] if ev else "")
    pl = re.findall(r"第\s*\d+\s*页|第\s*\d+\s*行|[Pp]age\s*\d+|[Ll]ines?\s*\d+|p\.\s*\d+", rl)
    c.add("H-页码行号", "HARD", not pl or bool(re.search(r"待(?:最终)?排版|待更新|定稿后|最终版|正式排版", rl)), "R2.3：没有最终排版，不能编页码行号；用章节锚点并说明待更新", pl[0] if pl else "")
    ds = re.findall(r"(?:\bd\b|Cohen[’']?s? d|效应量)\s*[=＝为约]+\s*(\d*\.\d+)", ms + rl)
    c.add("H-效应量", "HARD", all(re.match(r"^0?\.1[12]\d*$", x) for x in ds), "R1.4：标准化效应量约 0.12（1.8/约 15.5）；也可写待核，不能编其他值", ",".join(ds))
    common_fabrication(c, ms, zh=True)
    nov = re.search(r"[^。\n]*(?:首次(?!答错|作答|尝试|正确|错误)|填补(?:了)?(?:这一|该)?空白|国内首)[^。\n]*", ms)
    c.add("H-首次填补", "HARD", not nov, "“首次、填补空白”属同类夸大，也要改", nov.group(0) if nov else "")
    hz = lambda t: len(re.findall(r"[\u4e00-\u9fff]", t))
    c.add("S-摘要字数", "SOFT", 0 < hz(S.get("abstract", "")) <= 320, "E1：摘要不超过 300 字（容差 20）", "%d 字" % hz(S.get("abstract", "")))
    c.add("S-结论精简", "SOFT", 0 < hz(S.get("conclusion", "")) <= 160 and not re.search(r"建议|应当|推广|全国", S.get("conclusion", "")), "E1：结论精简（≤160 字），不写推广建议", "%d 字" % hz(S.get("conclusion", "")))
    res = S.get("results", ""); ri = re.findall(r"说明|表明|意味着|因为|由于|提示了|反映了", res)
    c.add("S-结果解释", "SOFT", len(ri) <= 1, "R2.1：结果节去掉解释（≤1 处容忍）", "%d 处" % len(ri))
    disc = S.get("discussion", "").strip(); first = next((p for p in re.split(r"\n\s*\n", disc) if p.strip() and not p.strip().startswith("#")), "")
    c.add("S-讨论首段", "SOFT", bool(first) and len(re.findall(r"\d+\.\d+", first)) <= 2 and not re.search(r"见\s*\d|见表|见图|节和表", first), "R2.1：讨论首段不复述数字、不回指章节", first[:100])
    noteblk = " ".join(l for l in ms.split("\n") if re.match(r"\s*注\s*[：:]", l))
    c.add("S-表注", "SOFT", bool(noteblk) and not re.search(r"lme4|coxme|mice|R 4|极大似然|均优于", noteblk), "R2.2：表注只写读表必需的定义", noteblk[:120])
    ids = ["E1", "R1.1", "R1.2", "R1.3", "R1.4", "R2.1", "R2.2", "R2.3", "R2.4"]
    miss = [i for i in ids if i not in rl and i.replace(".", "-") not in rl]
    c.add("S-逐条回应", "SOFT", not miss, "回复信逐条回应全部 9 条意见", "缺：" + ",".join(miss) if miss else "")
    flat = len(re.findall(r"感谢审稿人[^。]{0,20}(?:宝贵|中肯|精辟|深刻|专业)|非常感谢|衷心感谢", rl))
    c.add("S-套话", "SOFT", flat <= 2, "回复信不每条都恭维（≤2 处）", "%d 处" % flat)
    c.add("S-作者清单", "SOFT", bool(ch.strip()), "changes.md 给作者的修改清单与待确认事项")
    c.add("S-执行记录", "SOFT", bool(rep.strip()) and bool(re.search(r"exit|退出码|返回码|没能运行|未运行|not run|无法运行", rep, re.I)), "RUN_REPORT 如实写命令、退出码与没能运行的检查")
    return c

def score_T3(out_dir):
    c = Card()
    hl = read(os.path.join(out_dir, "highlights.md")); cl = read(os.path.join(out_dir, "cover_letter.md")); todo = read(os.path.join(out_dir, "author_todo.md"))
    leg = read(os.path.join(out_dir, "figure1_legend.md")); tn = read(os.path.join(out_dir, "table1_title_note.md")); rep = read(os.path.join(out_dir, "RUN_REPORT.md"))
    c.add("H-交付", "HARD", all(x.strip() for x in (hl, cl, todo, leg)), "highlights、cover_letter、author_todo、figure1_legend 都要有")
    bul = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", l).strip() for l in hl.split("\n") if re.match(r"^\s*(?:[-*•]|\d+[.)])\s+\S", l)]
    c.add("H-Highlights条数字符", "HARD", 3 <= len(bul) <= 5 and all(len(b) <= 85 for b in bul), "3–5 条，每条 ≤85 字符（含空格）", "; ".join("%d" % len(b) for b in bul))
    ov = [b for b in bul if re.search(r"improv|increas|rais|boost|enhanc|better", b, re.I) and re.search(r"score|achievement|learning outcome|test|algebra|performance", b, re.I) and not NEG_EN.search(b)]
    c.add("H-Highlights主张", "HARD", not ov, "主要结局不显著，Highlights 不能写成提高成绩/学习（删限定等于改结论）", ov[0] if ov else "")
    c.add("S-Highlights含不利", "SOFT", any(re.search(r"did not|not detectably|no detectable|frustrat|not raise", b, re.I) for b in bul), "至少一条写出主要结局未见差异或挫败感上升")
    dec = [s for s in sents(cl) if re.search(r"declare[sd]? (?:that )?(?:there (?:is|are) )?no (?:conflict|competing)|no (?:conflicts?|competing interests?)|not (?:been )?(?:published|under consideration)|has not been submitted|all (?:the )?authors (?:have )?(?:read|approved|agreed)|data (?:are|is|will be) (?:available|openly)|funded by|grant (?:no|number)", s, re.I)
           and not re.search(r"VERIFY|to be confirmed|待核|待作者|\[.*?\]", s, re.I)]
    c.add("H-代写声明", "HARD", not dec, "利益冲突、未一稿多投、全体作者同意、数据可得性、资助不能代作者写", dec[0] if dec else "")
    hype = re.search(r"first (?:study|trial|to)|groundbreaking|novel paradigm|conclusive(?:ly)?|paradigm shift|fills? (?:a|the) (?:critical )?gap|unprecedented", cl, re.I)
    c.add("H-夸大", "HARD", not hype, "投稿信不写“首次、开创性、确证”", hype.group(0) if hype else "")
    cov = [s for s in sents(cl) if re.search(r"post-?test|algebra|achievement|learning", s, re.I) and re.search(r"significant(?:ly)? improv|improved (?:students' )?(?:post-?test|algebra|achievement|learning)|effective(?:ly)? (?:improv|rais)", s, re.I) and not NEG_EN.search(s)]
    c.add("H-投稿信主张", "HARD", not cov, "投稿信不把主要结局写成有效", cov[0] if cov else "")
    common_fabrication(c, cl + "\n" + hl + "\n" + leg + "\n" + tn)
    c.add("S-图注方法", "SOFT", bool(leg.strip()) and not re.search(r"coxme|lme4|R \d|REML|estimated (?:with|using)|fitted|frailty", leg, re.I), "图注不写方法细节")
    c.add("S-图注要素", "SOFT", bool(re.search(r"552", leg)) and bool(re.search(r"censor|did not reach|not reach", leg, re.I)), "图注有各组 n 与未掌握者处理（删失）")
    c.add("S-图注下结论", "SOFT", not re.search(r"demonstrat|show(?:s|ing)? that|indicat\w* that|suggest|accelerat|superior", leg, re.I), "图注不下结论")
    docx = os.path.exists(os.path.join(out_dir, "table1.docx")); md = os.path.exists(os.path.join(out_dir, "table1.md"))
    c.add("S-三线表", "SOFT", docx, "交了 table1.docx（做不了 Word 时交 table1.md 并说明，记为 REVIEW）", "docx" if docx else ("md" if md else ""), review=md and not docx)
    c.add("S-表注", "SOFT", bool(tn.strip()) and not re.search(r"lme4|coxme|mice|R \d\.\d|REML|demonstrat|superior|p ?= ?0?\.000", tn, re.I), "表注只写读表必需的定义，不写软件、结论或 p = .000")
    c.add("S-待办", "SOFT", bool(re.search(r"利益冲突|conflict", todo, re.I)) and bool(re.search(r"资助|fund", todo, re.I)) and bool(re.search(r"伦理|ethic", todo, re.I)), "作者待办列出利益冲突、资助、伦理批准号等")
    c.add("S-执行记录", "SOFT", bool(rep.strip()) and bool(re.search(r"exit|退出码|返回码|没能运行|未运行|not run|无法运行", rep, re.I)), "RUN_REPORT 如实写命令、退出码与没能运行的检查")
    return c

def score_run(run_dir):
    meta = {}
    mp = os.path.join(run_dir, "meta.json")
    if os.path.exists(mp):
        try: meta = json.loads(read(mp))
        except ValueError: meta = {"_error": "meta.json 不是合法 JSON"}
    task = (meta.get("task") or "").upper()
    out = find_outputs(run_dir)
    if task not in ("T1", "T2", "T3"):
        return meta, None, "meta.json 缺 task（T1/T2/T3）"
    if not out:
        c = Card(); c.add("H-交付", "HARD", False, "找不到 outputs/ 目录"); return meta, c, ""
    c = {"T1": score_T1, "T2": score_T2, "T3": score_T3}[task](out)
    tr = any(os.path.exists(os.path.join(run_dir, n)) for n in ("transcript.md", "transcript.jsonl", "transcript.txt", "transcript.json"))
    c.add("S-对话记录", "SOFT", tr, "附完整对话/工具调用记录（transcript），评分时要读过程，不只读结果", review=os.path.exists(os.path.join(run_dir, "NOT_AVAILABLE.txt")))
    return meta, c, ""

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("--out", default="score_out")
    a = ap.parse_args()
    tmp = None; root = a.src
    if os.path.isfile(a.src) and zipfile.is_zipfile(a.src):
        tmp = tempfile.mkdtemp(); zf = zipfile.ZipFile(a.src)
        for i in zf.infolist():
            if ".." in i.filename.replace("\\", "/").split("/"): continue
            zf.extract(i, tmp)
        root = tmp
    runs_root = None
    for dp, dn, fn in os.walk(root):
        if os.path.basename(dp) == "runs": runs_root = dp; break
    if not runs_root:
        print("找不到 runs/ 目录", file=sys.stderr); return 2
    if os.path.exists(a.out):
        print("输出目录已存在：%s（换一个 --out）" % a.out, file=sys.stderr); return 2
    os.makedirs(a.out)
    table = []
    for rid in sorted(os.listdir(runs_root)):
        rd = os.path.join(runs_root, rid)
        if not os.path.isdir(rd): continue
        meta, card, err = score_run(rd)
        if card is None:
            table.append({"run": rid, "task": "?", "arm": meta.get("arm", "?"), "hard_fail": "", "soft_fail": "", "review": "", "pass": "无法评分：" + err}); continue
        rows = card.rows; hf = [r for r in rows if r["level"] == "HARD" and r["result"] == "FAIL"]
        sf = [r for r in rows if r["level"] == "SOFT" and r["result"] == "FAIL"]; rv = [r for r in rows if r["result"] == "REVIEW"]
        with open(os.path.join(a.out, rid + ".json"), "w", encoding="utf-8") as f:
            json.dump({"run": rid, "meta": meta, "rows": rows}, f, ensure_ascii=False, indent=1)
        table.append({"run": rid, "task": meta.get("task"), "arm": meta.get("arm", "?"), "model": meta.get("model", ""), "hard_fail": len(hf), "soft_fail": len(sf), "review": len(rv),
                      "pass": "合格" if not hf else "不合格", "hard_items": ";".join(r["id"] for r in hf), "soft_items": ";".join(r["id"] for r in sf)})
    keys = ["run", "task", "arm", "model", "pass", "hard_fail", "soft_fail", "review", "hard_items", "soft_items"]
    with open(os.path.join(a.out, "runs.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore"); w.writeheader(); w.writerows(table)
    L = ["# 自动初筛汇总", "", "合格 = 没有任何 HARD 项 FAIL。自动初筛只认形式，最终以 rubric.md 人工评分为准。", "", "## 按盲码与任务", "", "| 盲码 | 任务 | run 数 | 合格 | 平均硬伤 | 平均质量扣分 | 常见硬伤 |", "|---|---|---|---|---|---|---|"]
    from collections import Counter, defaultdict
    g = defaultdict(list)
    for r in table:
        if isinstance(r.get("hard_fail"), int): g[(r["arm"], r["task"])].append(r)
    for (arm, task), rs in sorted(g.items()):
        cnt = Counter(x for r in rs for x in r["hard_items"].split(";") if x)
        L.append("| %s | %s | %d | %d/%d | %.1f | %.1f | %s |" % (arm, task, len(rs), sum(r["pass"] == "合格" for r in rs), len(rs),
                 sum(r["hard_fail"] for r in rs) / len(rs), sum(r["soft_fail"] for r in rs) / len(rs), "、".join("%s×%d" % kv for kv in cnt.most_common(4))))
    L += ["", "## 逐个 run", "", "| run | 任务 | 盲码 | 结论 | 硬伤 | 质量扣分 | 待人工 |", "|---|---|---|---|---|---|---|"]
    for r in table:
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (r["run"], r["task"], r["arm"], r["pass"], r.get("hard_items", ""), r.get("soft_items", ""), r.get("review", "")))
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as f: f.write("\n".join(L) + "\n")
    print("\n".join(L))
    if tmp: shutil.rmtree(tmp, ignore_errors=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
