# 15 · 不进稿的事：肯定句、否定句、侧面带出
<!-- test: tool=none 说明：该不该进稿是语义判断，由结果台账（ledger_check）与人工审查承担 -->

任务：分清三件事：必须披露的、可以放补充材料的、不进稿的。

## 先判断是否必须披露

依次问，任一为“是”就必须披露（位置可以在正文或补充材料）：

1. 它是预定的主要或次要结局、注册或方案承诺、报告规范的必需项吗？
2. 它改变样本、变量意义、纳入排除、估计目标或结论可信度吗？
3. 不利或不确定的结果限制了主要主张吗？合理的另一种分析会给出不同结论吗？
4. 计划偏离、事后选择、分析失败、数据问题或伦理事实，隐去会让读者误判吗？

**必须披露的事，不因结果不利、可能被追问或同类文献没写而隐去。** 这个判断在前，篇幅分配在后。

## 不进稿是什么意思

不进稿的意思是：正文和表注里既不写“做了”，也不写“没做”。

```bad
§2.1 ... Diagnoses were taken from routine clinical records and were not verified for research purposes.

Table 1 note. ... Diagnoses were not verified for research.

§2.6 ... Analyses were not preregistered.

Table 2 note. No solution had a negative variance estimate or a non-positive-definite latent covariance matrix.

§2.4 ... Independent reproduction in Python confirmed all reported quantities; random seeds were set to 2024.
```

这五句报告的都是同一类事：**内部核对**。前三句用否定式报告，第四句用“全部正常”侧面带出了“我们做过一个没报告的检查”，第五句是执行日志。读者读到它们，只会生出新的追问，却得不到任何能用来判断研究的信息。

**三种写法都算报告：**

| 写法 | 例子 |
|---|---|
| 肯定句 | Diagnoses were verified for research purposes. |
| 否定句 | were not verified、未经研究核实、未作预注册 |
| 侧面带出 | All solutions were proper.（读者据此知道做过一个检查）、条目层指标结果相似 |

## 改写

```good
§2.1 ... Diagnoses were taken from routine clinical records.

Table 1 note. ... Diagnoses were taken from routine clinical records.
```

直接写事实来源，不加核查免责句。审稿人如果问“诊断是否为本研究重新核实过”，按内部记录如实回答。答案一直都在，只是不主动写进论文。

## 但是不要用它来少写

同一类事实，换一个条件就必须写：

- 草率作答标记如果只是无影响的内部核对，就归档；**如果据此排除了样本或选择了结果，就必须报告处理方式和影响。**
- 扩大年龄范围如果参与了分析，就必须报告，并评估伦理、人群与结果变化。
- 问卷改版如果改变了已分析的测量或可比性，就必须报告。
- 预注册：作者**声称**预定，就必须说明依据（时间戳、方案）；没有注册，不写“未注册”，也绝不能写成“已预注册”。

反事实检验：**知情读者如果知道这件事，会改变对这项研究的判断吗？** 会，就写；不会，就归档，并在结果台账里登记决定依据，以备追问。

## 落到工具上

结果台账（`assets/templates/results_ledger.csv`）里，每项分析写 `tier`（main / supp / reserve / omit）和 `must_disclose`，并写明决定依据。`ledger_check.py` 做两件事：必须披露的项目不能定为 reserve 或 omit；定为 reserve 或 omit 的项目若在稿件中命中关键词，先复核披露义务。关键词命中不是删稿指令。

关键词要用这项分析独有的短语（careless respond、questionnaire version、not verified），不用 model 这种泛词。**否定式写法也要写进关键词**，否则“未经核实”这句话不会被发现。

## 这份范例不校准什么

- 某个项目的不报告清单不是通用规则。换一篇论文、换一本刊、换一次证据，都要重判。
- 某一轮决定“暂不写 AI 使用声明”，不代表当前期刊不需要这份声明。
