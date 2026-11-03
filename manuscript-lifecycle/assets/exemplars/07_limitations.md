# 07 · 优势与局限：影响判断，而不是仪式
<!-- test: tool=lint section=limitations design=cross_sectional bad=G1 good_no=G1 -->

任务：告诉读者这项研究的可信度从哪里来，以及哪条推断受什么影响。

## 坏例

```bad
This study has several limitations. First, the sample size was relatively small. Second, the cross-sectional design is a limitation. Third, self-report measures may introduce bias, which likely leads to an overestimation of the associations. Fourth, generalizability may be limited. Despite these limitations, the present study has notable strengths, including its novel methodology and large sample, which outweigh the limitations noted above.
```

## 为什么坏

1. **仪式化清单。** 四条局限换到任何一篇问卷研究上都成立，读者不知道哪一条真的威胁结论。
2. **样本量自相矛盾。** 先说 relatively small，后面又说 large sample。
3. **偏倚方向是编的。** “likely leads to an overestimation”需要证据；自评偏倚同样可能压低相关。方向不明就写不明。
4. **“generalizability may be limited”没说限制到哪里。**
5. **用优点抵消局限。** “outweigh the limitations”是作者替读者下的判断。

## 改写

```good
The survey was cross-sectional and cannot show the direction of associations between symptoms: a tighter network may precede more persistent symptoms, follow from them, or both.

Symptoms were self-reported on one questionnaire. Shared method variance can inflate connections, but it would have to differ between school types to produce the difference we observed, and we have no evidence either way.

The network includes only eight symptoms. Anxiety or stress items might change which symptoms are most connected, so the prominence of sleep problems should be read as "most connected among these eight".

The sample came from six schools in one province. Boarding and day schools may also differ in location or family income; either would offer an alternative explanation for the difference in global strength, which the present data cannot rule out.
```

每条局限都写出它威胁哪条推断、影响方向是否已知、本文能不能排除。不写“尽管如此”，也不替读者权衡。

## 逐条自检

- 它威胁哪条主张？限制的是关联、因果、测量还是推广？
- 证据能判断影响方向吗？不能就写不能。
- 已做的核对真正缓解了什么、没有缓解什么？缓解措施必须是真做过的。

## 这份范例不校准什么

- 局限写几条。不按“同类论文常写三条”决定数量。
- 是否单列“优势”小节，按体裁与目标刊；有些刊明确不要这一节。

## 校准：局限的篇幅与版式按领域分布

“每条局限写出它威胁哪条推断”说的是内容，不是“每条一段、单列小标题”。一次实测：同类 13 篇里 12 篇没有单独的局限小标题，局限多为讨论末尾的 0–3 段；按本范例每条一段写出的四段加小标题成了离群值。先跑 convention_profile，按多数做法合并为一段（必要时两段），每句仍写清它限制哪条主张。
