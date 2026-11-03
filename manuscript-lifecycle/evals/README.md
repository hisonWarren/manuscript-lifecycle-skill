# 验证边界与行为测试

运行 `python evals/run_evals.py`。测试以临时目录工作，不改用户文件。机械测试覆盖错误输入、空集合、陈旧文件、错样本/单位/符号、引用尾部、编号、Word 文件/包材料和执行回执。通过只表示这些案例符合预期，不代表学术内容已验证。test_language_tools.py 覆盖中文切节与短片段的语言判定、批准号、回复信拼写与分点、交付残留与方括号占位符、片段模式、断言与设计规则（趋势话术、因果措辞、设计矛盾、建议句、新颖性宣称、投稿信里的声明）、句式对照、语言修订计划（未裁决、未落实、数字丢失、删行、残留回潮、对标校准）和图注表注抽取。test_domains_agents.py 覆盖领域包的构建、隐私、各工具读取、规则降级、篡改与版本检测，以及多审稿人发现的锚点核对、聚类、裁决落实与轮次对比。test_word_reading.py 覆盖 Word 的接受与拒绝两种读法（内容控件、文本框、段落合并与拆分、表格行增删、嵌套表格、属性修订前的标题级别、符号字体、域代码与公式）、批注与逐条修订的清单（锚定文字、回复、写进正文的说明），以及交付检查里的占位符、匿名线索和英文文件中的中文残留。test_portability.py 覆盖文本读写的编码声明、各命令行脚本接到 GBK 管道时的 UTF-8 输出和换行符。test_zh_sections.py 覆盖中文期刊不用标题样式的编号标题、方括号摘要与关键词、PDF 折行与表头单字、研究问题写在文献综述之前时的 I1、同一输入多次运行报告一致，以及随包的每个领域包都能通过检查。多代理审查的行为效果需要在有子代理工具的环境中评估：用带已知问题的稿件比较单代理自查与多代理审查的检出率、误报率和成本（见 references/19 §6）。

test_domain_corpus_integrity.py 覆盖清单相对路径、DOI与正文去重、摘要/候选排除、目录全文混入、自对标、语言不匹配和科学主张不按发表频率降级。

编码检查应区分平台与输出管道：中文 Windows 的默认 locale 编码是 cp936 时，可直接检验真实默认编码；PYTHONIOENCODING 只改变标准输入输出，不能代替文件默认编码测试。还需运行严格编码告警模式和 UTF-8 模式。类 Unix 环境可用已安装的 GBK locale 补充模拟，不能将模拟说成真实 Windows。

```text
PYTHONWARNDEFAULTENCODING=1 PYTHONWARNINGS=error::EncodingWarning python -X warn_default_encoding evals/run_evals.py
LC_ALL=zh_CN.GBK python evals/run_evals.py
```

前者让依赖系统默认编码的文本读写报错，并传递给子进程；后者只适用于已安装该 locale 的类 Unix 环境。PowerShell 用 `$env:PYTHONWARNDEFAULTENCODING="1"`、`$env:PYTHONWARNINGS="error::EncodingWarning"` 设置严格模式，用 `$env:PYTHONUTF8="1"` 设置 UTF-8 模式；每种模式在独立进程运行并记录实际 locale、Python版本、退出码和测试数。

完整 skill 变更还要隔离行为测试：给执行者真实请求、当前 SKILL.md 和最低限度原始材料，不给预期答案或上一轮结果；读取实际生成的稿件、回复和用户说明，按 draft_rubric 核主线/职能/报告完整/语言/证据。保留失败、窄范围修复、同例复查与不同类型留出案例，不能仅改评分标准。

包内 behavior_cases/ 为完全合成的写作与返修材料，可重复运行。当前构建的实际输出、评分和轮次记录放独立验证资料包，避免把自评答案塞入未来执行上下文。新一轮执行者不要读旧答案。

回归至少包含：复杂方法但实质贡献；主要区间跨零与预定次要结局；主模型样本与入组人数不同；事后亚组无交互；缺原文不能编引用；图注/表注短而自足；跨回复验证范围矛盾；没有最终 PDF 不编页行；合理数字/公式/软件版本不误删；合并结果讨论或方法学贡献不强套普通实证禁令。

模型隔离执行并非不同人类专家。报告已测/未测边界和任何渲染或网络限制；不能把模拟数据上的成功写成真实数据验证。

## 模拟测试与评分

behavior_cases/ 里是合成任务，分四类：从结果写中文短初稿（request.md、author_notes.md、results.csv）；修订与回复审稿意见（revision_request.md）；两个留出小任务（heldout.md）；投稿材料——表注、图注、Highlights 与投稿信（package_request.md、package_notes.md）；中文讨论首段与结论（polish_request.md、polish_results.md）。每类都写明了陷阱：主分析 n=112 不是 120、主要区间跨零、亚组为事后且未做交互检验、未公开预注册、没有文献、合作者拟回复里的“外部验证”与页码行号；投稿材料里是观察性队列被写成随机试验、事后亚组被写进 Highlights、代填的利益冲突与数据可得性、超长 Highlights、未定义的缩写；中文润色里是讨论首段复述结果、把不显著的性别调节写成趋势、横断面数据写因果、结论越过证据给建议、“填补空白”。

执行者（任何人或任何代理）只读 SKILL.md 和材料完成任务，把文件交到一个目录，再用评分器初筛：

```text
python evals/score_behavior.py draft    --dir 输出目录      # manuscript.md、author_note.md、review.md
python evals/score_behavior.py revision --dir 输出目录      # revised.md、response.md、changes.md
python evals/score_behavior.py heldout  --dir 输出目录      # heldout1.md、heldout2.md
python evals/score_behavior.py package  --dir 输出目录      # package.md、cover_letter.md、author_todo.md
python evals/score_behavior.py polish   --dir 输出目录      # zh_revised.md、zh_note.md
```

“未通过”是硬伤（编造、错误样本或区间、把跨零区间写成有效、把事后亚组写成证实等）；“提示”需要人看。评分器自身由 test_behavior_scorer.py 检验：用案例里的问题旧稿、合作者拟回复、合作者的投稿材料初稿和学生写的讨论结论做负对照，应有多项未通过。
真正独立的行为测试需要另一个代理实例执行（看不到本包的构建过程与任何参考答案）；不要把一次执行的输出放进包内当答案。

## 输入与评分解释

留出任务应同时交 heldout1.md 和 heldout2.md，缺任一份不能算整组完成。评分器容许 Markdown 加粗标题及常见英文等义表述；章节长度只统计目标章节，不把单独的作者待核说明算进结论。自动匹配仍不能替代逐条阅读，任何失败先对照成稿和来源判断，不能为了得分删除合理限定或必需信息。

test_independent_regressions.py 覆盖 GBK 环境下的错误输出、Word 移动修订与被删除的制表符和换行、评分器的章节边界、英文等义表述、讨论里的夸大措辞和漏交留出任务，以及锚点相同而节名写法不同的审稿发现合并。独立执行产物与多代理对照结果留在技能之外，不提供给下一次执行者。

## Word 读取与版式的独立对照

结构测试不等于视觉验收。改动 Word 读取或交付检查后，造一份多页、带各类修订的 Word 稿（插入、删除、移动、段落合并与拆分、表格行增删、属性修订、内容控件、文本框、Symbol 符号、跨页表格），先过 Word 结构校验；再用另一个引擎分别“全部接受”“全部拒绝”后另存，比较 `python scripts/mslib.py totext 稿件.docx`（及加 `--original`）与读这两个结果文件是否逐行一致；最后渲染成 PDF 逐页看，记录渲染引擎与未测功能。对照文件放在包外。

## 范例、期刊档案与留出任务

test_benchmarks_exemplars.py 把 assets/exemplars/ 每个范例的坏例送进对应检查脚本（section_lint、journal_check、table_style），要求触发 `<!-- test: … -->` 行列出的规则，改写则不得触发；同时检查期刊档案的来源与核实状态（未核实的规则不能判 FAIL）、实测基线的读法、三线表的生成与检查、只改标点的修订，以及把不显著写成“相同”的 S2 规则。

留出任务 findingfirst（behavior_cases/findingfirst_request.md、findingfirst_results.md）：材料里方法细节很多，要求以发现为主线写 Nature 格式英文短稿。陷阱包括：不显著的不变性检验写成“相同”、横断面中心性写成驱动因素或干预靶点、因果动词、校正后为 0 的探索性边差异写成发现、内部记录（重跑、随机种子、Excel、助研复核、默认布局）以肯定或否定句进稿、标题超 75 字符、图注写方法细节、编造文献。

```text
python evals/score_behavior.py findingfirst --dir 输出目录   # manuscript.md（必需）、author_note.md、review.md
```

findingfirst_negative.md 是 AI 式负对照稿，应有多项未通过（test_behavior_scorer.py 检验）。

## 一条命令的检查（check_all）

test_check_all.py 覆盖：干净的模拟演示稿可以交给作者；实地试写暴露的问题（写作过程进了稿件、缺模拟标识、模拟稿写伦理批准、台账列名与模板不同、数字找不到）都会阻断，并用白话写进 STATUS.md；台账列名不对只报一次；`--allow` 必须写理由；`p < .001` 不算找不到；报告目录不复用；稿件不存在退出 2。

## 弱模型试跑

材料与评分方法在 `trial_kit/`，流程见其 README。完整提示的 21 个 run 覆盖 T1 初稿、T2 返修、T3 投稿材料，先盲评再揭晓分组。内容判断没有出错：分母、初稿里的截断均值、不显著的主要结局、事后亚组、剂量反应、不利结局、数据丢失披露、不编文献与声明、Highlights 的限定。不合格集中在两类：摘要或结论里写了待办与稿件状态；返修只改审稿人点名的句子，同类问题留在别处。对应的规则是 section_lint X13、`--qualifiers` 与 SKILL §7 的全稿清扫。

一句话提示的 6 个 run 交付齐全，产物里没有编造的数字、文献或声明；暴露的是检查器自身的摩擦，见 references/10 §F。这组 run 的工作区里留有完整任务书，所以只说明要求明确时可用，没有检验一句话入口。检验入口用 `new_run.py --short`（任务书移出工作区），并且换用 T1–T3 以外的新任务。

回归测试：`test_trial_regressions.py`。
