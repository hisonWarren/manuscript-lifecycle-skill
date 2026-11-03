# 核实来源与借鉴边界

核查日：2026-10-25（用户时区）。这里记录的是规范、方法建议和开源项目本身；不是对它们效果的独立验证。网页会更新，正式投稿前重新查目标刊当前要求。网页全文、网页检索片段、论文全文、摘要、仓库说明必须分别记录，不能互相冒充。

## 一、优先使用的原始来源

| ID | 来源与本次访问程度 | 支持本 skill 的具体决策 | 边界 |
|---|---|---|---|
| S01 | [ICMJE：稿件准备](https://www.icmje.org/recommendations/browse/manuscript-preparation/preparing-for-submission.html)，官方网页正文 | 按研究设计选报告规范；各节分工；方法须足以复现；统计软件版本、预设与探索性分析须区分；结果避免逐项复述表格；引文核对原始出处与撤稿状态 | 医学投稿建议，不能替代目标刊规则；不支持“软件细节永远不写”“不利结果等审稿人问再说” |
| S02 | [APA：Table setup](https://apastyle.apa.org/style-grammar-guidelines/tables-figures/tables)，官方网页正文 | 表题简短；表注仅在读者确实需要时加入；表格独立可读；使用真实表格、必要边框、跨页重复表头 | APA 样式，不是全学科统一版式；横向页面等须服从目标刊 |
| S03 | [PLOS One：Tables](https://journals.plos.org/plosone/s/tables)，官方网页正文 | 题目在表上，注释在表下；首次引用顺序与编号一致；按期刊要求放置 | PLOS 的位置/网格线规定不直接套给 APA 或 Nature |
| S04 | [PLOS One：Figures](https://journals.plos.org/plosone/s/figures)，官方网页正文 | 文件名、图号、正文引用对应；尺寸、分辨率、图像完整性要求；阶段不同要求可能不同 | 元数据合格不等于图形清晰；不依据 DPI 数字宣称已验看 |
| S05 | [Nature：Formatting guide](https://www.nature.com/nature/for-authors/formatting-guide)，官方网页检索缓存正文；直接打开发生跳转失败 | 表下注释应简短且必要；图注定义面板、符号和误差；方法与说明分工；图表尺寸影响可读性 | 本次访问不是直接网页全文成功。其图注词数等上限是 Nature 专属且需投稿时重查，不写进通用硬门控 |
| S06 | [EQUATOR：什么是报告规范](https://www.equator-network.org/about-us/what-is-a-reporting-guideline/)，官方网页正文 | 由设计匹配 CONSORT、STROBE、PRISMA、STARD、TRIPOD、CARE、SRQR/COREQ 等；取得实际清单及适用扩展 | 清单是报告下限，不保证设计质量；版本须按当次官网核实 |
| S07 | [EQUATOR：STROBE](https://www.equator-network.org/reporting-guidelines/strobe/)，官方网页正文 | 横断、队列、病例对照按对应清单；条目映射至稿件位置 | STROBE 明确不用于评价研究质量，不把“清单全勾”算研究有效性通过 |
| S08 | [Crossref：Retraction Watch](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/)，官方网页正文 | 可从 REST API 与数据集核查撤稿；记录检索日、DOI、原文/公告关联 | 纠错和关注声明覆盖较撤稿不完整；未命中不等于已证明无问题；要复核出版商页面 |
| S09 | [Crossref：Crossmark](https://www.crossref.org/crossmark/)，官方网页正文 | 查更正、撤稿及版本更新，回到正式公告 | Crossmark 标识本身不是保证；缺少标识也不是问题证据 |
| S10 | [ICMJE：作者使用 AI](https://www.icmje.org/recommendations/browse/artificial-intelligence/ai-use-by-authors.html)，官方网页正文 | 人类作者负责；按要求在投稿信和稿件适当位置披露实际用途；AI 不能作作者或原始事实来源 | 披露文案必须对应真实使用记录与目标刊政策，不能生成虚构声明 |
| S11 | [PLOS One：返修](https://journals.plos.org/plosone/s/revising-your-manuscript)，官方网页正文 | 逐点回复；干净稿与标记稿；核实原图表/补充材料是否沿用或替换 | 这是 PLOS 文件要求示例，其他期刊需单独确认 |
| S12 | [Mensh & Kording，2017：Ten simple rules for structuring papers](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005619)，出版社论文正文相关段落 | 围绕核心贡献组织读者的信息路径；先画证据支持主张的逻辑，再写段落 | 写作建议，不是实验验证的普适阈值；已读 [2017 更正公告](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005830)，修正 Fig 1 缺少图例 key，并非撤稿 |
| S13 | [Noble，2017：Ten simple rules for writing a response to reviewers](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005730)，出版社论文正文相关段落 | 一条意见含多个问题时拆分；直接答复；区分原稿已有内容与此次改动；注明修订版本位置 | 不机械采纳所有审稿建议；不为了服从而做无效或不当分析 |

## 二、公开的去 AI 味写作指南：可迁移与不采纳

这些指南只作为模式线索，没有复制其代码或提示词。可迁移的做法：先定位真实出现的模式，再改写，最后核对原主张；单个标点或词不足以定罪；
保护否定、归因、条件和确定程度；检查要引用具体原句；每处改动说明原因；记录数字与极性是否漂移；清楚的段落可以不改；
分清多余辩护与必要范围；学术语域单独处理，不套用博客或评论的风格偏好。

不采纳：以检测分数或“像不像人写的”验收；随机长短句或制造不规则；口语化、人格化声口；反检测目的；
用模式数量或项目关注度判断写作质量。

## 三、如何变成可验收的行为

1. 每条语言意见写原句位置、上下文问题、保留的信息、修改理由；同一模式允许“无问题，保留”。
2. 优先级：事实/数字/极性/条件/引用绑定 → 研究与章节职能 → 目标刊 → 同类语料 → 作者风格 → 表面模式。
3. 分布仅触发复核。不得为了更像中位数，删必要解释、补虚构细节或更换准确术语。
4. 每次修订同时检查新增、删失、加强、弱化与归因迁移；数字集合相同仍可能比较对象互换。
5. 用正例、反例和“无需修改”例验证，不用改动数量、词表命中率、检测器分数宣布质量收敛。

## 补充：顶刊格式规则（核查日 2026-10-26）

| ID | 来源与访问程度 | 支持的决策 | 边界 |
|---|---|---|---|
| S14 | [Nature：Formatting guide](https://www.nature.com/nature/for-authors/formatting-guide)，官方正文经检索缓存读取 | 标题、摘要段、图注、表注、方法的写法与上限，见 `assets/journal_profiles/nature_article.json` | Nature 专属；小标题 40 字符只见于存档副本，标为未核实 |
| S15 | [Cell Press：Final submission](https://www.cell.com/device/information-for-authors/final-submission)，官方正文 | Highlights 条数与字符、In Brief 写法 | Cell Press 专属；Cell 的标题与 Summary 上限只见于二手对照表 |
| S16 | [Elsevier：Highlights](https://www.elsevier.com/researcher/author/tools-and-resources/highlights)，官方正文 | Highlights 只写结果、每条 85 字符 | 各刊条数不同，按目标刊 |
| S17 | AMA Manual of Style 摘要章节（检索片段）与出版商社论对照表 | Science 摘要不超过 125 词、非结构式 | 二手来源；未取得 science.org 原文，档案标为未核实 |

## 四、文献核对接口（核查日 2026-10-27；依据官方文档的镜像与实际返回样本）

| ID | 来源 | 支持的决策 | 边界 |
|---|---|---|---|
| S20 | Crossref REST API 文档（github.com/CrossRef/rest-api-doc） | `/works/{doi}` 取注册记录；`updated-by` 给更正、撤稿等更新 | 只证明注册可检索；不比对语义 |
| S21 | Crossref：Retraction Watch 数据说明页 | 撤稿信息可经 Crossref 取得 | 未命中不等于没有问题 |
| S22 | OpenAlex API 与 LLM quick reference（页面称 2026-10-15 更新） | `/works/doi:…` 取记录；`is_retracted`、开放获取入口；MCP 端点 https://mcp.openalex.org/mcp | 命中属于 L1；不等于主张支持或分布对标 |
| S23 | Cursor MCP 文档摘录 | MCP 配在用户环境（全局或项目 mcp.json），密钥用 `${env:…}` | 不是本技能的依赖 |
| S24 | 实拉样本：10.1371/journal.pcbi.1005619 的 Crossref 与 OpenAlex 记录 | 更正信号示例（updated-by → 10.1371/journal.pcbi.1005830） | 记录会更新；样本只作测试与教学 |
