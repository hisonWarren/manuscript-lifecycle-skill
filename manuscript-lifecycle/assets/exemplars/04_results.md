# 04 · 结果：把解释挤进结果节
<!-- test: tool=lint section=results design=cross_sectional bad=R1,S2 good_no=R1,S2 -->

任务：按研究问题的顺序，报告估计值、不确定性和不利结果；读者自己能看出发现是什么。

## 坏例

```bad
As shown in Table 1, the network structure did not differ between the two groups, which indicates that the architecture of depression is fundamentally the same regardless of living environment. Global strength was higher in boarding pupils, suggesting that the boarding environment intensifies the mutual reinforcement of symptoms, probably because dormitory sleep and the absence of family support act on several symptoms simultaneously. Sleep problems had the highest expected influence, which implies that sleep is the engine of the symptom network and should therefore be prioritized in school mental-health programmes. Three edges were stronger in boarding schools. Although the main comparison did not reach significance, there was a trend towards a difference in the low-baseline subgroup.
```

## 为什么坏

1. **段落以表起句。** 已发表论文很少这样开头（实测中文 3/1131 段、英文 1/151 段）。先写发现，再把表放进括号。
2. **每句话都在解释。** which indicates、suggesting、probably because、which implies：机制、原因和建议都属于讨论。
3. **没有数字。** 结果节的任务就是给估计值和精度，这里一个都没有。
4. **“did not differ”被解释成了“fundamentally the same”。**
5. **“should be prioritized”是建议**，而这项研究没有检验任何干预。
6. **三条边被当成发现**，却没说这是探索性的、校正后还剩几条。
7. **“a trend towards”把不显著写成了半个显著。**

## 改写

```good
### A similar pattern in both school types

The network structure did not differ detectably between boarding and day pupils (M = 0.14, P = 0.41; Fig. 1). In both groups the closest pair was low mood and loss of interest (edge weight 0.31 in boarding and 0.29 in day pupils; Table 1), and sleep problems had the highest expected influence (1.21 and 1.15), with stable estimates (CS = 0.67 and 0.59).

### Stronger connections in boarding pupils

Global strength was higher in boarding than in day pupils (3.92 versus 3.41, a difference of 0.51, P = 0.02). In exploratory tests of the 28 individual connections, three differed at an uncorrected P < 0.05 and none after Holm correction (Supplementary Table 2).
```

这份改写的小标题用的是发现句式。它是合法写法之一，不是通则：很多实验心理学、认知神经科学和临床期刊按分析对象、指标或成分命名结果小节，发现放在该小节的第一句。同一内容的分析对象式写法：

```good
### Network structure

The network structure did not differ detectably between boarding and day pupils (M = 0.14, P = 0.41; Fig. 1). In both groups the closest pair was low mood and loss of interest (edge weight 0.31 in boarding and 0.29 in day pupils; Table 1).

### Global strength and individual connections

Global strength was higher in boarding than in day pupils (3.92 versus 3.41, a difference of 0.51, P = 0.02). In exploratory tests of the 28 individual connections, three differed at an uncorrected P < 0.05 and none after Holm correction (Supplementary Table 2).
```

用哪一种，依次看用户偏好、目标刊、近邻论文实测（`bench_profile.py` 第六节），选定后写进决策登记，全节统一。预定分析与探索性分析分开；探索性结果连同校正结果一起报告，已经做过的分析不选择性隐去。

## 否定句与限定：哪些留，哪些移

判断依据是句子的功能，不是有没有否定词：否定只改变方向，不改变功能（合成例）。

| 句子 | 功能 | 去向 |
|---|---|---|
| The difference between school types in this estimate was uncertain (P = 0.21). | 局部统计限定 | 留 |
| These estimates do not establish equivalence between the groups. | 局部统计限定 | 留 |
| We therefore describe the effect in boarding pupils without claiming that day schooling abolished it. | 作者叙述决策 | 删去；按什么规则报告写进方法 |
| These intervals do not show that sleep is irrelevant to the network, nor do they bound a mediated effect. | 否定式的过程判断 | 讨论 |
| Because school type was not randomised, the difference cannot be separated from family background. | 设计限制 | 方法写设计，讨论写局限 |

`results_function.py` 按这张表的功能逐句分类，供逐句裁决；科学上必要的限定换到正确的章节，而不是删掉。

## 什么样的“解释”可以留在结果节

把系数翻成读者的话可以留，例如“a difference of 0.51 on this scale corresponds to about one-tenth of the between-pupil spread”。它没有引入新的因果判断，只是让数字可读。合并 Results and Discussion 的体裁另当别论，那时解释本来就该出现在这里。

## 这份范例不校准什么

- 结果节的长度和小标题数量，按研究问题的个数决定。
- 有些学科在结果节引用方法学出处，这是惯例；与既往研究结论的比较才要移到讨论。
