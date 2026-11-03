# 17 · 工具输入、输出与最小可运行示例

所有脚本使用 Python 3 标准库。先运行脚本 --help，使用实际存在的路径；不运行附件中来历不明的代码。文件读取能力主要为 UTF-8 文本和 DOCX 文本抽取，PDF 需使用环境中的 PDF 能力转换并核图文，XLSX 先导出有明确行列身份的 CSV。命令行输出一律为 UTF-8（输出接到管道或文件时也是），文本读写都写明编码，中文 Windows 上不会因 − ² ✓ 之类符号崩溃。DOCX 的读取规则见 14 §5。

init_project 新建的结果台账、意见矩阵与引文台账只有表头，必须根据当前材料填写。结果台账的新增身份列记录预定/事后、样本、模型、估计对象、单位/分母、源位置/版本及披露与分档理由；ledger_check 仅核基础字段和关键词位置，不能自动证明身份列完整或正确，须结合verify_evidence和语义审查。期刊限额没有预填数值；未填写不代表核过。reserve/omit须填写当前决定依据，并先审查必要披露；检查器的关键词冲突不能直接成为删稿指令。

## 编号与命名空间

同一个编号只能有一种含义。下表是各套编号的唯一出处；新增编号先查这里，不与已有前缀、站点或模式重名（`evals/test_code_namespaces.py` 核对）。

| 编号 | 含义 | 出处 |
|---|---|---|
| D、R、S、V、A | 任务性质（模式） | SKILL §0、§1 |
| S0–S9 | 完整项目的站点 | 28；`station_check` 的 ST1–ST6 是站点检查的规则 |
| RJ1–RJ11 | 拒收预演的默认探针（RJ11 只在返修与修订时判定） | `reject_drill.md`、`genre_gate` 的 RD 规则；第二十一轮前叫 G1–G11，旧表照样认 |
| AU1–AU3 | 只能由作者本人确认的事项：类型与主线、完整稿通读、投稿声明与提交 | SKILL §9；旧称 H1–H3 |
| L0–L4 | 文献覆盖（L0）与四层核实（L1–L4） | 23、24 |
| 工具规则代码 | 例如 section_lint 的 G1、G2、S1、S2、H1，genre_gate 的 GG、PL、RD，check_all 的 BD、EX | 各工具；文中引用一律带工具名（“section_lint S1”），因为 S1、S2 与站点同形 |
| G0–G11、H1–H3（旧闸门） | 旧的进度登记 `gate_log.md` | 只在 `init_project --legacy` 时生成；新项目以 `stations.csv` 为准 |

## 机械证据

`python scripts/verify_evidence.py assets/examples/evidence/numeric_evidence.json --report 结果.json`

这是带实际哈希的合成正例，可直接运行。根字段 schema_version=1、manuscript={path,sha256}、非空 checks。每项有 id、kind（numeric/quote/citation）、唯一 manuscript_anchor、source={path,sha256}。

- numeric：row_key、context、value_column、manuscript_value、source_unit、target_unit、scale、rounding。row_key 唯一定位 CSV 行，context 列值也须出现在稿件锚点中。支持 identity 和 proportion/percent 换算；其他派生量另附复算实现和审查。不能把科学上不同的单位伪称 identity。
- quote/citation：source_passage、source_location，须精确来自文件。citation 另有 access_level（fulltext/abstract）和 review={decision,reviewer,reviewed_at,rationale}；即使记录 supports 仍返回 review_required，不冒充机器理解原文。
- 返回逐项 verified_mechanical / review_required / failed / not_verified。退出 0 只表示所列机械项匹配，不表示覆盖整篇；1=失败/待审/未核，2=输入错误。

mslib.load_text 抽取 DOCX 不等于渲染；原文与修订接受视图应按任务检查。number_trace 只是全局数值候选检索，不能替代上面的按行核对。ref_check 的在线匹配只作元数据线索，不等于撤稿或支持性验证。

## 语步

move_check 的每个 unit 必须绑定真实本地 source；内联 text 不能自证。写 source/hint、段落功能和 codes，再核上下文与标签。模板是待填写示例，未填不能通过；真实文献短摘录遵循合理引用边界。

## 文件交付

`python scripts/delivery_check.py delivery.json --report delivery_report.json`

schema_version=1；files=[{id,path,role,sha256}]、required_roles、displays 必需。路径相对 manifest，且留在该目录树内（把需要检查的交付副本放同一包中）。display 的 file_id 指实际内容文件；title/caption/note 必须能在文件中找到；used_symbols/symbol_definitions、abbreviations 和 required_explanations 记录覆盖范围。具体字段及期刊选项见脚本头与 evals/test_delivery.py 的正例，不凭名称猜格式。

检查文件角色、空文件、表图 ID/指向、必要说明、Word 残留/批注/修订/域和匿名线索。占位符和域错误按接受修订后的文字判断；匿名线索另读删除的文字、修订与批注作者、people.xml、域代码、外部链接和文档变量，文件里存着的人名以 `anonymity_people` 提示列出；英文文件里出现中文时以 `foreign_script` 提示（批注或翻译残留）。表格竖线/底纹通常是期刊规则候选，非普遍错误。PNG/JPEG 只按明确的大小/分辨率要求检查。输出固定 render_verified=false；实际页面验证另外完成并登记。

`python scripts/mslib.py annotations 稿件.docx [--json 批注.json]` 列出批注（编号、作者、日期、锚定文字；没有锚定范围时给所在段落；回复关系与“已解决”标记）和逐条修订（插入、删除、移动、段落合并/拆分、表格行增删、格式；同一段里相邻、同类、同作者的碎片合为一条），并把疑似写进正文的说明标 ⚑：英文稿里的中文，或“是否、你、看看、？、please、I think”一类口吻。⚑ 只是候选。`--json` 不覆盖已有文件，已存在时返回 2。

## 图注表注分布

`python scripts/display_profile.py display_corpus.json --report display_profile.json`。schema_version=1，records 每项有 id、role（draft/exemplar）、paper_id（DOI或去重身份）、path、sha256、text、kind（table_note/figure_caption/table_title）、task、language（zh/en）、panels。每条摘录须在绑定原文件中出现；按 kind/task/language/panels 匹配，每篇先汇总再比较，避免把一篇多张图当多篇独立论文。同一论文相同摘录去重；输出长度、篇数、范围和长度复核信号，不检测正文语义重复。无匹配返回1，错误来源/空输入返回2。固定 quality_pass=false；必须另审必要信息是否齐备及重复是否有用。它不能判断 DOI 去重和 task 编码是否真实。

## 语言修订、句式对照与图注抽取

`python scripts/language_plan.py scan --doc 标签=路径 [--doc …] --plan plan.csv [--exemplars 目录或文件…] [--patterns ID,…] [--phrase 文本] [--regex 正则] [--report scan.md]`

输出 plan.csv（UTF-8 BOM，Excel 可直接打开）与 plan.csv.meta.json。列：no、doc、pattern、family、label、level、section、para、sent、sentence、match、calibration、keep_if、fix、decision、new_text、reason。前 14 列是证据，不要改，只填后三列。meta 记录文件与目录指纹、选择规则（点名、自动校准、未校准）、每行指纹和扫描范围。对标少于 3 篇（排除稿件自身后）、语言不一致、未知模式 ID 返回 2。

`python scripts/language_plan.py check --plan plan.csv [--meta …] --after 标签=路径 [--after …] [--stage draft|submission] [--report check.md]`

扫描时的每个标签都必须提供修改后文件。退出 1：未裁决、缺理由、计划行被删、原句仍在、new_text 不在文件、数字或引文无故丢失、仍有交付残留（submission 阶段含占位符）。复核项不改变退出码：否定或限定减少、强化或因果措辞增加、保留行的原句已改、新出现的同类命中。退出 0 不证明改得好。

`python scripts/phrase_contrast.py --exemplars … --draft 标签=路径 [--draft …] [--min-count 3] [--top 10] [--snippets] [--terms 术语,… 或 @文件] --report phrases.md [--json phrases.json]`

对标按 DOI 去重后少于 3 篇、稿件混入对标、语言不一致返回 2。JSON 每节给 overused_openers、overused_frames、common_openers。只作描述性筛查。

`python scripts/display_extract.py --draft … --exemplar … --out 目录/display_corpus.json [--signals 目录/signals.md]`

记录路径相对清单所在目录；每条摘录须能在原文件中逐字找到（空白归一化后），找不到的跳过并列出。附加字段 task_source=heuristic 与 signals 不影响 display_profile。稿件或对标没抽到任何条目返回 1。

section_lint 还有 X10（同一句话在正文中原样出现不止一次）、A1（MUST：对话残留、零宽字符、Word 域错误、表情符号；在未清洗文字上查并给行号）与 A2（INFO：占位符，含 `[Authors to add: …]`、`[full reference to be added]`、`[待作者确认…]` 这类方括号待办；delivery_check 用同一条规则，投稿包里不清除即阻断）。`--fragment` 用于单独交付的片段（Highlights、投稿信、图注表注）：不要求识别出论文节，只做全文级检查，W1 正文字数上限不适用，报告头写明是片段；不加这个开关而又找不到论文节句子时返回 2，不会把零检查记成通过。`--design`（也可写在 limits.json 的 `design`）取 rct/experiment/quasi_experiment/cohort/cross_sectional/case_control/observational/qualitative/simulation/review；声明为非实验设计时运行 G1（因果动词；同句有否定、rather than 或防御性措辞的不计）与 G2（MUST：正文出现 randomized/随机分配，与声明的设计矛盾）。另有 S1（把未达显著说成趋势或接近显著）、P1（建议他人采取行动；非实验设计升为 SHOULD）、N1（引言以外的新颖性宣称）、N2（片段模式：利益冲突、资助、伦理、数据可得性、未一稿多投、全体作者同意等须由作者确认的声明）。response_lint 识别常见拼写变体（Anwser、Respone 等），`--resp-label` 可补充本信专用的回复标记；回复内部以冒号引出或用作者口吻的 1. 2. 分点不再被当成新意见。

## 领域包与多代理

`python scripts/domain_pack.py build --corpus 目录… --id 领域_语言 --label "…" [--field …] --lang zh|en [--manifest 清单.csv] [--genre-map 文件=体裁…] --out assets/domains/领域_语言 [--boot 60]`

清单列：file、id（DOI 优先）、title、journal、year、genre、license；没有清单时读 md 的 YAML 头。输出 profile.json、bench_baseline.json、phrase_baseline.json、texture_baseline.json、rule_rates.json、corpus_manifest.csv、build_report.md。支持 file 相对路径并拒绝歧义；清单仅补元数据，不充当入选白名单。同 DOI 或去除起始 YAML 后的同文本去重；非全文 completeness、候选索引和无可测正文排除；可用论文不足 3 篇、隐私扫描发现长文本字段返回 2。`check <包目录>`：缺文件、不足 8 篇、词表或模式目录指纹不符、出现长文本字段或七个规定文件以外的文件/子目录返回 1。构建输出目录含额外文件时返回 2 并保留原件。`list` 列出已有领域包。

四个消费者均检查稿件是否为包中原文或新包登记的去 YAML 副本；自对标返回 2。section_lint 拒绝跨语言领域包。各工具读取领域包：bench_profile `--baseline 包 [--genre 体裁]`（稿件文本指纹在包中时拒绝，防止拿自己当参照）；phrase_contrast `--baseline 包 [--genre]`（词表或切词版本不符返回 2；报告给出留一法标记数参照）；language_plan scan `--baseline 包 [--genre]`（模式目录或词表指纹不符返回 2）；section_lint `--domain 包`（用包内分布校准阈值；同领域触发率 ≥50% 的规则降为 INFO 并注明，A1、W1、H1、G1、G2、S1、P1、N1、N2 不按发表频率降级）。

`python scripts/review_merge.py validate --manuscript ms.md 发现文件…`；`merge --manuscript ms.md --out 裁决表.csv [--previous 上轮裁决表] [--report 汇总.md] 发现文件…`；`check --adjudication 裁决表.csv --after 修改稿 [--report …]`。发现文件格式见 agents/README.md：schema_version=1、role、manuscript_sha256、findings[{id, severity=major|minor|note, category, section, quote, problem, why, suggestion, confidence}]。稿件指纹不符整份退回；major 发现的 quote 不在稿件中即退回（validate/merge 返回 1）。裁决表列：cluster、severity、section、category、reviewers、n_reviewers、status、quote、problems、suggestions、anchor、decision、reason；check 在未裁决、不采纳或暂缓无理由、采纳的锚点原文仍在时返回 1。

## 运行回执与最终交付

audit_run 和 release_check 的 schema/退出码见 13。进度表 gate_check 保留兼容，不能给最终质量证书。对启发式候选可以有理由保留，不允许伪造空报告消除状态。

脚本回归：`python evals/run_evals.py`。行为评估是单独的隔离任务；测试脚本通过不可冒充已执行行为评估。根目录 evals/README.md 给出实际做法与目前覆盖范围。

## journal_check.py · 期刊规则档案

档案在 `assets/journal_profiles/`，`schema_version=1`，必须有 `id`、`journal`、`sources`、`rules`。每条 `sources` 写 `id`、`url`、`access`（访问到的是什么：官方网页正文、存档副本、二手来源或未访问）和 `accessed`（日期）。每条 `rules` 写 `id`、`check`、`level`、`status`（verified 或 unverified）、`source`（指向 sources 的 id）和 `note`。缺任何一项，脚本退出 2。

`status=unverified` 的规则，即使写了 `level: FAIL` 也只报 CAND，并注明“来源未核实”。期刊规则会改版，凭记忆或第三方转述写死数字，比不检查更糟。

已实现的 `check`：`title_chars`、`abstract_words`、`abstract_numbers`、`abstract_citations`、`main_words`、`heading_chars`、`legend_words`、`note_words`、`legend_no_methods`、`legend_defines_stats`、`legend_conclusion`、`highlights`（`max_n`、`max_chars`）、`one_sentence_summary`、`in_brief_words`、`results_display_led`。未实现的 check 报 INFO 并跳过，不静默忽略。描述读图编码的句子（thicker lines indicate…、粗体表示…）不算下结论。

`--baseline` 读 `assets/benchmarks/display_baseline.json`，按档案的 `display_family` 给出本条说明在实测分布中的位置。`--fragment` 用于单独交付的 Highlights、投稿信、图注表注，跳过整稿项目。`--list` 列出档案，`--show` 打印某个档案的全部规则与来源。

目标刊不在档案里时，按当期作者须知新建一份，写明 URL 与访问日。**档案里没有的项目不检查，也不虚构“期刊要求”**；脚本通过不代表全部符合期刊要求。

## table_style.py · 三线表生成与版式检查

`build` 从 CSV 生成 docx：三线表边框、表头跨页重复、数据行不跨页、数值列右对齐并统一小数位、表题在上、表注在下。CSV 行列数不一致时退出 2，并提示给含逗号的字段加引号。输出文件已存在时拒绝覆盖。

`check` 读 docx 或 md：竖线与内部横线、表头下横线缺失、表头重复与行跨页、同列小数位不一致、`p = 0.000`、区间写法混用、表注顺序、超长注释。只有表注、没有表格的片段也能检查；既无表格也无表注时退出 2，不把零检查当通过。

它检查结构，**不是版式验收**。列宽、断词、跨页表头、上下标、负号仍须渲染后逐页看，报告里固定写明这一点。

## section_lint.py 的 S2 · 把比较写成“相同”

同句出现 identical、equivalent、the same、完全一致、毫无差异等措辞，且有统计量或组间比较的字样时列出。同句报告了不显著的检验（p ≥ .05、did not differ、不显著）为 SHOULD，否则为 INFO。等效性检验、贝叶斯因子、描述材料与程序的句子（materials were identical to Experiment 1）以及紧挨着的否定（not identical）不算。S2 不按领域发表频率降级。

## check_all.py · 一条命令的检查与状态页

`python scripts/check_all.py 稿件 [--out 目录] [--results 结果文件…] [--allow allow.txt] [--design 设计] [--domain 领域包] [--profile 期刊档案] [--ledger 台账] [--supplement 补充] [--simulation]`

依次运行 section_lint、density_check、ref_check；给了 `--results` 运行 number_trace（只查摘要、结果、讨论、局限、结论与表图题注），给了 `--ledger` 运行 ledger_check，给了 `--profile` 运行 journal_check；`--simulation` 检查开头的模拟标识，以及模拟稿里不该出现的伦理批准与知情同意。

输出目录默认在稿件旁新建“检查_时间”，已有文件的目录拒绝复用（退出 2）。STATUS.md 分四块：必须先处理、没能运行（不算通过）、需要看一眼、机器查不了需要人看的。台账列名与模板不同时只报一次“没能运行”，不逐行刷屏。

`--allow` 文件每行“数字 # 理由”，登记不来自结果文件的数字（任务参数、种子、版本号）。登记过的数字不阻断，但会连同理由列进 STATUS.md 请作者复核；没写理由的行不生效。number_trace 本身不接受全局豁免，这一层登记只在 check_all 里做，且留下记录。

退出码：0 没有必须处理的问题且请求的检查都跑了；1 有必须处理的问题或有检查没能运行；2 输入错误。

## section_lint 的 X11、X12 · 写作过程进了稿件

X11（MUST）：稿件任何位置出现工具名、对标或门控说明、“作者待办”、审计列表等写作过程的痕迹，例如把“句式分布对标未完成”写进局限，或把作者待办接在参考文献后面。文件头的 YAML 元数据与代码块不查。X11 不按领域发表频率降级。

X12（SHOULD）：摘要、结果、讨论、局限或结论里出现本地文件路径或脚本名。数据与代码的位置写进可得性声明，用公开仓库地址或 DOI。

## number_trace 的阈值写法

`p < .001`、`P ≤ 0.01` 这类写法，只要结果文件里有一个更小的非负值就算匹配。它不核对是哪一个 p，承重的 p 值仍要按行核对。

## init_project 只建本模式用得到的模板

D：盘点、来源覆盖、类型、故事卡、结果台账、大纲、决策登记、引文台账；R：盘点、故事卡、台账、决策登记、主张登记、引文台账；S：投稿清单、投稿信、限额、引文台账、决策登记；V：盘点、意见矩阵、回复信、主张登记、决策登记；A：盘点、问题登记、评分量表、引文台账。作者说明在项目根目录“作者说明.md”。`--full` 拷入全部模板。

## lit_evidence.py · 文献证据阶梯

`resolve --ledger 台账 --out 新台账 [--online] [--sources crossref,openalex] [--fixtures 目录] [--save-raw 目录] [--mailto 邮箱]`：逐个 DOI 查 Crossref（`/works/{doi}`）与 OpenAlex（`/works/doi:{doi}`，环境变量 OPENALEX_API_KEY 可选）。填 doi_status、identity（ref_title、ref_first_author、ref_year 与注册库比对；年份差 1 年以内视为一致）、version_status 与 version_source（Crossref `updated-by` 的 correction、erratum、retraction、withdrawal、expression of concern；OpenAlex `is_retracted`）、tool、checked_on。请求了核对却失败记 not_verified；所查注册库都返回 404 记 not_in_index；只有 OpenAlex 的 is_retracted=false 时 version_status 记 inconclusive。`--fixtures` 读以前保存的注册库记录（文件名 `crossref_<DOI>.json`，“/”换成“_”），用于无网复查与测试；`--save-raw` 保存本次取到的原始记录。输出文件已存在时拒绝写入。

`check [--ledger 台账] [--text 文件…] [--execution …] [--benchmark-mode …] [--benchmark-report 报告] [--benchmark-corpus 目录或清单] [--min-distribution 8]`：核对台账枚举、主张类型与访问程度（数字、方法、机制、比较、发现要 fulltext；存在性与背景至少 abstract）、resolved 是否写了工具与日期、REASONING-ONLY 下的 resolved 记录（沿用旧记录须在 tool 写“沿用”或来自 `--fixtures`）、更正与撤稿是否写了影响；扫描文本里的 F01–F16 说法，否定句不计。退出码 0 无 FAIL；1 有 FAIL 或字段错误；2 输入错误。

它只核对说法与记录是否对得上：DOI 能解析不等于支持本句；未见撤稿不等于可靠；relation 与 citation_access 要读过原文的人来填。

## metric_audit.py · 指标复算

`--csv 行级数据 --spec 口径.json --out 结果.json`。口径文件 schema_version=1，`group_by` 指定分组列；`metrics` 每项 kind 为 rate（numerator、denominator、aggregation=pooled 或 mean_row_ratios）、event_fraction（column、positive_values）、capped_mean（column、event_column、event_values、cap）或 mean。`reported_by_group` 可选，给出稿件报告的值；默认容差是报告值末位小数的半个单位（0.070 → 0.005），`tolerance` 可显式指定。退出 1 = 报告值与复算不符；2 = 输入或口径错误；输出文件已存在时拒绝写入。列选对不等于科学定义正确。

## reference_identity.py · 单条 DOI 的书目比对

`DOI --title 题名 --author 第一作者姓 --year 年份 [--report 报告]`：向 Crossref 取记录，比对题名、第一作者与年份。退出 0 一致；1 不一致或无法核实；2 输入错误。不核主张支持。批量核对用 lit_evidence resolve。

## check_all.py 的其他选项

`--design` 认常见写法（cluster-rct、randomised、longitudinal、survey、横断面等），认不出就退出 2 并列出可用名称。`--allow` 里的 95 与 95%、1,240 与 1240 视为同一登记。`--qualifiers`（values、requires 两列）：提到这些数字的句子，本句或上一句没有限定词就列为必须处理。给了 `--results` 时，稿件里的伦理批准号与注册号（NCT、ISRCTN、ChiCTR、ACTRN、DRKS、CRD、osf.io）要能在结果与材料文件里找到；说已注册却没有注册号，材料写明未注册时列为必须处理，否则列为看一眼。正文有作者–年份或编号引文却没有参考文献表时列为必须处理。`--citations`、`--note`、`--execution`、`--benchmark-mode`、`--benchmark-report`、`--benchmark-corpus` 交给 lit_evidence check。`--simulation` 只核对题目下那一句标识；稿件里的伦理与同意说法列为看一眼（只保留材料写明的）。

## number_trace.py 的变化

来源里原样出现的百分数（62.0%、9.8%）算有出处；“95% CI”里的 95% 是区间水平，不计入核对；派生或换算出来的百分数仍要登记理由。`--json` 另存未匹配清单。

## section_lint.py 的变化

X13（MUST）：摘要或结论里的待办清单或稿件状态话（伦理、资助、文献待补；“本稿未提供”“待作者核实”“写作流程测试”）。X14（SHOULD）：摘要或结论里的行内待核事实占位（如 [VERIFY: city]）。X11 增加稿件状态话的写法；题目下一句纯粹的合成数据标识不计。I1 认“The primary question … was whether”“we asked whether”等目的句；S1 认“showed a trend towards improvement”。紧跟表或题注的“注 / Note.”按表注处理，不计入所在节的正文。

X15（SHOULD）：方法、结果、讨论、局限里的内部处理过程（重跑、合并出错、Excel 清洗）。P2（SHOULD）：用因果动词描述使用量或剂量梯度（组内按使用量分组的比较是观察性的，随机试验也一样）。S2 的程序句豁免不适用于带置信区间或 p 值的句子（“多重插补证实两组等同（1.5，95% CI …）”会被报出）。

check_all 的输出目录：`--out` 指向的目录已有报告时，写到 `目录_2`、`目录_3`……，并在 STATUS.md 写明上一轮报告的位置；旧报告不覆盖。STATUS.md 每条末尾的括号写明工具与规则代码（如 `section_lint R1`、`number_trace NT1`、`check_all SIM3`、`qualifiers Q1`），同目录的 `summary.json` 列出同样的条目（tool、code、text）、退出码与所用选项。check_all 自己的代码：NT0 没给结果文件，NT1 数字找不到出处，NT2 已登记理由的数字；RC1 正文有引文却没有参考文献表，RC2 还没有参考文献表，RC3 引文与文献表对不上；SIM1 缺模拟标识，SIM2 伦理说法待核对，SIM3 伦理说法在给出的材料里找不到；ID1 编号在材料里找不到，ID2 编号无从核对；REG1 说已注册却没有注册号；Q1 缺口径限定；EX1 没写执行条件；LC1 结果台账错误。口径限定的匹配跳过版本号与软件包名里的数字（R 4.4.1、lme4 1.1-35），− 与 - 视为相同。

`check_stats.py 目录… [--notes 作者说明…] [--report 汇总.md] [--json 汇总.json]`：递归读取 summary.json，汇总运行次数、可交次数、没能运行的检查，以及每条规则的命中次数、出现在几次运行里、被作者说明列为误报的次数（读写有“误报”的行与小节里的规则代码）。用于监控，不判断规则对错。退出 2：没找到 summary.json。

section_lint：R1 在解释句比例超过阈值且不少于 3 句时才是 MUST；中文“提示”只在作动词时（“结果提示”“这提示”）计入。P2 跳过明确否认因果的句子（“不能推出”“cannot be interpreted as”）。V1（SHOULD）：图注写了线型、颜色或标记，提醒核对实际的图。V2（SHOULD）：表注或图注下了结论（demonstrate、表明、优于），或写了软件与估计细节（REML、lme4、R 4.4.1）。X11 也包括“材料里没有记录”这类材料缺口的说法。

response_lint 的 `--comments` 可以给条数，也可以给审稿意见文件，按行首编号（E1、R1.1）计数。

## results_function.py

`python scripts/results_function.py 稿件 [--heading-style object|finding|either] [--strict] [--must-share 0.10] [--lang auto|en|zh] [--report …] [--json …]`。逐句分类结果节：DIRECT、TRANSLATE、QUALIFIER 可留；NARRATION、INFERENCE、DESIGN、MECHANISM、CONSTRUCT、IMPLICATION、LITERATURE 待核位置。否定句不豁免；INFERENCE 的对象若只是统计状态（等效、精度、两估计之差、显著性、区间）则记 QUALIFIER。RF1：待核句 ≥3 且占结果句比例 ≥ --must-share（或 `--strict` 下 ≥1）为 MUST，否则 SHOULD；RF0（INFO）列出保留的统计限定；HS1（MUST）声明分析对象式却有发现句标题；HS1b、HS2（SHOULD）风格不一致；HS0 未声明风格时的分布（全部且 ≥3 个是发现句时 SHOULD，否则 INFO）；RF9 没有结果节。节标题本身（Results、3. Results、结果、Results and Discussion）不算小标题；给成分命名的句子（this component was termed N170）不算叙述决策或文献比较；合并 Results and Discussion 只报 INFO。JSON：items、headings（text、style）、sentences（sub、text、cls、also、dest）。退出码 0/1/2；报告与 JSON 必须是新路径。

## display_terms.py

`scan 稿件… [--tables …] [--legends …] [--figures …] [--figure-text …] [--terms …] [--report …] [--json …]`：表头、单元格、表注图注、图内文字是读者看到的位置。DT1 未登记的代码式标识（下划线或加号连接）、DT2 已登记未替换、DT3 显示名为空或 status 不是 verified/author_confirmed、DT8 p 值写成 0，均为 MUST；DT2b 正文里的内部 ID、DT4 原始分类值写法、DT5 正文代码式标识、DT6 非标准记号、DT9 分析过程史、DT10 ≥4 位小数、DT11 负号不一致、DT12 p 值前导零不一致为 SHOULD；DT7 公式下标为 INFO。代码式 ID 各处都查，普通单词式 ID 只在表头与单元格整格匹配；单元格已含显示名的不再报。网址、DOI、LaTeX 公式与参考文献表不扫。图片：SVG 读文本元素、PDF 用 pdftotext、位图用 OCR，做不到记入 notrun。JSON：items、notrun、unknown_ids、files。退出码 0/1/2。`apply 表.csv --terms … --out …`：按登记表替换表头与非数值列（或 `--columns`），可选 `--p-columns`、`--p-style apa|leading`、`--decimals 列=位数`、`--minus unicode`；有未登记或未核实的标签时退出 1、不写输出（`--draft` 允许未核实的显示名）。`template [--scan …] [--from-tables …] [--terms 已有] --out …`：把 scan 的 unknown_ids 与分析表里像内部标签的分类值、列名写成待填登记表（status=pending），已登记的跳过。

## coverage_check.py

`python scripts/coverage_check.py 稿件 --map coverage_map.csv [--neighbors …] [--note …] [--stage draft|submission] [--roles 键=说明,…] [--report …] [--json …]`，或 `--scan-only`。CV1 缺角色、status 不认识、na 无理由；CV2 gap 或 searched_none 无检索记录；CV4 covered 无来源或来源不在参考文献表；CV7 作者说明声称就绪而缺口未关闭，均为 MUST。CV3 已检索仍缺口（submission 为 MUST）、deferred；CV5 方法与结果里命名方法、刺激或软件所在句无引文；CV6 参考文献数不到实际读到的近邻最少者的一半（只作信号）；CV0 没有覆盖表，均为 SHOULD。参考文献表按 References / 参考文献 标题之后的条目识别。JSON：items、open_gaps、references、candidates、roles。退出码 0/1/2。

## review_pack.py

`python scripts/review_pack.py --manuscript 稿件 [--supplement …] [--tables …] [--legends …] [--figures …] [--expectations …] --out review_package.md [--manifest …]`：把正文、表（CSV 转成 Markdown 表）、图注、补充材料与图片清单（只列指纹）写进一个文件，开头是来源与 SHA-256。审稿人把它当稿件，manuscript_sha256 填它的指纹。退出码 0/2。

## review_merge.py、check_all.py、release_check.py、bench_profile.py、init_project.py 的补充

- review_merge validate：findings 为空时必须有 coverage（sections、checked，以及至少 2 条能在稿件中找到的 ok_examples），否则整份退回。check：采纳理由去空白后完全相同的 ≥3 组报错；裁决表有 change_evidence 列时，采纳的 major 必须填写，没有这一列时提示。
- check_all：新增 `--displays`、`--terms`、`--coverage`、`--neighbors`、`--benchmark-decisions`、`--expectations`、`--heading-style`、`--stage`；每次运行 results_function 与 display_terms scan；有参考文献表却没有覆盖表时提示（`--stage submission` 时阻断，coverage CV0）。对标决策表：BD0 空表或投稿阶段没有表、BD1 行缺 neighbor、locator 或 decision（MUST）、BD2 manuscript_sha256 不是当前稿件（submission 为 MUST，否则提示）、BD3 有结果小标题却没有 results_headings 一维（提示）。expectations 的 check：results_heading_style（HS1 或 HS2 即未满足）、results_function（RF1）、display_terms（任一 MUST 或没能运行）、coverage（没运行或有未关闭缺口）、manual（列入人工确认）；未满足记 expectations EX1（MUST）。STATUS.md 增“分维度状态”，summary.json 增 dimensions 与 expectations。
- release_check：submission 另要 lit_coverage、display_semantics、expectations；response 另要 display_semantics、expectations；后两项可在确实不适用时 na（写理由、fallback 与审查证据）。
- bench_profile：报告第六节对照结果小标题风格（只认带标题标记的全文：Markdown、带标题样式的 Word；PDF 转写的标题没有标记，抽不到时在 benchmark_decisions.csv 人工记录近邻的小标题与位置）；JSON 每篇增 results_heads 与 results_head_styles（领域包允许 results_heads 的长文本）。
- init_project：D 模式另建 expectations.json、coverage_map.csv、benchmark_decisions.csv；R 建 expectations.json；S 另建 expectations.json、coverage_map.csv、display_terms.csv、benchmark_decisions.csv、neighbors.csv；V 另建 expectations.json、display_terms.csv。

## genre_gate.py · 体裁与节职能

`python scripts/genre_gate.py 稿件 [--stage draft|submission] [--decisions benchmark_decisions.csv] [--placement placement_decisions.csv] [--memo genre_memo.md] [--drill reject_drill.md] [--neighbor-texts 近邻全文…] [--report …] [--json …]`

文本规则：GG1 摘要末句是局限或否定（MUST）；GG2 摘要否定、不确定句 ≥3 且 ≥30%；GG3 摘要程序细节 ≥3 处；GG4 引言首段前两句没有读者能感到的对象或利害；GG4b 首段 ≥2 句“某研究发现”罗列（SHOULD）；GG5 引言末段 ≥2 句分析清单（MUST）；GG5b 末段既无预测也无结果预告（SHOULD）；GG6 方法记账、防御说明与敏感性罗列 ≥8 句且 ≥25%；GG7 主文有分析样本或试次总表（MUST）；GG8 讨论首段 ≥2 处程序细节，或否定、不确定句 ≥2 且 ≥40%；GG8b 首段没有解释句；GG9 讨论小标题多数是限定式（SHOULD）；GG10 结论末句是局限或否定；GG12 泛化名词组合在关键段出现 ≥3 次、近邻全文里没有（SHOULD，需 --neighbor-texts）；GG13 正文引用 ≥12 个补充条目（SHOULD）。未标级别的在草稿阶段为 SHOULD，投稿阶段为 MUST。

产物规则：BD4 对标决策缺职能维度（abstract_ending、intro_opening、intro_closing、methods_grain、main_displays、discussion_opening），BD5 职能维度少于两篇近邻；PL0 没有去向登记，PL1 缺列或去向不是 main/supp/omit，PL2 进主文或补充却没写读者问题，PL3 没有近邻位置也没有规则依据，PL4 必须披露的被 omit，PL5 没绑定当前稿件，PL6 补充条目未登记，PL7 主文表未登记；MM0 没有体裁备忘，MM2 必填节空着，MM3 近邻对照不到两篇，MM4 没绑定指纹，MM5 白话复述还有 ✗；RD0 没有拒收预演，RD1 默认探针 RJ1–RJ10 没逐条判定，RD2 本稿特有理由不到两条，RD3 行缺位置、状态或证据，RD4 仍在的条目（SHOULD），RD5 没绑定指纹。投稿阶段 BD4、PL0、MM0、RD0、PL5、MM4、RD5 为 MUST。

豁免：benchmark_decisions.csv 中 dimension 写规则代码（如 GG7）、decision 含“保留/keep”、有 neighbor 与 locator 且绑定当前稿件的行，使该规则降为 INFO 并记入 waived。缺某一节（没有摘要、引言或方法）时对应规则记入 notrun，不算通过。JSON：schema_version、manuscript_sha256、stage、must、should、items（level、code、sec、msg、examples）、metrics、waived、notrun、supplementary_items。退出码 0 无 MUST；1 有 MUST；2 输入错误；报告与 JSON 必须是新路径。

## station_check.py · 流水线站点

`python scripts/station_check.py --project 项目目录 --manuscript 稿件 [--stations stations.csv] [--report …] [--json …]`。stations.csv 列：mode、station、name、status（todo/doing/done/blocked）、outputs（分号分隔的相对路径，空着用默认）、qc_evidence、inspector、manuscript_sha256、note。规则 ST1–ST6 与各站放行条件见 28；blocked 的站不挡后站（ST2 不计），但必须写“缺材料：…”（否则 ST6），且流水线不算完成。退出码 0 流水线完整；1 未完成、证据不足或等待材料；2 输入错误。

## check_all.py 与 init_project.py 的补充（第二轮）

- check_all 每次运行 genre_gate，新增 `--placement`、`--memo`、`--drill`、`--neighbor-texts`（`--benchmark-decisions` 同时交给 genre_gate）；STATUS 与 summary.json 的分维度状态增“体裁与节职能”，summary.json 增 genre（must、should、waived、metrics）。genre_gate 内部的 notrun（如稿件没有摘要节）列入“需要看一眼”（genre_gate GG0），不改变退出码；genre_gate 本身运行失败才列入“没能运行”。
- init_project 另建 stations.csv（按模式列出站点、默认产物路径，状态 todo），各模式补齐站点要用的模板（placement_decisions.csv、genre_memo.md、reject_drill.md、neighbors.csv 等）。
- mslib：只有“Keywords”或“Keywords: …”这样的标题才算关键词行，“Keyword co-occurrence network”这类结果小标题不再被切进前置部分；`--design` 认 bibliometric、scientometric、文献计量（映射为 observational）。
- section_lint X11：“were not available for this check/analysis/…”这类研究本身的说明不再算写作状态话；“not available for this draft”照常报出。


## 第三轮：选材与同类调研（survey_check、genre_gate、station_check、check_all、init_project）

**survey_check.py**：`python scripts/survey_check.py survey_corpus.csv [--synthesis survey_synthesis.md] [--stage draft|submission] [--min-screen 20] [--min-full 6] [--min-matched 4] [--min-axes 3] [--norms-out norms.json] [--report …] [--json …]`。列：id、doi_or_url、title、year、journal、axes、type_match、access、coded、n_main_analyses、n_main_displays、n_supp_items、exploratory_handling、omitted_but_possible、why_only_these、locator。规则 SV0–SV7（SV1–SV3、SV7 在 draft 为 SHOULD）。norms 给出类型匹配的全文编码论文的主文分析数、主文图表数、补充项数的最小值、中位数与最大值。退出码 0/1/2；输出文件已存在时拒绝写入。

**genre_gate.py**：新增 `--concept paper_concept.md`、`--survey survey_corpus.csv`。去向登记新版列：item_id、item、kind、claim、function、evidence_quality、reader_question、placement、if_favorable、reviewer_if_shown、reviewer_if_absent、disclosure_basis、neighbor、locator、reason、manuscript_sha256。

- placement 取 main / supp / reserve / omit；if_favorable 取同样四个值；
- function 取 core / support / qualify / preempt / context / out_of_scope；
- evidence_quality 取 robust / fragile / failed / uninterpretable / descriptive；
- disclosure_basis 取 registered / claim / data / journal / ethics，可多个，用 | 分隔。

规则 PL8–PL15、PB1、PC0–PC1 见脚本说明与 29 §8。旧版登记（有 disclosure_required、缺选材字段）报 PL11，照旧检查 PL1–PL7。PL3 只查放进论文的行；备答与不属于本文的行要写理由。PB1 的降级：benchmark_decisions.csv 写 dimension=PB1、decision 含“保留”、给出近邻与位置并绑定当前稿件。

**station_check.py**：S2（同类调研）的产物是 survey_corpus.csv、survey_synthesis.md、neighbors.csv，放行要过 survey_check 的投稿阶段规则与近邻分层；S3（构想、选材与体裁蓝图）另要 paper_concept.md 各节已填、去向登记为新版。

**check_all.py**：新增 `--concept`、`--survey`，转交 genre_gate。**init_project.py**：D、R、S 模式另建 paper_concept.md、survey_corpus.csv、survey_synthesis.md。

**通用性（第三轮）**：
- genre_gate 给了 `--neighbor-texts` 时，会对每篇近邻跑同样的文本规则（GG1–GG10 及其变体、GG13）。近邻里至少两篇、且至少三分之一也触发的规则，降一级（MUST→SHOULD，SHOULD→INFO），并在条目前写明“近邻 k/n 篇同样触发”；结果记在 metrics.neighbor_calibration。`--no-calibrate` 关闭这一步（近邻运行时内部也用它，防止递归）。
- survey_check 新增 `--scope survey_scope.json`。字段为 min_screen、min_full、min_matched、min_axes、reason。改了默认值却没写理由，或低于最低限度（筛选 5、全文编码 2、类型匹配 2、维度 2），报 SV8 MUST。
- station_check 的 S2 会读取 02_bench/survey_scope.json（如有）。init_project 在 D、R、S 模式下复制 survey_scope.json 模板。

## convention_profile、derivation_check、claim_strength 及整合

**convention_profile.py**：`--neighbors 近邻全文… --draft 稿件 [--supplement 补充] [--titles survey_corpus.csv] [--term-groups "名=式|式;…"] [--min-share 0.25] [--report] [--json]`。维度：title_words、title_form（statement/question/noun_phrase；复数名词后接介词不算动词）、title_subtitle、title_method、title_terms:<组>、supp_labels（称呼族）、limitations_heading、limitations_paras、discussion_subheads、abstract_structured。数值维度落在近邻范围外、类别维度在近邻里占比 < min-share、称呼族在用过补充称呼的近邻里占比 < min-share，记为偏离。调研表有 type_match 列且类型匹配 ≥5 篇时，题目维度以类型匹配的论文为参照（同时报告全部）。有效值不足 3 的维度记 NA。退出码 0 无偏离、1 有偏离（要裁决，不等于错误）、2 输入错误。

**genre_gate CN1**：给了 `--neighbor-texts` 时内部调用 convention_profile（`--survey` 的题目一并作参照，`--term-groups` 透传）；每个偏离都要在 benchmark_decisions.csv 有 dimension=`convention:<维度>`、写了 decision 与 locator 且绑定当前稿件指纹的行，否则 draft 为 SHOULD、submission 为 MUST。补充条目识别（PL6、GG13）现在认 Supplementary Table/Figure/Section/Note、Table S1、Fig. S1、S1 Table、Appendix S1。

**derivation_check.py**：`derivations.csv [--report] [--json]`。列 id、label、formula（+ − * / **、sqrt、abs、变量名）、variables（`名=值[单位]`，分号分隔）、reported、reported_unit、tolerance（空则取报告值末位半个单位）、kind（identity / approx）、source、note。规则 DV0 无法解析、DV1 单位不一致、DV3 符号相反（MUST），DV2 数值不符（identity 为 MUST，approx 为 SHOULD）。单位写法 uV、ms、s、SD、logit、logit/SD、ms/SD、1；乘 `*`、除 `/`、幂 `^`。

**claim_strength.py**：`稿件 [--concept paper_concept.md] [--citations 引文台账] [--stage draft|submission] [--report] [--json]`。概括位置 = 题目、摘要、讨论首段与末段、结论；图注另列。IF1 显著性之差（only when、confined to、restricted to、no longer、but not in、效应 disappeared/was absent……）SHOULD；IF2 用不显著证明不存在 INFO；IF3 簇边界当时程 INFO；IF4 分离或不同机制 SHOULD；IF5 相关写成来源或因果 SHOULD；FW1 概念文件“禁用表述：”登记的说法出现在稿件 MUST；LG1 引言或讨论里概括一组前人研究的句子，引文台账没有 claim_location 写到该段、claim_type=comparison、fulltext、supports 的行：给了台账且 submission 为 MUST，其余 SHOULD。措辞信号不是判决。

**check_all**：新增 `--derivations`、`--term-groups`；每次运行 claim_strength（`--concept`、`--citations`、`--stage` 透传）；给了 `--derivations` 运行 derivation_check，没给而稿件有派生量线索时记 DV0（看一眼）。分维度状态增“主张强度与文献概括”“派生量复算”。CODE_RX 认 claim_strength 与 derivation_check。

**review_pack**：打印与清单里的 package_sha256 取写入后的文件字节（Windows 文本模式写入会换行转换，按内存字符串算的指纹与文件不符）。

**figure_layout_qa.py**：保持 `--json` 的逐图列表格式，另以 `--status-json` 指定执行状态；给了 `--json` 而未指定状态路径时，写旁侧 `<报告>.status.json`。状态含 status、checked_count、script_exit、qa_exit：只有 status=complete、checked_count>0 且 qa_exit=0 才能称本次自动检查通过。qa_exit=1 是发现重叠；2 是空检查、脚本非零退出或其他执行/输出错误。报告与状态须使用不同的新路径，不覆盖输入或旧文件。除线外也检查 scatter/区间带等可见集合对象，仍不能替代成图的人工视觉验收。

**genre_gate FG1**：按可识别的主图图注逐幅核对具体 figure: 行，兼容普通/Markdown 英文与中文图注。neighbor、locator、observed、decision、reason 和当前稿件指纹须完整；缺失只给 INFO。登记覆盖不代表已验证画法质量、引用内容或全部面板。

**evals/mutation_sim.py**：新 spec 每个变体给 oracle（error、benign、context）；error 的 expected_rules 必须指定工具与规则，如 `[{"tool":"claim_strength","rule":"IF5"}]` 或 `["claim_strength:IF5"]`，可指定 level。多个目标是可替代检测器（任一命中）；只命中无关规则不算检出。INFO 可作为显式目标；benign/context 不计错误召回，产生的信号分别报告为复核候选。没有 oracle 的旧 spec 标 legacy/unscored，caught 只兼容新增信号，不能报准确率。子工具异常、超时、返回2、缺失或无效报告单列 execution_error，整体退出2；有目标漏检退出1，其余0（旧 spec 保留其退出约定）。输出目录须不存在或为空，不递归删除已有结果。

**station_check ST7**：S7 没有审查裁决表、只有标明“非独立”的 self_review.md 时，自查要含七项结构（前提审计、推断链、概括位置漂移、派生量复算、文献概括核对、惯例偏离、冷读；中英文写法都认），缺项则本站不放行。模板 assets/templates/self_review.md。

## deviation_register、move_check 段落级与 JSON、genre_gate MV/TX/LX、station S5

**deviation_register.py**：`--draft 稿件 [--supplement] [--neighbors 全文…] [--texture-exemplars 全文…] [--survey survey_corpus.csv] [--term-groups …] [--moves 语步编码.json] [--baseline 领域包] [--terms 主题词|@文件] [--decisions benchmark_decisions.csv] [--stage] [--report] [--json] [--todo]`。收集 convention:（convention_profile）、move:（move_check.analyze）、texture:<节>:<指标>（bench_profile 子进程；n<10 用范围，10–19 用 p10–p90，≥20 用 p05–p95）、lexis:<词>（对数似然 ≥15.13，稿件 ≥3 次、频率 ≥3 倍、近邻文档频率 ≤1/3；题目词与 --terms 不计；需要 ≥2 篇全文）。adjudicate 类：convention、move、散文节（abstract、introduction、discussion_all、limitations、conclusion）的文风指标、方法与结果节的标点与连接词人称；其余 review。裁决行需 decision、locator 或 reason、绑定指纹；texture 可用 `texture:*:<指标>` 或 `texture:<节>:*`。退出码 0 无待裁决、1 有、2 输入错误；--todo 写出待填的裁决行。

**move_check.py**：新增 SIG 代码；单元可写 `"granularity": "paragraph"`：不给 text/hint 时整份 source 就是这一节，按空行切段，段数必须等于编码条数；段落级代码可用 + 连写多职能，线索用 || 分隔且条数不少于职能数；线索按顺序在上一条之后查找。新增 `--json`（sections → presence、first、last、drafts[missing_common、rare_present]）与可导入的 `analyze(data, base, min_common, max_rare)`。

**genre_gate.py**：新增 `--moves`、`--baseline`、`--terms`、`--texture-exemplars`。给了近邻全文、语步编码或领域包时调用 deviation_register：CN1（惯例）、MV1（语步）、TX1（文风质感）未裁决时 draft 为 SHOULD、submission 为 MUST；TX2、LX1 为 INFO；给了近邻全文却没有 `--moves` 为 MV0（SHOULD）。metrics 增 deviation_meta（moves 每单元近邻数、texture 是否测量）与 deviations 计数。

**check_all.py**：新增 `--moves`、`--texture-baseline`、`--study-terms`、`--texture-exemplars`，转给 genre_gate。

**station_check.py**：项目有 02_bench/neighbors.csv 时，S5 还要求 genre_gate.json 的 deviation_meta 显示做过语步对照（每单元 ≥3 篇近邻）与质感分布。自查第 6 项认“惯例偏离／偏离登记／convention／deviation”。

**bench_profile.py**：计数前去掉 `[VERIFY: …]`、`[ref]`、`[TODO]` 等占位符。

**section_lint.py**：I1 的补充式样认得 We then/first examined…、Here we / In this study, we …、To fill this gap, we …、accounts make different predictions（近邻的当前研究句；词表本身未改，领域包指纹不变）。

## 方法无关的站点条件、语言与学科中立（第六轮修订）

**station_check S5**：项目有 02_bench/neighbors.csv 时，关键段对照与质感对照各需一种证据：genre_gate.json 的 deviation_meta（moves 每单元 ≥3 篇近邻；texture 为真）；或 benchmark_decisions 中绑定当前指纹的 `keypara:`/`move:` 行（neighbor 列合计 ≥3 篇不同近邻，用分号、逗号或顿号分隔）与 `texture:`（含 `texture:checked`）行；或 `exempt:moves`、`exempt:texture` 行且 reason 不少于 15 个字符。

**claim_strength.py**：按稿件语言选式样；中文有 IF1–IF5 与 LG 的对应式样（仅在、局限于、效应消失；没有差异；分离、两条通路；导致、决定；从 N 毫秒开始；以往研究、尚无研究、首次）。报告首行写明语言。

**convention_profile.py**：title_method 的默认词表跨学科（神经影像、试验、队列、调查、访谈、元分析、面板与计量、模拟、机器学习、测序等，含中文）；`--term-groups` 里给了 `method=…` 时不再计算默认的 title_method，以作者的词表为准。中文题目按汉字数计长度。

**deviation_register.py**：中文稿不算词汇 keyness（字或二元组噪声大），在“没能测的”里写明并指向 phrase_contrast。

**evals/score_behavior.py neighbourfit**：对 behavior_cases/neighbourfit_request.md（合成材料、与真实案例不同的领域）产出的 manuscript.md 与 author_note.md 打分：引言末段有目的与设计、引言交代两个候选测量、概括位置不写“仅在计数器可见时”、不出现量纲错误的 −1.6 s、不把虚构近邻当文献（未通过项）；间接效应用 R8、补充称呼、局限版式、摘要分号、讨论人称、作者说明交代近邻比较（提示项）。必须在新会话里生成被评文件。

## 检查级别的依据与删减（第七轮）

级别不由“这条规则重要”决定，而由两类证据决定：变异模拟里它抓到了什么（召回），已发表论文和干净稿上它报了什么（误报）。

**evals/mutation_sim.py**：`spec.json --out 目录 [--baseline 领域包]`。往干净稿里一次注入一个缺陷，跑 section_lint、density_check、genre_gate（投稿阶段，含近邻、语步编码、禁用表述、主题词、可选领域包）、claim_strength、check_all（引文守卫）、number_trace 与 derivation_check，报告每个变体相对干净稿新增的 MUST/SHOULD 项，以及干净稿本身的 MUST/SHOULD。退出码 0 全部抓到、1 有漏掉、2 输入错误。它检验检查层，不检验执行者。

本轮按证据做的调整：
- deviation_register：必须裁决的质感指标只留读者会感到的十二项（句长、分号、冒号、破折号、rather than、连接词、第一人称、否定句占比、防御句式、模板、风格词、自造标签），只在散文节；参照少于 10 篇时一律只供看。依据：同分布的新稿件落在 n 篇范围外的概率是 2/(n+1)；3 篇合成近邻时干净稿被报 21 项，收窄后为 1 项，12 个变体仍全部抓到（参照 ≥10 篇时）。
- section_lint：R1（结果节解释）、M1（无统计分析总节）、M5（分析写明目的的比例）、X1（跨节重复）、X5（小数位混用）默认降为 INFO。依据：五个领域包 86 篇已发表论文的平均触发率分别为 89%、43%、38%、81%、36%（rule_rates.json）。R1 在解释句很多时仍为 MUST；结果节的句子功能由 results_function 判断。
- density_check E6：引言首段不再算“无锚点段落”，它与 GG4（首段要有读者能感到的现象与利害）互相冲突。
- check_all 的引文守卫认得括号里用分号列多篇、带 see/e.g./cf. 的写法；投稿阶段有派生量说法却没登记 derivations 时为 MUST。
- claim_strength：IF5 不再只认脑电词主语，改认“被测量的量”作主语（比较级主语或信号类主语），并扫描结果节；含 may have、could have、whether 的推测句不报。IF4 的 distinct 只在“A 与 B 是 distinct 的”或“distinct 的信号、阶段、机制”时报。IF1 只在句子讲效应或差异时报。实测：两篇已发表论文的误报从 7 处降到 4 处（剩下的是确有直接检验的“分离”说法），v1 稿原有的 6 处（三处“仅在”、一处“分离”、两处“相关写成来源”）全部保留。

没有删除任何检查：要判断一条检查从没抓到过真问题，需要多篇稿件的运行统计（check_stats.py）与更多变异用例；本轮能确定的只是上面这些级别与范围的调整。

## 近邻分层、语步写法、引言预告与叙事承接（第八轮）

**move_check.py**：单元可写 `type_match`（true/false）与 `family`；出现比例只用 type_match 不为 false 的近邻算，未标注的照算并提示。输出增 `families`（各层篇数与比例）、`conditional`（两层做法相反的语步）、`realizations`（类型匹配近邻里每个语步的起句键与句首）；稿件条目增 `conditional_present`、`conditional_absent` 与 `realizations`（起句键、有没有近邻用过、近邻的起句键）。不给 text/hint 时 source 文件本身就是单元。

**deviation_register.py**：类型匹配近邻少于 3 篇的语步单元只写进“没能测的”；rare_present 的语步若各层做法不同，提示按目标刊决定；conditional_absent 为供看；`phrasing:<单元>:<语步>:<起句键>`——稿件起句近邻没人用时列出，该语步在近邻里有 ≥4 处实现且首词也没人用时为必须裁决。

**genre_gate.py**：GG5b 只看引言末段有没有预测（结果预告不再算替代）。IP1：引言最后两段写出了本研究的结果（we found/show…、our results showed…、我们发现），引用前人的句子不算；有 `role:intro_preview` 或 `move:intro*:FND` 裁决时为 INFO，否则草稿 SHOULD、投稿 MUST。NR1：摘要、引言或结果里的叙事式承接（we first/then/next asked…）为 SHOULD。IP1、NR1 参加近邻校准：近邻同样触发时自动降一级。genre_gate 的偏离类别增 PH1（写法，必须裁决）、PH2、MV2（供看）。

## key_units.py（第九轮）

`--neighbors 02_bench/neighbors.csv [--pair "标签=全文.md" …] [--draft 稿件] [--units intro_closing,disc_first,abs_last,conclusion,intro_paras] --out 目录`。只从 neighbors.csv 登记的近邻取材：type_match 列以 yes/y/是 开头记为类型匹配；tier 列 flagship → general、field → discipline，其余照写为 family。全文路径取 file 列或 --pair。按单元抽出引言末段、讨论首段与末段、摘要最后两句、结论节（没有结论节时取讨论里以 In conclusion/In summary 起的段）、引言全文（段落级），原文摘录写进 目录/src/，coding_template.json 的代码一栏是 “?”，move_check 会把没填的当作错误。类型匹配的近邻少于 3 篇时退出码 1（模板照写，比例不作数）。

### figure_layout_qa 与 claim_strength 的两处复核调整（第十三轮补强版之后）

- figure_layout_qa：本工具上次写的图件报告与状态文件可以覆盖。状态文件带 `"tool": "figure_layout_qa"`；图件报告是含 file、overlaps、whitespace 的列表。复跑是常态，第二次运行不再因状态文件已存在而判为无效。其他已有文件与输入脚本仍一律不覆盖（退出码 2）。
- claim_strength 的 IF2 等效提示：同一处出现模型、成分、变量、定义、方程等概念名词、且没有效应、结果、组别、条件等结果词时，视为概念上的等价（例如“this model would be equivalent to the DDM”），不提示。统计等效结论（“the two approaches were equivalent”“equivalent outcomes”）照旧提示。

### genre_gate IC1（第十四轮）

引言最后一段出现 ≥2 处数字加单位（ms、s、Hz、µV、°、cm、mm、% 或“N trials/participants/blocks/electrodes”），或出现逐项列分析的句子（以 Finally、Lastly、Next、Then、In addition、Moreover、We then/next/also/finally 开头，并接 we tested/examined/analysed/computed/fitted/compared/asked）时，给 INFO。参加近邻校准。


## 读者的理解前提（本次修订）

**reader_readiness.py**：`稿件 --json scan.json --report scan.md [--terms terms.txt]`；可导入 `inspect_text(text)`。输出 `items`、按范围的名称库存与覆盖边界。RR 前缀均为非阻断候选：形式定义和首用的位置线索，不证明概念、测量效度或预测依据。数字名称/符号不要求展开全称。词项可由项目输入补充，不含固定学科词表。摘要与正文独立；正文跨节不重置；可识别的图注/表格独立处理，绑定不明的部分明示限制。

**section_lint.py**：旧 X3/X3b 由 reader_readiness 的同一实现替代，不再把摘要定义当正文定义、把任意括号或后文孤立全称当作已定义。

**check_all.py**：自动保存 reader_readiness.json/md，并单列“术语与理解前提”；形式扫描完成仍明确概念与论证待人工核查。词项列表用 `--reader-terms`，与内部显示名表 `--terms` 区分。

**genre_gate.py / mslib.py**：引言取第一个明确章节，遇同级或更高标题即止，避免未知的非 IMRaD 章节被当作引言末段。GG4 是词表未命中的 SHOULD 候选，不能以领域词表替代开篇判断；GG5b 提示先核研究类型，不要求探索性或新方法补假设；IP1 没有明确的目标刊/用户约束时最多 SHOULD，已有有效裁决为 INFO，不因投稿阶段或目标刊未定而自动要求删除预告。明确约束仍由期刊/用户要求检查执行。此前第八轮的升级说明作为历史记录，当前行为以本段为准。


### 第十五轮 b：引言边界与汇总

- **mslib.first_section_paras / reader_readiness**：没有方法或结果节（法学、理论、工程方法）时，引言在第一个同级标题处截止；有方法或结果节时，解析器仍归入引言的同级标题（理论小节、The present study）属于引言，只有不存在目的类小节时，相关研究或文献综述类的同级标题才截止引言。第十五轮的写法会把 `## Introduction / ## 理论小节 / ## The present study / ## Methods` 截成第一段，误报 I1 MUST，并漏掉末段的分析菜单（GG5）。RR4 用同一边界。
- **check_all**：reader_readiness 在“需要看一眼”里最多占两行：引言末段才首次具名的术语（RR4）单列；RR1/RR2 按阅读范围合并。明细仍在 reader_readiness.md。section_lint 的计数不含 RR 候选。
- **reader_readiness**：示例截取术语前后约 80 字，不再逐条附整段。

## 改稿增量与融入（第十六轮）

**deviation_register.py / genre_gate.py / check_all.py**：`--submitted 上次投稿的原稿`。按累计增量列 `revision:<节或小节>:growth`（节：增 ≥50 词且 ≥20%；小节：增 ≥100 词且 ≥50%）、`revision:trace`（新增句里读得出审稿或改稿过程、局限回指别处）、`revision:repeat:<百分数>`（改稿后出现在 ≥4 节，供看）。变长节的文风质感与数字密度偏离升为必须裁决，不受近邻 ≥10 篇的限制；一行 `revision:<节>:growth` 可同时裁决该节质感。裁决行要有 neighbor 与不少于 15 字符的 reason。genre_gate：RV1（未裁决，draft 为 SHOULD、submission 为 MUST）、RV2（≥3 行同一理由，MUST）、RV3（供看）；给了 `--submitted` 时 reject_drill 须判定 RJ11。

**station_check.py**：V 模式含 S2，近邻要有 tier=target 或 `exempt:target`；V、R 模式 S5 要有 `--submitted` 的结果或 `exempt:submitted`，S8 要有 RJ11。

**section_lint.py**：X15 增加改稿过程（mslib.REVISION_TRACE）；L3（SHOULD）局限回指本文其他部分或补充材料。在 10 篇真实近邻全文上两类都是 0 次命中。

**response_lint.py**：WARN 增加 p./pp. 缩写定位、页行粒度不一致、用编号指文献、靠另一条回复才读得懂；审稿人分组且每组重新编号时按累计计条。逐条致谢：标同义词轮换与附理由，同一致谢公式重复不再 WARN；页码口径取正文页脚。section_lint I6：引言指向 Methods。

## revision_diff.py package · 包级一致性扫描（第十七轮）

`python scripts/revision_diff.py package 旧包目录|- 新包目录 [--letter 回复信] [--corrections corrections.csv] [--report r.md] [--json r.json]`。读两个目录里的 docx（按接受修订）、xlsx、md、txt、csv；clean、highlighted、tracked 同文只算一份；文件名去掉版本记号与共同前缀后跨轮配对，配不上时按名称与内容相似度配。

- **MUST**：悬空引用（旧包有题注、新包已撤的表、图、补充文件，新包正文仍在提及；回复信里只提示）；已登记更正的旧说法仍在（corrections.csv 每行 old,new[,note]，回复信以外的任何文件）。
- **核对**：改动对象的其他提及（题注或工作表内容变了的对象，新包里一字未改的句子对它的描述）；改了说法的数字（百分数或三位以上数字，在配对的改动段里换了说法，别处原样未改且不用新说法）；同一对象多种写法（同一文件补充前缀混用、同一软件多个版本号、等号两侧空格不一）；不存在的文件名；包里找不到的补充对象（被引用的补充表、图没有题注，也没有同名工作表，如 `Table_S7c_…`）；回复信点名的节本轮正文没改。改了说法的数字不报已用上新说法里实词的句子。
- 报告另附“回复信各条点名的节”表，不计入发现，用于逐条确认节名就是改动所在。
- xlsx 数据单元格（编码记录、摘要）不当作作者措辞，只读题注与注释行；统计量缩写（CI、OR、AUC 等）与 0. 开头、全大写且两位以上小数的不当作软件版本。
- 旧包给 `-` 时只做写法、文件名、更正、找不到的补充对象与节名检查。JSON 带新包各文件的 `files_sha256`，供 station_check 判断扫描是否在最后一次改稿之后。
- **station_check.py（S8，V、R 模式）**：`05_revision/sweep.md`（init_project 在 V、R 模式生成）第 1–8 项都要有结果（已改、无问题、不适用）与不少于 8 字的证据；第 7 项不是“不适用”时要有 `04_audit/package_scan.json`，MUST 为 0，且当前稿件指纹在 `files_sha256` 里或扫描晚于稿件；“不适用”要写不少于 15 字的理由。退出码 0 无发现，1 有发现，2 输入错误。只给候选，不判断该不该改。
- 在一篇真实文献计量稿的返修包上：修复前 12 条核对候选，覆盖人工复核找到的 Highlights 分母、S1 旧描述、前缀混用、版本写法、文件名；修复后余 6 条，均为需作者判断的写法或同数异义。

## 按问题选工具：能力与裁决边界

本节集中维护工具目录。先按 SKILL §0 确定任务，再选能提供所需证据的工具；完整流程见 28，局部任务不默认运行 check_all。是否重跑由 SKILL §7 的实际变更决定。下列工具说明不扩大用户授权范围。

先跑 `check_all.py`，它依次调用下表前几项工具，把结果合成一页 STATUS.md：必须先处理的、没能运行的（不算通过）、需要看一眼的、机器查不了需要人看的。原始报告留在同一目录。需要单独深查时再直接调用各工具。读 [13](13_quality_contract.md)；自动检查和语义审查分开记录。

| 工具 | 能做什么；不能证明什么 |
|---|---|
| check_all | 一条命令跑 section_lint、density_check、ref_check；有结果文件时跑 number_trace 并核对批准号与注册号；有口径表时查限定词；有台账或作者说明时跑 lit_evidence；有期刊档案时跑 journal_check。不判断论证、引文支持与图表好不好读 |
| section_lint / density_check | 职能错位、冗余、术语堆积、交付残留、写作过程进稿（X11）、摘要与结论里的待办和状态话（X13）、本地路径（X12）等候选；`--fragment` 查单独的 Highlights、投稿信、图注表注；`--design` 查因果措辞。不判断真实贡献与因果论证 |
| number_trace / verify_evidence / metric_audit | 搜索数字的候选出处（原样出现在来源里的百分数算有出处，95% CI 的 95% 不算结果数字）；按指纹、CSV 行列与单位核对；按声明的分子分母复算比率、事件比例与截断均值。列选错了，算出来也对得上 |
| ref_check / lit_evidence / reference_identity | 引用格式与双向匹配；正文有引文却没有参考文献表时阻断；DOI 解析、书目比对、更正与撤稿信号；越界说法 F01–F16。DOI 存在不等于支持本句主张 |
| journal_check / table_style | 按期刊规则档案（每项带来源与核实状态）查标题、摘要、图注、表注、Highlights；生成并检查三线表（小数位不动 p 值与计数列）。规则会更新，投稿前须重查；不代替渲染后的逐页查看 |
| claims_guard / ledger_check | 检查登记的规则与位置，包括不进稿事项的肯定、否定和侧面写法。没有命中，不等于没有越界或遗漏 |
| revision_diff / response_lint | 定位改动与回复中的问题候选（含定位缩写、文献编号、跨条指向）；`package` 模式对照新旧交付包查跨文件漂移（悬空引用、未扫掉的更正、改过对象的旧描述、写法不一、文件名）。条数相同，不等于所有子问题都已回应 |
| delivery_check / display_extract / display_profile | 检查投稿包材料、表图说明和 Word 结构；按同类图表对比注释长度。不能代替视觉检查 |
| phrase_contrast / language_plan / bench_profile | 找出句式与分布偏离；对同类问题逐处列计划并在改后核对。不判断改写是否更好 |
| claim_strength / derivation_check | 概括位置（题目、摘要、讨论首末段、结论、图注）的推断谬误式样（显著性之差、用不显著说不存在、簇边界当时程、无直接检验的分离、相关写成来源）与作者登记的禁用表述；概括前人的句子是否有全文依据；派生量的单位、符号与数值复算。中英文式样都有。措辞信号不是判决，复算只核登记了的量 |
| figure_layout_qa | 用 matplotlib 出图时，保存前查重叠（必须处理）与多余留白（提醒）；可直接对作图脚本运行 |
| deviation_register / convention_profile / move_check | 与近邻比较的偏离：惯例、语步、质感、词汇；给了 `--submitted` 再列相对原稿的累计增量与读得出改稿过程的新增句；adjudicate 类在投稿阶段要有裁决。不说明论证成立；近邻选得不对，比较也就不对 |
| results_function | 结果节逐句功能（直接报告、数字翻译、统计限定可留；作者叙述决策、过程或机制判断、设计限制、文献比较待核位置，否定句不豁免）与小标题风格（按声明检查）。不判断解释本身对不对 |
| genre_gate | 体裁与节职能：摘要末句、摘要否定与程序细节、引言首末段、方法记账与防御说明、主文样本表、讨论首段、结论末句、自造标签、补充条目数；投稿阶段核对去向登记、体裁备忘与拒收预演是否齐全并绑定指纹；去向登记另查交代依据、结果盲测试、离题与失败材料、审稿人两问、主张编号与材料预算（PL8–PL15、PB1），以及论文构想（PC0–PC1）。给了近邻全文时，近邻也触发的文本规则自动降一级（按同类惯例校准，`--no-calibrate` 关闭）。在 10 篇真实全文上校准过（27 §8）。不判断贡献本身是否成立 |
| station_check | 流水线站点：产物存在且不是空模板、有质检证据与质检员、放行条件、不跳站、指纹一致、暂停原因。不证明质检认真 |
| survey_check | 同类调研：筛选篇数、相似维度、全文编码数，选材编码与“为什么只呈现这些”是否齐全、是否雷同；输出同类论文的材料范围供 PB1 对照。不判断所选文献是否最合适、推断是否准确 |
| display_terms | 表、图注、图内文字与正文里的分析代码和内部分类值，p 值、负号、小数位写法；template 从分析表收集待登记 ID，apply 按登记的显示名生成投稿表，未登记就不写出。不证明表图好读，仍要渲染后逐张看 |
| coverage_check | 按论证职能核对文献覆盖、缺口的检索记录、命名方法与刺激是否有出处；参考文献数只作信号。不判断所引文献是否最合适 |
| reader_readiness | 按摘要、正文与可识别的独立图表范围定位缩写/名称的首用与定义候选；可用项目术语列表扩充。只给阅读前提候选，不判断概念已讲懂或预测已有证据；不为字母数字标签编造全称 |
| review_pack | 把正文、全部表、图注、补充材料与图片清单打成一个带指纹的审查包。不保证审稿人真的读了：零发现必须附覆盖证明 |
| domain_pack / review_merge / audit_run / gate_check / release_check | 领域包构建与检查；多位审稿人发现的汇总（空审与模板化裁决会被退回）；真实执行的回执；进度表与证据契约。不代替作者批准或科学审查 |

脚本报出的 MUST，意思是“必须裁决的候选”，不是必须删掉的句子。以下属于阻断问题：错误的输入、已证实的数字错误、伪造的引文或编号、缺少必要的披露、写作过程或状态话进了稿件、带限定的数字丢了限定、没有记录支撑的“已核实/已对标”；已登记的用户要求没有满足；读者看到的表图里有未登记的内部代码；投稿阶段文献覆盖有未关闭的缺口。每条重要问题记录位置、证据、严重度、处理方式和复查结果。合理的例外写明理由，不为了全部通过去改词表、阈值或正确的内容。站点表和作者说明里的“通过”必须指向工具的实际输出；工具没能运行，就不能记通过。

完整稿还要审查类型与主线、主要结果是否完整、引用的上下文、讨论的推理、作者声音和图表。每次运行都用新的报告文件名或新目录。退出码 1 表示有发现，读完后逐条裁决；2、124、125 表示输入或执行出了问题，先修正，不能算作检查通过。
