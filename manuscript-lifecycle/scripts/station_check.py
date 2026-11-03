#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
station_check.py — 投稿级流水线的站点核对：每站有产物、有质检证据、前站完成才算完成（references/28）。

  python station_check.py --project 项目目录 --manuscript 稿件 [--stations stations.csv] [--report out.md] [--json out.json]

stations.csv（init_project 生成）列：mode, station, name, status, outputs, qc_evidence, inspector, manuscript_sha256, note。
status：todo / doing / done / blocked。blocked 的 note 以“缺材料：”开头，写需要用户提供的最少项。

  ST1 MUST  标为 done，但产物缺失、仍是空模板、质检证据不存在、没写质检员，或该站的放行条件没满足。
  ST2 MUST  跳站：后面的站标了 done，前面要求的站还没 done。
  ST3 INFO  暂停：有站点等待用户提供材料（note 原文列出）。
  ST4 MUST  需要绑定稿件的站（S3、S5、S8）指纹不是当前稿件：稿件改过后要重新确认。
  ST5 MUST  stations.csv 缺本模式要求的站。
  ST6 MUST  标为 blocked，但 note 没以“缺材料：”开头写需要用户提供的最少项。blocked 的站不挡后站，但流水线不算完成。
放行条件（脚本能核的部分）：S1 台账有数据行；S2 同类调研过 survey_check（筛选 ≥20 篇、≥3 个维度、全文编码 ≥6 篇且写了选材字段、综述四节已填），近邻全文 ≥3 且 tier 含 flagship 与 field（V 模式改为含 target，或 exempt:target）、每行写 type_match；
S3 论文构想各节已填、去向登记是新版（选材字段齐全）、对标决策覆盖六个职能维度、体裁备忘各节已填；S5 genre_gate.json 为投稿阶段、MUST 0、指纹一致（V、R 模式另要 --submitted 的结果或 exempt:submitted）；
S6 check_all summary.json 退出 0 且 stage=submission；S7 有审查裁决表或标明“非独立”的自查记录；
S8 拒收预演通过 genre_gate 的 RD 规则（V、R 模式另要 RJ11（旧编号 G11），以及 05_revision/sweep.md 的全稿清扫逐项有结果与证据，
第 7 项整包一致要有最后一次改稿后的 04_audit/package_scan.json 且 MUST 为 0，或写明理由的“不适用”）；S9 作者说明有“分维度状态”且没有空状态格。
退出码：0 流水线完整、可以交付；1 有站没完成、证据不足或等待材料；2 输入错误。
它核对的是产物与证据是否存在且对得上，不证明质检员真的认真看过；后者靠审查包、覆盖证明与作者通读。
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import genre_gate as GG  # noqa: E402

TPL = os.path.join(os.path.dirname(HERE), "assets", "templates")
STATIONS = [
    ("S0", "任务与材料", ["00_inputs/task_brief.md", "00_inputs/expectations.json"]),
    ("S1", "数字与口径", ["01_frame/results_ledger.csv", "01_frame/qualifiers.csv"]),
    ("S2", "同类调研", ["02_bench/survey_corpus.csv", "02_bench/survey_synthesis.md", "02_bench/neighbors.csv"]),
    ("S3", "构想、选材与体裁蓝图", ["01_frame/paper_concept.md", "01_frame/story_card.md", "02_bench/benchmark_decisions.csv", "02_bench/placement_decisions.csv", "01_frame/genre_memo.md"]),
    ("S4", "起草", []),
    ("S5", "体裁门", ["04_audit/genre_gate.json"]),
    ("S6", "机器审计", ["04_audit/check_all/summary.json"]),
    ("S7", "隔离与范式外审稿", []),
    ("S8", "拒收预演与修订", ["04_audit/reject_drill.md", "05_revision/decision_log.md"]),
    ("S9", "交付", ["作者说明.md"]),
]
SELF_REVIEW_PARTS = [("前提审计", r"前提审计|premise audit"), ("推断链", r"推断链|inference chain"), ("概括位置漂移", r"概括位置|摘要漂移|summary drift"),
                     ("派生量复算", r"派生量|derived quantit"), ("文献概括核对", r"文献概括|literature characteri"), ("惯例、语步与质感偏离", r"惯例偏离|偏离登记|convention|deviation"),
                     ("冷读", r"冷读|cold read")]
MODES = {"D": "S0 S1 S2 S3 S4 S5 S6 S7 S8 S9", "R": "S0 S1 S2 S3 S4 S5 S6 S7 S8 S9", "S": "S0 S2 S3 S5 S6 S7 S8 S9",
         "V": "S0 S1 S2 S5 S6 S7 S8 S9", "A": "S0 S6 S7 S9"}
BOUND = {"S3", "S5", "S8"}


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def is_template(path):
    t = os.path.join(TPL, os.path.basename(path))
    if not os.path.exists(t):
        return os.path.getsize(path) == 0
    with open(path, "rb") as a, open(t, "rb") as b:
        return a.read().strip() == b.read().strip()


def csv_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


SWEEP_ITEMS = [str(i) for i in range(1, 9)]
SWEEP_RESULTS = ("已改", "无问题", "不适用")


def sweep_gate(p, ms, msha):
    """V、R 模式：07 §9 全稿清扫逐项有结果与证据；第 7 项（整包一致）要有当前稿件之后的包级扫描且 MUST 为 0。"""
    path = p("05_revision/sweep.md")
    if not os.path.exists(path):
        return ["缺全稿清扫记录 05_revision/sweep.md（模板 assets/templates/sweep.md，references/07 §9）"]
    rows = {}
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            c = [x.strip() for x in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
            if len(c) >= 4 and c[0] in SWEEP_ITEMS:
                rows[c[0]] = c
    bad = []
    lack = [k for k in SWEEP_ITEMS if k not in rows or rows[k][2] not in SWEEP_RESULTS or len(rows[k][3]) < 8]
    if lack:
        bad.append("全稿清扫第 %s 项没有结果（%s）或没写证据" % ("、".join(lack), "/".join(SWEEP_RESULTS)))
    r7 = rows.get("7")
    if r7 and r7[2] == "不适用":
        if len(r7[3]) < 15:
            bad.append("全稿清扫第 7 项标“不适用”，要写明理由（例如只交一份正文、没有其他交付文件）")
    elif r7 and r7[2] in SWEEP_RESULTS:
        js = p("04_audit/package_scan.json")
        if not os.path.exists(js):
            bad.append("全稿清扫第 7 项没有包级扫描结果 04_audit/package_scan.json（revision_diff.py package 旧包 新包 --json）")
        else:
            try:
                with open(js, encoding="utf-8") as fh:
                    d = json.load(fh)
            except ValueError:
                d = None
            if not isinstance(d, dict) or "findings" not in d:
                bad.append("04_audit/package_scan.json 不是 revision_diff.py package 的输出")
            else:
                if d["findings"].get("MUST"):
                    bad.append("包级扫描还有 %d 条 MUST（悬空引用或已登记更正的旧说法）" % len(d["findings"]["MUST"]))
                fresh = msha in (d.get("files_sha256") or {}).values() or os.path.getmtime(js) >= os.path.getmtime(ms)
                if not fresh:
                    bad.append("包级扫描早于当前稿件：最后一次改稿后要重跑")
    return bad


def gate(sid, proj, ms, msha, mode="D"):
    """该站的放行条件；返回问题列表（空表示满足）。"""
    p = lambda rel: os.path.join(proj, rel)
    bad = []
    if sid == "S1" and os.path.exists(p("01_frame/results_ledger.csv")) and not csv_rows(p("01_frame/results_ledger.csv")):
        bad.append("结果台账没有数据行")
    if sid == "S2" and os.path.exists(p("02_bench/neighbors.csv")):
        rows = csv_rows(p("02_bench/neighbors.csv"))
        full = [r for r in rows if r.get("access", "").lower() == "fulltext"]
        tiers = {r.get("tier", "").lower() for r in full}
        if len(full) < 3:
            bad.append("近邻全文只有 %d 篇（至少 3 篇；只读到摘要的不算）" % len(full))
        if mode == "V":
            # 返修比的是受审各节在目标刊和同类里通常怎么写，不需要旗舰分层；目标刊拿不到要说明
            bd_ = p("02_bench/benchmark_decisions.csv")
            ex_ = os.path.exists(bd_) and any((r.get("dimension") or "").lower() == "exempt:target" and len(r.get("reason") or "") >= 15 for r in csv_rows(bd_))
            if "target" not in tiers and not ex_:
                bad.append("近邻没有目标刊全文（tier=target）：拿不到就把 DOI 清单交作者，并写 exempt:target 行说明（references/29 §10）")
        elif not {"flagship", "field"} <= tiers:
            bad.append("近邻缺分层：要有 flagship 与 field 各至少一篇全文（现有 %s）" % ("、".join(sorted(t for t in tiers if t)) or "无"))
        if any(not r.get("type_match") for r in rows):
            bad.append("有近邻没写 type_match（类型是否匹配及理由）")
    if sid == "S2" and os.path.exists(p("02_bench/survey_corpus.csv")):
        import survey_check as SV
        syn = p("02_bench/survey_synthesis.md")
        scope, sp = None, p("02_bench/survey_scope.json")
        if os.path.exists(sp):
            try:
                with open(sp, encoding="utf-8-sig") as f:
                    scope = json.load(f)
            except ValueError:
                bad.append("survey_scope.json 不是合法 JSON")
        its, _, _ = SV.evaluate(SV.read_rows(p("02_bench/survey_corpus.csv")), syn if os.path.exists(syn) else "", "submission", scope=scope)
        mus = [i["code"] + " " + i["msg"][:60] for i in its if i["level"] == "MUST"]
        if mus:
            bad.append("同类调研没过关（survey_check）：%s" % "；".join(mus[:3]))
    if sid == "S3":
        bd = p("02_bench/benchmark_decisions.csv")
        if os.path.exists(bd):
            dims = {r.get("dimension", "") for r in csv_rows(bd) if r.get("neighbor") and r.get("locator")}
            miss = [d for d in GG.GENRE_DIMS if d not in dims]
            if miss:
                bad.append("对标决策缺职能维度：%s" % "、".join(miss))
        pl = p("02_bench/placement_decisions.csv")
        if os.path.exists(pl) and not csv_rows(pl):
            bad.append("去向登记没有行")
        if os.path.exists(pl) and csv_rows(pl):
            lack = [c for c in GG.PL_NEW if c not in csv_rows(pl)[0]]
            if lack:
                bad.append("去向登记是旧版，缺选材字段：%s（references/29 §5）" % "、".join(lack))
        con = p("01_frame/paper_concept.md")
        if os.path.exists(con):
            csecs = GG.parse_md_sections(con)
            cempty = [k for k in ("1", "2", "3", "5", "6", "7") if k not in csecs or not GG.filled(csecs[k])]
            if cempty:
                bad.append("论文构想第 %s 节没填" % "、".join(cempty))
        memo = p("01_frame/genre_memo.md")
        if os.path.exists(memo):
            secs = GG.parse_md_sections(memo)
            empty = [k for k in ("1", "2", "3", "4", "5", "7") if k not in secs or not GG.filled(secs[k])]
            if empty:
                bad.append("体裁备忘第 %s 节没填" % "、".join(empty))
    if sid == "S5" and os.path.exists(p("04_audit/genre_gate.json")):
        d = json.load(open(p("04_audit/genre_gate.json"), encoding="utf-8"))
        if d.get("stage") != "submission" or d.get("must", 1) != 0 or d.get("manuscript_sha256") != msha:
            bad.append("genre_gate.json 不是当前稿件的投稿阶段零阻断结果（stage=%s，MUST=%s，指纹%s）"
                       % (d.get("stage"), d.get("must"), "一致" if d.get("manuscript_sha256") == msha else "不一致"))
        if os.path.exists(p("02_bench/neighbors.csv")):
            # 放行看结果，不看用了哪个工具：关键段与近邻的对照、文本质感与近邻的对照，各有一种证据即可——
            # 工具路线（genre_gate 的 deviation_meta）、人工路线（benchmark_decisions 里 keypara:/move: 行列出 ≥3 篇近邻、
            # texture: 行或 texture:checked 行），或写明理由的豁免（exempt:moves、exempt:texture，例如该语言或文体没有可得的近邻全文）。
            meta = (d.get("metrics") or {}).get("deviation_meta") or {}
            rows = [r for r in csv_rows(p("02_bench/benchmark_decisions.csv"))] if os.path.exists(p("02_bench/benchmark_decisions.csv")) else []
            bound = [r for r in rows if (r.get("manuscript_sha256") or "").lower() == msha and r.get("decision")]
            dims = lambda pre: [r for r in bound if (r.get("dimension") or "").lower().startswith(pre)]
            exempt = lambda k: any(len((r.get("reason") or "").strip()) >= 15 for r in dims("exempt:" + k))
            nbs = set()
            for r in dims("keypara:") + dims("move:"):
                nbs.update(x.strip() for x in re.split(r"[;；,，、]", r.get("neighbor") or "") if x.strip() and x.strip() != "distribution")
            moves_ok = (meta.get("moves") and all(n >= 3 for n in (meta["moves"].get("sections") or {"_": 0}).values())) or len(nbs) >= 3 or exempt("moves")
            texture_ok = bool(meta.get("texture")) or bool(dims("texture:")) or exempt("texture")
            lack = []
            if not moves_ok:
                lack.append("关键段与近邻的对照（任一方式：move_check 编码、逐段并排阅读后写 keypara:<段> 行并列出 ≥3 篇近邻，或写明理由的 exempt:moves）")
            if not texture_ok:
                lack.append("文本质感与近邻的对照（deviation_register 或 bench_profile 的结果、texture:checked 行，或写明理由的 exempt:texture）")
            if mode in ("V", "R") and not meta.get("submitted") and not exempt("submitted"):
                lack.append("改稿增量（genre_gate --submitted 上次投稿的原稿，或写明理由的 exempt:submitted，例如 R 模式的输入稿就是初稿）")
            if lack:
                bad.append("体裁门没有做近邻分布对照：%s（references/28 S5、29 §4c）" % "；".join(lack))
    if sid == "S6" and os.path.exists(p("04_audit/check_all/summary.json")):
        d = json.load(open(p("04_audit/check_all/summary.json"), encoding="utf-8"))
        if d.get("exit") != 0 or d.get("options", {}).get("stage") != "submission" or d.get("manuscript") != os.path.basename(ms):
            bad.append("check_all summary.json 不是本稿投稿阶段的零阻断结果（exit=%s，stage=%s）" % (d.get("exit"), d.get("options", {}).get("stage")))
    if sid == "S7":
        adj = glob.glob(p("review/round*/adjudication.csv"))
        selfr = p("04_audit/self_review.md")
        if not adj and not (os.path.exists(selfr) and "非独立" in open(selfr, encoding="utf-8").read()):
            bad.append("没有审查裁决表（review/round*/adjudication.csv），也没有标明“非独立”的自查记录（04_audit/self_review.md）")
        elif not adj:
            st = open(selfr, encoding="utf-8").read()
            lack = [n for n, rx in SELF_REVIEW_PARTS if not re.search(rx, st, re.I)]
            if lack:
                bad.append("非独立自查没有按规定的七项逐项做（references/19 §5；模板 assets/templates/self_review.md），缺：%s" % "、".join(lack))
    if sid == "S8" and os.path.exists(p("04_audit/reject_drill.md")):
        rows = []
        for line in open(p("04_audit/reject_drill.md"), encoding="utf-8-sig"):
            if line.strip().startswith("|") and not re.match(r"^\s*\|\s*[-:]", line):
                c = [x.strip() for x in line.strip().strip("|").split("|")]
                if len(c) >= 5 and c[0] not in ("#", "ID", "编号"):
                    rows.append(c)
        ids = {GG.probe_id(r[0]) for r in rows}
        if mode in ("V", "R") and GG.REVISION_PROBE not in ids:
            bad.append("拒收预演缺 %s：读者不看回复信时，读得出审稿或改稿过程吗（references/07 §10）" % GG.probe_label(GG.REVISION_PROBE))
        if [k for k in GG.DRILL_PROBES if k not in ids] or len([r for r in rows if GG.probe_id(r[0]) not in GG.DRILL_PROBES and GG.probe_id(r[0]) != GG.REVISION_PROBE]) < 2 \
                or any(not (r[2] and r[3] in ("已消除", "仍在", "不适用") and r[4]) for r in rows):
            bad.append("拒收预演没有逐条判定默认探针，或本稿特有理由不到两条，或有行缺位置、状态、证据")
    if sid == "S8" and mode in ("V", "R"):
        bad += sweep_gate(p, ms, msha)
    if sid == "S9" and os.path.exists(p("作者说明.md")):
        t = open(p("作者说明.md"), encoding="utf-8").read()
        if "分维度状态" not in t or re.search(r"^\|\s*[^|\n-][^|\n]*\|\s*\|", t, re.M):
            bad.append("作者说明没有逐维填写状态（“分维度状态”表有空格）")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--manuscript", required=True)
    ap.add_argument("--stations", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    st = a.stations or os.path.join(a.project, "stations.csv")
    for x in (a.project, a.manuscript, st):
        if not os.path.exists(x):
            print("找不到输入：%s" % x, file=sys.stderr)
            return 2
    for x in (a.report, a.json):
        if x and os.path.exists(x):
            print("输出文件已存在，换一个新路径：%s" % x, file=sys.stderr)
            return 2
    rows = csv_rows(st)
    if not rows or "station" not in rows[0]:
        print("stations.csv 为空或缺 station 列", file=sys.stderr)
        return 2
    mode = (rows[0].get("mode") or "D").upper()
    if mode not in MODES:
        print("认不出的模式：%s" % mode, file=sys.stderr)
        return 2
    msha = sha(a.manuscript)
    by = {r["station"]: r for r in rows}
    req = MODES[mode].split()
    names = dict((s, n) for s, n, _ in STATIONS)
    outs = dict((s, o) for s, _, o in STATIONS)
    items = []
    add = lambda lvl, code, sid, msg: items.append({"level": lvl, "code": code, "station": sid, "msg": msg})
    for sid in req:
        if sid not in by:
            add("MUST", "ST5", sid, "stations.csv 缺本模式要求的站 %s %s" % (sid, names[sid]))
    seen_todo = None
    for sid in req:
        r = by.get(sid)
        if not r:
            continue
        status = r.get("status", "todo").lower()
        if status == "blocked":
            note = (r.get("note") or "").strip()
            if note.startswith("缺材料：") and len(note) > len("缺材料：") + 1:
                add("INFO", "ST3", sid, "暂停，等待用户：%s" % note)
            else:
                add("MUST", "ST6", sid, "%s %s 标为 blocked，但 note 没有以“缺材料：”开头写明需要用户提供的最少项。只有缺事实材料才能暂停。" % (sid, names[sid]))
            continue   # 缺材料的站暂停；不依赖它的后站照常推进，但整条流水线不算完成
        if status != "done":
            seen_todo = seen_todo or sid
            continue
        if seen_todo:
            add("MUST", "ST2", sid, "跳站：%s 标了 done，但前面的 %s %s 还没完成。返工时把受影响的后站改回 todo。" % (sid, seen_todo, names[seen_todo]))
        probs = []
        listed = [x.strip() for x in re.split(r"[;；]", r.get("outputs", "")) if x.strip()] or outs[sid]
        for rel in listed:
            path = os.path.join(a.project, rel)
            if not os.path.exists(path):
                probs.append("产物不存在：%s" % rel)
            elif os.path.isfile(path) and is_template(path):
                probs.append("产物还是空模板：%s" % rel)
        qc = [x.strip() for x in re.split(r"[;；]", r.get("qc_evidence", "")) if x.strip()]
        if not qc:
            probs.append("没写质检证据（qc_evidence：实际报告的路径）")
        for rel in qc:
            if not os.path.exists(os.path.join(a.project, rel)):
                probs.append("质检证据不存在：%s" % rel)
        if not r.get("inspector"):
            probs.append("没写质检员（inspector）")
        probs += gate(sid, a.project, a.manuscript, msha, mode)
        if probs:
            add("MUST", "ST1", sid, "%s %s 标为 done，但：%s。" % (sid, names[sid], "；".join(probs)))
        if sid in BOUND and (r.get("manuscript_sha256") or "").lower() != msha:
            add("MUST", "ST4", sid, "%s %s 没有绑定当前稿件（当前指纹 %s…）。" % (sid, names[sid], msha[:12]))
    done = [s for s in req if by.get(s, {}).get("status", "").lower() == "done"]
    must = [i for i in items if i["level"] == "MUST"]
    complete = not must and len(done) == len(req)
    paused = [i for i in items if i["code"] == "ST3"]
    pending = [s for s in req if s not in done]
    if complete:
        verdict = "流水线完整，可以交付。"
    elif paused and not must:
        verdict = "暂停：等待用户提供材料（%s）；%d 站未完成（%s），不能交付。" % ("、".join(i["station"] for i in paused), len(pending), "、".join(pending))
    else:
        verdict = "还不能交付：%d 站未完成（%s），%d 项证据问题。" % (len(pending), "、".join(pending), len(must))
    L = ["# 流水线站点核对（%s 模式）" % mode, "", "稿件 %s（指纹 %s…）。**%s**" % (os.path.basename(a.manuscript), msha[:12], verdict), "",
         "| 站 | 名称 | 状态 | 质检员 |", "|---|---|---|---|"]
    L += ["| %s | %s | %s | %s |" % (s, names[s], by.get(s, {}).get("status", "缺"), by.get(s, {}).get("inspector", "")) for s in req]
    L += ["", "## 问题", ""] + (["- **%s %s**（%s）%s" % (i["level"], i["code"], i["station"], i["msg"]) for i in items] or ["没有。"]) + [""]
    L += ["站点核对只证明产物与证据存在且对得上，不证明质检员认真看过。", ""]
    res = {"schema_version": 1, "mode": mode, "manuscript_sha256": msha, "complete": complete, "verdict": verdict, "items": items,
           "done": done, "required": req}
    if a.report:
        with open(a.report, "x", encoding="utf-8") as f:
            f.write("\n".join(L))
    if a.json:
        with open(a.json, "x", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    print(verdict if a.report else "\n".join(L))
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
