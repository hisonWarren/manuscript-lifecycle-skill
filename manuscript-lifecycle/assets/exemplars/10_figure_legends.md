# 10 · 图注
<!-- test: tool=journal profile=nature_article section=legend bad=legend_methods,legend_conclusion good_no=legend_methods,legend_conclusion -->

任务：读者只看这张图和这条图注，就知道每个面板画的是什么、点和线代表什么、误差条是什么、样本是谁。

## 坏例

```bad
Fig. 1 | Symptom networks. Networks were estimated with EBICglasso (tuning parameter 0.5) in qgraph 1.9.8 using Spearman correlations, with 1,000 bootstrap iterations for edge-weight accuracy. These results demonstrate that sleep problems are the central driver of adolescent depression and should be prioritized in intervention.
```

## 为什么坏

1. **方法细节。** 有方法节时，图注不写估计器、调参值、软件与迭代次数（Nature 官方格式指南明确写了这一条）。
2. **下结论，而且越过了证据。** central driver、should be prioritized 既是因果判断，也是建议。
3. **没说怎么读图。** 面板、节点、线的粗细、位置能否比较，全都没写。
4. **没有样本量。**

## 改写

```good
Fig. 1 | Connections among eight depressive symptoms in boarding and day pupils. a, Boarding pupils (n = 1,032). b, Day pupils (n = 1,108). Nodes are symptoms and lines are connections (regularized partial correlations); thicker lines indicate stronger connections and dashed lines indicate negative ones. Node positions are the same in both panels, so panels can be compared directly.
```

先给整图的简短标题，再逐面板说明，再解释符号。读者拿到的是“怎么读”，不是“该信什么”。

## 长度

Nature 的官方要求是每条图注少于 300 词。实测本机 Nature 系列 4 篇 23 条图注：中位 176.0 词、p90 783.4 词，最短 43、最长 1118；其他英文刊 105 条：中位 158.0 词，范围 17–523。**所以“图注要短”不是通则**：多面板复杂图的图注本来就长，缺定义才是问题。

同样是实测：Nature 系列约 44% 的图注里有结论句，其他英文刊约 14%。所以“图注一律不下结论”也不是事实，它是复读候选，不是错误。真正的硬条件只有一条：只看这张图能不能读对。

## 对标怎么做

按相同的图表任务和复杂度比：多面板网络图和多面板网络图比，不和一行描述表比。记录面板数、需要定义的符号数、是否给了样本量与误差条说明，再比长度。
`python scripts/display_extract.py` 抽取，`display_profile.py` 分层比较；`journal_check.py --baseline assets/benchmarks/display_baseline.json` 给出本条图注在实测分布中的位置。

## 这份范例不校准什么

- 图注能否用结果性标题（如 Sleep problems are the most connected symptom），按学科与目标刊；不少刊鼓励这样写。
- 误差条、显著性标记的写法按目标刊体例。
