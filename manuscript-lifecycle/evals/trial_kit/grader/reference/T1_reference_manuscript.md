# Adaptive hints helped pupils correct errors but did not detectably raise algebra scores: a cluster-randomized trial

## Abstract

Online practice platforms increasingly give hints that adapt to each wrong answer, but it is unclear whether such hints improve what students learn or only how they practise. In a cluster-randomized trial, 12 middle schools were assigned to adaptive hints or to standard answer feedback for 8 weeks of algebra practice; 1,240 grade-7 students were randomized and 1,118 completed the post-test. The adjusted difference in post-test algebra scores was 1.8 points on a 0–100 scale (95% CI −0.6 to 4.2), so a benefit for the primary outcome was not shown. Students with adaptive hints corrected more of their errors on the next attempt (0.46 vs 0.31; difference 0.15, 95% CI 0.11 to 0.19), and more of them reached mastery within 40 days (62.0% vs 55.1%; hazard ratio 1.21, 95% CI 1.03 to 1.42). They also reported slightly more frustration (difference 0.21 on a 1–5 scale, 95% CI 0.06 to 0.36). Adaptive hints changed how students practised and how many reached mastery, but within 8 weeks this did not translate into a detectable gain on the end-of-study test.

## Introduction

Online practice platforms give feedback after every attempt, and hints matched to the error a student has made are widely expected to help students repair misconceptions [ref]. Much of the supporting evidence comes from short laboratory tasks and from platform logs, where better performance during practice is easy to observe [ref].

Better practice does not guarantee better learning. A hint can help a student answer the next item without building knowledge that holds on an unaided test, and frequent hints may make practice feel harder [ref]. Classroom trials that measure both practice behaviour and end-of-study achievement are needed to tell these possibilities apart.

This trial compared adaptive hints with standard answer feedback in 12 middle schools. The primary question, specified before unblinding, was whether adaptive hints raised post-test algebra scores. Secondary questions concerned error correction during practice, mastery within the practice period and students' frustration.

## Methods

### Design and participants

Twelve middle schools in one city were randomized 1:1 to adaptive hints or to standard feedback, stratified by school size, with a computer-generated sequence prepared by a statistician who was not involved in recruitment. All grade-7 students in participating classes were eligible. In total, 1,240 students were randomized with their schools (adaptive hints, 618; standard feedback, 622), and 1,118 completed the post-test (552 and 566). Parents gave written consent and students gave verbal assent. The study was approved by [VERIFY: ethics committee and approval number]. The analysis plan was finalized before outcome data were unblinded.

### Conditions

Both conditions used the same platform and item bank for 8 weeks (56 days). With adaptive hints, the platform responded to an incorrect answer with a hint matched to the type of error, in up to three levels, before the student tried again. With standard feedback, students saw whether the answer was correct and could open the full worked solution. Teachers and students knew which condition they were in.

### Outcomes

The primary outcome was the post-test algebra score (0–100), a parallel form of the pretest scored automatically by the platform. Prespecified secondary outcomes were the error-correction rate, defined for each student as the proportion of incorrect first attempts answered correctly on the next attempt; mastery, defined as at least 80% on the unit quiz, recorded as whether and when it was reached within 40 days; and frustration at the end of the study, measured with a four-item self-report scale (1–5). The platform also logged how often hints or feedback were displayed and how often the next attempt after a display was correct. In one adaptive-hint school, a server failure lost the practice logs for 3 of the 56 days, so practice-log measures for that school cover the remaining 53 days.

### Statistical analysis

Post-test scores were analysed with a linear mixed model with random intercepts for schools and classes, adjusting for pretest score and school size, in students who completed the post-test. A sensitivity analysis included all 1,240 randomized students, with missing post-test scores handled by multiple imputation (20 imputations). Error correction and frustration were analysed with the same model structure. Time to mastery was analysed with a mixed-effects Cox model with a school frailty term; students who had not reached mastery by day 40 were censored at day 40. Three analyses were added after unblinding and are reported as exploratory: the effect in the lowest pretest tercile, with a test of the tercile-by-condition interaction; a per-protocol comparison restricted to students with at least 20 practice sessions; and, within the adaptive-hint condition, a comparison of post-test gains across tertiles of hint use. Hint use was not randomized, so the last comparison is observational. Analyses used R 4.4.1 with lme4 1.1-35, mice 3.16 and coxme 2.2-18.

## Results

### Participants

Of the 1,240 randomized students, 122 (9.8%) did not complete the post-test: 66 (10.7%) with adaptive hints and 56 (9.0%) with standard feedback. Pretest scores were similar in the two conditions (52.1 and 51.6).

### Post-test algebra scores

Post-test scores did not differ detectably between conditions (adjusted difference 1.8 points, 95% CI −0.6 to 4.2, P = 0.14; Table 1). The intraclass correlation for schools was 0.06. Multiple imputation including all randomized students gave a similar estimate (1.5, 95% CI −1.0 to 4.0).

### Practice, mastery and frustration

Students with adaptive hints corrected more of their errors on the next attempt than students with standard feedback (0.46 vs 0.31; adjusted difference 0.15, 95% CI 0.11 to 0.19). They also received about twice as many hints per practice item (0.166 vs 0.084), and the next attempt was correct after 0.42 of hint displays with adaptive hints and after 0.47 of feedback displays with standard feedback. More students reached mastery within 40 days with adaptive hints (62.0% vs 55.1%; hazard ratio 1.21, 95% CI 1.03 to 1.42), and the median time to mastery was 22 versus 28 days. Frustration was slightly higher with adaptive hints (2.91 vs 2.68; adjusted difference 0.21, 95% CI 0.06 to 0.36).

### Exploratory analyses

In the lowest pretest tercile (adaptive hints, n = 184; standard feedback, n = 189), the difference in post-test scores was 4.6 points (95% CI 0.4 to 8.8), and the tercile-by-condition interaction was not statistically significant (P = 0.21). Among students with at least 20 practice sessions, the difference was 3.1 points (95% CI 0.4 to 5.8). Within the adaptive-hint condition, students in the highest tertile of hint use gained 6.2 points more than those in the lowest (95% CI 3.1 to 9.3).

**Table 1.** Primary and secondary outcomes by condition

| Outcome | Adaptive hints (n = 552) | Standard feedback (n = 566) | Difference (95% CI) |
|---|---|---|---|
| Post-test score, mean (SD) | 63.4 (15.2) | 61.9 (15.8) | 1.8 (−0.6 to 4.2) |
| Error-correction rate, mean | 0.46 | 0.31 | 0.15 (0.11 to 0.19) |
| Mastered within 40 days, n (%) | 342 (62.0) | 312 (55.1) | HR 1.21 (1.03 to 1.42) |
| Frustration (1–5), mean (SD) | 2.91 (0.78) | 2.68 (0.80) | 0.21 (0.06 to 0.36) |

*Note.* Differences are adaptive hints minus standard feedback, adjusted for pretest score and school size, with random intercepts for schools and classes. HR = hazard ratio from a mixed-effects Cox model with a school frailty term; students without mastery by day 40 were censored.

**Figure 1.** Cumulative proportion of students reaching mastery within 40 days, by condition. Curves are Kaplan–Meier estimates; students who had not reached mastery were censored at day 40. Adaptive hints, n = 552; standard feedback, n = 566.

## Discussion

Adaptive hints changed how students practised but not, detectably, what they could do on the end-of-study test. Students corrected more of their errors and more of them reached mastery during the practice period, yet post-test algebra scores were similar in the two conditions, and students found practice slightly more frustrating.

Several explanations fit the gap between practice and test. A hint can help a student complete the next item without building knowledge that holds when no hint is available [ref]. The post-test may also have been too early or too coarse to detect a small gain: the confidence interval is compatible both with no difference and with gains of about four points. A delayed test or a trial with more schools could separate these accounts.

The practice logs need careful reading. Students with adaptive hints had more correct next attempts per practice item mainly because they saw about twice as many hints; per display, the next attempt was correct slightly less often than after standard feedback. Counts of successes per item therefore reflect how often hints were shown as much as how useful each hint was.

The exploratory results are easy to over-read. The larger difference among low-achieving students was not supported by a significant interaction, and students who used more hints may differ in motivation or engagement from those who used fewer. A trial that prespecifies the subgroup or randomizes the intensity of hints would be needed to test either idea.

The small increase in frustration is a cost to track. These data cannot show whether it comes from receiving more hints or from the error-focused design of the hints.

### Limitations

With 12 schools, precision for the primary outcome was limited, and the confidence interval is wide. Teachers and students knew their condition; post-tests were scored automatically, but frustration was self-reported and may have been influenced by knowing the condition. Practice-log measures depend on how the platform defined a hint display, and one school lost three days of logs. The trial lasted 8 weeks in one city, so longer-term effects and other settings remain untested.

## Conclusion

In this 8-week trial, adaptive hints improved error correction and mastery during practice but did not detectably raise post-test algebra scores, and they slightly increased frustration. Whether gains during practice carry over to achievement over a longer period remains open.
