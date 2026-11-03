# assets/domains · 领域包

每个子目录是一个领域包：选定语言、期刊及体裁范围内已发表论文的统计特征，不含全文或句子。用途、证据、需要多少篇和构建方法见 references/18_domains.md。

| 包 | 语言 | 篇数 | 内容 |
|---|---|---|---|
| psychology_zh | 中文 | 22 | 《心理学报》2023–2026 定量实证（实验 11、调查 9、量表编制 2） |
| education_zh | 中文 | 11 | 《开放教育研究》2017–2025 原始数据实证（调查 5、实验 4、二次数据分析 1、预测模型 1） |
| clinical_psych_en | 英文 | 24 | 临床心理与精神医学期刊中抑郁与主观认知相关的实证论文 |
| social_perception_en | 英文 | 18 | 社会知觉与生物运动任务（行为 13、神经影像 4、计算模型 1） |
| education_psych_en | 英文 | 11 | 学业表现相关观察性研究（调查 10、二次数据分析 1；单刊） |

使用：`bench_profile.py --baseline assets/domains/psychology_zh`、`phrase_contrast.py --baseline …`、`language_plan.py scan --baseline …`、`section_lint.py --domain …`。
构建与检查：`python scripts/domain_pack.py build …`、`python scripts/domain_pack.py check assets/domains/<包>`、`python scripts/domain_pack.py list`。
语料全文只留在本机；本目录不包含全文。每节实际篇数见 profile.json，教育包小样本/缺节提示应保留，不能把单刊样本外推为整个学科。词表或模式目录更新后需要重建，否则工具会因指纹不符而拒绝使用。
