#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_all.py — 一条命令跑完稿件的常规检查，写出一页白话状态（STATUS.md）。

  python check_all.py 稿件.md|docx [--out 检查目录] [--results 结果.csv 结果目录/ ...] [--allow allow.txt]
         [--design rct] [--domain assets/domains/包] [--profile assets/journal_profiles/刊.json]
         [--ledger results_ledger.csv] [--supplement 补充.md] [--simulation] [--lang auto|en|zh]
         [--qualifiers qualifiers.csv] [--citations citation_ledger.csv] [--note 作者说明.md]
         [--execution EXECUTE|EXECUTE+NET|REASONING-ONLY] [--benchmark-mode distribution|domain_pack|case|none]
         [--benchmark-report 报告] [--benchmark-corpus 语料目录]

依次运行 section_lint（含交付残留与写作过程痕迹）、density_check、ref_check；给了 --results 就跑 number_trace，
给了 --ledger 就跑 ledger_check，给了 --profile 就跑 journal_check；--simulation 检查模拟标识与不该出现的真人研究声明。
各工具的原始报告留在 --out（默认在稿件旁新建“检查_时间”目录），STATUS.md 只写四件事：
必须先处理的、没能运行的检查（不算通过）、需要看一眼的、机器查不了需要人看的。
--supplement、--displays（表 CSV、图注、图片）、--terms：一并检查读者看到的用语（display_terms）；--coverage、--neighbors：文献覆盖（coverage_check）；
--benchmark-decisions：写法依据绑定终稿；--expectations：用户明确要求登记表（未满足即必须处理）；--heading-style：结果小标题风格（不给就从 expectations 取）；
--stage submission：覆盖缺口、未绑定终稿的对标决策升为必须处理。结果节的句子功能（results_function）与正文用语每次都查。
STATUS.md 另列“分维度状态”：任何一维没过都不是投稿就绪。
体裁与节职能（genre_gate，每次都跑）：摘要末句、引言首末段、方法粒度、主文表型、讨论首段与结论末句；--placement、--memo、--drill 给出去向登记、
体裁备忘与拒收预演，--neighbor-texts 给近邻全文。--stage submission 时缺这三件或没绑定当前稿件即必须处理（references/27）。
--concept 给论文构想、--survey 给同类调研表：选材的主张、结果盲测试、审稿人两问与材料预算一并检查（references/29）。
--allow：不来自结果文件的数字（任务参数、种子、版本号）的登记表，每行“数字 # 理由”。登记过的数字不阻断，但会连同理由列在 STATUS.md 里请作者复核。
退出码：0 没有必须处理的问题，请求的检查都跑了；1 有必须处理的问题，或有检查没能运行；2 输入错误。
--qualifiers：口径限定表（两列 values、requires，多个值或词用 | 分隔）。稿件里每一句提到这些数字的话，本句或上一句必须带
上限定词（如截断均值必须写明“未掌握者按 40 天计”），否则列为必须先处理。
--citations / --note：跑 lit_evidence check，核对引文台账与作者说明里的“已核实”“已对标”等说法（references/23）。
--design 认 cluster-rct、randomised、横断面等常见写法；认不出就直接报错并列出可用名称，不会让检查半途“没能运行”。
--out 已有上一轮报告时，自动写到 目录_2、目录_3……，旧报告不覆盖。STATUS.md 每条末尾的括号写明工具与规则代码；
同目录的 summary.json 是同样内容的机器可读版本，供 check_stats.py 汇总。
它不判断论证是否成立、引文是否支持主张、图表是否好读。
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIM_MARK = re.compile(r"SIMULAT\w*|synthetic|模拟研究|模拟数据|合成数据|模拟标识", re.I)
INTEXT_CITE = re.compile(r"\((?:(?:see|e\.g\.,?|cf\.|for (?:a )?review,? see)\s+)?(?:[^()]*?;\s*)?(?:[A-Z][A-Za-z\-]+(?: et al\.)?(?:,| and| &) ?)+(?:19|20)\d\d[a-z]?(?=[;)])|(?<![\w\[])\[\d+(?:[,–-]\d+)*\](?!\()")
APPROVAL_ID = re.compile(r"(?:approv\w*|ethic\w*|IRB|REC\b|伦理|批准)[^\n。]{0,70}?(?:No\.|number|编号|批准号|批号|文号|#)\s*[:：]?\s*([A-Z0-9][A-Z0-9\-/]{2,})", re.I)
REGISTRY_ID = re.compile(r"\b(NCT\d{8}|ISRCTN\d{6,}|ChiCTR[\w-]{6,}|ACTRN\d{10,}|DRKS\d{6,}|CRD\d{8,}|osf\.io/[a-z0-9]{4,})\b", re.I)
REG_CLAIM = re.compile(r"\b(?:pre-?registered|prospectively registered|registered (?:at|with|on|in)\b|trial registration)|预注册|已注册|注册号", re.I)
NOT_REG = re.compile(r"未在公开平台注册|未公开注册|未注册|not (?:publicly |prospectively )?registered|no (?:public )?registration", re.I)
REAL_CLAIM = re.compile(r"ethics (?:committee|approval|board)|approved by|informed consent|伦理(?:审查)?委员会|伦理批准|批准号|知情同意", re.I)
NEG = re.compile(r"\b(?:no|not|without|none)\b|无|未|不|没有|并非", re.I)
HOWTO = {
    "X11": "把这些句子移到作者说明或工作记录；论文正文、局限和标识段只写研究本身。",
    "A1": "交付残留（对话残留、零宽字符、域错误）投稿前必须删除。",
    "I1": "在引言最后一两段写明研究问题、目的或假设。",
    "R1": "结果节只报发现与精度，解释、机制和与文献的比较移到讨论。",
    "G2": "正文里的设计词和声明的设计对不上，先确认真实设计。",
    "H1": "Highlights 的条数或字符超了，删修饰词，不删限定。",
    "X13": "摘要和结论只写研究；把 [VERIFY] 放回事实本来所在的方法或结果句，稿件状态与待办写进作者说明。",
    "W1": "正文超过字数上限。",
}


def run(args, timeout=900):
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


CODE_RX = re.compile(r"(deviation_register|genre_gate|section_lint|density_check|number_trace|ref_check|ledger_check|journal_check|lit_evidence|check_all|qualifiers|claim_strength|derivation_check|reader_readiness)\s+([A-Za-z][\w-]*)")


def qual_hit(v, x):
    """口径表里的数字是否出现在句中；版本号与软件包名里的数字（R 4.4.1、lme4 1.1-35）不算，− 与 - 视为相同。"""
    v2, x2 = v.replace("−", "-"), x.replace("−", "-")
    for m in re.finditer(r"(?<![\d.])" + re.escape(v2) + r"(?![\d])", x2):
        tok = re.search(r"[\w.\-]*$", x2[:m.start()]).group(0) + m.group(0) + re.match(r"[\w.\-]*", x2[m.end():]).group(0)
        if re.fullmatch(r"v?\d+(?:\.\d+){2,}(?:-\d+)?|v?\d+\.\d+-\d+|[A-Za-z]+\d[\w.\-]*", tok):
            continue
        return True
    return False


def coded(items):
    out = []
    for x in items:
        hits = list(CODE_RX.finditer(x.split("；例：")[0]))
        out.append({"tool": hits[-1].group(1) if hits else "", "code": hits[-1].group(2) if hits else "", "text": x.split("\n")[0][:300]})
    return out


def first_line(s):
    return next((l.strip() for l in s.splitlines() if l.strip()), "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manuscript")
    ap.add_argument("--out", default="")
    ap.add_argument("--results", nargs="*", default=[])
    ap.add_argument("--allow", default="")
    ap.add_argument("--design", default="")
    ap.add_argument("--domain", default="")
    ap.add_argument("--profile", default="")
    ap.add_argument("--ledger", default="")
    ap.add_argument("--supplement", default="")
    ap.add_argument("--simulation", action="store_true")
    ap.add_argument("--lang", default="auto", choices=["auto", "en", "zh"])
    ap.add_argument("--qualifiers", default="")
    ap.add_argument("--citations", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--execution", default="", choices=["", "EXECUTE", "EXECUTE+NET", "REASONING-ONLY"])
    ap.add_argument("--benchmark-mode", default="", choices=["", "distribution", "domain_pack", "case", "none"])
    ap.add_argument("--benchmark-report", default="")
    ap.add_argument("--benchmark-corpus", default="")
    ap.add_argument("--displays", nargs="*", default=[], help="投稿表 CSV、图注文件、图片（svg/pdf/png）：检查读者看到的用语")
    ap.add_argument("--terms", default="", help="display_terms.csv：内部 ID 到正式显示名的登记表")
    ap.add_argument("--coverage", default="", help="coverage_map.csv：按论证职能的文献覆盖表")
    ap.add_argument("--neighbors", default="", help="实际读到的近邻论文参考文献数：label,doi,n_refs,source_locator")
    ap.add_argument("--benchmark-decisions", default="", help="benchmark_decisions.csv：写法依据，逐行绑定终稿指纹")
    ap.add_argument("--expectations", default="", help="expectations.json：用户明确提出的要求，登记后是硬回归项")
    ap.add_argument("--heading-style", default="", choices=["", "object", "finding", "either"])
    ap.add_argument("--stage", default="", choices=["", "draft", "submission"])
    ap.add_argument("--placement", default="", help="placement_decisions.csv：每项分析、表、图与补充条目的去向、读者问题与依据")
    ap.add_argument("--memo", default="", help="genre_memo.md：一句话贡献、读者问题、说明了什么、近邻对照、白话复述")
    ap.add_argument("--drill", default="", help="reject_drill.md：作者拒收预演")
    ap.add_argument("--neighbor-texts", nargs="*", default=[], help="近邻论文全文（txt/md），供体裁对照与自造标签检查")
    ap.add_argument("--submitted", default="", help="上次投稿的原稿（返修时用）：转给 genre_gate 查改稿增量与融入（references/07 §10）")
    ap.add_argument("--concept", default="", help="paper_concept.md：作者目的、候选构想、主张清单、审稿人预判与搁置清单（references/29）")
    ap.add_argument("--survey", default="", help="survey_corpus.csv：同类调研表，用来对照材料预算（genre_gate PB1）")
    ap.add_argument("--derivations", default="", help="derivations.csv：派生量的公式、分量数值与单位（derivation_check，references/22 §8）")
    ap.add_argument("--term-groups", default="", help="题目术语组，转给 genre_gate 的表面惯例画像（convention_profile）")
    ap.add_argument("--reader-terms", default="", help="补充的读者术语列表（每行一个），转给 reader_readiness；不同于显示名表 --terms")
    ap.add_argument("--moves", default="", help="语步编码 JSON（move_check 格式），转给 genre_gate（MV1）")
    ap.add_argument("--texture-baseline", default="", help="领域包目录，转给 genre_gate 作文本质感参照（TX1）")
    ap.add_argument("--study-terms", default="", help="本研究主题词（逗号分隔或 @文件），转给 genre_gate 的词汇 keyness（LX1）")
    ap.add_argument("--texture-exemplars", nargs="*", default=None, help="只用于质感与词汇的近邻全文")
    a = ap.parse_args()
    nd = M.normalize_design(a.design)
    if nd is None:
        print("认不出的设计名：%s。可用：%s（也认 cluster-rct、randomised、longitudinal、survey、横断面等写法）" % (a.design, "、".join(M.DESIGNS)), file=sys.stderr)
        return 2
    a.design = nd
    ms = os.path.abspath(a.manuscript)
    if not os.path.isfile(ms):
        print("找不到稿件：%s" % a.manuscript, file=sys.stderr)
        return 2
    for p in a.results + a.displays + [x for x in (a.allow, a.domain, a.profile, a.ledger, a.supplement, a.qualifiers, a.citations, a.note, a.benchmark_corpus,
                                                  a.terms, a.coverage, a.neighbors, a.expectations, a.benchmark_decisions,
                                                  a.placement, a.memo, a.drill, a.concept, a.survey, a.derivations, a.moves, a.reader_terms, a.submitted) if x] + a.neighbor_texts + (a.texture_exemplars or []):
        if not os.path.exists(p):
            print("找不到输入：%s" % p, file=sys.stderr)
            return 2
    out = a.out or os.path.join(os.path.dirname(ms), "检查_" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    prev = ""
    if os.path.exists(out) and os.listdir(out):
        base, k = out.rstrip("/\\"), 2
        while os.path.exists("%s_%d" % (base, k)) and os.listdir("%s_%d" % (base, k)):
            k += 1
        prev, out = out, "%s_%d" % (base, k)
        print("检查目录 %s 里已有上一轮的报告；本轮写到 %s，旧报告不覆盖。" % (prev, out))
    os.makedirs(out, exist_ok=True)
    S = lambda name: os.path.join(HERE, name)
    O = lambda name: os.path.join(out, name)
    must, notrun, look, ran = [], [], [], []

    # 1. section_lint
    args = [S("section_lint.py"), ms, "--json", O("section_lint.json"), "--report", O("section_lint.md"), "--lang", a.lang]
    if a.design:
        args += ["--design", a.design]
    if a.domain:
        args += ["--domain", a.domain]
    code, so, se = run(args)
    if code == 2 or not os.path.exists(O("section_lint.json")):
        notrun.append("section_lint：%s" % (first_line(se) or first_line(so) or "退出码 %d" % code))
    else:
        items = json.load(open(O("section_lint.json"), encoding="utf-8"))
        for it in items:
            if it["code"].startswith("RR"):
                continue  # Complete inventory/report is collected below, once.
            ex = ("；例：" + it["examples"][0][:120]) if it.get("examples") else ""
            line = "%s（section_lint %s，%s）%s" % (it["msg"], it["code"], it["sec"], ex)
            if it["level"] == "MUST":
                must.append(line + ("\n   怎么改：" + HOWTO[it["code"]] if it["code"] in HOWTO else ""))
            elif it["level"] == "SHOULD":
                look.append(line)
        ran.append(("section_lint", "MUST %d、SHOULD %d、INFO %d" % tuple(sum(i["level"] == k for i in items if not i["code"].startswith("RR")) for k in ("MUST", "SHOULD", "INFO")), "section_lint.md"))

    # Lexical first-use candidates are separate from semantic/evidence review.
    rr_args = [S("reader_readiness.py"), ms, "--json", O("reader_readiness.json"), "--report", O("reader_readiness.md")]
    if a.reader_terms:
        rr_args += ["--terms", a.reader_terms]
    rr_code, rr_so, rr_se = run(rr_args)
    rr_res, rr_ok = {}, False
    if rr_code != 0 or not os.path.exists(O("reader_readiness.json")):
        notrun.append("reader_readiness：%s" % (first_line(rr_se) or first_line(rr_so) or "退出码 %d" % rr_code))
    else:
        with open(O("reader_readiness.json"), encoding="utf-8") as f:
            rr_res = json.load(f)
        rr_ok = bool(rr_res.get("scopes"))
        if not rr_ok:
            notrun.append("reader_readiness：没有可扫描文字范围；不能把空输入记为检查通过。")
        # 15b: form candidates take at most two lines, so they cannot push process reminders
        # (--results, --displays, ...) out of the 15 lines STATUS.md shows. Names first used in the
        # introduction's closing paragraph (RR4) get their own line: it is the reader-facing case.
        rr_items = rr_res.get("items", [])
        late = list(dict.fromkeys(it["term"] for it in rr_items if it["code"] == "RR4"))
        if late:
            look.append("引言末段才首次具名：%s。回读此前是否已交代它们是什么、为什么能回答本文问题；首次具名本身不是缺陷（reader_readiness RR4，introduction）" % "、".join(late))
        groups = {}
        for it in rr_items:
            if it["level"] == "SHOULD":
                groups.setdefault(it["sec"], []).append(it["term"])
        if groups:
            look.append("缩写首用候选 %d 个（摘要、正文与各图表分开计）：%s。按读者与目标刊逐个裁决，常用统计符号与目标读者熟悉的简称可保留（reader_readiness RR1/RR2，汇总；明细见 reader_readiness.md）"
                        % (sum(len(set(v)) for v in groups.values()), "；".join("%s %s" % (k, "、".join(dict.fromkeys(v))) for k, v in groups.items())))
        ran.append(("reader_readiness", "形式候选 %d；概念与论证未自动核查" % len(rr_res.get("items", [])), "reader_readiness.md"))

    # 2. density_check
    code, so, se = run([S("density_check.py"), ms, "--json", O("density.json"), "--report", O("density.md"), "--lang", a.lang])
    if code == 2 or not os.path.exists(O("density.json")):
        notrun.append("density_check：%s" % (first_line(se) or first_line(so)))
    else:
        items = json.load(open(O("density.json"), encoding="utf-8"))
        for it in items:
            line = "%s（density_check %s）" % (it.get("msg", ""), it.get("code", ""))
            if it.get("level") == "MUST":
                must.append(line)
            elif it.get("level") == "SHOULD":
                look.append(line)
        ran.append(("density_check", "MUST %d、SHOULD %d" % (sum(i.get("level") == "MUST" for i in items), sum(i.get("level") == "SHOULD" for i in items)), "density.md"))

    # 3. ref_check
    code, so, se = run([S("ref_check.py"), ms, "--report", O("ref_check.md")])
    m = re.search(r"文献表\s*(\d+)\s*条", so + se)
    nref = int(m.group(1)) if m else -1
    if code == 2:
        notrun.append("ref_check：%s" % (first_line(se) or first_line(so)))
    elif nref == 0:
        body = M.load_text(ms)
        cites = INTEXT_CITE.findall(body)
        if cites:
            must.append("正文有 %d 处作者–年份或编号引文（如 %s），却没有参考文献表：材料没给文献时这些多半是编的。"
                        "起草阶段用 [ref] 标出检索需求，真有文献就补参考文献表并登记引文台账（ref_check RC1）。" % (len(cites), cites[0]))
        else:
            look.append("还没有参考文献表：起草阶段可以用 [ref] 标出检索需求，投稿前补齐后重跑（ref_check RC2）。")
        ran.append(("ref_check", "无参考文献表%s" % ("，正文有 %d 处引文" % len(cites) if cites else ""), "ref_check.md"))
    else:
        if code == 1:
            must.append("引文与参考文献表对不上，或 DOI 格式、重复有问题（ref_check RC3）：%s" % first_line(so))
        ran.append(("ref_check", "问题" if code == 1 else "对得上（只核对得上，不核引得对）", "ref_check.md"))

    # 4. number_trace
    if a.results:
        args = [S("number_trace.py"), ms, "--sources"] + a.results + ["--report", O("number_trace.md"),
                                                                     "--sections", "abstract,results,discussion,limitations,conclusion", "--captions"]
        code, so, se = run(args)
        if code == 2 or not os.path.exists(O("number_trace.md")):
            notrun.append("number_trace：%s" % (first_line(se) or first_line(so)))
        else:
            rep = open(O("number_trace.md"), encoding="utf-8").read()
            rows = [r.split("|") for r in rep[rep.find("| 节 | 数字 |"):].splitlines()[2:] if r.startswith("| ")] if "| 节 | 数字 |" in rep else []
            reasons = {}
            key = lambda x: x.strip().replace("−", "-").replace(",", "").rstrip("%").strip()   # 95 与 95%、1,240 与 1240 视为同一登记
            if a.allow:
                for line in open(a.allow, encoding="utf-8-sig"):
                    if line.strip() and not line.startswith("#") and "#" in line:
                        reasons[key(line.split("#")[0])] = line.split("#", 1)[1].strip()
            unexplained = [r for r in rows if key(r[2]) not in reasons]
            explained = sorted({"%s（%s）" % (r[2].strip(), reasons[key(r[2])]) for r in rows if key(r[2]) in reasons})
            if unexplained:
                ex = "；".join("%s 在%s" % (r[2].strip(), r[1].strip()) for r in unexplained[:6])
                must.append("%d 处数字在结果文件里找不到（number_trace NT1）：%s。逐个核对：写错了就改；是派生量就写明算法并用 verify_evidence 核；"
                            "本来就不来自结果（任务参数、种子、版本号）就写进 --allow 文件，每行“数字 # 理由”，理由会列在本页。" % (len(unexplained), ex))
            if explained:
                look.append("这些数字不来自结果文件，已登记理由，请作者复核（number_trace NT2）：" + "、".join(explained))
            ran.append(("number_trace", "未匹配 %d（其中已登记理由 %d）" % (len(rows), len(rows) - len(unexplained)), "number_trace.md"))
    else:
        look.append("没有给 --results：数字没有和结果文件核对。有结果表时一定要给（number_trace NT0）。")

    # 5. ledger_check
    if a.ledger:
        args = [S("ledger_check.py"), a.ledger, "--manuscript", ms, "--report", O("ledger_check.md")]
        if a.supplement:
            args += ["--supplement", a.supplement]
        code, so, se = run(args)
        if code == 2 or not os.path.exists(O("ledger_check.md")):
            notrun.append("ledger_check：%s" % (first_line(se) or first_line(so)))
        else:
            errs = [l[len("- **ERROR** "):] for l in open(O("ledger_check.md"), encoding="utf-8").read().splitlines() if l.startswith("- **ERROR** ")]
            cols = [e for e in errs if "缺列" in e]
            if cols:
                notrun.append("ledger_check：台账的列名和模板不同（%s），逐行检查跑不了。按 assets/templates/results_ledger.csv 的列改好后重跑；"
                              "自己发明的列名会让“台账已核对”变成一句没有依据的话。" % cols[0])
                ran.append(("ledger_check", "没能运行（列名不对）", "ledger_check.md"))
            else:
                for e in errs:
                    must.append("结果台账：%s（ledger_check LC1）" % e)
                ran.append(("ledger_check", "ERROR %d" % len(errs), "ledger_check.md"))

    # 6. journal_check
    if a.profile:
        args = [S("journal_check.py"), ms, "--profile", a.profile, "--json", O("journal.json"), "--report", O("journal.md")]
        base = os.path.join(ROOT, "assets", "benchmarks", "display_baseline.json")
        if os.path.exists(base):
            args += ["--baseline", base]
        code, so, se = run(args)
        if code == 2 or not os.path.exists(O("journal.json")):
            notrun.append("journal_check：%s" % (first_line(se) or first_line(so)))
        else:
            items = json.load(open(O("journal.json"), encoding="utf-8"))
            if isinstance(items, dict):
                items = items.get("items", [])
            for it in items:
                line = "%s（journal_check %s）" % (it.get("msg", ""), it.get("rule", ""))
                (must if it.get("level") == "FAIL" else look if it.get("level") == "CAND" else []).append(line)
            ran.append(("journal_check", "FAIL %d、候选 %d" % (sum(i.get("level") == "FAIL" for i in items), sum(i.get("level") == "CAND" for i in items)), "journal.md"))

    src_text = ""
    for p in a.results:
        for q in ([os.path.join(dp, f) for dp, dn, fn in os.walk(p) for f in fn] if os.path.isdir(p) else [p]):
            try:
                src_text += "\n" + M.load_text(q)
            except Exception:
                pass
    # 7. 模拟标识
    text = M.load_text(ms)
    doc_sents = [x for b in M.parse(text) if b["kind"] in ("para", "caption") for x in M.sentences(b["text"])]   # 按块切句，不跨标题
    if a.simulation:
        if not SIM_MARK.search(text[:1500]):
            must.append("模拟稿的开头没有模拟标识。在题目下写一句：全部数据为合成数据，不代表真实被试。只写这一句，别的状态话写进作者说明（check_all SIM1）。")
        real = [s for s in doc_sents if REAL_CLAIM.search(s) and not NEG.search(s)]
        if real and src_text and REAL_CLAIM.search(src_text):
            look.append("模拟稿里有伦理批准或知情同意的说法，材料里也写了：核对说法与材料一致，不要补材料没有的细节（check_all SIM2）：%s" % real[0][:120])
        elif real and not src_text:
            look.append("模拟稿里有伦理批准或知情同意的说法；没有给 --results，无法和材料核对。把写有伦理信息的材料（分析笔记、研究方案）加进 --results 重跑（check_all SIM2）：%s" % real[0][:120])
        elif real:
            must.append("稿件里有真人研究才有的说法（伦理批准、知情同意），但 --results 给的文件里没有相应记录（check_all SIM3）：%s。先看是不是漏传了写有伦理信息的材料"
                        "（分析笔记、研究方案、任务说明）：有就加进 --results 重跑，不要删掉材料写明的事实；材料里确实没有，再删去或写成 [VERIFY: …]。"
                        "作者让你生成的模拟数据没有伦理审批可写。" % real[0][:120])
        ran.append(("模拟标识", "有" if SIM_MARK.search(text[:1500]) else "缺", "—"))

    # 8. 伦理批准号与注册号：稿件里出现的编号必须能在材料里找到
    ids = [m.group(1) for m in APPROVAL_ID.finditer(text) if re.search(r"\d", m.group(1)) and "VERIFY" not in m.group(0).upper()]
    ids += [m.group(1) for m in REGISTRY_ID.finditer(text)]
    for x in dict.fromkeys(ids):
        if src_text and x.lower() not in src_text.lower():
            must.append("稿件里的批准号或注册号“%s”在结果与材料文件里找不到：材料没有就写成 [VERIFY: …] 并列进作者说明，不能编（check_all ID1）。" % x)
        elif not src_text:
            look.append("核对批准号或注册号“%s”的出处（没有给 --results，无法比对材料；check_all ID2）。" % x)
    reg_neg = re.compile(r"\b(?:no|not|without|none|rather than|instead of)\b|无|未|不|没有|并非|而非|而不是", re.I)
    regs = [s for s in doc_sents if REG_CLAIM.search(s) and not reg_neg.search(s) and not REGISTRY_ID.search(s) and "VERIFY" not in s.upper()]
    if regs:
        (must if NOT_REG.search(src_text) else look).append("稿件说研究已注册或预注册，却没有注册号%s（check_all REG1）：%s" % (
            "，而材料写明未公开注册" if NOT_REG.search(src_text) else "；有就写上平台与编号，没有就改", regs[0][:140]))

    # 9. 口径限定：截断均值、换了分母的比率等，每次提到都要带限定
    if a.qualifiers:
        import csv as _csv
        with open(a.qualifiers, encoding="utf-8-sig", newline="") as f:
            qrows = [r for r in _csv.DictReader(f) if (r.get("values") or "").strip()]
        if not qrows:
            notrun.append("口径限定表为空或缺 values、requires 两列（--qualifiers）。")
        else:
            sents_all = []
            for b in M.parse(text):
                if b["kind"] in ("para", "caption"):
                    sents_all += [(b["sec"], x) for x in M.sentences(b["text"])]
            miss = []
            for q in qrows:
                vals = [v.strip() for v in q["values"].split("|") if v.strip()]
                req = [w.strip() for w in (q.get("requires") or "").split("|") if w.strip()]
                for i, (sec, x) in enumerate(sents_all):
                    if any(qual_hit(v, x) for v in vals):
                        ctx = x + " " + (sents_all[i - 1][1] if i else "")
                        if req and not any(w.lower() in ctx.lower() for w in req):
                            miss.append("%s：%s（%s）" % (q.get("label") or "/".join(vals), x[:140], sec))
            if miss:
                must.append("%d 句提到需要限定口径的数字却没带限定词（qualifiers Q1）：%s。在本句写明口径，例如“未掌握者按 40 天计”“分母是全部练习题”。"
                            % (len(miss), "；".join(miss[:4])))
            ran.append(("口径限定", "缺限定 %d 句" % len(miss), "—"))

    # 10. 文献证据阶梯：引文台账与作者说明里的说法
    if a.citations or a.note:
        args = [S("lit_evidence.py"), "check", "--text", ms] + ([a.note] if a.note else []) + ["--json", O("lit_evidence.json"), "--report", O("lit_evidence.md")]
        for flag, val in (("--ledger", a.citations), ("--execution", a.execution), ("--benchmark-mode", a.benchmark_mode),
                          ("--benchmark-report", a.benchmark_report), ("--benchmark-corpus", a.benchmark_corpus)):
            if val:
                args += [flag, val]
        code, so, se = run(args)
        if code == 2 or not os.path.exists(O("lit_evidence.json")):
            notrun.append("lit_evidence：%s" % (first_line(se) or first_line(so)))
        else:
            items = json.load(open(O("lit_evidence.json"), encoding="utf-8"))
            for it in items:
                must.append("%s（lit_evidence %s，%s）" % (it["msg"], it["code"], it["where"]))
            ran.append(("lit_evidence", "FAIL %d" % len(items), "lit_evidence.md"))
    if not a.execution:
        look.append("作者说明第一行写执行条件（EXECUTE / EXECUTE+NET / REASONING-ONLY）和可用工具；引文与对标的说法要与它相称（references/23；check_all EX1）。")

    # 11. 结果节：句子功能与小标题风格（results_function）。否定句不豁免，短的统计限定照常保留
    blocks_all = M.parse(text)
    eitems = []
    if a.expectations:
        try:
            with open(a.expectations, encoding="utf-8-sig") as f:
                _exp = json.load(f)
            eitems = [e for e in _exp.get("items", []) if isinstance(e, dict)]
        except (OSError, ValueError, AttributeError) as e:
            notrun.append("expectations：读不了用户要求登记表（%s）" % e)
    hs = a.heading_style or next((str(e.get("value") or "") for e in eitems if e.get("check") == "results_heading_style"), "")
    if hs not in ("", "object", "finding", "either"):
        notrun.append("expectations：results_heading_style 的 value 只能是 object、finding 或 either（现在是 %s）" % hs)
        hs = ""
    strict = any(e.get("check") == "results_function" and str(e.get("value", "")).lower() == "strict" for e in eitems)
    rf_codes, rf_ok = set(), False
    if any(b["sec"] == "results" and b["kind"] == "para" for b in blocks_all):
        args = [S("results_function.py"), ms, "--json", O("results_function.json"), "--report", O("results_function.md"), "--lang", a.lang]
        if hs:
            args += ["--heading-style", hs]
        if strict:
            args += ["--strict"]
        code, so, se = run(args)
        if code == 2 or not os.path.exists(O("results_function.json")):
            notrun.append("results_function：%s" % (first_line(se) or first_line(so) or "退出码 %d" % code))
        else:
            rf_ok = True
            with open(O("results_function.json"), encoding="utf-8") as f:
                rj = json.load(f)
            for it in rj.get("items", []):
                rf_codes.add(it["code"])
                ex = ("；例：" + it["examples"][0][:120]) if it.get("examples") else ""
                line = "%s（results_function %s）%s" % (it["msg"], it["code"], ex)
                if it["level"] == "MUST":
                    must.append(line)
                elif it["level"] == "SHOULD":
                    look.append(line)
            ran.append(("results_function", "MUST %d、SHOULD %d" % tuple(sum(i["level"] == k for i in rj.get("items", [])) for k in ("MUST", "SHOULD")), "results_function.md"))
    elif hs or strict:
        notrun.append("results_function：稿件里没有识别到结果节，登记的结果写法要求无法核对")

    # 12. 读者看到的用语与数字写法（display_terms）：表、图注、图内文字里不出现分析代码与内部分类值
    tabs = [p for p in a.displays if p.lower().endswith((".csv", ".tsv"))]
    figs = [p for p in a.displays if p.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".svg", ".pdf"))]
    legs = [p for p in a.displays if p not in tabs and p not in figs]
    args = [S("display_terms.py"), "scan", ms] + ([a.supplement] if a.supplement else [])
    for flag, vals in (("--tables", tabs), ("--legends", legs), ("--figures", figs)):
        if vals:
            args += [flag] + vals
    if a.terms:
        args += ["--terms", a.terms]
    code, so, se = run(args + ["--json", O("display_terms.json"), "--report", O("display_terms.md")])
    dt_must, dt_ok = 0, False
    if code == 2 or not os.path.exists(O("display_terms.json")):
        notrun.append("display_terms：%s" % (first_line(se) or first_line(so) or "退出码 %d" % code))
    else:
        dt_ok = True
        with open(O("display_terms.json"), encoding="utf-8") as f:
            dj = json.load(f)
        for it in dj.get("items", []):
            line = "%s（display_terms %s，%s）" % (it["msg"], it["code"], it.get("file", ""))
            if it["level"] == "MUST":
                must.append(line)
                dt_must += 1
            elif it["level"] == "SHOULD":
                look.append(line)
        notrun += ["display_terms：" + x for x in dj.get("notrun", [])]
        ran.append(("display_terms", "MUST %d、SHOULD %d、没能运行 %d" % (dt_must, sum(i["level"] == "SHOULD" for i in dj.get("items", [])), len(dj.get("notrun", []))), "display_terms.md"))
    if a.stage == "submission" and not a.displays:
        look.append("没有给 --displays：独立交付的表 CSV、图注和图片没有检查用语。投稿包里的每张表图都要过 display_terms（display_terms DT0）。")

    # 13. 文献覆盖（coverage_check）：该引的有没有引，与引文核实分开记账
    cv_open = None
    if a.coverage:
        args = [S("coverage_check.py"), ms, "--map", a.coverage, "--json", O("coverage.json"), "--report", O("coverage.md")]
        for flag, val in (("--neighbors", a.neighbors), ("--note", a.note), ("--stage", a.stage)):
            if val:
                args += [flag, val]
        code, so, se = run(args)
        if code == 2 or not os.path.exists(O("coverage.json")):
            notrun.append("coverage_check：%s" % (first_line(se) or first_line(so) or "退出码 %d" % code))
        else:
            with open(O("coverage.json"), encoding="utf-8") as f:
                cj = json.load(f)
            cv_open = cj.get("open_gaps", 0)
            for it in cj.get("items", []):
                (must if it["level"] == "MUST" else look).append("%s（coverage_check %s）" % (it["msg"], it["code"]))
            ran.append(("coverage_check", "未关闭缺口 %d、MUST %d" % (cv_open, sum(i["level"] == "MUST" for i in cj.get("items", []))), "coverage.md"))
    elif nref > 0:
        (must if a.stage == "submission" else look).append("有参考文献表，但没有文献覆盖表：引文逐条核实不等于该引的都引了。按 references/24 建 coverage_map.csv，加 --coverage 重跑（coverage CV0）。")

    # 14. 对标决策（benchmark_decisions.csv）：写法依据要落到具体近邻与位置，并绑定当前稿件
    bd_ok = False
    if a.benchmark_decisions:
        import csv as _csv2
        import hashlib as _hl
        with open(a.benchmark_decisions, encoding="utf-8-sig", newline="") as f:
            brows = [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in _csv2.DictReader(f)]
        with open(ms, "rb") as f:
            msha = _hl.sha256(f.read()).hexdigest()
        if not brows:
            notrun.append("对标决策表是空的：没有记录任何写法依据（benchmark BD0）")
        else:
            bd_ok = True
            thin = [r for r in brows if not (r.get("neighbor") and r.get("locator") and r.get("decision"))]
            unbound = [r for r in brows if (r.get("manuscript_sha256") or "").lower() != msha]
            if thin:
                must.append("对标决策表有 %d 行缺近邻、位置或决定：没有具体出处的“已对标”只是一句话（benchmark BD1）。例：%s" % (len(thin), thin[0].get("dimension") or "?"))
            if unbound:
                (must if a.stage == "submission" else look).append("对标决策表有 %d 行没有绑定当前稿件（当前指纹 %s…）：稿件改过后重新核对这些决定还成立，再写入新指纹（benchmark BD2）。" % (len(unbound), msha[:12]))
            has_sub = any(b["sec"] == "results" and b["kind"] == "heading" and M.classify_heading(b["text"]) != "results" for b in blocks_all)
            if has_sub and not any(r.get("dimension") == "results_headings" for r in brows):
                look.append("对标决策表没有 results_headings 这一维：结果小标题的风格依据没有记录（benchmark BD3）。")
            ran.append(("对标决策", "%d 行" % len(brows), "—"))
    elif a.stage == "submission":
        look.append("投稿阶段没有对标决策表：说不出结果小标题、段落职能等写法依据来自哪几篇近邻的哪一处（benchmark BD0）。")

    # 15. 用户明确要求（expectations）：登记后是硬回归项，其他检查通过不能抵消，也不能改记为偏好
    unmet, manual = [], []
    for e in eitems:
        ck = e.get("check", "manual")
        label = "%s %s" % (e.get("id", "?"), (e.get("text") or "")[:70])
        if ck in ("results_heading_style", "results_function"):
            bad = ("HS1" in rf_codes or "HS2" in rf_codes) if ck == "results_heading_style" else ("RF1" in rf_codes)
            if not rf_ok or bad:
                unmet.append(label + ("" if rf_ok else "（结果节检查没能运行）"))
        elif ck == "display_terms":
            if not dt_ok or dt_must:
                unmet.append(label + ("" if dt_ok else "（用语检查没能运行）"))
        elif ck == "coverage":
            if cv_open is None or cv_open:
                unmet.append(label + ("（没有运行覆盖检查）" if cv_open is None else "（未关闭缺口 %d）" % cv_open))
        else:
            manual.append(label + ("；要的证据：%s" % e["evidence_required"] if e.get("evidence_required") else ""))
    for u in unmet:
        must.append("用户明确要求未满足：%s。登记过的用户要求是硬回归项，其他检查通过不能抵消，也不能改记为偏好（expectations EX1）。" % u)
    if eitems:
        ran.append(("用户明确要求", "未满足 %d、需人工 %d" % (len(unmet), len(manual)), "—"))

    # 16. 体裁与节职能（genre_gate）：稿件读起来是不是这类期刊的研究论文，而不是实验说明或分析报告。
    #     数字、引文、用语全部通过时，这一维照样可能不合格；它不能被其他维度抵消（references/27）。
    gg_ok, gg_res = False, {}
    gargs = [S("genre_gate.py"), ms, "--stage", a.stage or "draft", "--json", O("genre_gate.json"), "--report", O("genre_gate.md")]
    for flag, val in (("--decisions", a.benchmark_decisions), ("--placement", a.placement), ("--memo", a.memo), ("--drill", a.drill), ("--concept", a.concept), ("--survey", a.survey)):
        if val:
            gargs += [flag, val]
    if a.neighbor_texts:
        gargs += ["--neighbor-texts"] + a.neighbor_texts
    if a.submitted:
        gargs += ["--submitted", a.submitted]
    if a.term_groups:
        gargs += ["--term-groups", a.term_groups]
    for flag, val in (("--moves", a.moves), ("--baseline", a.texture_baseline), ("--terms", a.study_terms)):
        if val:
            gargs += [flag, val]
    if a.texture_exemplars:
        gargs += ["--texture-exemplars"] + a.texture_exemplars
    code, so, se = run(gargs)
    if code == 2 or not os.path.exists(O("genre_gate.json")):
        notrun.append("genre_gate：%s" % (first_line(se) or first_line(so) or "退出码 %d" % code))
    else:
        with open(O("genre_gate.json"), encoding="utf-8") as f:
            gg_res = json.load(f)
        for it in gg_res.get("items", []):
            ex = ("；例：" + it["examples"][0][:120]) if it.get("examples") else ""
            line = "%s（genre_gate %s，%s）%s" % (it["msg"], it["code"], it["sec"], ex)
            if it["level"] == "MUST":
                must.append(line)
            elif it["level"] == "SHOULD":
                look.append(line)
        for x in gg_res.get("notrun", []):
            look.append("体裁门有一部分没能检查：%s（genre_gate GG0）" % x)
        gg_ok = True
        ran.append(("genre_gate", "MUST %d、SHOULD %d" % (gg_res.get("must", 0), gg_res.get("should", 0)), "genre_gate.md"))

    # 17. 概括位置的主张强度与文献概括（claim_strength）：题目、摘要、讨论首末段、结论最容易比结果说得强（references/22 §9）
    cs_ok = False
    cargs = [S("claim_strength.py"), ms, "--stage", a.stage or "draft", "--json", O("claim_strength.json"), "--report", O("claim_strength.md")]
    for flag, val in (("--concept", a.concept), ("--citations", a.citations)):
        if val:
            cargs += [flag, val]
    code, so, se = run(cargs)
    if code == 2 or not os.path.exists(O("claim_strength.json")):
        notrun.append("claim_strength：%s" % (first_line(se) or first_line(so) or "退出码 %d" % code))
    else:
        cs_ok = True
        with open(O("claim_strength.json"), encoding="utf-8") as f:
            cj2 = json.load(f)
        for it in cj2.get("items", []):
            line = "%s（claim_strength %s，%s）；例：%s" % (it["msg"], it["code"], it["where"], it["example"][:120])
            (must if it["level"] == "MUST" else look if it["level"] == "SHOULD" else []).append(line)
        ran.append(("claim_strength", "MUST %d、SHOULD %d" % (sum(i["level"] == "MUST" for i in cj2.get("items", [])), sum(i["level"] == "SHOULD" for i in cj2.get("items", []))), "claim_strength.md"))

    # 18. 派生量复算（derivation_check）：数字出现过不等于量纲说得通（references/22 §8）
    if a.derivations:
        code, so, se = run([S("derivation_check.py"), a.derivations, "--json", O("derivations.json"), "--report", O("derivations.md")])
        if code == 2 or not os.path.exists(O("derivations.json")):
            notrun.append("derivation_check：%s" % (first_line(se) or first_line(so) or "退出码 %d" % code))
        else:
            with open(O("derivations.json"), encoding="utf-8") as f:
                dj2 = json.load(f)
            for it in dj2.get("items", []):
                (must if it["level"] == "MUST" else look).append("%s（derivation_check %s，%s）" % (it["msg"], it["code"], it["id"]))
            ran.append(("derivation_check", "MUST %d、SHOULD %d" % (sum(i["level"] == "MUST" for i in dj2.get("items", [])), sum(i["level"] == "SHOULD" for i in dj2.get("items", []))), "derivations.md"))
    elif re.search(r"\bindirect effect|\bmediat\w+|\bper (?:one )?standard deviation|\bper SD\b|\bone-(?:third|quarter|fifth|sixth|seventh|tenth)\b|\b(?:twice|three times|half) (?:as|the)\b|converted|间接效应|中介|换算", text, re.I):
        (must if a.stage == "submission" else look).append("稿件里有派生量（间接效应、每标准差换算、比例说法……），没有登记公式、分量与单位并复算：建 derivations.csv，加 --derivations 重跑（derivation_check DV0）。")

    def _tag(lst, *tags):
        return any(any(t in x for t in tags) for x in lst)

    def _dim(tags, ran_ok, absent):
        if _tag(must, *tags):
            return "有必须处理项"
        if _tag(notrun, *tags):
            return "没能运行（不算通过）"
        return "机器未见问题" if ran_ok else absent
    dims = [("数字与出处", _dim(("number_trace", "qualifiers", "check_all ID", "check_all REG"), bool(a.results), "没检查（没给 --results）")),
            ("引文身份与说法记录", _dim(("ref_check", "lit_evidence"), True, "")),
            ("文献覆盖", _dim(("coverage",), cv_open is not None, "没检查（没给 --coverage）")),
            ("写法依据（对标决策）", _dim(("benchmark BD",), bd_ok, "没检查（没给 --benchmark-decisions）")),
            ("章节职能与结果写法", _dim(("section_lint", "density_check", "results_function"), True, "")),
            ("体裁与节职能", _dim(("genre_gate",), gg_ok, "没能运行")),
            ("主张强度与文献概括", _dim(("claim_strength",), cs_ok, "没能运行")),
            ("派生量复算", _dim(("derivation_check",), bool(a.derivations), "没检查（没给 --derivations）")),
            ("图表与正文用语", _dim(("display_terms",), dt_ok, "没能运行")),
            ("改稿融入（V、R）", ("有必须处理项" if _tag(must, "genre_gate RV") else "机器未见问题；读者视角需人工（RJ11）") if a.submitted else "没检查（返修或修订稿要给 --submitted）"),
            ("用户明确要求", "有未满足项" if unmet else ("需人工确认 %d 项" % len(manual) if manual else ("机器未见问题" if eitems else "未登记（没给 --expectations）"))),
            ("术语与理解前提", ("形式扫描完成（%d 个候选）；概念与依据需人工核查" % len(rr_res.get("items", []))) if rr_ok else "没能运行有效形式扫描；概念与依据需人工核查"),
            ("论证与讨论", "只能人工：隔离审稿与作者通读"),
            ("版式与渲染", "只能人工：导出后逐页看")]
    ok = not must and not notrun
    L = ["# 检查状态：%s" % os.path.basename(ms), "",
         "生成于 %s。原始报告在本目录。" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    if prev:
        L.insert(3, "上一轮的报告在 %s，没有覆盖。" % prev)
    if ok:
        L += ["**结论：可以交给作者通读。** 机器检查没有必须处理的问题；“需要看一眼”的条目在通读时顺手处理。", ""]
    else:
        L += ["**结论：还不能交给作者。** 必须先处理 %d 项%s。" % (len(must), "，另有 %d 项检查没能运行（不能算通过）" % len(notrun) if notrun else ""), ""]
    L += ["## 分维度状态", "", "| 维度 | 状态 |", "|---|---|"] + ["| %s | %s |" % d for d in dims] + ["",
          "上面的结论只针对机器能查的部分，不等于投稿就绪。任何一维有问题、没运行或需要人工而没做完，作者说明都不能写“投稿包备齐”。", ""]
    L += ["## 必须先处理（%d）" % len(must), ""] + ["%d. %s" % (i + 1, x) for i, x in enumerate(must)] + ([""] if must else ["没有。", ""])
    L += ["## 没能运行的检查（%d，不能算通过）" % len(notrun), ""] + ["- " + x for x in notrun] + ([""] if notrun else ["没有。", ""])
    L += ["## 需要看一眼（%d）" % len(look), ""] + ["- " + x for x in look[:15]]
    if len(look) > 15:
        L.append("- 其余 %d 条见各工具的原始报告。" % (len(look) - 15))
    L += ["", "## 已运行的检查", "", "| 检查 | 结果 | 报告 |", "|---|---|---|"] + ["| %s | %s | %s |" % r for r in ran]
    L += ["", "## 机器查不了、需要人看的", "",
          "- 到目的、预测或解释依赖术语时，读者是否已理解名称、含义与测量依据；形式扫描不能证明这些已通过；",
          "- 论证是否成立，讨论的解释是否有支持；",
          "- 读起来像不像这类期刊的研究论文：体裁备忘、近邻逐节对照与 reviewer_genre（genre_gate 只认形式）；",
          "- 引文是否真的支持所在句（脚本只核对得上，不核引得对）；",
          "- 图表渲染后是否好读；",
          "- 作者才知道的事实：伦理、利益冲突、资助、作者贡献、是否一稿多投。", ""]
    if manual:
        L += ["## 用户要求中只能人工确认的（%d）" % len(manual), ""] + ["- " + x for x in manual] + [""]
    with open(O("STATUS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    summary = {"manuscript": os.path.basename(ms), "generated": datetime.datetime.now().isoformat(timespec="seconds"),
               "exit": 0 if ok else 1, "out": os.path.abspath(out), "previous": os.path.abspath(prev) if prev else "",
               "options": {"design": a.design, "simulation": a.simulation, "lang": a.lang, "results": len(a.results), "allow": bool(a.allow),
                           "qualifiers": bool(a.qualifiers), "citations": bool(a.citations), "note": bool(a.note),
                           "profile": os.path.basename(a.profile) if a.profile else "", "domain": os.path.basename(a.domain.rstrip("/\\")) if a.domain else "",
                           "execution": a.execution, "benchmark_mode": a.benchmark_mode},
               "dimensions": dict(dims), "expectations": {"unmet": unmet, "manual": manual},
               "genre": {"must": gg_res.get("must"), "should": gg_res.get("should"), "waived": gg_res.get("waived", []), "metrics": gg_res.get("metrics", {})},
               "reader_readiness": {"scan_completed": rr_ok, "candidates": len(rr_res.get("items", [])), "semantic_status": "not_automatically_assessed"},
               "must": coded(must), "notrun": coded(notrun), "look": coded(look), "ran": [list(r) for r in ran]}
    with open(O("summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print("%s 必须先处理 %d 项；没能运行 %d 项；需要看一眼 %d 项。详见 %s" % ("可以交给作者通读。" if ok else "还不能交给作者。", len(must), len(notrun), len(look), O("STATUS.md")))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
