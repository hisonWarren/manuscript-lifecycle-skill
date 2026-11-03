# 11 · Highlights
<!-- test: tool=lint section=fragment limits={"highlights_max_n":4,"highlights_max_chars":85} bad=H1 good_no=H1 -->

任务：每条一个承重发现，加上必要的限定；读者扫一眼就知道这篇论文做出了什么。

## 坏例

```bad
Highlights

- We applied a state-of-the-art regularized partial correlation network analysis framework combined with permutation-based network comparison testing to adolescent depression data
- Sleep is the core driver of adolescent depression and should be the primary intervention target in schools
- Boarding students in the low-baseline subgroup benefit most
- Networks were identical across groups
- The study fills an important gap in the literature
```

## 为什么坏

1. **第一条 177 字符**，写的是方法清单，不是发现。Cell Press 的要求是至多 4 条，每条不超过 85 字符（含空格）。
2. **五条，超了条数。**
3. **core driver、primary intervention target 越过了证据。**
4. **事后亚组被写成了发现。**
5. **identical 把不显著写成了相同。**
6. **fills an important gap 是新颖性宣称，不是发现。**

## 改写

```good
Highlights

- Depressive symptoms were more tightly connected in boarding than day pupils
- The pattern of connections was similar in the two groups
- Sleep problems were the most connected symptom in both groups
- Cross-sectional data: connection strength does not show causal order
```

四条，最长 75 字符。每条一个发现，第四条把必须带上的边界写了进去。

## 省字符的时候不要做的事

把 “Depressive symptoms were more tightly connected in boarding pupils (cross-sectional)” 压成 “Boarding intensifies depressive symptoms”，字符省下来了，主张也被改掉了。**删限定等于改结论。** 要省字符，就删修饰词和冗余的名词化，不删限定、样本和方向。

## 这份范例不校准什么

- 条数与字符上限按目标刊：Cell Press 为 3–4 条，Elsevier 其他刊通常 3–5 条，很多刊根本不要 Highlights。
- 能否写方法贡献：方法学论文的 Highlights 当然可以写方法。
