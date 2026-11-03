#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gate_check.py — 旧式门控登记表的格式筛查；最终判定改用 release_check.py。

  python gate_check.py gate_log.md [--mode D|R|S|V|A]

gate_log.md 由 init_project.py 生成，格式：
| 门控 | 状态 | 证据 | 备注 |
|---|---|---|---|
| G1 论文类型与评价对象 | pass | 01_frame/paper_type.md | … |
状态取 pass / fail / na / blocked / todo。规则：
  · pass 必须写证据路径（相对 gate_log 所在目录，多个用 ; 分隔），文件存在且非空。
  · na 必须在备注里写理由；blocked 必须写在等谁、等什么。
  · 人工确认点（H1–H3）的 pass 必须在备注里写谁、何时确认；模型不能替人签字。
  · 不接受本表单独声明 `DONE: yes`：存在文件不等于执行过有效检查。
模式未给时读 gate_log.md 里的 `MODE:` 行。
退出码：0 登记格式一致（不证明完成）；1 有问题或无依据的完成声明；2 输入错误。
"""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

REQUIRED = {"D": ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"],
            "R": ["G0", "G2", "G3", "G7", "G8"],
            "S": ["G7", "G9"],
            "V": ["G0", "G10", "G7"],
            "A": ["G0", "G11"]}
STATES = {"pass", "fail", "na", "blocked", "todo"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log"); ap.add_argument("--mode", default="")
    a = ap.parse_args()
    if not os.path.exists(a.log):
        print("找不到 %s" % a.log, file=sys.stderr); return 2
    base = os.path.dirname(os.path.abspath(a.log))
    text = open(a.log, encoding="utf-8-sig").read()
    mm = re.search(r"^MODE:\s*([A-Z])", text, re.M)
    mode = a.mode or (mm.group(1) if mm else "")
    if mode not in REQUIRED:
        print("MODE 必须明确为 D/R/S/V/A；不能用未知模式跳过必需检查", file=sys.stderr); return 2
    rows = {}
    duplicates = []
    for line in text.split("\n"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
        if len(cells) >= 4 and re.match(r"^(G\d+|H\d)\b", cells[0]):
            code = re.match(r"^(G\d+|H\d)", cells[0]).group(1)
            if code in rows:
                duplicates.append(code)
            rows[code] = (cells[0], cells[1].lower(), cells[2].strip("` "), cells[3])
    if not rows:
        print("没有读到门控表", file=sys.stderr); return 2
    problems, notes = ["重复门控：%s" % c for c in duplicates], []
    for code, (name, st, ev, note) in rows.items():
        if st not in STATES:
            problems.append("%s：状态「%s」不合法" % (name, st)); continue
        if st == "pass":
            if code.startswith("H"):
                if len(note) < 4 or re.search(r"claude|\bai\b|模型|助手|assistant", note, re.I):
                    problems.append("%s：人工确认必须写明是谁、何时确认（不能由模型代签）" % name)
            else:
                paths = [p.strip() for p in re.split(r"[;；]", ev) if p.strip() and p.strip() not in ("—", "-")]
                if not paths:
                    problems.append("%s：标为通过却没有证据文件" % name)
                for p in paths:
                    fp = p if os.path.isabs(p) else os.path.join(base, p)
                    if not os.path.isfile(fp) or os.path.getsize(fp) == 0:
                        problems.append("%s：证据文件不存在或为空：%s" % (name, p))
        elif st == "na" and len(note) < 4:
            problems.append("%s：标为不适用，但没写理由" % name)
        elif st == "blocked" and len(note) < 4:
            problems.append("%s：标为阻塞，但没写在等谁、等什么" % name)
        elif st == "fail":
            notes.append("%s：未通过（%s）" % (name, note or "无备注"))
    req = REQUIRED.get(mode, [])
    missing = [c for c in req if c not in rows or rows[c][1] not in ("pass", "na")]
    done = re.search(r"^DONE:\s*yes\b", text, re.M | re.I)
    if done:
        problems.append("此旧式清单只核对登记格式与文件存在，不能证明检查执行、内容有效或版本一致。DONE 必须另经 release_check.py 的阶段清单与实际运行回执审核")
    for c in req:
        if c in rows and rows[c][1] == "na":
            problems.append("%s：必需项 N/A 不能仅凭备注豁免；请在阶段发布清单中记录适用性依据" % c)
    if done and missing:
        problems.append("声明 DONE，但必需门控未完成：%s" % "、".join(missing))
    print("模式 %s；门控 %d 个；问题 %d 个；必需门控未完成 %d 个%s" % (mode or "未指定", len(rows), len(problems), len(missing),
                                                       ("（%s）" % "、".join(missing)) if missing else ""))
    for p in problems:
        print("- " + p)
    for n in notes:
        print("- " + n)
    print("边界：退出 0 仅表示清单格式检查无误，不是论文质量、人工同意或最终交付通过。")
    return 1 if problems or (done and missing) else 0


if __name__ == "__main__":
    sys.exit(main())
