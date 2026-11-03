# 12 · 投稿信
<!-- test: tool=lint section=fragment bad=N2 good_no=N2 -->

任务：让编辑在一分钟内知道这篇论文问了什么、发现了什么、为什么适合这本刊。

## 坏例

```bad
Dear Editor,

We are pleased to submit our groundbreaking manuscript, which represents the first study ever to apply network analysis to boarding school populations and fills a critical gap in the literature. Our findings conclusively demonstrate that boarding environments cause tighter symptom coupling and have profound implications for policy worldwide.

We confirm that this manuscript has not been published elsewhere and is not under consideration by another journal. All authors have approved the manuscript and agree with its submission. The authors declare no conflict of interest. All data are available upon reasonable request.

We believe this paper is a perfect fit for your prestigious journal given its high impact factor.
```

## 为什么坏

1. **夸大。** groundbreaking、first study ever、conclusively demonstrate、profound implications。
2. **因果动词。** 横断面研究写了 cause。
3. **代作者签了四项声明。** 一稿多投、全体作者同意、利益冲突、数据可得性，都是只有作者本人知道的事实。模型不能代填，更不能默认填“无”。
4. **“perfect fit … high impact factor”说的是期刊，不是读者。** 适配性要具体到这本刊的读者和近期方向。

## 改写

```good
Dear Editor,

We submit our manuscript, "Depressive symptoms connect more tightly in boarding-school pupils", for consideration as an Article.

Adolescent depression research usually compares how severe symptoms are between groups. We asked a different question: whether the symptoms hang together differently. In 2,140 secondary-school students, the pattern of connections among eight depressive symptoms was similar in boarding and day pupils, but the connections were stronger overall in boarding pupils. The data are cross-sectional, so we draw no conclusion about causal order.

The paper speaks to readers of your journal who work on school environments and adolescent mental health, and it connects to the work you published last year on sleep and school timetables.

[VERIFY: 作者确认后填写——未一稿多投、发表与预印本状态、相关稿件说明。]
[VERIFY: 作者确认后填写——全体作者同意投稿、利益冲突、资金、数据可得性，按本刊要求。]

Sincerely,
```

待确认的事实留成显眼的占位符，并同时列进作者待办。`section_lint.py --fragment` 会标出未清除的占位符，`delivery_check` 在投稿包检查时阻断它们。

## 这份范例不校准什么

- 是否推荐或回避审稿人、是否写字数与图表数，按目标刊的投稿信要求。
- 有些刊要求投稿信写明文章类型与所属栏目。
