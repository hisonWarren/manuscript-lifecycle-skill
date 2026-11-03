# manuscript-lifecycle

科研论文全周期写作与修订技能：从已有数据起草、修订、投稿到审稿返修。

## 文档首页（HTML）

本仓库以 HTML 可视化作为文档入口（GitHub Pages）：

**https://hisonwarren.github.io/manuscript-lifecycle-skill/**

| 页面 | 说明 |
|------|------|
| [流程框架](./index.html) | 五线路 · 三条范围 · 十站点（Pages 首页） |
| [方法导航图](./manuscript-lifecycle-map.html) | 方法与模块总图 |
| [使用说明](./使用说明.md) | 安装与五种模式用法 |
| [审稿返修总指令](./%23%20%E7%A7%91%E7%A0%94%E8%AE%BA%E6%96%87%E5%AE%A1%E7%A8%BF%E8%BF%94%E4%BF%AE%E6%80%BB%E6%8C%87%E4%BB%A4%EF%BC%9A%E8%AF%81%E6%8D%AE%E9%A9%B1%E5%8A%A8%E3%80%81%E7%81%B5%E6%B4%BB%E6%89%A7%E8%A1%8C%E3%80%81%E7%8B%AC%E7%AB%8B%E5%AE%A1%E6%9F%A5%E4%B8%8E%E5%AE%8C%E6%95%B4%E4%BA%A4%E4%BB%98.txt) | 证据驱动的返修执行指令 |

## 安装

解压或使用发布包，将完整 `manuscript-lifecycle/` 放入技能目录：

- Cursor：`~/.cursor/skills/`
- Codex：`~/.codex/skills/`
- Claude Code：`~/.claude/skills/`

发布文件：

- [`manuscript-lifecycle.skill`](./manuscript-lifecycle.skill)（Cursor skill 包）
- [`manuscript-lifecycle.zip`](./manuscript-lifecycle.zip)（完整文件夹压缩包）

已有同名技能时先备份再完整替换。脚本仅需 Python 3 标准库。

## 仓库结构

```
manuscript-lifecycle/          # Skill 本体（SKILL.md · agents · references · scripts · assets · evals）
manuscript-lifecycle.skill     # 可直接上传的 skill 包
manuscript-lifecycle.zip       # 同内容 zip
index.html                     # GitHub Pages 首页 = 流程框架
manuscript-lifecycle-*.html    # 框架与导航图
使用说明.md                    # 安装与用法
# 科研论文审稿返修总指令….txt # 返修总指令
```

详细用法见 [使用说明.md](./使用说明.md)。
