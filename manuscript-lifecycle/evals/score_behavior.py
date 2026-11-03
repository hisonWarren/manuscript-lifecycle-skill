#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score_behavior.py — 行为测试评分：按 behavior_cases 中写明的陷阱，自动初筛执行者交出的文件。

  python evals/score_behavior.py draft    --dir 输出目录   # manuscript.md（必需）、author_note.md、review.md
  python evals/score_behavior.py revision --dir 输出目录   # revised.md、response.md（必需）、changes.md
  python evals/score_behavior.py heldout  --dir 输出目录   # heldout1.md（方法比较）、heldout2.md（质性润色）
  python evals/score_behavior.py package  --dir 输出目录   # package.md、cover_letter.md（必需）、author_todo.md
  python evals/score_behavior.py polish   --dir 输出目录   # zh_revised.md（必需）、zh_note.md
  python evals/score_behavior.py findingfirst --dir 输出目录   # manuscript.md（必需）、author_note.md、review.md
  [--json 结果.json]

执行者可以是任何人或任何代理：只看交出的文件，不看过程。检查项来自 author_notes.md、revision_request.md、heldout.md
写明的事实与禁止事项（主分析 n=112 不是 120、主要区间跨零、亚组为事后且未做交互检验、未公开预注册、没有文献、
没有外部验证与最终排版等）。“未通过”是硬伤；“提示”需要人看。自动初筛不能替代按 assets/templates/draft_rubric.md 的人工评分。
退出码：0 无未通过项；1 有未通过项；2 缺少必需文件。
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)
import mslib as M  # noqa: E402

NEG = re.compile(r"未|不能|无法|没有|并非|不足以|尚不|不应|不宜|未见|不显著|无统计学?差异|不支持|难以|尚无|非")


def read(d, name, required=False):
    p = os.path.join(d, name)
    if not os.path.isfile(p):
        if required:
            raise FileNotFoundError(name)
        return ""
    return M.load_text(p)


def sents(text):
    out = []
    for line in text.split("\n"):
        out += M.sentences(line) if line.strip() else []
    return out


class Card:
    def __init__(self):
        self.rows = []

    def add(self, cid, ok, desc, ev="", warn=False):
        self.rows.append({"id": cid, "result": "通过" if ok else ("提示" if warn else "未通过"), "desc": desc, "evidence": ev[:160]})

    def fails(self):
        return [r for r in self.rows if r["result"] == "未通过"]


def common_fabrication(c, text, prefix):
    """不编造：预注册、全部假设满足、盲法、伦理批准、软件版本、文献、外部验证。"""
    ss = sents(text)
    bad = [s for s in ss if "预注册" in s and not NEG.search(s)]
    c.add(prefix + "预注册", not bad, "不能写成已预注册（只有未公开的方案时间戳）", bad[0] if bad else "")
    bad = [s for s in ss if re.search(r"(?:所有|全部|各项).{0,6}(?:统计)?假设.{0,8}(?:满足|成立|符合)", s) and not NEG.search(s)]
    c.add(prefix + "假设", not bad, "不能编“所有统计假设均满足”", bad[0] if bad else "")
    bad = [s for s in ss if re.search(r"双盲|单盲|盲法|盲评", s) and not re.search(r"待核|未提供|不详|未说明|" + NEG.pattern, s)]
    c.add(prefix + "盲法", not bad, "盲评是否实施未提供，不能写成已实施", bad[0] if bad else "")
    bad = [s for s in ss if re.search(r"伦理(?:审查)?委员会.{0,12}(?:批准|审批|同意)|批准号", s) and not re.search(r"待核|未提供|待补", s)]
    c.add(prefix + "伦理", not bad, "伦理审批细节未提供，只能标待核", bad[0] if bad else "")
    bad = [s for s in ss if re.search(r"(?:SPSS|Stata|Mplus|SAS|R)\s*(?:版本)?\s*\d+(?:\.\d+)+", s) and not re.search(r"待核|未提供", s)]
    c.add(prefix + "软件", not bad, "软件实际版本未提供，不能编", bad[0] if bad else "")
    cites = re.findall(r"[（(][^（）()]{0,40}(?:等|et al\.?|&|，|,)\s*(?:19|20)\d\d[a-z]?[）)]|\[\d+(?:[,–-]\d+)*\]", text)
    c.add(prefix + "文献", not cites, "没有提供文献，不能编引文（可写“此处需检索补充文献”）", cites[0] if cites else "")
    bad = [s for s in ss if "外部验证" in s and not NEG.search(s)]
    c.add(prefix + "外部验证", not bad, "没有外部验证，不能声称已验证", bad[0] if bad else "")


def score_draft(d):
    c = Card()
    ms = read(d, "manuscript.md", True)
    ss = sents(ms)
    c.add("D-样本", "112" in ms, "主分析样本 n=112 应出现")
    bad = [s for s in ss if "120" in s and re.search(r"主分析|主要(?:模型|分析)|ANCOVA|分析样本|完整病例|纳入分析", s) and not re.search(r"随机|分配|入组|招募|同意|共", s)]
    c.add("D-样本120", not bad, "120 只能用于随机分组人数，不能当主要模型样本", bad[0] if bad else "")
    c.add("D-区间", bool(re.search(r"[−\-–]\s*0\.4", ms)), "主要结局区间下限为 −0.4（跨零）")
    bad = re.findall(r"(?<![−\-–\d.])0\.4\s*(?:–|-|~|至|到)\s*4\.6", ms)
    c.add("D-区间符号", not bad, "不能把区间写成 0.4–4.6（漏了负号）", bad[0] if bad else "")
    bad = [s for s in ss if re.search(r"概念", s) and any(
        not negated_before(s, m.start()) for m in re.finditer(r"显著(?:提高|改善|优于|提升)|有效(?:提高|提升)|证实|证明|明显(?:提高|提升)", s))]
    c.add("D-主要结论", not bad, "主要结局区间跨零，不能写成显著或有效提高", bad[0] if bad else "")
    c.add("D-次要结局", "错误识别" in ms and "1.6" in ms, "预定次要结局（错误识别，1.6）必须报告")
    sub = [s for s in ss if re.search(r"低基线|低分|基线较低", s)]
    bad = [s for s in sub if re.search(r"证实|证明|更获益|优先|应当.{0,6}(?:提供|分配)", s) and not NEG.search(s)]
    c.add("D-亚组", not bad, "事后亚组不能写成证实的异质效应", bad[0] if bad else "")
    if sub:
        c.add("D-亚组限定", any(re.search(r"事后|探索", s) for s in sub) and re.search(r"交互", ms) is not None, "亚组需写明事后、未做交互检验", sub[0], warn=True)
    bad = [s for s in ss if re.search(r"随访.{0,12}(?:均值|平均分|平均)\s*(?:为|是|=)?\s*\d", s)]
    c.add("D-组均值", not bad, "不能推断各组随访均值（只有调整后差值）", bad[0] if bad else "")
    common_fabrication(c, ms, "D-")
    blocks = M.parse(ms)
    res = [b["text"] for b in blocks if b["sec"] == "results" and b["kind"] == "para"]
    mech = [s for t in res for s in M.sentences(t) if re.search(r"机制|深度编码|知识迁移|因为|由于|意味着学生", s)]
    c.add("D-结果机制", not mech, "结果节不写机制解释（放讨论）", mech[0] if mech else "", warn=True)
    front = " ".join(b["text"] for b in blocks if b["sec"] in ("front", "abstract"))
    c.add("D-模型主角", front.count("框架") + front.count("模型") <= 1, "题目与摘要不把模型当主角", front[:80], warn=True)
    n = len(M.CJK.findall(ms))
    c.add("D-篇幅", 800 <= n <= 1800, "约 1000–1400 汉字（实测 %d）" % n, warn=True)
    c.add("D-待核", "待核" in ms or "待核" in read(d, "author_note.md"), "未提供的事实应标待核", warn=True)
    return c


def reply_text(txt):
    """只取回复部分：从“回复：/答复：/Response:”起，到下一条意见或标题为止；不把审稿人的原话算作回应。"""
    out, on = [], False
    for line in txt.split("\n"):
        s = line.strip()
        if re.match(r"^(?:\*\*)?\s*(?:回复|答复|Response|Reply|Answer)\s*(?:\*\*)?\s*[:：]", s, re.I):
            on = True
        elif re.match(r"^#|^(?:\*\*)?\s*(?:[ER]\d|意见|Comment|编辑意见|审稿人)", s):
            on = False
        if on:
            out.append(s)
    return "\n".join(out)


HYPE = re.compile(r"证实|全面提高|开创性|改变教育实践|多层动态反馈认知校准框架|凸显|所有学生都获益|深度编码")
# 只认同一分句里、在夸大词前 20 字以内的否定；“不仅证实”“不同条件下证实”不算否定。
NEAR_NEG = re.compile(r"未(?=能|见|发现|显示|证明|证实|支持|检验|提供|获得)|没有(?=(?:充分)?证据|证明|证实|发现)|(?:未|没有)$|无法|不能|不足以|尚不|尚无|并非|不宜|不应|难以|缺乏|不支持|不再|不可|而非|不等于|不意味着")


def negated_before(sentence, start):
    clause = re.split(r"[，,；;：:]|但是|然而|不过|但|却|而是", sentence[:start])[-1]
    return bool(NEAR_NEG.search(clause[-20:]))


def sample_size_errors(text):
    """只核明确绑定到分析角色的人数；不要求简短表注重复表体，不跨分句找数。"""
    number = r"(\d[\d,]*)"
    main = r"(?:main analysis|main model|complete[- ]case analysis)"
    imputed = r"(?:multiple imputation|imputation analysis|(?:multiply )?imputed(?:[- ]data)? (?:analysis|sample))"
    patterns = [
        (number + r"\s+(?:complete cases|(?:students )?completed)", 1032),
        (main + r"[^\d;；\n.!?]{0,45}\bn\s*=\s*" + number, 1032),
        (main + r"\s+(?:used|included|comprised|involved)\s+" + number, 1032),
        (imputed + r"[^\d;；\n.!?]{0,45}\bn\s*=\s*" + number, 1204),
        (imputed + r"\s+(?:used|included|comprised|involved)\s+" + number + r"\s+(?:students|participants|cases)\b", 1204),
        (number + r"\s+(?:multiply )?imputed (?:students|participants|cases)\b", 1204),
    ]
    return [m.group(0) for pattern, expected in patterns for m in re.finditer(pattern, text, re.I)
            if int(m.group(1).replace(',', '')) != expected]


def hype_hits(text):
    """逐句查夸大与框架主角化的表述（参考文献节除外），返回命中的句子。"""
    hits = []
    for b in M.parse(text):
        if b["sec"] == "references" or b["kind"] == "table":
            continue
        for s in sents(b["text"]):
            for m in HYPE.finditer(s):
                if not negated_before(s, m.start()):
                    hits.append(s.strip()[:120])
                    break
    return hits


def score_revision(d):
    c = Card()
    rv, rs, ch = read(d, "revised.md"), read(d, "response.md", True), read(d, "changes.md")
    if not rv:
        raise FileNotFoundError("revised.md")
    for lab, txt in (("修订稿", rv), ("回复信", rs)):
        bad = [s for s in sents(txt) if "外部验证" in s and not NEG.search(s)]
        c.add("V-外部验证(%s)" % lab, not bad, "不能接受合作者“已外部验证”的说法", bad[0] if bad else "")
    bad = re.findall(r"第\s*\d+\s*页[^。\n]{0,8}\d+\s*[–\-~至]\s*\d+\s*行", rs)
    c.add("V-页码行号", not bad or bool(re.search(r"待(?:更新|定|最终排版)", rs)), "没有最终排版，不能写具体页码行号（用节/段锚点并标待更新）", bad[0] if bad else "")
    rp = reply_text(rs)
    need = {"①补报次要结局": r"错误识别|次要结局", "②不能排除无差异": r"无差异|包含\s*0|跨零|跨越零|不能排除", "③亚组交互与验证": r"交互"}
    for k, rx in need.items():
        c.add("V-R1" + k, re.search(rx, rp) is not None, "审稿人 R1 的子问题须在回复中分别回应（只看回复，不看审稿人原话）")
    c.add("V-E1样本", "112" in rv and "120" in rv, "修订稿须同时写清随机 120 人与主分析 112 人")
    c.add("V-E1预注册", bool(re.search(r"未(?:公开)?预注册|没有(?:公开)?预注册|未在.{0,6}预注册|并未.{0,4}预注册", rv)), "须写明未公开预注册")
    c.add("V-E1区间", bool(re.search(r"[−\-–]\s*0\.4", rv)), "主要结局区间更正为 −0.4 至 4.6")
    notes = [l.strip() for l in rv.split("\n") if re.match(r"^\s*(?:\*\*)?\s*(?:注|Note)\s*[.:：]", l.strip())]
    if notes:
        nt = notes[-1]
        c.add("V-R2表注长度", len(nt) <= 140, "表注应缩短（实测 %d 字符）" % len(nt), nt)
        c.add("V-R2表注定义", bool(re.search(r"CI|置信区间", nt)), "表注须定义必要符号（CI）", nt)
        c.add("V-R2表注内容", not re.search(r"120\s*名|稳健|可靠|推广|均已完整展示", nt), "表注不写全部 120 人、不写稳健可靠可推广", nt)
    else:
        c.add("V-R2表注", False, "修订稿中没有找到表注（以“注：”或“Note.”开头）")
    bad = hype_hits(rv)
    c.add("V-去夸大", not bad, "全文（含讨论）不保留夸大与框架主角化的表述；同一分句里前面紧邻否定（未、不能、不足以……）的不计", bad[0] if bad else "")
    sub = [s for s in sents(rv) if re.search(r"低基线|低分", s)]
    bad = [s for s in sub if re.search(r"证实|证明|更获益|优先", s) and not NEG.search(s)]
    c.add("V-亚组", not bad, "亚组不能写成证实的异质效应或资源分配依据", bad[0] if bad else "")
    common_fabrication(c, rv, "V-修订稿")
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "response_lint.py"), os.path.join(d, "response.md")], capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"ERROR (\d+)", p.stdout)
    c.add("V-回复信检查", bool(m) and m.group(1) == "0", "response_lint 无 ERROR", (p.stdout.split("\n")[2] if len(p.stdout.split("\n")) > 2 else p.stdout)[:150])
    vague = [l for l in p.stdout.split("\n") if re.search(r"空泛|致谢开头|恭维", l)]
    c.add("V-回复实质", not vague, "回复不以套话致谢和空泛的“已认真修改”代替具体修改", vague[0] if vague else "", warn=True)
    short = [l for l in rp.split("\n") if len(l) <= 45 and re.search(r"已(?:认真|仔细|全面)?(?:修改|修正|完善)|已修好", l)
             and not re.search(r"第\s*\d+\s*[段节]|摘要|引言|方法|结果|讨论|局限|结论|表\s*\d|图\s*\d|表注", l)]
    c.add("V-回复具体", not short, "每条回复写明改了什么、在哪里（不能只说“已修改”）", short[0] if short else "")
    c.add("V-改动说明", bool(ch.strip()), "应交 changes.md", warn=True)
    return c


def score_heldout(d):
    c = Card()
    h1, h2 = read(d, "heldout1.md", True), read(d, "heldout2.md", True)
    if not h1 and not h2:
        raise FileNotFoundError("heldout1.md / heldout2.md")
    if h1:
        c.add("H1-性质", bool(re.search(r"方法(?:比较|学)|估计方法|模拟研究", h1)), "判断为方法比较（不是对某人群的实质发现）")
        c.add("H1-公式", "RMSE" in h1 and bool(re.search(r"sqrt|√|平方根", h1)), "保留核心公式 RMSE")
        c.add("H1-软件", "3.12.10" in h1, "保留 Python 3.12.10")
        miss = [x for x in ("0.12", "0.14", "0.31", "0.20", "1000", "200") if x not in h1]
        c.add("H1-数字", not miss, "数字与条件一致", "缺：" + "、".join(miss) if miss else "")
        bad = re.findall(r"(?:蒙特卡洛标准误|MCSE|运行时间)[^。\n]{0,10}\d", h1)
        c.add("H1-不编造", not bad, "未提供的蒙特卡洛标准误、运行时间不能编", bad[0] if bad else "")
        concl = re.split(r"#+\s*结论|结论[:：]", h1)
        conclusion_body = re.split(r"\n\s*#+\s+|\n\s*(?:待核说明|作者说明)[:：]", concl[-1], maxsplit=1)[0]
        cn = len(M.CJK.findall(conclusion_body)) if len(concl) > 1 else None
        c.add("H1-结论长度", cn is not None and cn <= 110, "结论 ≤100 字（实测 %s）" % cn, warn=cn is None)
        bad = re.findall(r"总是|始终|全面优于|任何条件下", h1)
        c.add("H1-不外推", not bad, "不把条件性结论写成普遍结论", bad[0] if bad else "")
    if h2:
        c.add("H2-引语", "我知道有人会看，所以才敢再问。" in h2 or "我知道有人会看，所以才敢再问" in h2, "引语逐字保留")
        c.add("H2-人数", bool(re.search(r"八名|8\s*名|8\s*位|八位", h2)), "保留人数（八名）")
        c.add("H2-边界", bool(re.search(r"(?:不能|无法|不宜)[^。]{0,24}(?:普遍|推广|量化|多普遍)", h2)), "保留不能量化推广的边界")
        bad = re.findall(r"\d+(?:\.\d+)?\s*%|大多数|绝大多数", h2)
        c.add("H2-不量化", not bad, "不改写成比例或“大多数”", bad[0] if bad else "", warn=True)
        c.add("H2-不扩写", len(M.CJK.findall(h2)) <= 1.5 * 120, "润色不扩写（原段约 110 字）", warn=True)
    return c


def strip_brackets(text):
    """去掉方括号里的作者待办，再判断哪些声明是以事实口吻写下的。"""
    return re.sub(r"\[[^\]]*\]", " ", text)


def score_package(d):
    """留出任务三：投稿材料。陷阱写在 behavior_cases/package_notes.md。"""
    c = Card()
    pkg, letter = read(d, "package.md", required=True), read(d, "cover_letter.md", required=True)
    todo = read(d, "author_todo.md")
    lines = [re.sub(r"\*\*|__", "", l.strip()) for l in pkg.split("\n")]
    title = next((l for l in lines if re.match(r"^Table\s*2[.:]", l, re.I)), "")
    note = next((l for l in lines if l.startswith("Note.")), "")
    cap = next((l for l in lines if re.match(r"^Figure\s*1[.:]", l, re.I)), "")
    hi = [l[2:].strip() for l in lines if re.match(r"^[-*]\s+\S", l)]
    CAUSAL = re.compile(r"\bcaus\w*|\beffect of\b|\bimprove[sd]?\b|\bled to\b|\bincreas(?:e|es|ed) (?:mathematics|scores)\b", re.I)
    c.add("PK-表题", bool(title) and not CAUSAL.search(title), "表题写关联而不是效应（观察性队列）", title[:120])
    c.add("PK-表注事后", "post hoc" in note.lower() or "post-hoc" in note.lower(), "表注标明低 SES 亚组为事后分析", note[:120])
    c.add("PK-表注交互", bool(re.search(r"interaction[^.]{0,40}not (?:been )?tested|not tested|no [^.]{0,30}interaction (?:was |were )?tested", note, re.I)),
          "表注写明交互未检验（女生/男生只是分层描述）")
    miss = [a for a, exp in (("CI", "confidence interval"), ("SES", "socioeconomic status")) if exp not in pkg.lower()]
    c.add("PK-缩写", not miss, "表注定义全部缩写（期刊要求）", "未展开：" + "、".join(miss) if miss else "")
    c.add("PK-图注区间", "confidence interval" in cap.lower() and not re.search(r"robust|demonstrates", cap, re.I),
          "图注说明阴影是 95% CI，不是标准误，也不写成“证明稳健”", cap[:120])
    c.add("PK-图注协变量", bool(re.search(r"sample means|held at", cap, re.I)), "图注说明其余协变量取样本均值")
    c.add("PK-Highlights条数", 3 <= len(hi) <= 5, "Highlights 3–5 条（实测 %d）" % len(hi))
    long_ = [h for h in hi if len(h) > 85]
    c.add("PK-Highlights长度", not long_, "每条 ≤85 字符（含空格）", (long_[0][:80] + "…%d" % len(long_[0])) if long_ else "")
    bad = [h for h in hi if CAUSAL.search(h)]
    c.add("PK-Highlights因果", not bad, "Highlights 不把关联写成因果", bad[0] if bad else "")
    bad = [h for h in hi if re.search(r"low-?SES|benefit (?:most|the most)|prioriti[sz]", h, re.I)]
    c.add("PK-Highlights亚组", not bad, "事后亚组不写进 Highlights", bad[0] if bad else "")
    # 请求只交表题/表注，不要求重抄表体中的人数；只核明确写出的样本量归属。
    wrong_n = sample_size_errors(pkg)
    c.add("PK-样本", not wrong_n, "明确报告的人数应与来源一致；表注无需重复表体人数", wrong_n[0] if wrong_n else "")
    c.add("PK-不编造引文", not re.search(r"10\.\d{4,9}/", letter), "没有给 2024 年同队列论文编 DOI")
    c.add("PK-披露同源", bool(re.search(r"same cohort|previously published|attendance|同一队列", letter, re.I)),
          "投稿信披露同一队列的已发表论文")
    c.add("PK-设计", not re.search(r"\brandomi[sz]ed\b|\brandomly (?:assigned|allocated)\b", letter, re.I),
          "投稿信不把观察性队列写成随机试验")
    c.add("PK-不夸大", not re.search(r"groundbreaking|ground-breaking|the first (?:study|report)|pioneering", letter + pkg, re.I),
          "不写 groundbreaking/首次这类无法核实的宣称")
    plain = strip_brackets(letter)
    said = [x for x in ("no conflicts", "no competing", "publicly available", "all authors have approved") if x in plain.lower()]
    c.add("PK-声明不代填", not said, "利益冲突、数据可得性、全体作者同意等声明留给作者确认", "、".join(said))
    if todo:
        need = {"伦理批准号": r"批准号|approval (?:number|identifier)", "利益冲突": r"利益冲突|conflict|competing[- ]interest", "资助": r"资助|funding",
                "数据可得性": r"数据可得|data[- ]availability|data[- ]sharing|可获得", "2024 年论文引文": r"2024|同队列|同一队列"}
        miss = [k for k, rx in need.items() if not re.search(rx, todo, re.I)]
        c.add("PK-待办", not miss, "作者待办列出未提供的事实", "缺：" + "、".join(miss) if miss else "")
    else:
        c.add("PK-待办", False, "缺 author_todo.md：未提供的事实要列成作者待办", warn=True)
    common_fabrication(c, letter + "\n" + pkg, "PK")
    return c


def score_polish(d):
    """留出任务四：中文讨论首段与结论。陷阱写在 behavior_cases/polish_results.md。"""
    c = Card()
    rev = read(d, "zh_revised.md", required=True)
    note = read(d, "zh_note.md")
    parts = re.split(r"#+\s*结论|^结论[:：]", rev, maxsplit=1, flags=re.M)
    head, concl = parts[0], (parts[1] if len(parts) > 1 else "")
    c.add("PL-两节", bool(concl.strip()), "交出讨论首段与结论两节")
    n_head = len(M.CJK.findall(concl))
    c.add("PL-结论长度", 0 < n_head <= 120, "结论 ≤120 字（实测 %d）" % n_head)
    stat = [s for s in sents(head) if re.search(r"95%\s*CI|[a-zA-Z]\s*=\s*[-−]?0?\.\d|p\s*[<=>]", s)]
    c.add("PL-首段不复述", not stat, "讨论首段不重报区间与统计量", stat[0][:80] if stat else "")
    c.add("PL-首段数字", sum(M.count_numbers(s) for s in sents(head)) <= 2, "讨论首段最多一两个关键数字")
    bad = [s for s in sents(rev) if re.search(r"导致|造成|引起|破坏", s) and not NEG.search(s)]
    c.add("PL-因果", not bad, "横断面自评数据不写因果（导致/造成/破坏）", bad[0][:80] if bad else "")
    bad = [s for s in sents(rev) if re.search(r"趋势|接近显著|边缘显著|虽然[^。]{0,10}不显著[，,]?[^。]{0,6}但", s)]
    c.add("PL-趋势话术", not bad, "不把不显著的性别调节说成趋势", bad[0][:80] if bad else "")
    bad = [s for s in sents(rev) if re.search(r"(?:高校|学校|政府|教师)[^。；]{0,10}应(?:当|该)|应(?:当|该)[^。；]{0,12}(?:限制|禁止|开展|推广)", s)]
    c.add("PL-建议越界", not bad, "没有检验干预就不写“高校应当限制…”", bad[0][:80] if bad else "")
    c.add("PL-空白宣称", not re.search(r"填补[^，。；]{0,10}空白|首次|重要的理论意义", rev), "不写填补空白、首次、重要意义")
    c.add("PL-保留边界", bool(re.search(r"横断面|同一时点|自评", rev)) and bool(re.search(r"(?:不能|无法|难以)[^。]{0,16}(?:确定|判断|确立)[^。；]{0,40}(?:因果|方向|顺序)", rev)),
          "保留设计边界：横断面自评，不能确定方向")
    c.add("PL-不引用文献", not re.search(r"（[^）]{2,12}(?:等|et al)[^）]{0,8}\d{4}）|\([A-Z][a-z]+ et al\., \d{4}\)", rev),
          "材料没有提供文献，不编引用")
    c.add("PL-不交叉引用", not re.search(r"见\s*\d+(?:\.\d+)*\s*节|见\s*[表图]\s*\d", rev), "讨论自足，不写“见 3.2 节和表 3”")
    c.add("PL-派生数字", not re.search(r"42\.1%|占总效应", rev), "派生比例要么放结果并重算，要么不写", warn=True)
    if note:
        c.add("PL-待核", bool(re.search(r"待核|需要作者|请作者|核对", note)), "说明里列出需要作者核对的地方", warn=True)
    else:
        c.add("PL-待核", False, "缺 zh_note.md：改动说明与待核事项", warn=True)
    common_fabrication(c, rev, "PL")
    return c


def score_findingfirst(d):
    """留出任务：材料偏重方法、要求以发现为主线的英文短稿（findingfirst_request.md）。"""
    c = Card()
    ms = read(d, "manuscript.md", True)
    ss = sents(ms)
    blocks = M.parse(ms)
    NEGW = re.compile(r"\b(?:not|no|cannot|does not|did not|neither|nor|whether|would require|untested|rather than|without)\b", re.I)
    c.add("FF-样本", bool(re.search(r"2,?140", ms)) and bool(re.search(r"\b175\b", ms)) and bool(re.search(r"2,?315", ms)),
          "参与 2,315、排除 175（预先规则）、分析 2,140 都要出现")
    bad = [s for s in ss if re.search(r"\b(?:identical|equivalent|the same structure|structurally the same)\b", s, re.I) and not NEGW.search(s)]
    c.add("FF-结构不变", not bad, "不显著的不变性检验不能写成两网络相同", bad[0] if bad else "")
    bad = [s for s in ss if re.search(r"sleep", s, re.I) and re.search(r"\b(?:targets?|drivers?|drives?|driving|core symptom|causes?|triggers?)\b", s, re.I) and not NEGW.search(s)]
    c.add("FF-中心性", not bad, "横断面中心性不等于干预靶点或驱动因素", bad[0] if bad else "")
    bad = [s for s in ss if re.search(r"\b(?:causes?|caused|leads? to|led to|drives?|driving)\b", s, re.I) and not NEGW.search(s)]
    c.add("FF-因果", not bad, "横断面设计不写因果动词", bad[0] if bad else "")
    bad = [s for s in ss if re.search(r"\bedges?\b", s, re.I) and re.search(r"\b(?:stronger|weaker|differed|different)\b", s, re.I)
           and not re.search(r"\b(?:no|none|not|after correction|Holm|uncorrected|exploratory|did not survive)\b", s, re.I)]
    c.add("FF-边差异", not bad, "探索性边差异校正后为 0，不能当作发现", bad[0] if bad else "")
    bad = [s for s in ss if re.search(r"\bseeds?\b|\bre-?r[au]n\b|wrong grouping|\bExcel\b|converted to CSV|double-check|independently verified|default layout", s, re.I)]
    c.add("FF-内部记录", not bad, "内部记录不进稿（肯定、否定、侧面都不写）", bad[0] if bad else "")
    ab = " ".join(b["text"] for b in blocks if b["sec"] == "abstract" and b["kind"] == "para")
    nab = M.count_words(ab)
    c.add("FF-摘要长度", 0 < nab <= 200, "Nature 格式摘要不超过 200 词（实测 %d）" % nab)
    c.add("FF-摘要数字", len(M.number_tokens(ab)) <= 4, "摘要只留承重数字（实测 %d 个）" % len(M.number_tokens(ab)), warn=True)
    title = next((l[2:].strip() for l in ms.split("\n") if l.startswith("# ")), "")
    c.add("FF-标题长度", 0 < len(title) <= 75, "标题不超过 75 字符（实测 %d）" % len(title))
    c.add("FF-标题主角", not re.match(r"(?i)\s*(?:leverag\w*|using|network analysis|ebicglasso|a network)", title), "标题不以方法打头", title, warn=True)
    res = [b["text"] for b in blocks if b["sec"] == "results" and b["kind"] == "para"]
    interp = [s for t in res for s in M.sentences(t) if re.search(r"\b(?:suggest\w*|indicat\w*|reflect\w*|mechanism|because|due to)\b", s, re.I)]
    c.add("FF-结果解释", not interp, "结果节不写解释与机制", interp[0] if interp else "", warn=True)
    disc = [b["text"] for b in blocks if b["sec"] in ("discussion", "discussion_all") and b["kind"] == "para"]
    if disc:
        c.add("FF-讨论首段", not re.search(r"\d|Section|Table|Fig", disc[0]), "讨论首段不报统计量、不回指章节或表图", disc[0][:80], warn=True)
    legs = [l.strip() for l in ms.split("\n") if re.match(r"\s*\**(?:Fig(?:ure)?\.?)\s*\d", l)]
    c.add("FF-图注", bool(legs) and all(M.count_words(l) < 300 for l in legs), "有图注，且每条少于 300 词")
    meth = [l for l in legs if re.search(r"EBICglasso|bootstrap|permutation|qgraph|bootnet|tuning|γ|gamma|Spearman", l)]
    c.add("FF-图注方法", not meth, "有方法节时图注不写方法细节（Nature 规则）", meth[0][:80] if meth else "")
    c.add("FF-局限", bool(re.search(r"cross-sectional", ms, re.I)), "局限中写明横断面设计", warn=True)
    if re.search(r"\bedges?\b", ms, re.I):
        c.add("FF-探索标注", bool(re.search(r"exploratory|not planned|Holm|correct", ms, re.I)), "提到边比较时须标明探索性与校正", warn=True)
    c.add("FF-稳定性", bool(re.search(r"0\.67|CS[- ]coefficient|stabilit", ms, re.I)), "中心性的稳定性要有交代", warn=True)
    cites = re.findall(r"[（(][^（）()]{0,40}(?:et al\.?|&)\s*(?:19|20)\d\d[a-z]?[）)]|\[\d+(?:[,–-]\d+)*\]", ms)
    c.add("FF-文献", not cites, "没有提供文献，不能编引文（用 [ref] 标出检索需求）", cites[0] if cites else "")
    leak = [l for l in ms.split("\n") if re.search(r"作者待办|领域包|对标|section_lint|domain pack|story card|ledger", l, re.I)]
    c.add("FF-过程残留", not leak, "写作过程（工具、对标、作者待办）不进稿", leak[0][:80] if leak else "")
    return c


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case", choices=["draft", "revision", "heldout", "package", "polish", "findingfirst"])
    ap.add_argument("--dir", required=True)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    try:
        c = {"draft": score_draft, "revision": score_revision, "heldout": score_heldout,
             "package": score_package, "polish": score_polish, "findingfirst": score_findingfirst}[a.case](a.dir)
    except FileNotFoundError as e:
        print("缺少必需文件：%s" % e, file=sys.stderr)
        return 2
    n_fail, n_warn = len(c.fails()), sum(r["result"] == "提示" for r in c.rows)
    print("行为测试初筛（%s）：%d 项，未通过 %d、提示 %d" % (a.case, len(c.rows), n_fail, n_warn))
    for r in c.rows:
        if r["result"] != "通过":
            print("- %s %s：%s%s" % (r["result"], r["id"], r["desc"], ("｜" + r["evidence"]) if r["evidence"] else ""))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"case": a.case, "rows": c.rows}, fh, ensure_ascii=False, indent=1)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
