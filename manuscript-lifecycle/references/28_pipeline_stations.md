# 28 · 投稿级流水线：站点、产物与质检

一次“充分利用本技能重做投稿包”的会话暴露了以下问题：

- 先建了对标登记，后来才读到近邻全文；
- 审稿是单代理自查，却按多角色审稿的口吻写结论；
- 版式只抽看了几页；
- 机器检查退出 0，交出的稿件仍是报告腔。

流程写在手册里，不等于被执行了。这一页把“什么时候做什么、做到什么程度算完、由谁检查”落成一张站点表 `stations.csv`，由 `station_check.py` 核对。

## 1. 完整项目按模式走站点

用户要求完整初稿或整稿重建时，按 D/R 走全部站点 S0–S9；投稿、返修和只审按下表的 S/V/A 子集。整篇修改但没有要求重建主张的，走 SKILL §0 的单文档修订；只处理指定片段的，走 SKILL §0 的局部路线；这两条路线都不初始化项目。有结果、没成稿用 D 模式；已有稿件要重建才用完整 R。范围按 SKILL §0 定，范围小不等于标准低：要求含糊时不要停下来等确认，也不要把稿件写成“安全的实验报告腔”。

**不把常规写作判断当阻断。** 缺事实材料时只暂停依赖部分；用户限制范围、禁止检查或要求停止时遵从。执行受限时说明实际状态，不假装放行。下列是缺事实材料的记录方式：

1. 该站记 `status=blocked`。
2. note 以“缺材料：”开头，写需要用户提供的最少项。
3. 在对话里一次问完。
4. 不依赖这份材料的站照常推进。

“结果文件找不到”“伦理批准号未知”属于缺材料；“不确定摘要怎么写”不属于，那是本技能自己的工作。

## 2. 站点

| 站 | 做什么 | 产物 | 质检员要看的 | station_check 能核的放行条件 |
|---|---|---|---|---|
| S0 任务与材料 | 任务卡、权威材料、用户要求逐字登记 | 00_inputs/task_brief.md、expectations.json | 用户原话逐字进了登记；模式与交付写清 | 产物存在且不是空模板 |
| S1 数字与口径 | 结果台账、口径限定 | 01_frame/results_ledger.csv、qualifiers.csv | 每个承重数字有出处与口径 | 台账有数据行 |
| S2 同类调研 | 按主题、领域、方法、分析、背景、目标刊、旗舰刊多维检索；筛选、全文编码，读出同类作者为什么只呈现这些 | 02_bench/survey_corpus.csv、survey_synthesis.md、neighbors.csv | 全文真的读到了；“为什么只呈现这些”针对每一篇；维度够宽 | survey_check 投稿阶段零 MUST（筛选 ≥20、维度 ≥3、全文编码 ≥6 且类型匹配 ≥4、选材字段齐全、综述四节已填）；近邻 flagship 与 field 各 ≥1，每行写 type_match |
| S3 构想、选材与体裁蓝图 | 论文构想（作者目的、候选构想、主张清单、审稿人预判、搁置清单）、去向登记（四档，结果盲测试、审稿人两问、交代依据）、故事卡、六维对标决策、体裁备忘 | paper_concept.md、placement_decisions.csv、story_card.md、benchmark_decisions.csv、genre_memo.md | 主张清单与搁置清单对得上；没有与主张相关却因结果不好而不进论文的；审稿人两问不是套话；每维近邻位置能在全文里找到 | 构想各节已填，去向为新版且非空，六维齐全，备忘各节已填，绑定指纹；有子代理时附 reviewer_selection 的审查 |
| S4 起草 | 按蓝图逐节写 | 稿件 | — | — |
| S5 体裁门 | `genre_gate.py --stage submission` | 04_audit/genre_gate.json | 保留的偏离都有近邻依据 | 投稿阶段 MUST 0，指纹一致 |
| S6 机器审计 | `check_all.py --stage submission` | 04_audit/check_all/summary.json | 误报裁决写进作者说明 | 本稿投稿阶段退出 0 |
| S7 隔离与范式外审稿 | 审查包与审稿角色（含 reviewer_genre、reviewer_outsider） | review/round*/adjudication.csv，或标明“非独立”的 04_audit/self_review.md | 零发现附覆盖证明；裁决不模板化 | 二者之一存在 |
| S8 拒收预演与修订 | 拒收预演、修订登记 | 04_audit/reject_drill.md、05_revision/decision_log.md | 本稿特有的理由不是凑数 | 通过 genre_gate 的 RD 规则 |
| S9 交付 | 作者说明逐维报告 | 作者说明.md | 每一维都有证据 | “分维度状态”没有空格 |

各模式要过的站：

| 模式 | 站点 |
|---|---|
| D、R | 全部 |
| S（投稿） | S0、S2、S3、S5–S9 |
| V（返修） | S0、S1、S2（窄调研，29 §10）、S5–S9；沿用原稿的主张，不重做 S3，但体裁门要的去向登记与体裁备忘要承接过来（审稿人要求的新分析逐项登记去向） |
| A（只审） | S0、S6、S7、S9 |

`init_project.py` 按模式生成站点表。单文档修订和局部任务不走站点，做法见 SKILL §0；升到完整 R 时，已做的核对按 SKILL §7.1 复用。

## 3. 质检员

每站做完，由质检员按上表“质检员要看的”和放行条件核一遍（简报见 `agents/station_inspector.md`）。

- **记录。** 写 `04_audit/qc/S<n>.md`，结论为 pass 或 return；return 写明缺什么。然后在 stations.csv 填 qc_evidence（这份记录的路径）与 inspector。
- **有子代理时**，质检员用隔离上下文。
- **没有子代理时**，主对话在该站完成后单独做一次核对，inspector 写“self（非独立）”。

质检要找证据，不是确认格式：

- 近邻位置能不能在全文里找到；
- 去向登记的读者问题是否换个稿件也能照抄；
- 白话复述是否真的不用术语。

只写“已检查”的质检记录，等于没有质检。

## 4. 前站未完，不进后站

- **按序推进。** 后站标了 done 而前站没有，就是跳站（ST2）。
- **返工回退。** 前站返工时，受影响的后站改回 todo。例如 S2 换了近邻，S3 的对标决策要重做。
- **稿件改动。** 稿件改过后，S3、S5、S8 绑定的指纹失效（ST4），要重新确认。

## 5. station_check.py

```text
python scripts/station_check.py --project 项目目录 --manuscript 稿件 [--report out.md] [--json out.json]
```

规则：

| 代码 | 级别 | 含义 |
|---|---|---|
| ST1 | MUST | 标了 done，但产物缺失、仍是空模板、没有质检证据或质检员，或放行条件没满足 |
| ST2 | MUST | 跳站 |
| ST3 | INFO | 暂停等待材料 |
| ST4 | MUST | 需要绑定指纹的站没有绑定当前稿件 |
| ST5 | MUST | 缺本模式要求的站 |
| ST6 | MUST | 标了 blocked，但 note 没以“缺材料：”开头写明最少项。blocked 的站不挡后站，但只要有站 blocked，流水线就不算完成 |

退出码：0 表示流水线完整，可以交付；1 表示还不能交付，或正在等待材料；2 表示输入错误。

交付前必须退出 0。它核对的是产物与证据存在且对得上，不能证明质检员认真看过。后者靠审查包、覆盖证明与作者通读。

## 6. 与旧进度表的关系

新项目只记 `stations.csv`。旧的 `gate_log.md` 和 `gate_check.py` 保留给旧项目：`init_project --legacy` 才生成，文件里的 G0–G11、H1–H3 与新编号无关（编号表见 17）。

`release_check.py` 仍管证据契约（13）。两者分工如下：

- station_check 回答“该做的站做完没有”；
- release_check 回答“声称通过的检查有没有运行回执与审查证据”。

## 7. 各站的补充放行条件

这些条件写的是“要做到什么”；每一条都可以用不同方法满足，用了哪种方法写进质检记录。括号里是本技能现成的一种做法。

- S1：由其他估计值算出来的量（乘积、比值、换算、效应量、比例说法）登记了公式、分量与单位，并且复算对得上（derivations.csv 与 derivation_check）。
- S2：类型匹配的近邻至少 3 篇读到全文，记下它们的表面惯例（convention_profile）和关键段的职能组成——至少引言逐段职能，需要时加讨论首段与结论（move_check 段落级编码，原文存 `02_bench/moves_src/`；或逐段并排阅读后的笔记）。
- S3：每条主张写下不能用的说法（paper_concept.md 的“禁用表述”）；结果盲测试先写这项分析检验的是哪条主张（29 §2b）；表面惯例的每个偏离有裁决。
- S4：起草关键段（引言末段、讨论首段、结论）之前先看近邻的职能组成，按它写；偏离的地方有理由。
- S5：关键段与近邻比过、文本质感与近邻比过，每个必须裁决的偏离写进 benchmark_decisions（deviation_register，或 genre_gate 带 `--moves`、`--neighbor-texts`/`--baseline`）。station_check 接受三种证据中的任一种：工具结果（genre_gate.json 的 deviation_meta）、人工记录（`keypara:` 行列出 ≥3 篇近邻；`texture:` 或 `texture:checked` 行）、写明理由的豁免（`exempt:moves`、`exempt:texture`，例如该语言或文体拿不到近邻全文）。
- S6：概括位置的主张强度与派生量复算没有未裁决的问题（check_all 的 claim_strength 与 derivation_check）。
- S5（V、R）：相对上次投稿原稿的累计增量逐节裁决（genre_gate `--submitted`，07 §10）；R 模式输入稿就是初稿时写 `exempt:submitted` 并说明。
- S8（V、R）：reject_drill 判定 RJ11（读者不看回复信时，读得出审稿或改稿过程吗）；07 §9 的全稿清扫逐项写进 `05_revision/sweep.md`（结果为已改、无问题或不适用，各附证据）；第 7 项整包一致要有最后一次改稿之后的 `04_audit/package_scan.json` 且 MUST 为 0，只交一份文件时写“不适用”并说明。
- S7：没有隔离审查时，自查按 19 §5b 的七项逐项写，第 6 项写惯例、语步与质感偏离的裁决；有外部审查时按 26 §7 导入并逐组裁决。

- S2（第九轮补充）：关键段编码先用 key_units 从 neighbors.csv 抽取；编码中用到的每篇近邻都要在 neighbors.csv 里，有 type_match 与 tier。

## 完整项目的执行动作

以下集中保留原主入口的完整执行细节；站点以本文件模式表为准，不再在 SKILL 重复维护。这里的每次检查、调研数量和交付步骤适用于完整项目；局部任务、复查范围、用户执行限制和停止条件统一按 SKILL §0、§7，不能因读到本节而扩大范围。

0. **先写任务卡。** 用户只说了一句话时尤其要写（`assets/templates/task_brief.md`，写在工作记录第一段）：按哪种模式做、依据是什么；权威材料是哪些文件；语言与目标刊；默认交付（见 §1 表）与交付位置（没说就放在材料旁边的 outputs/，工作文件放 outputs/_work/）；执行条件与可用工具；作者想让读者记住什么（原话，没有就写推断并标明）。材料里找得到的答案不问；只有会改变主线或交付物、又找不到答案的事才问，最多两个问题。材料够写成不止一篇论文时，“这篇写哪一篇”就是这样的问题（[29](29_selection_and_survey.md) §3）。不必等用户确认任务卡就可以开工；在对话里用一句话告诉用户“我按××模式做，交付××”。用户对文体与交付的明确要求（如结果小标题的写法、引用要充分、图表里不出现代码）逐字写进 `expectations.json`（模板在 `assets/templates/`）：登记后它们是每轮检查的硬回归项，别的检查全部通过也不能抵消。同一轮要交多份大文件（报告、主稿、补充材料、PPT）时分里程碑交付，每份写明过了哪些维度，不为赶时间挤掉文献覆盖与对标。沙箱可能重置、额度可能用完：每个里程碑先落到 outputs/，说清做到哪一步、下次从哪接。
1. **锁定数字。** 找到结果文件（表、CSV、模型输出、分析代码），把它们当作唯一的数字来源。没有结果就不写结果。清点每项分析时只记是什么、样本多大、证据质量（稳健、依赖设定、失败、无法解释），这一步不定去向，也不对作者说“必须披露”。由其他估计值算出来的量（间接效应、换算、比值）登记公式、分量与单位（`derivations.csv`，[22](22_metrics_and_definitions.md) §8）。
2. **定口径，再定主线。** 先给每个承重指标写一行口径：实际怎么算（看代码，不看变量名）、分母是什么、未完成或到上限的观测怎样处理、哪些是生成设定而不是发现（[22](22_metrics_and_definitions.md)）。每次提到都必须带限定的数字，写进 `qualifiers.csv`。再填故事卡的“数字定方向”表：每个结局的方向、大小、区间、对应写法。不显著写“未见明确差异”，不写“趋势”，也不写“相同”。主线的方向跟着数字走，不跟着常识或作者的预期走；讲哪一个问题，由作者目的、同类调研与证据质量一起定（第 3 步）。
3. **先调研，再构想，再选材，然后定体裁。** 先做多维同类调研：按同主题、同领域、同方法、同分析、同背景、目标刊与旗舰刊分别检索，默认筛选不少于 20 篇、全文编码不少于 6 篇，记下同类论文呈现什么、呈现多少、为什么只呈现这些、审稿人常问什么（`survey_corpus.csv`、`survey_synthesis.md`，[29](29_selection_and_survey.md) §4）。再从作者目的写一到三个论文构想（`paper_concept.md`：主张清单、审稿人预判、搁置清单；材料够写不止一篇时请作者选）。然后逐项登记去向 `placement_decisions.csv`：主文、补充、备答（reserve，不进论文）或不属于本文（omit），每项写服务哪条主张、证据质量、结果理想时会放哪里（结果盲测试）、放了与不放审稿人各会问什么、交代依据。交代义务跟着主张走：做过不是放入的理由，与主张相关的不利结果不能因为不利而不进论文。调研与构想完成前，不向作者给去向结论。调研规模可以按领域与模式调整并写理由（`survey_scope.json`）；各模式与各类论文怎样用，见 29 §10。最后写体裁备忘 `genre_memo.md`（一句话贡献、读者为什么在乎、说明了什么、近邻逐节对照、白话复述），并把近邻的摘要末句、引言首末段、方法粒度、主文表型、讨论首段写进 benchmark_decisions（[27](27_genre_and_placement.md)）。写不出一句话贡献，先改主线，不先润色。每条主张写下不能用的说法（`paper_concept.md` 的“禁用表述”，[22](22_metrics_and_definitions.md) §9）。然后每节先读 [20](20_moves_and_exemplars.md) 的语步和 `assets/exemplars/` 的对应范例。通常先写方法和结果，再写讨论和引言，最后写摘要和题目。结果小标题先定风格再写：按用户偏好、目标刊、近邻论文实测（`bench_profile.py` 第六节）的次序选分析对象式或发现式，记进决策登记；两种都是合法写法，本技能不预设。**稿件里只写研究本身**：“本稿未提供……”“待作者核实”“这是一次写作测试”这类话一律写进作者说明；材料缺的事实用 `[VERIFY: …]` 留在它本来所在的方法或声明句里；摘要和结论不放占位，也不放状态话。
4. **一条命令检查。** `python scripts/check_all.py 稿件.md --results 结果文件… [--design 设计] [--qualifiers qualifiers.csv] [--citations citation_ledger.csv --note 作者说明.md --execution 执行条件] [--supplement 补充材料] [--displays 表.csv 图注.md 图…] [--terms display_terms.csv] [--coverage coverage_map.csv] [--benchmark-decisions benchmark_decisions.csv] [--expectations expectations.json] [--placement placement_decisions.csv --memo genre_memo.md --drill reject_drill.md --concept paper_concept.md --survey survey_corpus.csv --neighbor-texts 近邻全文…] [--submitted 上次投稿的原稿] [--stage submission] [--simulation]`。结果节的句子功能、正文用语与体裁（genre_gate）每次都查；STATUS.md 的“分维度状态”逐维列出机器能查的部分（维度清单见作者说明模板），任何一维没过都不是投稿就绪。写有设计、伦理与注册信息的材料（如分析笔记）也放进 `--results`，编号和伦理说法靠它核对。打开生成的 STATUS.md，先处理“必须先处理”，再处理“没能运行”的检查；后者不能算通过。你认为是误报的项目，保留原文，在作者说明里写上规则代码（每条末尾括号里的，如 section_lint R1）和理由；不为了全绿改坏正确的内容，也不换同义词绕过规则。重跑时沿用同一个 `--out`，脚本会另开新目录，旧报告不覆盖。
5. **交付并报告状态。** 交付前做作者拒收预演（`reject_drill.md`），再跑 `python scripts/station_check.py --project 项目 --manuscript 稿件`，退出 0 才交付。给作者稿件和一页作者说明（`assets/templates/author_delivery.md`）：用哪个文件、改了什么、还要作者确认什么、执行条件、引文核对程度与 benchmark_mode。每轮结束在对话里用三行说清：现在能用的文件；卡在哪里；下一步。作者说明按维度报告状态，不用一句“可交付”概括。
