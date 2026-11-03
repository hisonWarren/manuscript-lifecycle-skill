#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new_run.py — 为一次试跑建好干净的工作目录、提示词和记录表（在本工具包根目录执行）。

  python tools/new_run.py --run R01 --task T1 --arm X --model "模型名与版本" [--runs runs]

生成 runs/R01/：
  workspace/<任务目录>/  只含该任务的材料（不含 grader/ 和其他任务），模型就在 workspace/ 里工作
  prompt.txt             发给模型的完整提示（按盲码决定是否提到技能）
  meta.json              记录表：跑完后补 end_time、token、工具权限等
  hidden/request.md      仅 --short：完整任务书移到这里，评分时用，不给执行模型
盲码：在 arm_key.csv 里登记它对应哪个技能版本（或无技能）。arm 为 Z 时视为“无技能基线”。
"""
import argparse, datetime, json, os, shutil, sys
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = {"T1": "T1_draft", "T2": "T2_revision", "T3": "T3_package"}
PROMPT_SKILL = """请使用已安装的 manuscript-lifecycle 技能完成任务。
任务说明在当前工作目录的 {d}/request.md，所需材料都在 {d}/ 目录里。
请先读 request.md，再按技能的要求完成任务，把所有交付文件写到 {d}/outputs/。
这是一次测试：除了已安装的技能文件，不要读取当前工作目录以外的文件，不要联网检索。完成后在 {d}/outputs/RUN_REPORT.md 里如实写明：你读了哪些技能文件、运行了哪些命令（含退出码）、哪些检查没能运行，以及交付状态。
"""
SHORT = {"T1": "结果都在 T1_draft 文件夹里，帮我写个英文初稿，准备投教育心理学的期刊。",
         "T2": "按 T2_revision 里的审稿意见把中文稿改一下，再写个回复。",
         "T3": "T3_package 里这篇要投 Computers & Education，帮我准备投稿材料。"}
PROMPT_NOSKILL = """请完成任务。
任务说明在当前工作目录的 {d}/request.md，所需材料都在 {d}/ 目录里。
请先读 request.md，再完成任务，把所有交付文件写到 {d}/outputs/。
这是一次测试：不要读取当前工作目录以外的文件，不要联网检索。完成后在 {d}/outputs/RUN_REPORT.md 里如实写明：你读了哪些文件、运行了哪些命令（含退出码）、哪些检查没能运行，以及交付状态。
"""
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True); ap.add_argument("--task", required=True, choices=sorted(TASKS))
    ap.add_argument("--arm", required=True, help="盲码，如 X/Y/W/Z；Z = 无技能基线"); ap.add_argument("--model", required=True)
    ap.add_argument("--runs", default=os.path.join(ROOT, "runs"))
    ap.add_argument("--short", action="store_true", help="用一句用户短话代替完整提示，检验技能入口（任务卡、默认交付）")
    a = ap.parse_args()
    rd = os.path.join(a.runs, a.run)
    if os.path.exists(rd):
        print("已存在 %s：换一个 run 编号，不要覆盖已有记录" % rd, file=sys.stderr); return 2
    d = TASKS[a.task]
    shutil.copytree(os.path.join(ROOT, "executor", d), os.path.join(rd, "workspace", d))
    os.makedirs(os.path.join(rd, "workspace", d, "outputs"))
    if a.short:
        # 一句话试跑检验的是入口：工作区里留着任务书，模型就会照任务书交付，测不到默认交付
        os.makedirs(os.path.join(rd, "hidden"))
        shutil.move(os.path.join(rd, "workspace", d, "request.md"), os.path.join(rd, "hidden", "request.md"))
    prompt = SHORT[a.task] + "\n" if a.short else (PROMPT_NOSKILL if a.arm.upper() == "Z" else PROMPT_SKILL).format(d=d)
    with open(os.path.join(rd, "prompt.txt"), "w", encoding="utf-8") as f: f.write(prompt)
    meta = {"run_id": a.run, "task": a.task, "arm": a.arm.upper(), "model": a.model, "prompt_style": "short" if a.short else "full",
            "model_settings": "温度、最大输出、上下文长度等（尽量填）", "agent_tool": "用什么客户端/代理运行（如命令行代理、IDE 插件）",
            "can_run_python": "是/否", "network": "关闭", "skill_installed": "技能包文件名（Z 填 无）",
            "start_time": datetime.datetime.now().isoformat(timespec="minutes"), "end_time": "", "tokens_or_cost": "",
            "interventions": "过程中你是否插话、回答了模型的问题（照实写；理想情况是不插话）", "orchestration": "直接新开对话（推荐）；由编排代理派发时，把子任务实际收到的完整提示另存为 prompt_sent.txt", "notes": ""}
    with open(os.path.join(rd, "meta.json"), "w", encoding="utf-8") as f: json.dump(meta, f, ensure_ascii=False, indent=1)
    print("已建好 %s\n1) 安装盲码 %s 对应的技能（Z 不装）；2) 新开对话，工作目录设为 %s；3) 原样粘贴 prompt.txt；4) 跑完导出对话为 %s；5) 补 meta.json 的 end_time 等。"
          % (rd, a.arm.upper(), os.path.join(rd, "workspace"), os.path.join(rd, "transcript.md")))
    if a.short:
        print("完整任务书已移到 %s，评分时用；不要让执行模型读到。" % os.path.join(rd, "hidden"))
    return 0
if __name__ == "__main__":
    sys.exit(main())
