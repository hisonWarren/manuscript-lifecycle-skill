# 09 · 表题与表注
<!-- test: tool=journal profile=nature_article section=legend bad=legend_conclusion good_no=legend_conclusion -->
<!-- test: tool=table bad=表注顺序 good_no=表注顺序 -->

任务：读者只看这一张表，就知道在比较什么、单位是什么、样本是谁、符号代表什么。

## 坏例

```bad
Table 1. Results of the network comparison analysis demonstrating that boarding school students exhibit significantly stronger symptom connectivity than day school students, supporting the hypothesis that the boarding environment intensifies symptom co-occurrence.

| Measure | Boarding | Day |
| --- | --- | --- |
| Global strength | 3.92 | 3.41 |

Note. ***p < .001. This table presents the results of the network comparison test (NCT), which was conducted using the NetworkComparisonTest package version 2.2.2 in R version 4.3.2 with 1,000 permutations. The NCT invariance test compares the largest difference in any single edge between the two networks. The results indicate that the two networks are structurally equivalent. EI = expected influence; CS = correlation-stability coefficient.
```

## 为什么坏

1. **表题在下结论。** 表题回答“这是什么”，不回答“这说明了什么”。significantly stronger … supporting the hypothesis 把一张描述表写成了论点。
2. **表注变成了小型方法节。** 软件、版本、置换次数在方法节已经写过。
3. **表注在解释，而且解释错了。** “The results indicate that the two networks are structurally equivalent”属于正文，还把不显著说成了等价。
4. **缺必要信息。** 没有样本量，没有单位，没说边权是什么尺度。
5. **顺序颠倒。** 概率说明（***p）写在缩写定义前面。顺序应为：总说明 → 缩写 → 符号 → 概率。
6. **定义了用不到的符号。** 表里没有 ***，也没有 EI、CS，却都定义了。

## 改写

```good
Table 1. Closest symptom pair, most connected symptom, and overall connection strength, by school type

| Measure | Boarding (n = 1,032) | Day (n = 1,108) |
| --- | --- | --- |
| Edge weight, low mood–loss of interest | 0.31 | 0.29 |
| Expected influence, sleep problems | 1.21 | 1.15 |
| Global strength | 3.92 | 3.41 |

Note. Edge weights are regularized partial correlations between symptoms; expected influence is the sum of a symptom's edge weights; global strength is the sum of all absolute edge weights. Higher values mean more strongly connected symptoms. The difference in global strength was tested with a permutation test (P = 0.02).
```

读者得到了尺度、方向、样本量和检验，但没有读到方法节的复制品，也没有读到结论。

## 删除测试

逐项问“删掉它，读者会不会读错”：

| 信息 | 删掉会怎样 |
|---|---|
| 对象、结局、分组或时间点 | 不知道在比较什么 → 保留 |
| 单位、非标准缩写、符号含义 | 读错量纲 → 保留 |
| N、分母、缺失、参考组 | 把效应或百分比读错 → 保留 |
| 误差条、区间类型 | 不知道区间代表什么 → 保留 |
| 软件与版本、置换次数 | 方法节里已有 → 移走 |
| 机制解释、意义 | 讨论里有 → 移走 |

## 三线表

顶线、表头下横线、底线各一条；没有竖线；只有分组栏头下面再加一条横线。表头跨页重复，数据行不跨页，同一列用同一精度。
`python scripts/table_style.py build --csv 表.csv --title "…" --note "…" --out 表.docx` 生成，`check` 复查；渲染后仍要逐页看。

## 这份范例不校准什么

- 表注长度。实测《心理学报》注释中位 24.0、p90 86.2；《开放教育研究》中位 10.0、p90 44.5（汉字加英文词）。同为中文期刊相差一倍以上，只能按同刊比较。
- 注释位置与网格线规定按目标刊：APA 与 PLOS 的要求并不相同。
