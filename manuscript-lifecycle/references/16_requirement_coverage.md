# 16 · 要求覆盖与历史问题回归

本表说明规则为什么存在、由什么核对、哪里仍需判断。它不是“全部已通过”的证明；实际执行结果见本包的测试与审查记录。历史记录中的项目决定不自动成为通用规则。

## 1. 先确认材料覆盖

对每个输入文件登记相对路径、SHA-256、用途、权威性、是否重复、提取方式与阅读程度。使用 `assets/templates/source_coverage.csv`。压缩包递归盘点，防路径穿越；Word 除正文还需提取表格、批注和修订（`mslib.py annotations` 给出批注的锚定文字、回复与解决状态，以及逐条修订），PDF 记录文本提取与视觉查看的区别。

阅读状态必须区分：`inventoried`（仅盘点）、`extracted`（已提取）、`search_only`（全文检索但未逐段理解）、`targeted_review`（列出实际阅读范围）、`full_review`（全篇语义阅读）、`unread`（未读/无法访问）。重复文件继承同哈希版本的状态，不能把解包、关键词扫描或文件数称为通读。长聊天记录须完整检索请求和更正，再读每个命中的上下文；代码/工具输出与用户请求分开识别。

先读现行用户请求、索引、历史决定、作者不满与变更记录，再按风险读原稿、数据、分析和文献。科学文献并非因存入资料包就已核实；注明全文、摘要或书目访问程度。对必要但未读材料列出影响，不能用“材料很多”掩盖未知。用户原稿、个人数据和参考全文不进入可分享 skill。

## 2. 要求 → 规则 → 核对

`E:` 指 `evals/test_evidence.py` 中现有测试名；`F:` 指 `evals/test_trial_regressions.py`；`B:` 指 `evals/test_benchmarks_exemplars.py`（`FindingFirstNegativeControl` 在 `evals/test_behavior_scorer.py`）；`D:` 指 `evals/test_delivery.py`；`T:` 指 `evals/test_language_tools.py`；`G:` 指 `evals/test_domains_agents.py`。`L:` 指 `evals/test_lockin_regressions.py`。`H:` 为必须留实际判断证据的语义检查，不是声称已自动测试。运行状态以本次输出为准。

| 要求/历史问题 | 规则或工具 | 测试/审查证据 |
|---|---|---|
| 判初稿阶段、体裁、设计、贡献与推断性质；不要因方法复杂而错写方法论文 | SKILL §1–2、01；类型卡与故事卡 | H: 实证发现稿/方法比较稿/质性合并结果讨论的路由对照；无提纲不能推断作者无经验 |
| 初稿信息不足、权威版本冲突、旧指令与现请求混淆 | SKILL §1、输入清单、coverage 与 authority | H: 缺伦理/样本/结果不补造；非关键缺口仍推进；旧文件“只检查”不覆盖当前授权 |
| 方法喧宾夺主、各节错位 | 02、section_lint、density_check | H: 方法回答目的/做法/判据；结果描述性翻译与机制解释区分；四处主线一致 |
| 分档不能变成选择性不报 | 03、results_ledger、ledger_check | E: `test_empty_keywords_do_not_skip_disclosure_check`、`test_missing_supplement_is_not_pass`；H: 重要不利结果和计划偏离披露 |
| 引言/方法/讨论按各自需求选全文参照 | 04、bench_profile、move_check | E: `test_empty_benchmark_rejected`、`test_draft_cannot_benchmark_itself`、`test_mixed_language_pool_rejected` |
| 语步编码需要真实上下文，不是提供自己编的摘句 | move_check、04 | E: `test_inline_text_does_not_prove_external_source`、`test_empty_cue_rejected`、`test_real_anchor_still_not_semantic_validation`；H: 标签语义复核 |
| 句长/连接词/符号/术语分布仅作诊断，不追求统一比例或AI检测率 | 04–05、15 来源说明 | H: 合理三项列举、讨论概括句、标准术语和必要限定的负例；偏离有理由可留 |
| 一次修改只处理局部，遗漏同类问题；两极摆动与自造同义词 | 05、07；全稿同类问题扫查、保留清单 | H: 既不删承重内容也不变口语说明书；正确句不因命中模式被改坏 |
| 信息过多与精炼后单薄 | 06，删句测试与扩展必要性 | H: 每主要发现判断其解释增量；不强迫机制/实践/未来研究全套展开 |
| 方法软件声明辖域不清、标题与结果不对应 | 02、章节映射 | H: 全局声明不能误置单个分析小节；短节不为对称补字 |
| 讨论首段不像概括、结论冗长、局限没有影响判断 | 02、06、section_lint | H: 首段回答研究问题；结论不新增推断；局限方向未知不得编方向 |
| 巨大数值池偶然匹配、同值错行、符号与换算错误 | verify_evidence；number_trace仅候选搜索 | E: `test_membership_success_does_not_claim_context_verified`、`test_same_value_wrong_context_rejected`、`test_sign_is_not_automatically_ignored`、`test_arbitrary_unit_conversion_rejected` |
| 源数据/稿件更新后旧数字与判断未失效 | audit_run、verify_evidence、release_check | E: `test_stale_source_hash_rejected`、`test_stale_manuscript_hash_rejected`；H: “所有”“低于”“减少到”等判断同步复算 |
| 承重数字在表格、摘要、图形摘要、Highlights和补充里漏检 | verify_evidence、delivery_check、07/14 | E: `test_tables_are_scanned`；H: 最终可见产物的单位、样本、模型、分母与源一致 |
| DOI真实却不支持当前主张，原文转述或分母层级不符 | ref_check + 引文台账 + verify_evidence | E: `test_online_http_failure_does_not_pass`、`test_explicit_reference_numbers_are_used`、`test_citation_record_cannot_machine_certify_support`；H: 承重引文逐主张读原文 |
| 引文改写、版本/撤稿信息和相反证据遗漏 | 12/15、引用核查台账 | H: 当前正式版本/更正/撤稿状态与引用上下文；不可得标未核，不用题名猜结论 |
| caption/note过长却遗漏必要定义 | 14、delivery_check、显示项台账 | D: `test_forged_note_and_caption_are_not_evidence`、`test_missing_symbol_definition_and_abbreviation_block`；H: 按同图类型/面板复杂度对标，不固定词数上限 |
| 不同复杂度或同篇多图被混作独立图注样本 | display_profile、14、17 | evals/test_display_profile.py：来源绑定、语言/面板分层、同篇汇总、重复与自身参照排除；长度不作质量判定 |
| 未提供测量/程序被说成研究没有做 | SKILL §1、02、16 | H: 缺失材料只支持待核，不支持研究全貌的否定断言；试写时逐条核对 |
| 注释重述方法、解释结论或重复表体数据 | 14；注释功能编码、删句测试 | H: 保留区间类型、单位、分母、符号、缩写和条件；多面板长注按适用范围分开 |
| 表图编号/引用/标题/行序/颜色语义不一致、删图未清引用 | 14、delivery_check、稳定显示项ID | D: `test_title_cannot_be_its_own_body_citation`；H: 编号更换须同步模板/渲染映射、跨图语义与数据行 |
| 长表断词、标题与表体分离、公式是代码、补充排版无人处理 | 14、当前环境的文档工具、delivery_check | D: `test_table_layout_is_warning_unless_explicit_journal_rule`；H: 最终Word/PDF逐页视觉QA，不以结构检查代替 |
| 图件DPI要求误套、元数据不等于实际分辨率 | 14、delivery_check | D: `test_png_no_explicit_requirement_does_not_invent_dpi_failure`、`test_png_unknown_dpi_fails_explicit_requirement`、`test_png_effective_dpi_uses_physical_width` |
| EndNote域被跨界替换、纯净重建覆盖引文版、旧Word未同步 | 07/14、delivery_check、非破坏性编辑 | D: `test_clean_docx_tracks_comments_and_fields`、`test_cli_refuses_to_overwrite_inspected_file`；H: 域基线和结果逐一比对、打开更新域后复核 |
| 蓝字/删除线冒充真修订，纯净稿不等于接受修订后内容 | 07/14、delivery_check | D: `test_marked_docx_keeps_expected_changes`、`test_clean_word_rejects_move_and_format_revisions`、`test_deleted_placeholder_is_resolved_but_inserted_one_is_not`；H: 接受/拒绝视图与起终稿等价；图片/公式/表格也须核验 |
| Word 文字漏读、重读或读错：正文顶层内容控件、文本框、段落合并与拆分、表格行增删、嵌套表格、Symbol 字体符号 | mslib、delivery_check、14 §5 | D: `test_body_level_content_controls_are_read`、`test_textbox_is_read_once_as_its_own_paragraph`、`test_paragraph_mark_revisions_merge_and_split`、`test_table_row_revisions_and_nested_tables`、`test_reject_view_uses_previous_paragraph_style`、`test_symbol_fonts_hyphens_tabs_fields_and_equations`；H: 换一个引擎全部接受/拒绝后逐行对照（evals/README） |
| 批注者把意见写成修订插进正文，“全部接受”后混进稿件；批注只抄所在段落、丢了锚定文字 | mslib annotations（⚑ 标出）、delivery_check（英文文件出现中文即提示） | D: `test_comments_have_exact_anchor_replies_and_resolution`、`test_revisions_merge_fragments_and_flag_remarks_typed_into_the_text`、`test_chinese_left_in_an_english_file_is_flagged`、`test_cli_prints_report_and_will_not_overwrite_json`；H: ⚑ 只是候选，逐条判断是改稿还是说明 |
| 中文 Windows 上输出接到管道或文件时按 GBK 编码而崩溃，读写文件按系统编码出错 | 全部脚本 UTF-8 输出、文本读写写明编码、LF 换行 | D: `test_text_io_declares_encoding`、`test_every_cli_writes_utf8_through_a_gbk_pipe`、`test_init_project_and_release_check_end_to_end_through_gbk_pipe`、`test_line_endings`；整套测试另在 GBK 区域与“默认编码告警视为错误”下各跑一遍 |
| 中文期刊不用标题样式的编号标题、方括号摘要、PDF 折行与表头单字被切错节；领域惯例（研究问题写在文献综述之前）被当作缺陷；同一输入两次报告不同 | mslib 切节、section_lint I1/X1、18 §5 | D: `test_numbered_plain_headings_split_an_education_style_paper`、`test_english_text_keeps_its_previous_parsing`、`test_aims_stated_before_a_literature_review_satisfy_i1`、`test_report_is_identical_across_hash_seeds`、`test_every_shipped_domain_pack_checks_clean`；H: 新领域建包前逐篇看切节 |
| 页码/行号旧、倒置或凭空填写；清单定位错页 | 08/09，最终PDF定位表 | H: 回复与报告清单每个定位真实存在，起止顺序有效；投稿系统重排后刷新 |
| 回复漏子问题、先写承诺再找证据、不同回复互相矛盾 | 08、response_lint、comments_matrix | E: `test_empty_comment_extraction_not_success`、`test_full_quote_tail_must_match`；H: 逐子问题回应及回复↔回复↔正文三向检查 |
| 外部验证总体结果被写成特定亚组已验证 | 08、补分析决策卡 | H: 人群/目标/估计对象/验证方式矩阵；合理说明无法验证而不以相邻任务替代 |
| 审稿意见越出体裁，所有建议照单全收 | 08、意见分类与九问 | H: 文献计量稿无需因不适用建议强加原始实验；有据接受/部分接受/澄清/不接受 |
| 投稿包角色缺件、声明只在md不在Word、匿名属性泄漏 | 09/14、delivery_check | D: `test_missing_expected_package_role_blocks`、`test_anonymous_file_properties_are_checked`、`test_empty_manifest_is_not_pass`、`test_anonymity_reads_people_revision_authors_fields_links_and_variables`、`test_generic_author_labels_are_not_listed` |
| AI声明只写润色但实际还用于代码、标签与草拟 | 09/14、AI使用日志 | H: 按本次期刊政策与真实工作披露；历史暂不添加声明不是永久豁免 |
| 同源数据相关发表、退稿转投、作者贡献/署名/伦理信息缺口 | 09、SKILL §6 | H: related manuscripts/overlap说明、转投要求更新；未知不得填“无” |
| 作者收到内部日志和代号，难判断用哪个文件 | 14、交付读者测试 | H: 首页结论/文件用途/未核项/下一步；正式稿与作者说明分开 |
| 声称改了却文件未变；局部补丁未命中悄悄跳过 | revision_diff、07，逐编辑状态 | H: 唯一命中、幂等、失败不覆盖；实际diff与声称变化核对 |
| 中英/补充/图注旧禁句换措辞回潮 | 07、claims_guard、条件化回归 | H: 同义改写与跨产物回放；合法保留的相似句为负例 |
| 空输入、NA或只有文件存在就被判完成 | audit_run/release_check；gate_check 只看进度 | E: `test_unknown_mode_cannot_complete`、`test_na_cannot_bypass_required_gates`、`test_file_existence_does_not_certify_done`、`test_empty_structured_checks_rejected` |
| 自评全绿、同模型多角色当独立专家、只优化公开案例 | 11/13、隔离评估、缺陷注入、留出任务 | H: 写作与审查分离；冻结标准；报告误报/漏报/能力边界；连续轮次不退步 |
| 结果仍有重大问题却以措辞不再变化为收敛 | 13、rubric、release_check | H: 重大问题优先于综合分；两轮无新增重大问题、核心维度不退步才宣布收敛 |
| 同类文献在这种场合常用什么句式；稿件特有的反复句式 | 04 §4.4、phrase_contrast.py | T: test_flags_repeated_opener_and_lists_common_openers、test_draft_inside_exemplars_is_rejected、test_terms_are_masked_automatically_and_by_option；实测见验证记录 |
| 一次改完同类问题；声称改过的句子确实改了；精简不丢数字/引文/限定；复扫不引入新问题 | 05 §8、language_plan.py scan/check | T: test_unfilled_plan_fails、test_claimed_revision_not_in_file_fails、test_number_lost_without_reason_fails、test_deleted_row_fails、test_reintroduced_residue_fails、test_calibration_selects_only_categories_above_exemplars |
| 借鉴去 AI 味项目的模式：无出处归因、评价尾巴、叠加限定、模板短语、对话残留、零宽字符 | texture_catalog.json、section_lint A1/A2、language_plan | T: test_chat_residue_and_zero_width_are_must、test_placeholder_is_info_not_must；H: 合理用法按 keep 条件保留 |
| 图注表注对标因手工清单负担大而被跳过 | display_extract.py → display_profile.py；14 §2 | T: test_manifest_is_accepted_by_display_profile |
| 中文文献切节失败（私用区字符、分页标记、页眉、无标题样式的多实验容器行） | mslib.parse | T: test_pua_page_marks_running_heads_and_multi_experiment |
| PDF 转写断行后，结果段的统计量行（t(37) = 3.20, p = …）被当成表格，结果正文被低估 | mslib.parse 的正文判断 | T: test_statistics_lines_in_results_prose_are_not_tables；实测见验证记录 |
| 伦理批准号被当作引文 | ref_check.py | T: test_approval_number_is_not_a_citation |
| 回复信标记拼写错误；回复内部分点被当成新意见 | response_lint.py | T: test_misspelled_answer_label_is_recognised、test_numbered_points_inside_a_response_are_not_new_comments |
| 中文期刊 PDF 转写切节：行内“摘  要”、加空格的节名、页眉重复行、参考文献后的英文摘要、多研究论文的分研究讨论 | mslib.parse | 实测 16 篇《心理学报》：摘要不再混入英文，结论由最多 3842 字回到 68–373 字；英文 24 篇各节词数变化来自页眉与表格残留被移除 |
| 中文作者–年份引文：英文译文 + [中文原文] 的文献表、叙述式引用、跨行姓名、日期括号 | ref_check.py | 实测 16 篇：每篇误报由 52–110 条降到中位 3 条，剩余含已发表论文中的真实年份错误 |
| 规则在中文论文中的语言偏差（“结果表明”算解释、150 词结论上限、列表编号算数字、p 值小数位） | section_lint.py、zh 词表 | 实测：已发表论文 MUST 由 6 条降到 2 条 |
| 是否按专业领域区分资料；每个领域需要多少材料；如何扩展到新领域 | 18、domain_pack.py、assets/domains/ | G: test_pack_has_only_numbers_and_short_frames、test_tools_run_from_the_pack、test_rules_common_in_field_are_downgraded、test_tampered_or_stale_pack_is_refused、test_corpus_paper_cannot_benchmark_against_its_own_pack；样本范围和验证限制见 18 §2–3 |
| 多代理：何时用、隔离、汇总裁决、无子代理时降级 | 19、agents/、review_merge.py | G: test_fabricated_major_quote_is_rejected、test_version_mismatch_is_rejected、test_cluster_decide_and_check、test_previous_round_marks_persisting_issue、test_every_role_follows_the_contract、test_same_anchor_merges_across_section_labels；行为效果只在一份合成短稿上与单代理比较过（19 §6） |
| 领域校准把“结果节堆解释”整体降成提示，远超上界的稿件也被放过 | section_lint：数值超出同领域已发表论文上界时不降级 | B: `test_domain_calibration_does_not_excuse_going_beyond_the_field` |
| 不知道“写到什么程度”：只有分布数字，没有可读的范例 | `assets/exemplars/` 15 个中英文坏例与改写；[20](20_moves_and_exemplars.md) 分节语步 | B: `test_every_exemplar_bad_block_triggers_its_rules`、`test_exemplar_good_blocks_are_clean` |
| 标准由模型自行设定，与目标刊和顶刊规则脱节 | [21](21_benchmarks.md) 四级取标准次序；`assets/journal_profiles/` 每条规则带来源与核实状态 | B: `test_profiles_declare_sources_and_status`、`test_unverified_rule_cannot_fail`、`test_profile_missing_source_is_refused` |
| “图注要短”被当成规则；表注长度用一个数字管所有期刊 | `assets/benchmarks/display_baseline.json` 实测分布；14 §7 | B: `test_baseline_reports_position` |
| 三线表版式、小数位、p 值与表注顺序无人检查 | `table_style.py` build 与 check；14 §6 | B: `TableStyle` 四项 |
| 图注里描述读图编码的 thicker lines indicate … 被当作下结论 | journal_check 排除读图编码 | B: `test_visual_encoding_in_legend_is_not_a_conclusion` |
| 投稿信里 `[VERIFY: 作者确认后填写…]` 被判成代作者写声明 | section_lint N2 排除占位符内的文字 | B: `test_verify_placeholder_is_not_a_ghostwritten_declaration` |
| 结果段以“见表、如图、As shown in”起句识别不全 | section_lint R3 的补充式 | B: `test_display_led_results_paragraphs_are_caught` |
| 摘要里的因果措辞、趋势话术和越界建议没被扫到 | section_lint 的断言规则（S1、S2、G1、P1、N1）纳入摘要 | B: `test_assertion_rules_also_scan_the_abstract` |
| 把不显著的比较写成“相同 / identical / 完全一致”，只有任务专用评分器抓得到（留出模拟植入错误时发现） | section_lint S2：同句有不显著检验为 SHOULD，否则 INFO；等效性检验、程序描述、紧邻否定除外 | B: `NullAsEquivalence` 四项；范例 01、04、14；已发表论文触发率见验证资料 |
| 分布对标标出冒号、rather than 偏多，修订计划却列不出来；只改标点的修订被判未落实 | SKILL §4：用 `--phrase` 把符号补进计划；language_plan check 按原文再比一次 | B: `test_colon_to_period_counts_as_landed_and_phrase_lists_colons`；留出模拟第 3 轮 |
| 生成三线表时，含逗号的字段没加引号导致列错位 | table_style 校验列数并提示加引号 | B: `test_csv_with_unquoted_comma_is_refused` |
| 结果节用“稳定”“可接受”下判断，方法节却没写判据 | 20 方法语步 CRI；留出模拟第 5 轮通读发现 | H: 结果中的每个判断词回查方法节判据 |
| 论文类型判断太薄；作者不熟悉类型时无从解释 | 01 五步判定、三个例子、给作者的白话问法 | H: 试写时逐条对照 |
| 不进稿的事用否定句或侧面带出照样进了稿 | 03 三种写法与预判表；`assets/exemplars/15`；台账关键词须含否定式 | B: 留出模拟植入“not verified by a second rater”被 ledger_check 拦下；H: 在稿件中逐条搜索肯定、否定与侧面写法 |
| 留出任务：材料偏重方法，要求以发现为主线 | `evals/behavior_cases/findingfirst_*`；`score_behavior.py findingfirst` | B: `FindingFirstNegativeControl`；模拟记录见验证资料 |
| 实地试写（模拟精分概率翻转学习）：两份稿件都把写作过程写进了论文（局限里写“句式分布对标未完成”，标识段写起草工具与“见审计列表”，参考文献后接“作者待办”），MUST 仍为 0 | section_lint X11（MUST，不降级）；SKILL §3 局限一行、§8 | B: `WorkflowLeak` 两项；`test_check_all`；已发表论文 102 篇触发 0 篇（验证资料） |
| 实地试写：结论里写本地路径（`00_inputs/sim_data/`） | section_lint X12 | B: `test_local_paths_in_the_conclusion_are_flagged_and_clean_text_is_not` |
| 实地试写：台账自创列名，ledger_check 跑不了，门控仍记“通过（人工）” | check_all 把列名不对报为“没能运行”；SKILL §2、§5：门控“通过”必须指向工具输出 | B: `test_field_trial_failures_block_with_plain_reasons` |
| 实地试写：稿件写了结果文件里没有的数字（Welch 自由度 t(94)） | check_all 调用 number_trace 并阻断；`--allow` 只登记带理由的非结果数字 | B: `test_allow_file_needs_a_reason_and_thresholds_match`；实地稿复查记录 |
| p < .001 这类阈值写法被 number_trace 当成找不到的数字，检查一跑就刷屏 | number_trace 阈值匹配 | B: 同上 |
| 实地试写：初稿项目里 9 个模板（投稿信、回复信、意见矩阵等）从建好到交付一字未动 | init_project 按模式建模板，作者说明放项目根目录 | B: `test_new_project_has_no_fabricated_analysis_or_review` |
| 实地试写：没有演示与模拟稿的规则，执行者自行发明生成脚本与标识；模拟研究与“用模拟数据练手”混为一谈；植入的组间差异被当成发现 | SKILL §1.2；01 §模拟稿（ADEMP、参数恢复、循环论证）；check_all `--simulation` | B: `test_clean_simulated_draft_can_go_to_the_author`；H: 讨论里是否说明差异来自生成设定 |
| 实地试写：作者看不到卡在哪、什么已可交；结论只沉淀在门控表与审计目录 | check_all 的 STATUS.md；28 执行动作第 5 步每轮三行状态；§8 交付与工作区分开 | H: 每轮回复首三行是否给出可用文件、阻断、下一步 |
| 实地试写：主线由数字决定这一步只靠执行者自觉 | 故事卡模板的“数字定方向”表；SKILL §0 第 2 步 | H: 方向表与摘要、讨论首段逐条对照 |
| 弱模型把“待作者核实”“写作流程测试”“[VERIFY: 资助、利益冲突]”写进摘要或结论（试跑 5/21 个 run） | SKILL §0 第 3 步；§1.2 合成材料照研究写；section_lint X13、X14，X11 | F: `StatusTalk` 各项；试跑稿 R02–R05 重查均被拦 |
| 返修只改点名的问题，截断均值仍叫“平均掌握用时”（试跑 4/6 份返修稿） | 07 §9、08 §8 全稿清扫；check_all `--qualifiers` | F: `test_qualifiers_catch_unqualified_capped_mean` |
| 正确稿件被判“还不能交”：目的句写法、原文百分数、95% CI | section_lint 目的句补充式；number_trace 原样百分数与 CI 水平 | F: `test_clean_reference_is_deliverable`、`NumberTracePercents` |
| `--design cluster_randomized` 让检查半途没能运行 | mslib.normalize_design；check_all 与 section_lint 开头校验 | F: `test_design_aliases_and_unknown_design` |
| metric_audit 把正确四舍五入的值判成不符 | 默认容差取末位半个单位 | F: `test_rounded_report_matches_by_default` |
| 合成测试材料被写成“演示稿”，删掉材料写明的知情同意 | §1.2 三种情况；check_all `--simulation` 只查一句标识 | F: `test_simulation_flag_does_not_block_consent_from_materials` |
| 编造的伦理批准号、注册号、正文引文 | check_all 对照材料查编号；有引文无参考文献表即阻断 | F: `test_fabricated_ids_and_citations_are_blocked` |
| 引文核对与对标的说法没有边界：搜索当核实、记忆当来源、摘要当分布 | references/23 四层阶梯、平台对照、工具库存、F01–F16；lit_evidence resolve/check；作者说明必填字段 | F: `LitEvidence` 各项（含 Mensh 2017 更正样本） |
| 用户只说一句话时没有任务卡，默认交付不清 | SKILL §0 第 0 步、§1 表“默认交付”栏；assets/templates/task_brief.md | H: 短话试跑（evals/trial_kit 的 prompt_short） |
| 组内使用量梯度写成因果（“用得越多提高越多”）；内部处理过程（重跑、Excel 清洗）进稿；带区间的不显著结果写成“等同” | section_lint P2、X15（SHOULD），S2 程序句豁免收窄 | F: `TrapRules` |
| 中文“提示”作干预名时被当成解释句；否定因果的句子被报为因果；漏传分析笔记时伦理声明被列为必须处理；重跑撞上已有目录；图注编造线型与标记；表注图注下结论或写软件细节；局限里写材料缺口 | section_lint R1（动词用法、不少于 3 句）、P2（否定豁免）、V1、V2、X11；check_all SIM3 与自动另开目录 | F: `ToolFrictionRegressions` |
| 规则在实际使用中的命中与误报 | check_all 的 summary.json；check_stats.py | F: `ToolFrictionRegressions.test_check_stats_counts_hits_and_false_positives` |
| 重复的总结句、意义句 | section_lint X10 | 当前领域包触发率见各包 rule_rates.json |
| 模拟测试：执行者照 SKILL.md 完成初稿、返修、留出任务后自动初筛 | evals/score_behavior.py、behavior_cases/ | 负对照（案例旧稿与合作者拟回复）未通过 12 项；test_behavior_scorer.py |
| 中文目的句（“本研究在……中开展……，比较……”）、单独以“分析”为标题的统计小节、回复信里引用已删除的旧文字 | zh 词表 aim、section_lint UMB、response_lint | T: test_chinese_aim_and_plain_analysis_heading、test_quoting_deleted_text_is_not_an_error |
| 词表里每条规则都必须真的编译；写成字符串不能被静默跳过 | mslib.lex_rx 接受字符串；词表为列表 | T: test_lexicon_rules_are_all_compiled |
| 中文回复信的套话致谢、恭维、空泛“已认真修改”、防御措辞 | response_lint 中文模式 | 负对照触发；5 封真实回复信无误报 |
| 单独交付的 Highlights、投稿信、图注表注无法检查（整篇规则找不到论文节就拒绝） | section_lint `--fragment` | T: test_without_flag_the_fragment_is_refused、test_fragment_checks_highlight_limits、test_main_word_limit_is_not_applied_to_a_fragment |
| 方括号里的作者待办（[Authors to add: …]、[full reference to be added]）不算占位符，没写完的投稿信被当成可上传 | mslib.PLACEHOLDER；delivery_check 用同一条规则 | T: test_bracketed_author_todos_are_placeholders、test_plain_brackets_are_not_placeholders、test_delivery_check_uses_the_same_rule |
| 短的中文片段（Highlights、投稿信）被判成英文，整套中文规则不运行 | mslib.detect_lang | T: test_short_chinese_fragments_are_detected_as_chinese |
| 把未达显著的结果说成“趋势”“接近显著”“虽然不显著但值得关注” | section_lint S1、spin 词表 | T: test_spin_is_flagged_in_both_languages；当前领域包触发率见各包 rule_rates.json |
| 非实验设计写因果动词；正文设计词与声明的设计矛盾 | section_lint `--design` 的 G1、G2 | T: test_causal_wording_needs_a_declared_design、test_negated_or_contrasted_causal_sentences_are_not_flagged、test_declared_design_contradiction_is_a_must、test_random_intercept_is_not_a_design_contradiction |
| 没有检验过干预却写“高校应当限制……/clinicians should …” | section_lint P1 | T: test_recommendations_beyond_the_design_are_flagged；当前领域包触发率见各包 rule_rates.json |
| 引言以外的新颖性宣称（首次、填补空白、groundbreaking） | section_lint N1、overclaim 词表 | T: test_overclaims_outside_the_introduction_are_listed；当前领域包触发率见各包 rule_rates.json |
| 投稿信替作者写下利益冲突、数据可得性、全体作者同意等声明 | section_lint `--fragment` 的 N2 | T: test_declarations_are_only_checked_in_fragment_mode |
| 中文的“见 3.2 节和表 3”不算交叉引用，讨论不自足查不出 | zh 词表 section_xref | T: test_chinese_numbered_section_and_table_crossrefs_reach_the_discussion_rule |
| 模拟：投稿材料（表注、图注、Highlights、投稿信）与中文讨论首段、结论 | evals/score_behavior.py package/polish、behavior_cases/ | 负对照（合作者初稿、学生初稿）均触发多项未通过；test_behavior_scorer.py；局部否定、样本归属及英文等义写法见 test_independent_regressions.py |

| 重复 YAML 副本、摘要/候选误入、相对路径清单漏配、额外全文混入 | domain_pack、mslib、四个基线消费者 | T: test_domain_corpus_integrity.py；包外语料审计记录 |
| 带括号参考文献、摘要正文误当方法、主题标题、图内英文标签与合并方法/结果小节 | mslib.parse | T: test_zh_sections.py；33 篇入选中文论文切节复核 |
| 跨语言套包、用高发表率降低设计矛盾的严重度 | section_lint | T: test_lint_refuses_a_different_language_pack、test_prevalence_cannot_downgrade_design_contradictions |
| 结果小标题被技能规则诱导成结论句；风格应由用户、目标刊与近邻决定 | results_function HS0–HS2；bench_profile 第六节；expectations | L: test_declared_object_headings_block_finding_headings、test_finding_headings_pass_when_declared、test_undeclared_heading_style_is_reported_not_judged、test_heading_styles_in_both_languages、test_bench_profile_reports_results_heading_styles |
| 结果节的作者叙述决策、否定式机制判断、设计限制；短的统计限定要保留 | results_function RF1、RF0 | L: test_misplaced_functions_block_even_as_negations、test_short_statistical_qualifiers_are_kept、test_strict_mode_blocks_a_single_sentence、test_chinese_results_sentences |
| 引文全部核实却覆盖不足；缺口没检索；“投稿包备齐”与缺口并存；篇数只作信号 | coverage_check CV0–CV7；24 | L: test_verified_citations_do_not_prove_coverage、test_gap_without_search_log_blocks、test_reference_count_is_a_signal_not_a_threshold、test_submission_claim_with_open_gaps_blocks |
| 表图里的内部 ID（含无下划线的）、只修一张表、p = 0、合理下划线不误伤、未登记 ID 不原样输出、内部标签一次列全 | display_terms template/scan/apply；25 | L: test_codes_in_tables_block、test_registered_ids_without_underscore_block、test_fixing_one_table_is_not_enough、test_legitimate_underscores_are_spared、test_apply_refuses_unmapped_and_keeps_source、test_zero_p_value_blocks、test_template_harvests_ids_from_analysis_tables |
| 空审、模板化裁决、审稿看不到表 | review_merge、review_pack；26 | L: test_empty_review_needs_coverage、test_boilerplate_adjudication_is_rejected、test_review_pack_includes_tables |
| 用户明确要求被其他检查的通过抵消；多维通过合成一个“可交付”；对标说法不绑定终稿 | check_all --expectations、--benchmark-decisions 与分维度状态；release_check 新增必需项；init_project 新模板 | L: test_registered_expectations_cannot_be_offset、test_status_lists_dimensions、test_submission_requires_coverage_display_and_expectations、test_benchmark_decisions_bind_to_final_draft、test_new_projects_get_the_new_templates |

## 3. 现有工具的能力边界

每条能力都要同时记住它证明不了什么。

- 执行回执只证明命令真的按给定输入跑过，不证明科学正确；变异测试与语义审查仍需实跑。
- 图表说明的用途与面板数是启发式猜测，须人工确认；注释质量与版面仍需视觉复查。
- 模式命中不等于问题；保留条件与对标校准决定是否改。
- 引文的支持关系不能由元数据或状态字段自动认证。
- 没有通用的安全自动改写承诺；涉及引文域必须专用处理并逐处验证。
- Word 打开、域更新与视觉验收不可伪称；没有渲染工具就记未验看。
- 期刊规则须实时取证；备齐材料不等于已投稿，实际提交另需用户授权。
- 交付件的白话、可操作性与首页信息需要语义审读，脚本不判断。

## 4. 不应迁移的历史规则

- 某个项目的“不报告预注册、问卷版本、身份联结、异常解”清单不是通用规则。必要披露先于精简或减少追问；保留可审计理由。
- 某轮暂不把AI声明写入Word，不代表当前期刊无需声明。
- 某基金申请的禁预印本、禁比较表或不设局限节，不直接用于论文。
- 某期刊早先的字数、摘要标签、DPI或缩写偏好，不写死为所有论文硬阈值。
- “作者要求建议、不改稿”是该历史任务的范围，不限制已授权的当前修改；反之亦然。

## 5. 维护本表

模板本身也会诱导错误执行，因此：新建项目的结果台账留空，不预填其他研究的 reserve/omit；大纲、故事卡与类型模板不写死篇数、术语禁令或“补充只能引用一次”这类要求。新建项目的行为见 `evals/test_project_templates.py`：不继承虚构分析与评论；空台账不通过；排除须有理由；关键词冲突先核披露义务；必要披露不可定为 omit。

输出路径检查与独占创建由 output_safety 与 mslib.wfile 承担；`evals/test_output_safety.py` 覆盖各验证器的输入/源/报告路径碰撞、回执日志和正例，确保错误分支不会覆盖已被拒绝的输入。

新问题先记录来源和适用条件，再增加规则、正例、反例和复验依据。新增脚本必须与入口、模板、命令和本表同步。自动测试名称不存在或只写了计划时标 `pending`；不把“有规则”标成“行为已验证”。最终交付须附实际测试与模拟记录，以及剩余限制。

## 第二十一轮的结构性修正与落点

| 问题 | 落点 | 检查 |
|---|---|---|
| 改了无关的词表键，已发出的英文领域包全部失效 | `domain_pack.texture_fingerprint`；18 §5 | `evals/test_texture_fingerprint.py` |
| 同一编号多种含义（G2、G11、H1、S1） | 17 编号表；RJ、AU 系列；`init_project --legacy` | `evals/test_code_namespaces.py` |
| 整稿修改落在局部与完整流水线之间，两处规则方向相反 | SKILL §0 单文档修订；28 §1 | `evals/test_scope_routes.py`；行为用例 `evals/workflow_scope_cases.md` 为 pending |

## 第二轮作者要求（2026-10-29）与落点

| 作者要求（摘要） | 落点 | 检查 |
|---|---|---|
| 摘要末句交代含义或贡献，不以“限制推广、未经验证”收尾 | 27 §2；20；范式外与体裁审稿 | genre_gate GG1 |
| 摘要报主发现，不报一串未检出与校正细节 | 27 §2 | GG2、GG3 |
| 引言首段从读者能感到的现象或利害立题，不只罗列文献 | 27 §2；20 CTX | GG4、GG4b；benchmark_decisions intro_opening |
| 引言末段写问题与预测，分析清单属于方法 | 27 §2；20 AIM | GG5、GG5b |
| 方法写到概念上可复现，流水进补充 | 27 §5；03；20 SNS | GG6 |
| 主文表型对照领域惯例（样本总表不进主文） | 27 §2、§4 | GG7；PL7 |
| 整篇要有解释深度与贡献感，讨论首段回答“说明了什么” | 27 §1；体裁备忘 | GG8–GG10；MM2–MM5；reviewer_genre |
| 对标要对节职能，不只是语言统计；可以超越近邻 | 27 §2–§3 | BD4、BD5；station_check S2、S3 |
| 语言不能过于抽象；正文不塞不需要的内容；补充不堆不必要的分析；放什么要对照同类文献想过 | 27 §4–§5；05 §9 | GG12、GG13；placement_decisions PL0–PL7 |
| 让 AI 真的思考而不是机械执行，并有监督 | 体裁备忘、拒收预演、质检员 | MM、RD 规则；station_inspector；ST1 |
| 流程不能乱、不能跳步；要求模糊时走完全程，缺材料才中途索取 | 28 | station_check ST1–ST5 |
| 参考要够数、分层、类型对 | 27 §3；21 | station_check S2 |
