# 25 · 读者用语：内部 ID 到正式显示名

分析代码里的分类值、模型名与时间窗名（all_retained、drop_overdesign_subj、arm_b_pp、tfidf_v2、primary、vpp）在分析者眼里很清楚，在读者眼里是乱码。它们最常从 CSV 原样流进投稿表格，再流进图例、正文与补充材料。只禁下划线不够：primary、avgref 没有下划线照样难懂；而公式里的 aᵢ、DOI 和数据字段说明里的下划线又是合理的。

## 1. 原则

- 数据与代码保留原 ID：可追溯性在数据层，不在读者层。
- 读者看到的位置（表头、行名、图例、坐标轴、面板标签、表注图注、补充材料、正文）一律用正式显示名，首次出现给操作定义。
- 显示名要有依据：从方法、原结果表或分析代码核实，不凭标签猜（pp_set 不能写成“依从良好的参与者”，它的定义是完成至少 80% 课时）。
- 未登记的 ID 不原样输出，报待处理；只替换被点到的几处等于没改，同类标识要在全部表图里一起扫。
- 改名时顺便读一遍每行在说什么：显示名写不出来，往往说明表本身有问题（某行缺测量位置或时间点、某个敏感性分析与主分析逐位相同却没说明是否剔除了人）。

## 2. 显示名登记表

`assets/templates/display_terms.csv`：`internal_id, publication_label, definition, source_locator, applies_to, status, aliases`。下面是合成示例：

| internal_id | publication_label | definition | source_locator |
|---|---|---|---|
| all_retained | All trials retained after preprocessing | 仍经过预处理与伪迹剔除；不再实施后续次数上限与重复删除 | 分析脚本参数；方法“试次筛选” |
| pp_set | Per-protocol sample | 完成至少 80% 课时的参与者 | 统计分析计划；原结果表的定义列 |

`status` 为 verified 或 author_confirmed 才算定稿；proposed 只能用于起草（`apply --draft`）。`applies_to` 写 prose 或“正文”时，正文里出现该 ID 也会提示。代码式 ID（含下划线、加号、数字或驼峰）在所有位置都查；普通单词式 ID（primary、average）只在表头和单元格里按整格匹配。读者用语本来就合适的值（Upright），publication_label 照抄 internal_id 并写 verified。

## 3. 工具

- `display_terms.py template --from-tables 分析表.csv … [--scan scan.json] [--terms 已有登记表] --out 草稿.csv`：从整批分析输出里收集像内部标签的分类值与列名，列成待填登记表。一次列全，不等读者在某一张表里发现。
- `display_terms.py scan 稿件 补充材料 --tables 表.csv … --legends 图注.md --figures 图… --terms display_terms.csv`：DT1、DT2、DT3、DT8 为 MUST（读者看到的代码、已登记未替换、显示名未核实、p 值写成 0）；正文里的代码式标识、原始分类值写法、非标准记号、分析过程史、精度与负号不一致为 SHOULD；公式下标为 INFO。图片：SVG 读文本元素，PDF 用 pdftotext，位图用 OCR；提取不了就记“没能运行”，不能算通过，逐图打开看。
- `display_terms.py apply 分析表.csv --terms … --out 投稿表.csv [--p-columns …] [--decimals 列=位数] [--minus unicode]`：按登记表生成投稿表；遇到未登记或未核实的标签退出 1，不写输出；原表不动。

check_all 每次都对正文（与 `--supplement`）跑 scan；`--displays` 给独立交付的表 CSV、图注与图片，`--terms` 给登记表。

## 4. 数字写法

同一份投稿材料里：p 值不写 0（写 p < .001）；前导零按目标刊体例全稿统一；负号统一用 −；同一个量用同一精度，估计值与区间同精度；表里不出现分析软件输出的长尾小数。table_style 检查 Word 表格的同列小数位，display_terms 检查 Markdown 与 CSV 表格及其与正文的一致。

## 5. 不误伤

公式变量（写成下标）、DOI 与网址、电极与基因等领域标准名、期刊要求的数据字段说明，都不是要替换的对象。判断标准始终是：读者不看代码，能不能读懂这个标签。
