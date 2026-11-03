# 23 · 文献证据阶梯：DOI、撤稿与更正、主张支持、写法对标

“查过文献”“DOI 已核实”“已和同类文献对标”这几句话，必须有对应的记录才能写。原因很简单：网页搜索看起来像查过，模型记忆也常常自信地给出错误的 DOI。本页把文献工作拆成四层，每层分开记账，并规定每种条件下最多能说到哪一步。上层成功不会自动点亮下层：DOI 能解析，不等于原文支持你的句子。

这四层都在核对“已经引的”。在它们之前还有 L0「覆盖」：该引的有没有引（[24](24_literature_coverage.md)）。四层全部通过，只证明已引的引对了；能不能说“文献充分”，看覆盖表有没有未关闭的缺口（coverage_check CV7 拦截与缺口并存的“投稿包备齐”）。

## 1. 四层与取值

| 层 | 回答的问题 | 字段与取值 | 明确不等于 |
|---|---|---|---|
| L1 书目 | 这条文献存在吗？参考文献条目写对了吗？ | `doi_status`：resolved_crossref、resolved_openalex、resolved_other、not_in_index、not_verified、format_only、unchecked；`identity`：matched、mismatch、unchecked | 主张正确 |
| L2 版本 | 有没有更正、撤稿、关注声明？ | `version_status`：checked_clean、correction、retracted、expression_of_concern、unchecked、inconclusive | 未命中 = 已证明没有问题 |
| L3 主张支持 | 本句主张被原文支持到什么程度？ | `citation_access`：fulltext、abstract、metadata、metadata_web、unresolved；`relation`：supports、partially_supports、does_not_support、contradicts、unchecked | 只有元数据或搜索摘要 |
| L4 写法对标 | 节的职能、信息量、句式分布有没有外部尺子？ | `benchmark_mode`：distribution、domain_pack、case、none | “我见过同类论文”；一两篇或只看摘要的百分位 |

**主张类型决定需要的访问程度**（台账的 `claim_type`）：数字、方法、机制、比较、具体发现要读到全文（fulltext）；“已有研究讨论过某个问题”这类存在性、背景性主张，至少要读到摘要；只证明“这篇文献存在”的书目信息，元数据即可。`metadata_web`（只有搜索片段）不能支撑任何承重句。

**几条固定的读法**：

- Crossref 查到只说明注册可检索，查不到也不等于伪造（可能在其他注册机构）。
- 请求了在线核对却失败，记 `not_verified`，不能改口说已核实。
- `checked_clean` 只表示当时在所查来源里没看到撤稿或更正，要写来源和日期，不能升格为“文献可靠”。
- 有更正或撤稿时，要读更正公告，在 `notes` 里写明它是否影响本句引用的那一点。例：Mensh 与 Kording 2017 年的论文（10.1371/journal.pcbi.1005619）在 Crossref 记录里有 `updated-by` 更正（10.1371/journal.pcbi.1005830）；样本记录见 `assets/examples/literature/`。

## 2. 每种条件下最多能说到哪一步

执行条件写在作者说明第一行：EXECUTE（能跑脚本）、EXECUTE+NET（能跑脚本也能联网）、REASONING-ONLY（都不能），另列可用工具（脚本、网页搜索、浏览器、MCP）。

| 条件 | L1 书目 | L2 版本 | L3 主张支持 | L4 对标 |
|---|---|---|---|---|
| 脚本 + 联网（如 Cursor 本机） | `lit_evidence.py resolve --online`、`ref_check.py --online` → resolved_* 与 identity | Crossref `updated-by`（含 Retraction Watch 来源）+ OpenAlex `is_retracted`；必要时打开出版商公告 | 本机全文（作者给的 PDF/MD、开放全文），记位置与指纹 → fulltext | 本机可比全文 + `bench_profile`/`phrase_contrast`/`move_check` → distribution；只有领域包 → domain_pack |
| 脚本 + MCP（OpenAlex、Zotero 等） | MCP 与脚本双通道，记两边结果 | 同上，加库内标记 | Zotero 等库里的全文与段落页码 → fulltext | 从文献库导出全文进本地语料，清洗、按 DOI 去重后跑脚本 |
| 只有网页搜索（如 Claude 网页版、手机端） | 最高 `metadata_web`；如果实际打开并保存了注册库记录本身（api.crossref.org 或 api.openalex.org 的条目），可记 resolved_* 并写工具 | 只有实际打开了公告页才记，写网址和日期；否则 unchecked | 只有实际读到开放全文才记 fulltext，否则 abstract 或 metadata_web | 禁止 distribution；最多 case，或用随技能的领域包记 domain_pack |
| 都没有（REASONING-ONLY） | 全部 unchecked 或 not_verified；可以沿用以前带工具和日期的记录，tool 里写“沿用” | unchecked | 只有本地已有全文时才记 fulltext | none，或 domain_pack（领域包随技能提供，不需要联网） |

任何一列都不能空着：工具不够时写清降到了哪一层，而不是假装这一层不需要。

## 3. 工具库存（全部保留；P0 为默认，P1、P2 按可得性启用）

本技能运行不依赖任何 MCP。MCP 和外部 API 装在用户自己的环境里（Cursor 为 `~/.cursor/mcp.json` 或项目内 `.cursor/mcp.json`），密钥只用 `${env:…}` 引用，不进技能目录。没装 MCP 不等于技能损坏，只是降到上表对应的一行。示例配置见 `assets/templates/mcp_template.json`。下表来自用户 2026-10-27 的整理；第三方实现的能力、维护状态与许可证，启用前自己核对，本技能没有逐个验证。

| ID | 工具 | 用在哪一层 | 默认优先级 | 备注 |
|---|---|---|---|---|
| S01 | `scripts/ref_check.py`（本地格式、双向引用；`--online` 查 Crossref） | L1 | P0 | 只证明注册可检索 |
| S08 | `scripts/lit_evidence.py resolve`（Crossref + OpenAlex，比对题名作者年份，读 updated-by 与 is_retracted） | L1、L2 | P0 | 结果写进引文台账；`check` 拦越界说法 |
| S09 | `scripts/reference_identity.py`（单条 DOI 的书目比对） | L1 | P1 | 与 S08 同一逻辑，适合单条排查 |
| S02 | `scripts/bench_profile.py` | L4 | P0 | 需要可比全文或领域包 |
| S03 | `scripts/phrase_contrast.py` | L4 | P0 | 同上 |
| S04 | `scripts/move_check.py` | L4 | P1 | 核语步编码的原文摘录 |
| S05 | `scripts/domain_pack.py`（领域包） | L4 | P0（无全文时） | domain_pack 模式 |
| S06 | `scripts/verify_evidence.py` | L3 | P1 | 证据指纹 |
| S07 | `scripts/check_all.py`（`--citations`、`--note`） | 汇总 | P0 | 把 FAIL 说法列进 STATUS |
| M01 | OpenAlex MCP（https://mcp.openalex.org/mcp） | L1；L2、L3 的入口 | P1 | 文档称可检索、引文追踪、参考文献核对 |
| M02 | OpenAlex HTTP API（https://api.openalex.org） | L1 | P0（经 S08） | 建议 api_key；429 时退避 |
| M03 | Crossref REST（https://api.crossref.org） | L1、L2 | P0（经 S01、S08） | `updated-by` 给更正与撤稿信号 |
| M04 | 浏览器（如 Cursor 的浏览器工具） | L2、作者须知、偶尔 L3 | P1 | 不是文献库 |
| M05 | 宿主自带 WebFetch / WebSearch | 最多 metadata_web | P2 | 不是机械 DOI 协议 |
| M10 | mcp-zotero（npm，云库只读） | L1（库内） | P2 | 无全文时只到 metadata |
| M11 | zotero-mcp / zotero-mcp-server（54yyyu） | L1–L4 语料来源 | P1 | 语义检索、PDF、标注、本地库；适合导出对标语料 |
| M12 | @oscardvs/zoteus | L1–L3 | P1（Zotero 默认推荐） | PDF 段落与页码，便于记 L3 位置 |
| M13 | cookjohn/zotero-mcp | L1–L3 | P2 | 插件加服务器；全文、标注 |
| M20 | Semantic Scholar API 或社区 MCP | L1 辅助 | P2 | 启用前核对官方条款 |
| M21 | Unpaywall | L3 入口（开放 PDF） | P1 | 找到全文后读了才算 fulltext |
| M22 | Crossref 的 Retraction Watch 数据 | L2 | P0（经 S08 读取） | 未命中不等于没有问题 |
| M23 | Crossmark | L2 | P1 | 标识本身不是保证 |
| M24 | PubMed / Europe PMC（API 或 MCP） | L1、摘要级 L3 | P1（生物医学） | 按领域启用 |
| M25 | 机构图书馆代理或 EZProxy 浏览器流程 | L3（付费全文） | P2 | 只在用户环境；不进可分享技能 |
| M26 | 本地文件夹（filesystem MCP 或直接读写） | L3、L4 | P0 | 作者自己的文献 MD/PDF |
| M27 | doi.org 解析与出版商页面 | L1 辅助 | P2 | 跳转与反爬时降级 |
| — | 模型记忆 | 无 | 禁止 | 一律记 unresolved，直到外部核对 |

**默认路径**：有脚本和网络时，L1、L2 走 S08（必要时 S01），L3 读本机全文并在台账记位置，L4 用本机可比全文跑 S02、S03，没有全文就用领域包（domain_pack）。装了 Zotero 时 L3 优先 M12（能给页码），要导出对标语料时用 M11；装了 OpenAlex MCP 时，L1 与 S08 双通道，两边结果都记。

## 4. 引文台账与作者说明的必填字段

台账模板：`assets/templates/citation_ledger.csv`。每条承重引文一行：claim_text、claim_type、doi_or_url、ref_title、ref_first_author、ref_year、doi_status、identity、version_status、version_source、version_checked_at、citation_access、relation、source_locator、tool、checked_on、notes。`lit_evidence.py resolve` 会填 L1、L2 的字段并写出新文件，不覆盖原台账；L3 的 citation_access 与 relation 要读过原文的人来填。

作者说明（`assets/templates/author_delivery.md`）必写：执行条件与可用工具；承重引文的核对汇总（各 citation_access 有几条、doi_status 分布）；`benchmark_mode` 与对标语料、报告路径；限制。

```text
python scripts/lit_evidence.py resolve --ledger citation_ledger.csv --out ledger_checked.csv --online
python scripts/lit_evidence.py check --ledger ledger_checked.csv --text 作者说明.md manuscript.md --execution EXECUTE+NET --benchmark-mode case
python scripts/check_all.py manuscript.md --citations ledger_checked.csv --note 作者说明.md --execution EXECUTE+NET
```

## 5. 判为 FAIL 的说法

稿件、作者说明、审查报告、STATUS、回复信里出现下列说法而没有合格记录支撑，就是 FAIL。`lit_evidence.py check` 按这张表扫描；否定说法（“DOI 未核实”）不计。条目只增不删。

| ID | 说法或做法 | 合格前提 |
|---|---|---|
| F01 | “DOI 已核实 / DOI verified” | 承重条目的 doi_status 都是 resolved_*，且写了工具与日期 |
| F02 | 在线核对失败却写已核实 | 只能记 not_verified |
| F03 | “引文正确 / 文献支持该结论”，依据只是 DOI 能解析 | relation 有记录，且 citation_access 与主张类型相称 |
| F04 | “已完成同类文献对标 / 分布对标” | benchmark_mode=distribution，有本地可比全文（默认至少 8 篇）和存在的报告 |
| F05 | 一两篇或只看摘要就报百分位、“同类少见” | 最多 case，不用分布口吻 |
| F06 | “按领域包对标了近邻全文” | 领域包是统计基线；写“领域包基线参照” |
| F07 | “未发现撤稿，所以文献可靠” | 任何时候都不成立 |
| F08 | 据记忆、据训练数据支撑承重引文 | 一律 unresolved，直到外部核对 |
| F09 | 用网页搜索后写“已机械核实” | 最高 metadata_web |
| F10 | 没联网却写查过 Crossref / OpenAlex | 与 REASONING-ONLY 矛盾；沿用旧记录要写“沿用”与原日期 |
| F11 | 把没装 MCP 说成技能损坏 | MCP 不是依赖 |
| F12 | 把搜到的论文直接当对标语料进分布 | 入本地语料、清洗、按 DOI 去重后再跑脚本 |
| F13 | DOI 能解析但题名、作者或年份对不上，仍写已核实 | identity=matched |
| F14 | relation=supports，但访问程度配不上主张类型（如数字只读过摘要） | 见 §1 主张类型规则 |
| F15 | 有更正、撤稿或关注声明，却没写是否影响本句引用 | notes 写明影响 |
| F16 | 写“已核文献”，却没有台账或台账为空 | 先建台账 |

## 6. 分阶段落地与验收

1. **记录先行（无网也能做）**：执行条件、台账字段、作者说明必填项、FAIL 扫描。验收：三种条件下（脚本+联网、只有搜索、无网）作者说明对同一组文献的说法与台账一致，`lit_evidence.py check` 退出 0。
2. **机械核对（有网）**：`resolve --online` 填 L1、L2，`--save-raw` 保存注册库原始记录供复查。验收：样本 DOI 的更正被识别；断网时全部记 not_verified。
3. **增强层（可选）**：OpenAlex MCP 与脚本双通道；Zotero 提供 L3 全文与页码、L4 语料。验收：作者说明写明用了哪个 MCP、到了哪一层；不装时降级说法仍然合格。
4. **对标**：可比全文入本地语料后跑 S02、S03；不足 8 篇写 case。验收：没有全文时，任何文件里都不出现“已完成同类文献对标”。

**明确禁止**：把 MCP 写成安装前提；因为某个工具“可选”就从库存里删掉；把模型记得的文献记为已核；把 Crossref 或 OpenAlex 命中当成主张被支持；只凭摘要或搜索片段报分布；把密钥写进技能或作者说明。

## 7. 概括前人研究的句子是比较性主张

“These studies located the effect by…”“Previous work has not…”“remains unknown”这类句子不挂在某一条引文上，常常逃过逐条核对，却最容易把前人写窄（一次实测：把一篇同时分析了“条件 × 长短反应”的近邻概括成“只比较条件均值”）。这类句子按 claim_type=comparison 处理：所概括的每一篇都要读到全文（或把读不到全文的移出这句），在台账登记 claim_location 写到段（如 Introduction para 3）。claim_strength LG1 核对。写增量时说清本文多做了什么（如条件内的单试次检验），比把前人写成统一的薄弱做法更可信。
