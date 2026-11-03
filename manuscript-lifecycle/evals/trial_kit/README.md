# 弱模型试跑工具包

用同一个较弱的模型、同样的任务，分别装不同的技能包（或不装）来跑，比较能否交出合格稿件。T1–T3 已经用于开发，再跑只能当回归；要检验技能的真实能力，按同样格式另写新任务。

| 目录 | 内容 | 给执行模型看吗 |
|---|---|---|
| executor/ | 三个任务：T1 从结果写英文初稿，T2 按审稿意见改中文稿并写回复，T3 投稿材料 | 只给对应任务的那一个子目录（new_run.py 自动复制） |
| tools/ | new_run.py 建一次试跑；make_trial_skill.py 打一份不含 evals/ 的技能包；pack_return.py 打包回传；make_arm_key.py 随机盲码 | 不给 |
| grader/ | 自动初筛 score_return.py、人工评分表 rubric.md、隐藏陷阱 traps.md、参考稿 | 绝对不给 |

## 流程

1. `python tools/make_arm_key.py 技能A.zip 技能B.zip [--baseline]` 分配盲码。
2. 每个技能包先用 `python tools/make_trial_skill.py 技能目录 --out 试跑用.zip` 去掉 evals/，执行模型只装去掉后的那一份。
3. 每个 run：`new_run.py` 建目录，新开对话，工作目录设为 `runs/Rxx/workspace`，原样粘贴 prompt.txt，中途不插话；跑完导出对话为 transcript.md，补 meta.json。
4. `python tools/pack_return.py --tester 名字` 打包；`python grader/score_return.py RETURN.zip --out 初筛` 初筛，FAIL 逐条人工复核后再按 rubric.md 打分。

## 两种提示

完整提示（默认）给出任务书 request.md，检验要求明确时技能能否交出合格稿件。

一句话提示（`--short`）只给一句用户原话，检验入口：模式判断、任务卡、默认交付与交付位置。new_run.py 把 request.md 移到 `runs/Rxx/hidden/`，评分时用来核对事实；默认交付按 SKILL.md §1 的表判断，不按任务书里的文件名。工作区里留着任务书，模型就会照任务书交付，测不到入口。一句话试跑的文件名不固定，以人工评分为主。

## 让每个 run 独立

每个 run 新开一次对话，并行的 run 不共享工作目录。用编排代理批量派发时，子任务实际收到的提示往往比 prompt.txt 长（多了阅读限制、汇报格式），被测的东西随之改变：把子任务收到的完整提示存为 `prompt_sent.txt`，并在 meta.json 的 orchestration 里写明。

## 要记下的

模型名与设置、客户端、能否运行 Python、是否联网、开始与结束时间、是否插话。初筛分数只用来排定复核顺序，结论以人工复核为准。用同一批 run 调过的评分脚本，与人工判断一致也不能当独立证据。
