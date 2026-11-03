# assets/benchmarks · 图表说明的实测基线

`display_baseline.json` 是本机语料里图注、表题与注释长度的实测分布，只含统计量，不含原文。

## 为什么需要它

手工建一份图注对标清单负担很大，这一步常被跳过，“图注要短”“表注不要解释”这类说法就被当成了规则。实测并不支持：

- Nature 系列 4 篇 23 条图注：中位 176.0 词，最短 43、最长 1118 词；其他英文刊 105 条：中位 158.0 词，范围 17–523。**同一类期刊内部就差了一个数量级，所以“短”不是标准。**
- Nature 系列约 44% 的图注含结论句，其他英文刊约 14%。**“图注一律不下结论”不是事实，只是复读候选。**
- 《心理学报》注释中位 24.0、p90 86.2；《开放教育研究》中位 10.0、p90 44.5。**同为中文期刊相差一倍以上，只能按同刊比较。**
- 以“如表 2 所示 / As shown in Table 2”起句的结果段：中文 3/1131 段、英文 1/151 段。**这一条实测支持“先写发现，再把表图放进括号”。**

## 怎么用

```text
python scripts/journal_check.py 稿件.md --profile assets/journal_profiles/nature_article.json \
       --baseline assets/benchmarks/display_baseline.json
```

报告超长的图注时，会同时给出它在实测分布中的位置（高于 p90 / 在范围内 / 低于 p10）。

## 边界

见 JSON 里的 `limits` 与 `method`。本目录不含任何语料全文；重建方法见 `scripts/display_extract.py` 与 `display_profile.py`。
