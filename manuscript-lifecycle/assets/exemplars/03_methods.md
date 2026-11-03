# 03 · 方法：术语堆积与“报告到哪一层”
<!-- test: tool=lint section=methods bad=M7 good_no=M7 -->

任务：读者知道每项分析要回答什么、凭什么判断、结果从哪里来；同行能复现。

## 坏例

```bad
Analyses were conducted in R. We employed a regularized partial correlation network estimation procedure based on the graphical LASSO with extended Bayesian information criterion model selection, utilizing a hyperparameter tuning value of 0.5, applied to polychoric-adjusted Spearman rank-order correlation matrices, with subsequent computation of node-wise expected influence centrality indices, nonparametric and case-dropping subset bootstrap resampling procedures with 1,000 iterations each for the quantification of edge-weight accuracy and centrality stability, and permutation-based network comparison testing. Data were cleaned in Excel and exported to CSV. Random seeds were set to 2024. The analysis was re-run after an initial error in the grouping variable. A research assistant double-checked the item coding. All statistical assumptions were met.
```

## 为什么坏

1. **一句话 11 个术语。** 读者不知道每一步各自回答什么。方法节的骨架是“目的 → 对象与做法 → 关键设定 → 判断标准”，不是名词清单。
2. **没有目的。** 为什么要算中心性，为什么要做 bootstrap，读者无从判断。
3. **执行记录写进了稿件。** Excel 清理、随机种子、重跑、助研复核都是执行记录，不改变样本、变量意义或结论，归内部档案；审稿人问到时按记录如实回答（见 15）。
4. **“All statistical assumptions were met”是编的。** 没有说检验了哪些假设、怎样判断。
5. **软件句的辖域写大了。** “Analyses were conducted in R”放在段首，却没写版本和各个包。

## 改写

```good
### Statistical analysis

To describe how symptoms relate to one another, we estimated one network per school type. Each connection (edge) is the partial correlation between two symptoms after accounting for all other symptoms, with small connections shrunk to zero. For each symptom we computed expected influence, the sum of its connections with all other symptoms, to identify the symptoms most connected with the rest; because this index can be unstable in small samples, we assessed it by repeatedly dropping participants and report the correlation-stability coefficient, for which values above 0.5 are usually treated as acceptable. The accuracy of individual edge weights was assessed by bootstrap and is shown in Supplementary Fig. 1.

The two prespecified questions were tested with the network comparison test. Its invariance test compares the largest difference in any single edge between the two networks, and its global strength test compares the sums of absolute edge weights; both use 1,000 permutations. Differences in individual edges were not planned, and we report them as exploratory with the Holm correction.

Networks were estimated with EBICglasso (tuning parameter 0.5) on Spearman correlations. Analyses used R 4.3.2 with qgraph 1.9.8, bootnet 1.5.6 and NetworkComparisonTest 2.2.2.
```

每项分析先写目的（to describe…、to identify…），再写做法和判据。复现需要的设定（调参值、置换次数、校正、包与版本）都在，但集中放在段末，不打断阅读。预定分析与探索性分析分开说明。

## 报告到哪一层：四个问题

对每一条方法细节依次问：

1. 不写它，别人能复现吗？
2. 它改变样本、变量意义、纳入排除或估计目标吗？
3. 它是注册或方案承诺、报告规范的必需项吗？
4. 知情读者如果知道这件事，会改变对研究的判断吗？

任一为“是”，就必须写（位置可以在正文或补充材料）。全为“否”，就归内部档案，不主动写，被问到如实回答。第 4 问用来**防止漏报**，不是用来找理由少写。

## 这份范例不校准什么

- 方法的详略。Nature 要求方法精简，已发表的方法只给引用；Cell Press 的 STAR Methods 结构化、不限篇幅。两者方向相反，所以不存在“方法越短越好”的通则。
- 公式写不写、写在正文还是补充材料，取决于它是否让核心量更清楚。
