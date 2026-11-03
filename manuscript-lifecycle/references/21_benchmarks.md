# 21 · 标准从哪里来：目标刊、领域标杆、顶刊规则

“写得好”不由本 skill 自行设定。遇到“该多长、该多细、该不该写”的问题，按下面的次序取标准，并在决策登记里写明用的是哪一级。

| 次序 | 来源 | 地位 | 怎么取 |
|---|---|---|---|
| 1 | **目标刊当期作者须知** | 硬要求 | 联网取当期页面，记 URL 与访问日，写进 `assets/journal_profiles/` |
| 2 | **同刊或领域旗舰刊中的近邻论文** | 写法参照 | 按节匹配 3–5 篇；先核对题名、DOI 与实际研究类型 |
| 3 | **领域包里的分布** | 分布参照 | `assets/domains/`，回答“这个领域通常怎样” |
| 4 | **顶刊的公开规则** | 通用原则 | 见下表；它们管通用写作原则，不是你那本刊的硬指标 |

次序不能颠倒。顶刊规则写得最清楚，但**它只对那本刊有约束力**。拿 Nature 的图注上限去卡一篇临床刊的稿子，是把参照当成了规则。

## 一、顶刊规则及其核实状态

核查日 2026-10-26。规则会改版，所以每一条都写进了 `assets/journal_profiles/`，带来源与核实状态；`journal_check.py` 对未核实的条目只报候选，不判 FAIL。

| 刊 | 规则 | 来源与核实 |
|---|---|---|
| Nature（Article） | 标题不超过 75 字符（含空格；Letter 为 90），不用数字、缩略语与标点 | 官方格式指南正文，已核实 |
| Nature | 摘要段约 200 词、至多 300 词，带引文，面向其他学科读者；除必要外不用数字与缩写；用 Here we show 引出主要结论 | 同上，已核实 |
| Nature | 每条图注少于 300 词；有方法节时图注不写方法细节；先给整图简短标题，再逐面板说明符号；误差条与统计量在图注中定义 | 同上，已核实。历史版本另写过“有方法节时 100 词”，当前官网未写，不按 100 判 |
| Nature | 小标题不超过 40 字符（含空格） | 只见于官方信息页的存档副本，当前官网未确认 → 未核实，只作候选 |
| Nature | 表题简短；表下注释尽可能简短，先定义符号 | 官方格式指南正文，已核实 |
| Nature | 方法简洁但足以复现；已发表的方法只给引用，并说明本次的改动 | 官方格式指南正文，已核实 |
| Cell Press | Highlights 3–4 条，只写结果，每条不超过 85 字符（含空格），不用行话与缩写 | Cell Press 终稿材料页与 Elsevier Highlights 页，已核实 |
| Cell Press | In Brief（eTOC blurb）不超过 50 词、两句、第三人称，写意义而不是复述信息 | Cell Press 终稿材料页，已核实 |
| Cell Press | STAR Methods 结构化、不限篇幅，不以“引回旧文献”代替写清做法 | 出版商页面，已核实 |
| Cell（Article） | 标题 85 字符；Summary 至多 150 词、不带引文 | 出版商社论里的格式对照表 → 未核实，投稿前到当期作者须知核对 |
| Science（Research Article） | 摘要不超过 125 词、非结构式，不带引文与缩写，首句让一般读者看懂；标题 96 字符 | 两个二手来源一致（出版商社论对照表、AMA Manual of Style 摘要章节）。本次未取得 science.org 原文 → 未核实 |

**一个必须注意的分歧**：Nature 要求方法精简，已发表的方法只给引用；Cell Press 的 STAR Methods 要求结构化、详尽、不限篇幅。两家顶刊在同一件事上方向相反，所以“方法越短越好”不是通则，“方法越细越好”也不是。按目标刊走。

## 二、各领域常被当作标杆的期刊

这份清单来自通用知识，**不是本次检索的结果**，只用来起步找近邻论文。期刊地位会变，各学科内部也有分歧；真正的标准仍是目标刊的作者须知。使用前先核对该刊是否仍在出版、是否改名、栏目是否仍收这类论文。

| 领域 | 国际 | 中文 | 常用报告规范 |
|---|---|---|---|
| 综合 | Nature、Science、PNAS、Nature Communications、Science Advances | 中国科学、科学通报 | 按设计选 |
| 医学（临床） | NEJM、Lancet、JAMA、BMJ | 中华医学杂志 | CONSORT、STROBE、STARD、TRIPOD+AI |
| 公共卫生 | Lancet Public Health、Lancet Global Health、American Journal of Public Health | 中华流行病学杂志 | STROBE、RECORD |
| 心理学（实验与认知） | Psychological Science、JEP 系列、Cognition、Psychological Review | 心理学报、心理科学进展 | JARS |
| 临床心理与精神医学 | JAMA Psychiatry、Lancet Psychiatry、Clinical Psychological Science、Psychological Medicine | 中国临床心理学杂志 | CONSORT、STROBE、COSMIN |
| 神经科学 | Nature Neuroscience、Neuron、eLife、Journal of Neuroscience | 生理学报 | ARRIVE（动物研究） |
| 生物与细胞分子 | Cell、Nature、Molecular Cell、Cell Reports | 中国科学：生命科学 | ARRIVE、MIAME 类 |
| 教育学 | Review of Educational Research、American Educational Research Journal、Computers & Education、Learning and Instruction | 教育研究、开放教育研究、电化教育研究 | JARS、PRISMA |
| 经济与管理 | American Economic Review、Quarterly Journal of Economics、Econometrica、Management Science、Academy of Management Journal | 经济研究、管理世界 | 期刊自定的数据与复现规范 |
| 社会学 | American Sociological Review、American Journal of Sociology | 社会学研究 | COREQ、SRQR（质性） |
| 计算机与人工智能 | NeurIPS、ICML、ICLR、ACL、CVPR、IEEE TPAMI | 计算机学报、软件学报 | 会议自定的 checklist 与复现声明 |
| 方法学与统计 | Psychological Methods、Statistics in Medicine、JRSS-B、Behavior Research Methods | 心理科学进展（方法综述） | 期刊自定 |
| 综述与证据合成 | Cochrane Database of Systematic Reviews、Annual Review 系列 | 各刊综述栏目 | PRISMA 2020、PRISMA-ScR |

用法：**先找同刊，再找同领域旗舰，最后才用这张表。** 近邻要分层并写类型匹配：至少 3 篇全文，旗舰与领域惯习各至少一篇；类型不对的只作反例，不纳入职能对照（[27](27_genre_and_placement.md) §3）。 近邻论文的判据是问题类型、设计和章节职责相近，不是期刊名气大。影响因子高的论文不等于适合对标的论文。

## 三、它们能证明什么、不能证明什么

- 顶刊规则能证明“这本刊这样要求”，不能证明“所有刊都该这样”。
- 实测分布（`assets/benchmarks/`、`assets/domains/`）能证明“同类论文通常在这个范围”，不能证明“超出范围就是错的”。
- 近邻论文能证明“同类问题可以这样展开”，不能替读者判断本文的论证是否成立。
- 没有任何一级能免除必要披露。期刊的篇幅限制不是漏报的理由。

有理由的偏离可以保留，写进决策登记：目标刊格式、如实报告的不显著结果、作者要求的篇幅，都是正当理由。


## 四、近邻也是选材的尺子

近邻不只用来学措辞与节职能。这一类论文的作者选择呈现哪些分析、呈现多少、放在主文还是补充、为什么不放别的，同样要从同类论文里学。而且要读得够广：按主题、领域、方法、分析、背景、目标刊与旗舰刊分别找。调研的维度、数量与编码方法见 [29](29_selection_and_survey.md) §4。
