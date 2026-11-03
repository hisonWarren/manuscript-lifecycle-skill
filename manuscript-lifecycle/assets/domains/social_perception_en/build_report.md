# 领域包构建报告：social_perception_en

社会知觉与生物运动（英文任务实证）；语言 en；18 篇（behavioral_task 13、neuroimaging 4、computational_model 1）；期刊：Journal of Autism and Developmental Disorders、Journal of Nonverbal Behavior、Molecular Autism、Nature Communications、PLoS ONE、Philos Trans R Soc Lond B Biol Sci、Psychonomic Bulletin & Review、Scientific Reports；年份：2010–2026；构建 2026-10-26。

各节可测量的篇数：abstract 18、introduction 18、methods 18、results 18、discussion_all 18、limitations 1、conclusion 4。

## 样本量与判定稳定性

留一法：每篇已发表论文轮流当作“稿件”，用 k 篇随机子集判定各指标是否偏离，与用其余全部论文的判定比较。k<10 时按范围判定，10–19 篇按 p10–p90，≥20 篇按 p05–p95（与 bench_profile 相同）。

| 参照篇数 k | 与全部参照的判定一致率 | 可测指标比较中被标偏离的比例 |
|---|---|---|
| 3 | 82% | 30% |
| 5 | 89% | 20% |
| 8 | 92% | 14% |
| 10 | 93% | 20% |
| 12 | 95% | 20% |
| 15 | 98% | 18% |

“被标偏离的比例”的分母是可测指标比较次数（指标 × 留出论文 × 抽样重复），不是论文篇数。这些判定没有人工真值，不能称为误报率；单项偏离只是核查线索，不等于写作问题。

## 体裁是否改变常态

只比较 ≥3 篇的体裁（behavioral_task 13、neuroimaging 4）。125 个指标中，3 个的体裁差异超过随机打乱标签的 95% 分位（随机情况下预期约 6.2 个）；η² 中位数 0.03，随机打乱时 0.06。

差异最大的指标：results|numbers_per100（η²=0.42）；results|stat_terms_per100（η²=0.33）；abstract|stat_terms_per100（η²=0.21）

## 句式对照的校准参照

每篇已发表论文对其余论文做 phrase_contrast（留一法，默认标准）：被标出中位 4 项，范围 0–26 项。稿件的标记数应与此对照阅读。

## 检查规则在已发表论文上的触发率

| 规则 | 触发篇数 | 比例 | 级别分布 |
|---|---|---|---|
| D3c | 18/18 | 100% | INFO 18 |
| X2 | 18/18 | 100% | INFO 18 |
| R1 | 17/18 | 94% | MUST 2、SHOULD 15 |
| X6 | 16/18 | 89% | INFO 16 |
| X8 | 15/18 | 83% | INFO 15 |
| X1 | 13/18 | 72% | SHOULD 8、INFO 5 |
| X3 | 11/18 | 61% | SHOULD 11 |
| I3 | 9/18 | 50% | INFO 9 |
| M1 | 8/18 | 44% | SHOULD 8 |
| X9 | 8/18 | 44% | INFO 8 |
| D4 | 7/18 | 39% | SHOULD 7 |
| X5 | 7/18 | 39% | SHOULD 7 |
| I2 | 4/18 | 22% | SHOULD 4 |
| M5 | 4/18 | 22% | SHOULD 4 |
| X10 | 4/18 | 22% | SHOULD 4 |
| X7 | 4/18 | 22% | INFO 4 |
| C3 | 3/18 | 17% | SHOULD 3 |
| D2 | 3/18 | 17% | SHOULD 3 |
| D7 | 3/18 | 17% | INFO 3 |
| I1 | 3/18 | 17% | MUST 3 |
| M2 | 3/18 | 17% | SHOULD 3 |
| M4 | 3/18 | 17% | INFO 3 |
| M6 | 3/18 | 17% | SHOULD 3 |
| D1b | 2/18 | 11% | SHOULD 2 |
| M3 | 2/18 | 11% | INFO 2 |
| N1 | 2/18 | 11% | INFO 2 |
| R2 | 2/18 | 11% | INFO 2 |
| S1 | 2/18 | 11% | SHOULD 2 |
| X3b | 2/18 | 11% | SHOULD 2 |
| X4 | 2/18 | 11% | SHOULD 2 |
| A2 | 1/18 | 6% | MUST 1 |
| C1 | 1/18 | 6% | SHOULD 1 |
| C5 | 1/18 | 6% | SHOULD 1 |
| D1 | 1/18 | 6% | SHOULD 1 |
| D3 | 1/18 | 6% | SHOULD 1 |
| D6 | 1/18 | 6% | SHOULD 1 |
| I4 | 1/18 | 6% | SHOULD 1 |
| L1 | 1/18 | 6% | INFO 1 |
| T1 | 1/18 | 6% | INFO 1 |

触发率 ≥50% 的风格规则可降为 INFO 并注明；交付残留、字数限制、设计/因果、趋势话术、建议、新颖性和作者声明规则（A1、G1、G2、H1、N1、N2、P1、S1、W1）不按发表频率降级。常见不等于正确。

隐私：本目录只含统计量、短句式骨架与文献清单；语料全文不在其中。
