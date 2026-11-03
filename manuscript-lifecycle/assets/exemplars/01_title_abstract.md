# 01 · 题目与摘要：谁是主角
<!-- test: tool=lint section=front design=cross_sectional bad=G1,S2 good_no=G1,S2 -->
<!-- test: tool=journal profile=nature_article section=front bad=title good_no=title -->

任务：读者只看题目和摘要，就知道这篇论文问了什么、发现了什么、这个发现有多可靠。

## 坏例

```bad
# Leveraging a Regularized Partial Correlation Network Framework to Unravel the Intricate Symptom Architecture of Adolescent Depression Across Boarding and Day School Contexts

Using EBICglasso network estimation (tuning parameter 0.5), case-dropping bootstrap (1,000 iterations) and the Network Comparison Test with 1,000 permutations, we investigated the symptom-level architecture of depression. Sleep problems emerged as the core symptom driving the network in both groups (expected influence 1.21 and 1.15), indicating a key intervention target. Networks were identical in structure (M = 0.14, p = .41), while boarding students exhibited significantly stronger global connectivity (3.92 vs 3.41, p = .02), suggesting that boarding causes tighter symptom coupling.
```

## 为什么坏

1. **主角错了。** 题目的主语是方法，不是发现。做替换测试：把这套方法换成更简单可行的方法，“寄宿生的症状联系更紧”仍然成立，说明方法是手段，不是贡献。
2. **题目 173 字符。** Nature 的 Article 标题上限是 75 字符（含空格），不用数字、缩略语和标点。即使不投 Nature，超过两行的标题在多数刊里都会被编辑改掉。
3. **摘要从方法开始。** 三种方法名、两个调参值挤在第一句，学科外读者读不下去。
4. **“identical”把不显著说成了相同。** 不变性检验不显著，只能说没有发现结构差异。
5. **“driving”“causes”是因果动词，而设计是横断面。** 中心性只描述一个时点上的共现程度。
6. **“a key intervention target”越过了证据。** 这项研究没有做干预。

## 改写

```good
# Depressive symptoms connect more tightly in boarding-school pupils

Depressive symptoms in adolescence rarely occur alone, and the way they connect may differ between living environments. Boarding schools reduce daily contact with family and impose shared schedules, yet it is unclear whether depressive symptoms relate to one another differently in boarding and day pupils. Here we show, in 2,140 secondary-school students, that the pattern of connections among eight depressive symptoms was similar in the two groups, but the symptoms were more interconnected overall in boarding pupils. In both groups, sleep problems were the symptom most connected with the others. The school types therefore differed in how tightly symptoms co-occurred, and we found no difference in which symptoms were linked. Because the survey was cross-sectional, longitudinal work is needed to test whether tighter connections precede more persistent symptoms.
```

题目 66 字符，主语是发现。摘要按“领域入门 → 本文之前不知道什么 → 本文发现什么 → 意味着什么 → 边界”走，承重数字只留样本量，其余交给正文。“未见差异”写成“没有发现差异”，不写成“相同”。

## 这份范例不校准什么

- 摘要是否分结构（Background/Methods/…）按目标刊。Nature 系列不分结构，很多临床刊必须分结构。
- 摘要里允许几个数字，各刊差别很大。这里的“少放数字”是 Nature 对学科外读者的要求，不是通则。

## 校准：题目形式按领域分布，不按范例

本范例的“主语是发现”与 75 字符上限来自 Nature 体例，不是通则。一次实测：脑电时间知觉的类型匹配论文 14 篇里，11 篇用名词短语题目、13 篇在题目里点名方法或成分（ERP、EEG、CNV、electrophysiological）；照搬本范例写出的两分句结论题目既不点名方法，又把只在正立条件下检出的效应写成了普遍结论。起题目前先跑 convention_profile，把形式、长度、是否点名方法与刺激的偏离写进 benchmark_decisions；题目里的每个结论动词也要过 claim_strength。
