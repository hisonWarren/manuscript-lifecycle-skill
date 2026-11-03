#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_project.py — 建项目工作区：目录、模板、按模式预填的站点表。已存在的文件不覆盖。

  python init_project.py --dir 项目目录 --mode D|R|S|V|A [--title 短题] [--full] [--legacy]

只建本模式用得到的模板；作者先看的说明在项目根目录“作者说明.md”，其余是工作区。

模式：D 从数据写初稿；R 修改已有稿件；S 准备投稿；V 返修与回复审稿人；A 投稿前自审。
另建 stations.csv（投稿级流水线的站点表，station_check.py 核对；references/28）。进度只记这一套：
旧的 gate_log.md（G0–G11、H1–H3）只在 --legacy 时生成，供仍在用 gate_check 的旧项目对照。
单文档修订与局部任务不建项目（SKILL §0）。
"""
import json
import argparse, csv, os, shutil, sys

# Windows 中文系统把输出接到管道时默认按 GBK 编码，统计里常见的 − ² ✓ 会让脚本在打印时崩溃；统一按 UTF-8 输出。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(os.path.dirname(HERE), "assets", "templates")
GATES = [("G0", "材料盘点与阶段判断", "00_inputs/inventory.md"), ("G1", "论文类型与评价对象", "01_frame/paper_type.md"),
         ("G2", "故事卡", "01_frame/story_card.md"), ("G3", "结果台账与报告分档", "01_frame/results_ledger.csv; 04_audit/ledger_check.md"),
         ("G4", "对标语料与画像", "02_bench/corpus.md; 02_bench/bench_report.md"), ("G5", "大纲与各节契约", "03_draft/outline.md"),
         ("G6", "逐节初稿", "03_draft/manuscript.md"),
         ("G7", "审计", "04_audit/section_lint.md; 04_audit/density.md; 04_audit/number_trace.md; 04_audit/ref_check.md; 04_audit/claims_guard.md; 04_audit/review_findings.md"),
         ("G8", "分层修订", "05_revision/decision_log.md; 05_revision/changes.md"), ("G9", "投稿材料", "06_submission/submission_checklist.md"),
         ("G10", "返修与回复信", "07_response/comments_matrix.csv; 07_response/response_lint.md"), ("G11", "投稿前自审", "04_audit/self_review.md"),
         ("H1", "人工确认：类型、故事卡、台账", ""), ("H2", "人工通读：首个完整稿", ""), ("H3", "人工通读：投稿或返修前", "")]
REQ = {"D": "G0 G1 G2 G3 G4 G5 G6 G7 G8", "R": "G0 G2 G3 G7 G8", "S": "G7 G9", "V": "G0 G10 G7", "A": "G0 G11"}
COPY = {"inventory.md": "00_inputs", "paper_type.md": "01_frame", "story_card.md": "01_frame", "results_ledger.csv": "01_frame",
        "outline.md": "03_draft", "claims_register.json": "05_revision", "decision_log.md": "05_revision", "limits_example.json": "00_inputs",
        "submission_checklist.md": "06_submission", "cover_letter.md": "06_submission", "comments_matrix.csv": "07_response",
        "response_letter.md": "07_response", "moves_coding_example.json": "02_bench", "draft_rubric.md": "04_audit",
        "citation_ledger.csv": "04_audit", "task_brief.md": "00_inputs", "qualifiers.csv": "01_frame", "issue_log.csv": "04_audit", "author_delivery.md": "06_submission", "source_coverage.csv": "00_inputs",
        "expectations.json": "00_inputs", "coverage_map.csv": "04_audit", "display_terms.csv": "06_submission",
        "benchmark_decisions.csv": "02_bench", "neighbors.csv": "02_bench",
        "placement_decisions.csv": "02_bench", "genre_memo.md": "01_frame", "reject_drill.md": "04_audit",
        "paper_concept.md": "01_frame", "sweep.md": "05_revision", "survey_corpus.csv": "02_bench", "survey_synthesis.md": "02_bench", "survey_scope.json": "02_bench"}


# 只建这一模式用得到的文件：实地试写中，初稿项目里有 9 个模板从建好到交付一字未动，作者打开先看到一堆空壳。
# 其余模板在 assets/templates/，用到时再拷；--full 恢复旧行为（全部拷入）。
BY_MODE = {
    "D": ["task_brief.md", "inventory.md", "source_coverage.csv", "paper_type.md", "story_card.md", "results_ledger.csv", "qualifiers.csv",
          "outline.md", "decision_log.md", "citation_ledger.csv", "expectations.json", "coverage_map.csv", "benchmark_decisions.csv",
          "neighbors.csv", "placement_decisions.csv", "genre_memo.md", "reject_drill.md"],
    "R": ["task_brief.md", "inventory.md", "story_card.md", "results_ledger.csv", "qualifiers.csv", "decision_log.md", "claims_register.json", "citation_ledger.csv", "expectations.json",
          "coverage_map.csv", "benchmark_decisions.csv", "neighbors.csv", "placement_decisions.csv", "genre_memo.md", "reject_drill.md", "sweep.md"],
    "S": ["submission_checklist.md", "cover_letter.md", "limits_example.json", "citation_ledger.csv", "decision_log.md", "expectations.json",
          "coverage_map.csv", "display_terms.csv", "benchmark_decisions.csv", "neighbors.csv",
          "task_brief.md", "story_card.md", "placement_decisions.csv", "genre_memo.md", "reject_drill.md"],
    "V": ["task_brief.md", "inventory.md", "comments_matrix.csv", "response_letter.md", "claims_register.json", "qualifiers.csv", "decision_log.md", "expectations.json", "display_terms.csv",
          "results_ledger.csv", "reject_drill.md", "sweep.md",
          # 体裁门在投稿阶段要这些；返修沿用原稿的主张，调研只为比较受审各节（references/29 §10）
          "benchmark_decisions.csv", "neighbors.csv", "placement_decisions.csv", "genre_memo.md", "survey_corpus.csv", "survey_synthesis.md", "survey_scope.json"],
    "A": ["inventory.md", "issue_log.csv", "draft_rubric.md", "citation_ledger.csv", "task_brief.md", "expectations.json"],
}

# 第三轮：先调研、再构想、再选材（references/29）。D、R、S 模式另建论文构想与同类调研的模板。
for _m in ("D", "R", "S"):
    BY_MODE[_m] = BY_MODE[_m] + ["paper_concept.md", "survey_corpus.csv", "survey_synthesis.md", "survey_scope.json"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True); ap.add_argument("--mode", required=True, choices=list(REQ)); ap.add_argument("--title", default="")
    ap.add_argument("--full", action="store_true", help="拷入全部模板（旧行为）")
    ap.add_argument("--legacy", action="store_true", help="另建旧的 gate_log.md（G0–G11 进度项）；新项目只用 stations.csv")
    a = ap.parse_args()
    want = set(COPY) if a.full else set(BY_MODE[a.mode])
    for d in sorted({"03_draft", "04_audit"} | {COPY[f] for f in want}):
        os.makedirs(os.path.join(a.dir, d), exist_ok=True)
    made = []
    note = os.path.join(a.dir, "作者说明.md")
    if not os.path.exists(note) and os.path.exists(os.path.join(TPL, "author_delivery.md")):
        shutil.copy(os.path.join(TPL, "author_delivery.md"), note); made.append("作者说明.md")
    for f, d in COPY.items():
        if f not in want or f == "author_delivery.md":
            continue
        src, dst = os.path.join(TPL, f), os.path.join(a.dir, d, f)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy(src, dst); made.append(os.path.join(d, f))
    if a.mode == "V" and "survey_scope.json" in want:
        # 返修：主张已定，调研只比较受审各节，规模按此预设（可改；references/29 §10）
        sp = os.path.join(a.dir, COPY["survey_scope.json"], "survey_scope.json")
        with open(sp, "w", encoding="utf-8") as f:
            json.dump({"min_screen": 10, "min_full": 6, "min_matched": 4, "min_axes": 2,
                       "reason": "返修沿用原稿主张，调研只用于比较受审各节与回应写法，目标刊优先（references/29 §10）"}, f, ensure_ascii=False, indent=1)
    gl = os.path.join(a.dir, "gate_log.md")
    if a.legacy and not os.path.exists(gl):
        req = REQ[a.mode].split()
        L = ["# 门控记录%s" % ((" · " + a.title) if a.title else ""), "", "MODE: %s" % a.mode,
             "本模式进度项：%s。gate_check 仅检查日志一致性，不是交付证书；最终证据契约见 release_check。H 行为作者决策提醒，不代签、不阻断已授权的可逆写作。" % " ".join(req), "",
             "| 门控 | 状态 | 证据 | 备注 |", "|---|---|---|---|"]
        L += ["| %s %s%s | todo | %s |  |" % (c, n, "（必需）" if c in req else "", e) for c, n, e in GATES]
        L += ["", "DONE: no", ""]
        open(gl, "w", encoding="utf-8").write("\n".join(L)); made.append("gate_log.md")
    # 站点表：投稿级流水线的进度与质检证据（references/28），是唯一的进度事实源。
    st = os.path.join(a.dir, "stations.csv")
    if not os.path.exists(st):
        sys.path.insert(0, HERE)
        import station_check as SC
        names = dict((s, n) for s, n, _ in SC.STATIONS)
        outs = dict((s, o) for s, _, o in SC.STATIONS)
        with open(st, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["mode", "station", "name", "status", "outputs", "qc_evidence", "inspector", "manuscript_sha256", "note"])
            for sid in SC.MODES[a.mode].split():
                w.writerow([a.mode, sid, names[sid], "todo", "; ".join(outs[sid]), "", "", "", ""])
        made.append("stations.csv")
    print("工作区：%s；新建 %d 个文件：%s" % (a.dir, len(made), "、".join(made)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
