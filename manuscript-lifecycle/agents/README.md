# agents/ · 子代理角色简报

每个文件是一个可独立派发的角色简报。有子代理工具（Agent / Task）时，把简报路径连同下表规定的输入交给一个隔离上下文；
没有时，按 references/19_multi_agent.md §5 的降级方式运行。编排者（主对话）不扮演角色，只派发、汇总和裁决，必须保留分歧。

## 为什么要隔离

本 skill 记录的最顽固失败是"同模型盲区"：写稿的上下文会为自己的选择找理由，只改被点到的句子。隔离的价值在于审查者看不到
作者的理由、自评和既往结论，只能从稿件本身出发。同一模型的多个子代理仍会共享盲点，所以它们的一致不等于专家共识；
凡是能用脚本或原文核对的，以脚本和原文为准。

## 统一契约

| 节 | 含义 |
|---|---|
| 使命 | 这个角色防止哪种失败 |
| 输入 | 只给完成任务必需的材料 |
| 不给 | 明确不给的材料（作者理由、自评、其他角色输出、预期答案） |
| 流程 | 按什么顺序做 |
| 输出契约 | 固定格式，写入 review/round_N/<角色>.json，供 review_merge.py 校验与合并 |
| 禁止 | 不做什么（不改稿、不编造、不迎合） |
| 停止条件 | 何时交还 |
| 信心 | 每条标 high / medium / low；无法判断的写 unknown 并说明缺什么 |

## 审查发现的 JSON 格式（reviewer_* 与 cold_reader 共用）

```json
{"schema_version": 1, "role": "reviewer_methods", "manuscript_sha256": "<稿件文件的 sha256>",
 "findings": [{"id": "M1", "severity": "major|minor|note", "category": "design_claim|statistics|reporting|structure|argument|language|citation|consistency|other",
   "section": "discussion", "quote": "稿件原文，逐字，≤40 词（中文 ≤80 字）；全局问题可留空",
   "problem": "问题是什么", "why": "为什么影响读者或结论", "suggestion": "改向（不是重写全文）", "confidence": "high|medium|low"}]}
```

零发现时必须加 coverage 块，说明查了什么；没有它的空审会被 review_merge 退回：

```json
"coverage": {"sections": ["results", "tables"], "checked": ["结果句功能", "表头与行名"],
             "ok_examples": [{"quote": "稿件原文", "why_ok": "为什么没问题"}, {"quote": "稿件原文", "why_ok": "…"}]}
```

所有角色审查的“稿件”都是 `scripts/review_pack.py` 生成的审查包（正文、表、图注、补充材料与图片清单），manuscript_sha256 填审查包的指纹。

quote 必须逐字来自稿件：review_merge.py 会核对，找不到的发现标为"锚点不存在"，major 级别直接退回。

## 目录

| 文件 | 何时用 | 读原文/联网 |
|---|---|---|
| cold_reader.md | 完整初稿、每轮大改后 | 否 |
| reviewer_methods.md | 完整稿审查、投稿前 | 否（可运行 skill 脚本） |
| reviewer_argument.md | 完整稿审查、返修后复查 | 否 |
| reviewer_language.md | 语言修订前的诊断 | 否（运行 bench_profile / phrase_contrast / language_plan scan） |
| citation_checker.md | 承重引文核对（每个子代理 ≤10 条） | 是（只读被引文献） |
| response_drafter.md | 收到审稿意见（每位审稿人一个子代理） | 否 |
| reviewer_coverage.md | 完整稿与投稿前：该引而未引 | 是（检索与读候选文献） |
| reviewer_display.md | 有表图的完整稿与投稿前：读者用语与独立可读 | 否（看渲染页或原图） |
| reviewer_outsider.md | 投稿前：不读本技能规则，只拿近邻原文与用户要求对照，并做拒收预演 | 读近邻论文 |
| reviewer_genre.md | 完整稿与投稿前：对照近邻判断体裁与节职能、主文与补充的放置、假抽象与假具体 | 读近邻论文 |
| station_inspector.md | 流水线每站标 done 之前：核对产物、放行条件与原文位置（references/28） | 读该站引用的原文 |
| reviewer_selection.md | 选材定下之后、起草之前（S3 末）：审去向登记，防止把项目档案写成论文，也防止选择性报告（references/29） | 读调研语料 |

openai.yaml 是界面显示信息，不是角色简报。
