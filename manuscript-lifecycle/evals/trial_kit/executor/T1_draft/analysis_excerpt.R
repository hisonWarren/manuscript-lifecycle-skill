# ---- 练习日志指标（按组合计后相除）----
# hint_success_rate：提示后下一次作答正确的次数 / 全部练习题数
grp$hint_success_rate <- grp$success_after_hint / grp$practice_items
# hints_per_item：提示显示次数 / 全部练习题数
grp$hints_per_item <- grp$hints_shown / grp$practice_items

# ---- 纠错率（预定次要结局；每名学生一个比例，再进模型）----
stu$error_correction <- stu$errors_corrected / stu$errors

# ---- 掌握天数 ----
# 40 天内未掌握者赋值为 40（只用于 mean_days_to_mastery 这一描述量）
stu$days_to_mastery <- ifelse(stu$mastered_40d == 1, stu$mastery_day, 40)
# Cox 模型中未掌握者在第 40 天删失
fit_cox <- coxme(Surv(days_to_mastery, mastered_40d) ~ arm + pretest + size + (1 | school), data = stu)
