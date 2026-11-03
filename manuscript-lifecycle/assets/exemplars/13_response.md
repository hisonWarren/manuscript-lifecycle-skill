# 13 · 审稿回复
<!-- test: tool=none 说明：回复信的好坏要靠逐条阅读判断，没有对应的机器规则；格式问题由 response_lint 检查 -->

任务：逐条回应，说清改了什么、改在哪里；有据的不接受也要写清楚。

## 坏例

```bad
Reviewer 1, Comment 2: The cross-sectional design limits causal inference, and the subgroup analysis appears to be post hoc. The authors should also externally validate their findings.

Response: We sincerely thank the reviewer for this insightful and valuable comment, which has greatly improved the quality of our manuscript. We fully agree with the reviewer's excellent suggestion. We have carefully revised the manuscript accordingly. The analysis has now been externally validated. Please see page 12, line 340.
```

## 为什么坏

1. **一条意见里有三个问题，只回应了一个。** 设计、事后亚组、外部验证要拆开分别回应。
2. **恭维与套话。** insightful、greatly improved、carefully revised 占了一半篇幅，没有信息。
3. **“has now been externally validated”与事实不符。** 没做的事不能写成做了。这是最容易被编辑发现、也最致命的一种回复。
4. **“carefully revised accordingly”没说改了什么。**
5. **页码行号。** 最终排版还没生成时，页码行号多半是错的；投稿系统重排后还会变。

## 改写

```good
**Reviewer 1, Comment 2** (three points; we answer each in turn)

> The cross-sectional design limits causal inference, and the subgroup analysis appears to be post hoc. The authors should also externally validate their findings.

**(a) Causal inference.** We agree. We have removed "drives" and "intensifies" from the Abstract and Discussion and now state that connection strength describes co-occurrence at one time point. We also added to the Limitations that the direction of the association cannot be determined.
*Changes:* Discussion, first paragraph; Limitations, first paragraph.

**(b) The subgroup analysis is indeed post hoc.** It was not prespecified and we did not test the interaction. We now label it exploratory wherever it appears, report that no edge difference survived the Holm correction, and have removed it from the Highlights.
*Changes:* Results, "Stronger connections" subsection; Supplementary Table 2; Highlights.

**(c) External validation.** We cannot provide it: we have no second cohort with the same eight items, and validating on a different instrument would not test the same quantity. We have instead stated in the Limitations what an external test would require (an independent sample, the same items, and pupils who move between arrangements). We would welcome the editor's view on whether this is sufficient for the present submission.
*Changes:* Limitations, final paragraph.

Locations refer to sections of the revised manuscript; page and line numbers will be added once the final PDF is generated.
```

拆成三个子问题；接受的说清改在哪里；做不到的说清为什么做不到、用什么替代，并把判断交回编辑。没有一句恭维。

## 四种回应

| 回应 | 什么时候用 |
|---|---|
| 接受 | 意见成立，照改，写明改动与位置 |
| 部分接受 | 问题成立，但建议的做法不适用：说明采取了什么替代做法 |
| 澄清 | 原稿已有，但没写清楚：指出位置，并说明怎样改得更清楚 |
| 有据不接受 | 建议越出体裁、设计或数据能力：给出理由和证据，不照单全收 |

## 这份范例不校准什么

- 回复信的格式（是否引用原话、是否编号）按期刊要求。
- 中文回复信里礼节性的开场可以保留一句，但不要每条回复都写一遍。
