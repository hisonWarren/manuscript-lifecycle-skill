# 13 · 质量与执行证据契约

## 三类证据不能互相冒充

1. 机械事实：文件存在、哈希、数字单元格/单位、引用摘录、命令退出状态。
2. 语义判断：主张是否有支持、信息是否必要、例外是否合理、论证是否成立。必须有位置、上下文、判断理由和审查者类型。
3. 作者事实与授权：伦理/作者贡献/同意/真实投稿等，只有真实来源与授权，模型不得代签。

脚本 MUST 是候选裁决优先级；验证器 failed/not_verified 是证据链缺口。语言偏离允许有理由保留；捏造、错误承重结果、缺必要披露、文件损坏和未落实承诺不能靠豁免变绿。

## 检查前定义标准

先写阶段、适用类型、需要交付什么、必须核什么、每项证据在哪里。正文语义检查与图表注释、参考文献、元数据、补充及回复分别覆盖。部分检查尚未完成时可以交待核草稿，不能称“投稿就绪”。

运行 audit_run.py：输入必须包括待查文件、所有来源/词表/限额和实现脚本（通常整个 scripts 目录）。输入不可被检查过程修改；报告使用新文件名，避免旧文件被冒充新运行输出。回执包含命令、时间、实际退出码、输入/输出 SHA256 和 stdout/stderr 日志。返回 0 仍不意味科学质量通过。

输出保护先于执行：报告、回执和日志不可指向来源、输入目录或彼此冲突，已有文件不可覆盖。新验证器遇路径或输入错误退出2且只向标准输出说明，不把错误报告写进被拒绝的路径；旧lint若报告已存在会拒绝写入并可能显示FileExistsError，应换新报告名重跑，不把该执行错误当内容检查结果。此保护不把任意子进程变成安全沙箱。

## release.json（schema_version 1）

所有路径相对清单所在目录；回执内部由工具记录绝对路径。移动证据包后应重新运行，不能伪造旧路径的有效性。

```json
{
  "schema_version": 1,
  "stage": "revision",
  "artifacts": [{"id":"draft","path":"manuscript.md","sha256":"实际SHA256"}],
  "targets": ["draft"],
  "checks": [{
    "id":"section_logic","status":"pass","bindings":["draft"],
    "reviews":[{"path":"review.md","sha256":"实际SHA256","locator":"章节职能",
      "quote":"逐字存在的审查结论","reviewer":"审查者标识","kind":"model"}],
    "runs":[]
  }],
  "findings":[]
}
```

这是字段示意，不是可通过的现成清单；所有占位与必需 check 要实际补齐。stage 仅 draft/revision/submission/response/review/skill_release。artifacts 包含当前稿、来源、限额、评审及交付件；targets 是本次交付的内容文件。每项 check 都绑定所有 targets 及相关证据，报告和回执也带实际哈希。

基础检查：source_coverage、type_story、reporting、numbers、citations、section_logic、language、regression。
- draft 另要 benchmark。
- revision 另要 change_evidence。
- submission 另要 benchmark、display、render、package，以及 lit_coverage（覆盖表与 coverage_check）、display_semantics（display_terms 与逐张看表图）、expectations（用户明确要求逐条核对）。
- response 另要 response、change_evidence、display、render、package、display_semantics、expectations。
- review 要 source_coverage、numbers、citations、section_logic、reporting。
- skill_release 要 source_coverage、instruction_consistency、scripts、behavior、regression、package。

`runs` 每项为 {path,sha256} 指向 audit_run 回执；检查器给 exit 1 的候选必须在同项 reviews 逐条裁决并在 runs 项写 adjudication。输入/执行错误（2/124/125）不允许裁决放行。scripts、regression 必须有运行回执；其他项需有实际语义审查，不能只挂一份脚本日志。

`na` 仅允许 benchmark/display/render/numbers/citations/display_semantics/expectations（后两项只在确实没有表图、用户确实没提要求时），且必须 reason、fallback 和审查证据：例如纯理论段无数据数字，作者只要求 Markdown 文本无需排版；投稿 Word/PDF 的 render 不可标成无需渲染，不能渲染即未核。N/A 的真实性仍需审查，机器不能自行知道任务是否具有这些要素。

findings 每条有 id、severity（critical/major/minor）、status（fixed/accepted/open）、rationale、evidence。重大/关键问题必须 fixed，不能“接受风险”来宣称完成。证据一致性无法防止操作者蓄意伪造整套记录，哈希也不证明原始来源真实；报告写明此边界。

## 适度执行

一句编辑只核原意、事实、连带位置，不强迫完整 release 清单。完整稿和可提交材料才运行对应阶段。编写检查器时必须有坏例拒收、好例接受和合理例外保留；空输入/遗漏范围必须显性失败，不能把零检查当零问题。

## 收敛与独立试运行

保存基线、每轮候选、失败依据和变更；测试者只拿请求、skill 与必要原始材料，不拿预期答案。规则冻结后跑未见过的不同类型或边界案例。作者自评、同模型隔离审查、不同实现及人评分开报告。

两轮稳定仅意味着在已测试条件下无新重大缺陷，不表示全球最优、跨学科验证或发表保证。用 draft_rubric 的维度与硬条件选可行版本；同一问题修复后再遇到另一个问题应继续，不用总分遮挡残余错误。明确保留未测领域和无法执行的能力。

## 分维度验收

投稿前逐维报告，维度以作者说明模板的“分维度状态”表为准，机器能查的部分由 check_all 的 STATUS.md 给出。任何一维没过、没查或只能人工而没做完，不写“投稿就绪”或“投稿包备齐”；一维的通过不能抵消另一维的问题。用户指出过的问题登记进 expectations.json，之后的“通过”不能把它降为偏好。
